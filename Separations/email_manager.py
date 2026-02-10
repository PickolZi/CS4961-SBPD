import os

import smtplib
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import ssl

from typing import Optional
from pathlib import Path

class EmailManager:
    def __init__(
        self,
        smtp_server: str,
        port: int,
        sender_email: str,
        app_password: str,
        use_tls: bool = True
    ):
        self.smtp_server = smtp_server
        self.port = port
        self.sender_email = sender_email
        self.app_password = app_password
        self.use_tls = use_tls
    
    def _connect(self) -> smtplib.SMTP:
        server = smtplib.SMTP(self.smtp_server, self.port)
        server.ehlo()
        if self.use_tls:
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
        server.login(self.sender_email, self.app_password)
        return server

    def send_email(
        self,
        to: str,
        subject: str,
        body: Optional[str] = None,
        html_body: Optional[str] = None,
        attachments_path: Optional[Path] = None
    ):
        message = MIMEMultipart()
        message["From"] = self.sender_email
        message["To"] = to
        message["Subject"] = subject

        if body:
            message.attach(MIMEText(body, "plain"))

        if html_body:
            message.attach(MIMEText(html_body, "html"))
        
        if attachments_path:
            for filename in os.listdir(attachments_path):
                file_path = os.path.join(attachments_path, filename)

                # Skip directories, only attach files
                if not os.path.isfile(file_path):
                    continue

                with open(file_path, "rb") as attachment:
                    mime_part = MIMEApplication(
                        attachment.read(),
                        Name=os.path.basename(filename)
                    )
                    mime_part["Content-Disposition"] = f'attachment; filename="{os.path.basename(filename)}"'
                    message.attach(mime_part)

        with self._connect() as server:
            server.send_message(message)