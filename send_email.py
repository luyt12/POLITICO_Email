"""
POLITICO News Email Sender
"""
import os, sys, re, smtplib, ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

EMAIL_TO = os.getenv("EMAIL_TO") or ""
EMAIL_FROM = os.getenv("EMAIL_FROM") or ""
SMTP_HOST = os.getenv("SMTP_HOST") or ""
SMTP_PORT = int(os.getenv("SMTP_PORT") or "465")
SMTP_USER = os.getenv("SMTP_USER") or ""
SMTP_PASS = os.getenv("SMTP_PASS") or ""

_missing = [k for k, v in {"EMAIL_TO": EMAIL_TO, "EMAIL_FROM": EMAIL_FROM, "SMTP_HOST": SMTP_HOST, "SMTP_USER": SMTP_USER, "SMTP_PASS": SMTP_PASS}.items() if not v]
if _missing:
    print("ERROR: Missing required env vars: " + ", ".join(_missing))
    sys.exit(1)
TRANSLATE_DIR = "translate"


def format_html(content, date_str):
    import markdown
    html_body = markdown.markdown(content, extensions=['tables', 'fenced_code'])
    date_fmt = datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
    html = (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">" +
        "<style>" +
        "body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;line-height:1.6;color:#333;max-width:800px;margin:0 auto;padding:20px;background:#f5f5f5}" +
        ".container{background:#fff;padding:30px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1)}" +
        ".header{border-bottom:3px solid #c41230;padding-bottom:15px;margin-bottom:20px}" +
        "h1{color:#c41230;margin:0;font-size:24px}" +
        ".date{color:#666;font-size:14px;margin-top:5px}" +
        "h2{color:#1a1a1a;border-top:1px solid #e0e0e0;padding-top:20px;margin-top:30px;font-size:18px}" +
        "a{color:#0066cc;text-decoration:none}" +
        ".footer{margin-top:40px;padding-top:20px;border-top:1px solid #e0e0e0;font-size:12px;color:#888;text-align:center}" +
        "</style></head><body>" +
        "<div class=\"container\">" +
        "<div class=\"header\"><h1>POLITICO Daily News</h1><div class=\"date\">" + date_fmt + "</div></div>" +
        "<div class=\"content\">" + html_body + "</div>" +
        "<div class=\"footer\">Auto-sent by OpenClaw Agent</div></div></body></html>"
    )
    return html


def send_daily_email(date_str=None):
    if not date_str:
        date_str = datetime.now().strftime("%Y%m%d")
    filepath = os.path.join(TRANSLATE_DIR, date_str + ".md")
    if not os.path.exists(filepath):
        print("File not found: " + filepath)
        return False
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    if not content.strip():
        print("File is empty: " + filepath)
        return False
    print("Content length: " + str(len(content)) + " chars")
    html = format_html(content, date_str)
    msg = MIMEMultipart()
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg["Subject"] = "POLITICO Daily News - " + datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
    msg.attach(MIMEText(html, "html", "utf-8"))
    print("SMTP: " + SMTP_HOST + ":" + str(SMTP_PORT) + " -> " + EMAIL_TO)
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())
        print("Email sent: " + EMAIL_TO)
        return True
    except Exception as e:
        print("Error: " + str(e))
        return False


def main(filepath=None):
    if filepath is None and len(sys.argv) > 1:
        filepath = sys.argv[1]
    if filepath:
        m = re.search(r"(\d{8})", filepath)
        if m:
            send_daily_email(m.group(1))
        else:
            send_daily_email()
    else:
        send_daily_email()


if __name__ == "__main__":
    main()
