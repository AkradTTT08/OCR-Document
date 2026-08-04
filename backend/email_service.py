import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

# Fallback to root .env if not found
if not os.environ.get('GMAIL_USER'):
    root_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    load_dotenv(root_env_path)

GMAIL_USER = os.environ.get('GMAIL_USER')
GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD')

def send_qa_report(recipient_email: str, doc_type: str, filename: str, report_content: str) -> bool:
    """
    Sends a QA Consult report via Gmail SMTP.
    """
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        logger.error("GMAIL_USER or GMAIL_APP_PASSWORD not set in .env")
        return False
        
    if not recipient_email:
        logger.error("Recipient email is empty")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = recipient_email
        msg['Subject'] = f"Spectra QA: รายงานผลการตรวจสอบเอกสาร {filename} ({doc_type})"

        # Load SVG logo
        svg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'svelte-app', 'public', 'spectra-favicon.svg')
        logo_html = ''
        logo_part = None
        try:
            if os.path.exists(svg_path):
                with open(svg_path, 'rb') as f:
                    svg_data = f.read()
                logo_part = MIMEBase('image', 'svg+xml')
                logo_part.set_payload(svg_data)
                encoders.encode_base64(logo_part)
                logo_part.add_header('Content-ID', '<spectra_logo>')
                logo_part.add_header('Content-Disposition', 'inline', filename='spectra-favicon.svg')
                logo_html = '<img src="cid:spectra_logo" alt="Spectra QA Logo" style="width: 40px; height: 40px; vertical-align: middle; margin-right: 12px; border-radius: 8px;">'
        except Exception as e:
            logger.warning(f"Could not load logo for email: {e}")

        # Convert markdown report to simple HTML for email
        # Just wrapping in pre tag or basic formatting
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ padding: 20px; }}
                .header {{ background-color: #7c3aed; color: white; padding: 10px 20px; border-radius: 8px 8px 0 0; }}
                .content {{ background-color: #f9fafb; padding: 20px; border: 1px solid #e5e7eb; border-radius: 0 0 8px 8px; }}
                pre {{ white-space: pre-wrap; font-family: inherit; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    {logo_html}
                    <h2 style="display: inline-block; vertical-align: middle; margin: 0;">Spectra QA Consult Report</h2>
                </div>
                <div class="content">
                    <p>เรียนผู้ใช้งาน,</p>
                    <p>ระบบ Spectra QA ได้ทำการตรวจสอบเอกสาร <b>{filename}</b> ประเภท <b>{doc_type}</b> เรียบร้อยแล้ว</p>
                    <p>นี่คือผลการวิเคราะห์และเปรียบเทียบกับฐานข้อมูล Knowledge Base:</p>
                    <hr>
                    <pre>{report_content}</pre>
                    <hr>
                    <p><small>สร้างโดย Spectra QA Intelligent Analysis System</small></p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(html_content, 'html'))
        if logo_part:
            msg.attach(logo_part)

        # Prepare recipient list
        to_list = [e.strip() for e in recipient_email.split(',') if e.strip()]
        
        # Send email
        logger.info(f"Connecting to SMTP server to send email to {to_list}...")
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        text = msg.as_string()
        server.sendmail(GMAIL_USER, to_list, text)
        server.quit()
        
        logger.info(f"Successfully sent QA report to {to_list}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {recipient_email}: {e}", exc_info=True)
        return False
