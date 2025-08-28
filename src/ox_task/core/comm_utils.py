"""Utilities related to communications (e.g., email).
"""

import logging

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib


def send_email(msg, subject, to_email, from_email, app_passwd, mode='plain'):
    """Send an email via Gmail SMTP.

    Args:
        msg (str): The message body to send
        subject (str): Email subject line
        to_email (str): Recipient's email address
        from_email (str): Sender's Gmail address
        app_passwd (str): Gmail app password (not regular password)

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Create message
        email_msg = MIMEMultipart()
        email_msg['From'] = from_email
        email_msg['To'] = to_email
        email_msg['Subject'] = subject

        if mode == 'plain':
            email_msg.attach(MIMEText(msg, 'plain'))
        elif mode == 'html':
            email_msg.attach(MIMEText(msg, 'html'))

        # Gmail SMTP configuration
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()  # Enable encryption
        server.login(from_email, app_passwd)

        # Send email
        text = email_msg.as_string()
        server.sendmail(from_email, to_email, text)
        server.quit()

        print(f"Email sent successfully to {to_email}")
        return True

    except Exception as problem:  # pylint: disable=broad-except
        logging.exception("Error sending email: %s", problem)
        return False


def shorten_msg(msg, max_len=400, max_lines=6):
    short_msg = msg[:max_len]
    short_msg = '\n'.join(short_msg.split('\n')[:max_lines])
    if short_msg != msg:
        short_msg += '...'
    return short_msg
