"""
POLITICO News Email Sender
Sends translated POLITICO news to configured email address in HTML format.
"""

import os
import sys
import re
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import markdown

# 直接从环境变量读取
EMAIL_TO = os.getenv("EMAIL_TO", "HZ-lu2007@outlook.com")
EMAIL_FROM = os.getenv("EMAIL_FROM", "kimberagent@163.com")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.163.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "kimberagent@163.com")
SMTP_PASS = os.getenv("SMTP_PASS", "")

TRANSLATE_DIR = "translate"


def format_email_html(content, date_str):
    """Format Markdown content as HTML email with POLITICO red theme"""
    html_body = markdown.markdown(content, extensions=['tables', 'fenced_code'])
    display_date = datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background-color: #ffffff;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .header {{
            border-bottom: 3px solid #c41230;
            padding-bottom: 15px;
            margin-bottom: 20px;
        }}
        h1 {{
            color: #c41230;
            margin: 0;
            font-size: 24px;
        }}
        .date {{
            color: #666;
            font-size: 14px;
            margin-top: 5px;
        }}
        h2 {{
            color: #1a1a1a;
            border-top: 1px solid #e0e0e0;
            padding-top: 20px;
            margin-top: 30px;
            font-size: 18px;
        }}
        a {{
            color: #0066cc;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
            font-size: 12px;
            color: #888;
            text-align: center;
        }}
        hr {{
            border: none;
            border-top: 1px solid #e0e0e0;
            margin: 30px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>POLITICO 每日新闻摘要</h1>
            <div class="date">{display_date}</div>
        </div>
        <div class="content">
{html_body}
        </div>
        <div class="footer">
            此邮件由 OpenClaw Agent 自动发送<br>
        </div>
    </div>
</body>
</html>"""
    return html


def send_daily_email(date_str=None):
    """Send translated news email for a specific date"""
    if not date_str:
        date_str = datetime.now().strftime("%Y%m%d")
    
    display_date = datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
    
    translate_file = os.path.join(TRANSLATE_DIR, f"{date_str}.md")
    
    if not os.path.exists(translate_file):
        print(f"No translated news found for {date_str}: {translate_file}")
        return False
    
    with open(translate_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if not content.strip():
        print(f"Translated file is empty for {date_str}")
        return False
    
    print(f"Email content length: {len(content)} chars")
    
    html_content = format_email_html(content, date_str)
    
    msg = MIMEMultipart()
    msg['From'] = EMAIL_FROM
    msg['To'] = EMAIL_TO
    msg['Subject'] = f"POLITICO 每日新闻 - {display_date}"
    msg.attach(MIMEText(html_content, 'html', 'utf-8'))
    
    print(f"SMTP: {SMTP_HOST}:{SMTP_PORT}, User: {SMTP_USER}, Pass set: {bool(SMTP_PASS)}")
    
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())
        
        print(f"Email sent successfully to {EMAIL_TO}")
        return True
    
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


if __name__ == "__main__":
    path_arg = sys.argv[1] if len(sys.argv) > 1 else None
    
    if path_arg:
        if path_arg.endswith('.md'):
            m = re.search(r'(\d{8})', path_arg)
            if m:
                send_daily_email(m.group(1))
            else:
                send_daily_email()
        else:
            send_daily_email(path_arg.replace('-', '')[:8])
    else:
        send_daily_email()
