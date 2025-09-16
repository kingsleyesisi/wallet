import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

def send_notification(subject, body):
    """
    Sends an email notification.
    """
    try:
        # Fetch email configuration from environment variables
        smtp_host = os.environ.get("EMAIL_HOST")
        smtp_port = int(os.environ.get("EMAIL_PORT", 587))
        smtp_user = os.environ.get("EMAIL_HOST_USER")
        smtp_password = os.environ.get("EMAIL_HOST_PASSWORD")
        use_tls = os.environ.get("EMAIL_USE_TLS", "True").lower() in ["true", "1", "t"]

        recipient_email = "kingsleyesisi@gmail.com"

        if not all([smtp_host, smtp_port, smtp_user, smtp_password]):
            logging.error("Email configuration is incomplete. Please set all required environment variables.")
            return

        # Create the email message
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # Send the email
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if use_tls:
                server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
            logging.info(f"Email notification sent to {recipient_email}")

    except Exception as e:
        logging.error(f"Failed to send email: {e}")
