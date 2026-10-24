import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.core import config

logger = logging.getLogger(__name__)


def send_account_email(to_email: str, subject: str, text_body: str, html_body: str):
    if not config.SMTP_HOST or not config.MAIL_FROM:
        logger.warning("Account email was not sent because mail delivery is not configured.")
        return
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.MAIL_FROM
    message["To"] = to_email
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
            if config.SMTP_USER:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(message)
    except (OSError, smtplib.SMTPException):
        # Avoid logging exception text because SMTP exceptions can contain
        # addresses, server details, or credentials.
        logger.error("Account email delivery failed.")


def send_verification_email(to_email: str, otp: str):
    subject = "Your AutoML Studio verification code"
    text_body = (
        "Welcome to AutoML Studio.\n\n"
        f"Your email verification code is: {otp}\n\n"
        "Enter this six-digit code in the AutoML Studio sign-up screen. "
        "It expires in 10 minutes and can only be used once.\n\n"
        "If you did not create an account, you can ignore this email."
    )
    html_body = f'''<!doctype html>
<html lang="en">
  <body style="margin:0;padding:0;background:#f4efe7;font-family:Arial,Helvetica,sans-serif;color:#38262a;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4efe7;padding:36px 14px;">
      <tr><td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background:#fffdf9;border:1px solid #e7d9c8;border-radius:18px;overflow:hidden;">
          <tr><td style="background:#762f3b;padding:24px 32px;color:#fff8ef;">
            <div style="font-size:12px;letter-spacing:2px;text-transform:uppercase;opacity:.82;">AutoML Studio</div>
            <div style="font-size:25px;font-weight:700;margin-top:8px;">Verify your email</div>
          </td></tr>
          <tr><td style="padding:32px;">
            <p style="font-size:16px;line-height:1.6;margin:0 0 10px;">Welcome to AutoML Studio.</p>
            <p style="font-size:14px;line-height:1.7;color:#6d5e5d;margin:0 0 24px;">Enter this one-time code on the sign-up screen to verify your email address.</p>
            <div style="text-align:center;background:#f5eee2;border:1px solid #eadbc7;border-radius:12px;padding:19px 12px;margin:0 0 22px;">
              <div style="font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#806b68;margin-bottom:9px;">Your verification code</div>
              <div style="font-family:Arial,Helvetica,sans-serif;font-size:34px;font-weight:700;letter-spacing:10px;color:#762f3b;padding-left:10px;">{otp}</div>
            </div>
            <p style="font-size:13px;line-height:1.7;color:#6d5e5d;margin:0;">This code expires in <strong>10 minutes</strong> and works once. If you did not create an account, you can safely ignore this email.</p>
          </td></tr>
          <tr><td style="border-top:1px solid #eee4d8;padding:17px 32px;color:#887b75;font-size:11px;line-height:1.6;">AutoML Studio · Secure account verification</td></tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>'''
    send_account_email(to_email, subject, text_body, html_body)


def send_password_reset_email(to_email: str, raw_token: str):
    link = f"{config.FRONTEND_URL}/auth/reset-password?token={raw_token}"
    send_account_email(
        to_email,
        "Reset your AutoML Studio password",
        f"Reset your password within 45 minutes: {link}",
        f'<div style="font-family:Arial,sans-serif;max-width:560px;margin:30px auto;padding:28px;border:1px solid #e7d9c8;border-radius:16px;color:#38262a"><h1 style="color:#762f3b">Reset your password</h1><p>We received a request to reset your AutoML Studio password.</p><p><a href="{link}" style="display:inline-block;padding:13px 22px;border-radius:8px;background:#762f3b;color:#fff8ef;text-decoration:none;font-weight:bold">Choose a new password</a></p><p style="color:#6d5e5d;font-size:13px">This link expires in 45 minutes. If you did not request a reset, ignore this message.</p></div>',
    )
