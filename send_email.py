"""
POLITICO EU News Email Sender
"""
import os
import sys
import re
import ssl
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

EMAIL_TO   = os.getenv("EMAIL_TO")   or ""
EMAIL_FROM = os.getenv("EMAIL_FROM") or ""
SMTP_HOST  = os.getenv("SMTP_HOST")  or ""
SMTP_PORT  = int(os.getenv("SMTP_PORT") or "465")
SMTP_USER  = os.getenv("SMTP_USER")  or ""
SMTP_PASS  = os.getenv("SMTP_PASS")  or ""

_missing = [k for k, v in {
    "EMAIL_TO": EMAIL_TO, "EMAIL_FROM": EMAIL_FROM,
    "SMTP_HOST": SMTP_HOST, "SMTP_USER": SMTP_USER, "SMTP_PASS": SMTP_PASS
}.items() if not v]
if _missing:
    print("ERROR: Missing env vars: " + ", ".join(_missing))
    sys.exit(1)

TRANSLATE_DIR = "translate"

# POLITICO EU brand colors
BRAND_COLOR = "#D91E18"  # POLITICO EU red


def format_html(content, date_str):
    try:
        import markdown
        html_body = markdown.markdown(content, extensions=["tables", "fenced_code"])
    except Exception:
        import html
        html_body = "<pre>" + html.escape(content) + "</pre>"

    try:
        date_fmt = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y年%m月%d日")
    except Exception:
        date_fmt = date_str

    html = (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">" +
        "<style>" +
        "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;"
        "line-height:1.7;color:#222;max-width:800px;margin:0 auto;padding:20px;"
        "background:#f4f4f4}" +
        ".container{background:#fff;padding:30px;border-radius:8px;"
        "box-shadow:0 2px 8px rgba(0,0,0,0.08)}" +
        ".header{border-bottom:3px solid " + BRAND_COLOR + ";"
        "padding-bottom:15px;margin-bottom:25px}" +
        "h1{color:" + BRAND_COLOR + ";margin:0;font-size:26px;letter-spacing:-0.5px}" +
        ".date{color:#777;font-size:13px;margin-top:6px}" +
        "h2{color:#111;font-size:17px;border-top:1px solid #eee;"
        "padding-top:18px;margin-top:25px}" +
        "a{color:#0066cc;text-decoration:none}" +
        "a:hover{text-decoration:underline}" +
        "p{margin:8px 0}" +
        ".footer{margin-top:40px;padding-top:20px;border-top:1px solid #eee;"
        "font-size:12px;color:#999;text-align:center}" +
        ".tag{background:#f0f0f0;color:#555;padding:2px 8px;border-radius:3px;"
        "font-size:11px}" +
        "</style></head><body>" +
        "<div class=\"container\">" +
        "<div class=\"header\">" +
        "<h1>POLITICO EU</h1>" +
        f"<div class=\"date\">{date_fmt} — 欧洲政治日报</div>" +
        "</div>" +
        "<div class=\"content\">" + html_body + "</div>" +
        "<div class=\"footer\">由 OpenClaw Agent 自动发送 | POLITICO EU</div>" +
        "</div></body></html>"
    )
    return html


def send_email(filepath):
    m = re.search(r"(\d{4}-\d{2}-\d{2})", filepath)
    date_str = m.group(1) if m else datetime.now().strftime("%Y-%m-%d")

    if not os.path.exists(filepath):
        print("File not found: " + filepath)
        return False

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    if not content.strip():
        print("File is empty: " + filepath)
        return False

    html = format_html(content, date_str)
    msg = MIMEMultipart()
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO
    msg["Subject"] = f"POLITICO EU — {date_str}"

    msg.attach(MIMEText(html, "html", "utf-8"))

    print(f"SMTP: {SMTP_HOST}:{SMTP_PORT} -> {EMAIL_TO}")
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())
        print("Email sent: " + EMAIL_TO)
        return True
    except Exception as e:
        print("SMTP error: " + str(e))
        return False


def main(filepath=None):
    if filepath is None and len(sys.argv) > 1:
        filepath = sys.argv[1]
    if filepath:
        send_email(filepath)
    else:
        # find latest translate file
        files = sorted(glob.glob(os.path.join(TRANSLATE_DIR, "*.md")),
                       key=os.path.getmtime, reverse=True)
        if files:
            send_email(files[0])
        else:
            print("No translate files found")


import glob
if __name__ == "__main__":
    main()
