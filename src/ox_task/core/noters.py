"""Basic TaskNote classes.
"""

import logging

import requests

from ox_task.core import comm_utils


class Noter:

    def notify(self, config, job_results):
        raise NotImplementedError
def notify(task_note, results):
    # Handle notification
    try:
        note_config = task_plan.notes.get(job_config.note)
        if note_config:
            # Get notifier class
            notifier_class = getattr(noters, note_config.class_name)

            # Extract additional kwargs (excluding class_name)
            note_kwargs = {
                k: v for k, v in note_config.dict().items()
                if k != "class_name"
            }

            # Instantiate and call notifier
            notifier = notifier_class(**note_kwargs)
            notifier(job_results)

    except Exception as e:
        # Don't fail the job if notification fails
        job_results["notification_error"] = str(e)


class TelegramNotifier:

    def __init__(self, token, chat_id,
                 base_url="https://api.telegram.org",
                 conditions=None, **kwargs):
        self.token = token
        self.chat_id = chat_id
        self.base_url = base_url
        self.conditions = conditions
        kwargs.pop('class_name', None)
        kwargs.pop('description', None)
        if kwargs:
            logging.warning('Ignoring kwargs: %s', kwargs)

    def format_result_to_msg(self, job_result):
        if self.conditions:
            for item in self.conditions:
                if item == "only_if_output_non_empty":
                    if not job_result.get("output", None):
                        logging.info(
                            'Condition %s prevents notify job_result %s',
                            condition, job_result)
                        return
        return str(job_result)

    def notify_result(self, job_result):
        msg = self.format_result_to_msg(job_result)
        self.notify_message(msg)

    def notify_message(self, message):
        url = f"{self.base_url}/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message
        }

        try:
            response = requests.post(url, data=payload)
            response.raise_for_status()  # Raise an exception for bad status codes

            json_response = response.json()
            if json_response.get("ok"):
                logging.info("Message sent successfully!")
            else:
                logging.error(
                    "Failed to send message. Telegram API response: %s",
                    json_response)

        except requests.exceptions.RequestException as e:
            logging.exception(
                'Got exception trying to send message via Telegram')


class GmailNotifier:

    def __init__(self, to_email, from_email, app_passwd,
                 conditions=None, **kwargs):
        self.to_email = to_email
        self.from_email = from_email
        self.app_passwd = app_passwd
        self.conditions = conditions
        kwargs.pop('class_name', None)
        kwargs.pop('description', None)
        if kwargs:
            logging.warning('Ignoring kwargs: %s', kwargs)

    def format_result_to_msg(self, job_result):
        return str(job_result)

    def notify_result(self, job_result):
        msg = self.format_result_to_msg(job_result)
        self.notify_message(msg)

    def notify_message(self, msg):
        """Send an email via Gmail SMTP.
        """
        subject = msg.split('\n')[0]
        comm_utils.send_email(msg, subject, self.to_email, self.from_email,
                              self.app_passwd)


class FileNotifier:
    """Notifier that just puts output in a file.
    """

    def __init__(self, path, conditions=None, **kwargs):
        self.path = path
        self.conditions = conditions
        kwargs.pop('class_name', None)
        kwargs.pop('description', None)
        if kwargs:
            logging.warning('Ignoring kwargs: %s', kwargs)

    def format_result_to_msg(self, job_result):
        return str(job_result)

    def notify_result(self, job_result):
        msg = self.format_result_to_msg(job_result)
        self.notify_message(msg)

    def notify_message(self, msg):
        with open(self.path, 'w', encoding='utf8') as fdesc:
            fdesc.write(msg)
