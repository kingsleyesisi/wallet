import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import config

def send_email_notification(subject, body):
    """Sends an email notification."""
    if not config.EMAIL_USER or not config.EMAIL_PASSWORD or not config.TO_EMAIL:
        logging.warning("Email configuration missing. Skipping email notification.")
        return

    try:
        msg = MIMEMultipart()
        msg['From'] = config.EMAIL_USER
        msg['To'] = config.TO_EMAIL
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(config.EMAIL_HOST, config.EMAIL_PORT)
        server.starttls()
        server.login(config.EMAIL_USER, config.EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(config.EMAIL_USER, config.TO_EMAIL, text)
        server.quit()
        logging.info("Email notification sent successfully.")
    except Exception as e:
        logging.error(f"Failed to send email notification: {e}")
