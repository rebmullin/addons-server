import logging
import os
import urlparse
import random
import json

from django.conf import settings

from locust import TaskSet, task
import lxml.html
from fxa import oauth as fxa_oauth

import helpers
from . import BaseBehavior


log = logging.getLogger(__name__)
FXA_CONFIG = settings.FXA_CONFIG[settings.DEFAULT_FXA_CONFIG_NAME]


class AnonymousUserBehavior(BaseBehavior):

    @task(5)
    def browse(self):
        self.client.get('/en-US/firefox/')

        response = self.client.get(
            '/en-US/firefox/extensions/',
            allow_redirects=False, catch_response=True)

        if response.status_code == 200:
            response.success()
            html = lxml.html.fromstring(response.content)
            addon_links = html.cssselect('.item.addon h3 a')
            url = random.choice(addon_links).get('href')
            self.client.get(
                url,
                name='/en-US/firefox/addon/:slug/')
        else:
            response.failure('Unexpected status code {}'.format(
                response.status_code))

    @task(10)
    def search(self):
        response = self.client.get('/api/v3/addons/search/')

        check_next_url = random.choice((True, False))

        if check_next_url:
            next_url = response.json()['next']
            if next_url:
                self.client.get(next_url)


class RegisteredUserBehavior(BaseBehavior):

    def on_start(self):
        self.fxa_account, self.email_account = helpers.get_fxa_account()

        log.info(
            'Created {account} for load-tests'
            .format(account=self.fxa_account))

    def on_stop(self):
        log.info(
            'Cleaning up and destroying {account}'
            .format(account=self.fxa_account))
        helpers.destroy_fxa_account(self.fxa_account, self.email_account)

    @task(1)
    def upload(self):
        self.login(self.fxa_account)

        form = self.load_upload_form()
        if form is not None:
            self.upload_addon(form)

        self.logout(self.fxa_account)

    def login(self, account):
        log.debug('creating fxa account')
        fxa_account, email_account = helpers.get_fxa_account()

        log.debug('calling login/start to generate fxa_state')
        response = self.client.get(
            '/api/v3/accounts/login/start/',
            allow_redirects=False)

        params = dict(urlparse.parse_qsl(response.headers['Location']))
        fxa_state = params['state']

        log.debug('Get browser id session token')
        fxa_session = helpers.get_fxa_client().login(
            email=fxa_account.email,
            password=fxa_account.password)

        oauth_client = fxa_oauth.Client(
            client_id=FXA_CONFIG['client_id'],
            client_secret=FXA_CONFIG['client_secret'],
            server_url=FXA_CONFIG['oauth_host'])

        log.debug('convert browser id session token into oauth code')
        oauth_code = oauth_client.authorize_code(fxa_session, scope='profile')

        # Now authenticate the user, this will verify the user on the
        response = self.client.get(
            '/api/v3/accounts/authenticate/',
            params={
                'state': fxa_state,
                'code': oauth_code,
            },
            name='/api/v3/accounts/authenticate/?state=:state',
        )

    def logout(self, account):
        log.debug('Logging out {}'.format(account))
        self.client.get('/en-US/firefox/users/logout/')

    def load_upload_form(self):
        url = helpers.submit_url('upload-unlisted')
        response = self.client.get(
            url, allow_redirects=False, catch_response=True)

        if response.status_code == 200:
            response.success()
            html = lxml.html.fromstring(response.content)
            return html.get_element_by_id('create-addon')
        else:
            more_info = ''
            if response.status_code in (301, 302):
                more_info = ('Location: {}'
                             .format(response.headers['Location']))
            response.failure('Unexpected status: {}; {}'
                             .format(response.status_code, more_info))

    def upload_addon(self, form):
        url = helpers.submit_url('upload-unlisted')
        csrfmiddlewaretoken = form.fields['csrfmiddlewaretoken']

        with helpers.get_xpi() as addon_file:
            response = self.client.post(
                '/en-US/developers/upload',
                {'csrfmiddlewaretoken': csrfmiddlewaretoken},
                files={'upload': addon_file},
                allow_redirects=False,
                catch_response=True)

            if response.status_code == 302:
                response.success()
                poll_url = response.headers['location']
                upload_uuid = self.poll_upload_until_ready(poll_url)
                if upload_uuid:
                    form.fields['upload'] = upload_uuid
                    self.submit_form(form=form, url=url)
            else:
                response.failure('Unexpected status: {}'.format(
                    response.status_code))
