from dotenv import load_dotenv
import os, smtplib
from email.message import EmailMessage
load_dotenv()

msg = EmailMessage()
msg["Subject"] = "AutoML Studio test"
msg["From"] = os.getenv("MAIL_FROM")
msg["To"] = "hammad4study@gmail.com"
msg.set_content("Agar yeh mail mili to email setup theek hai.")

with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT"))) as s:
    s.starttls()
    s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
    s.send_message(msg)
print("Mail bhej di gayi")
