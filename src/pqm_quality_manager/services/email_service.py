from email.message import EmailMessage
import smtplib, ssl

class EmailService:
    """Entrega SMTP explícita. La contraseña se obtiene de keyring desde la interfaz."""
    def send(self, *, host, port, username, password, sender, recipients, subject, body, attachment, use_ssl=False, use_starttls=True):
        path = str(attachment)
        msg = EmailMessage(); msg["From"] = sender; msg["To"] = ", ".join(recipients); msg["Subject"] = subject
        msg.set_content(body)
        with open(path, "rb") as f: msg.add_attachment(f.read(), maintype="application", subtype="pdf", filename=path.split("/")[-1])
        if use_ssl:
            with smtplib.SMTP_SSL(host, int(port), context=ssl.create_default_context(), timeout=30) as smtp:
                smtp.login(username, password); smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, int(port), timeout=30) as smtp:
                smtp.ehlo()
                if use_starttls: smtp.starttls(context=ssl.create_default_context()); smtp.ehlo()
                smtp.login(username, password); smtp.send_message(msg)
