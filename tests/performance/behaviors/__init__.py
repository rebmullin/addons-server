import time

from locust import HttpLocust, TaskSet, task  # noqa
from lxml.html import submit_form  # noqa


class BaseBehavior(TaskSet):
    MAX_UPLOAD_POLL_ATTEMPTS = 200

    def submit_form(self, form=None, url=None, extra_values=None):
        if form is None:
            raise ValueError('form cannot be None; url={}'.format(url))

        def submit(method, form_action_url, values):
            values = dict(values)
            if 'csrfmiddlewaretoken' not in values:
                raise ValueError(
                    'Possibly the wrong form. Could not find '
                    'csrfmiddlewaretoken: {}'.format(repr(values)))

            response = self.client.post(
                url or form_action_url, values,
                allow_redirects=False, catch_response=True)

            if response.status_code not in (301, 302):
                # This probably means the form failed and is displaying
                # errors.
                response.failure(
                    'Form submission did not redirect; status={}'
                    .format(response.status_code))

        return submit_form(form, open_http=submit, extra_values=extra_values)

    def poll_upload_until_ready(self, url):
        for i in xrange(self.MAX_UPLOAD_POLL_ATTEMPTS):
            response = self.client.get(
                url, allow_redirects=False,
                name='/developers/upload/:uuid/',
                catch_response=True)

            try:
                data = response.json()
            except ValueError:
                return response.failure(
                    'Failed to parse JSON when polling. '
                    'Status: {} content: {}'.format(
                        response.status_code, response.content))

            if response.status_code == 200:
                if data['error']:
                    return response.failure('Unexpected error: {}'.format(
                        data['error']))
                elif data['validation']:
                    return data['upload']
            else:
                return response.failure('Unexpected status: {}'.format(
                    response.status_code))
            time.sleep(1)
        else:
            response.failure('Upload did not complete in {} tries'.format(
                self.MAX_UPLOAD_POLL_ATTEMPTS))
