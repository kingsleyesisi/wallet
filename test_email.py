import os
from email_utils import send_notification
import logging

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("--- Email Test Script ---")
    print("This script will attempt to send a test email using the credentials")
    print("specified in your environment variables.")
    print("\nBefore running, please ensure you have set the following environment variables:")
    print("  - EMAIL_HOST")
    print("  - EMAIL_PORT")
    print("  - EMAIL_USE_TLS")
    print("  - EMAIL_HOST_USER")
    print("  - EMAIL_HOST_PASSWORD")

    # Example for local testing:
    # Set these variables in your shell before running the script.
    # For example, in bash:
    # export EMAIL_HOST=smtp.gmail.com
    # export EMAIL_PORT=587
    # export EMAIL_USE_TLS=True
    # export EMAIL_HOST_USER=your_email@gmail.com
    # export EMAIL_HOST_PASSWORD=your_app_password

    # Check if variables are set
    required_vars = ["EMAIL_HOST", "EMAIL_PORT", "EMAIL_USE_TLS", "EMAIL_HOST_USER", "EMAIL_HOST_PASSWORD"]
    if not all(os.environ.get(var) for var in required_vars):
        logging.error("One or more required environment variables are not set. Exiting.")
    else:
        print("\nAll required environment variables are set. Proceeding to send email...")
        try:
            subject = "Test Email from Wallet Checker"
            body = "This is a test email to confirm that your SMTP settings are configured correctly."
            send_notification(subject, body)
            print("Test email function executed. Check the recipient's inbox and the logs for details.")
        except Exception as e:
            logging.error(f"An error occurred while trying to send the test email: {e}")

    print("\n--- Test Complete ---")
