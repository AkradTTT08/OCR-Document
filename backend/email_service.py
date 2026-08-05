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

def send_qa_report(recipient_email: str, doc_type: str, filename: str, report_content: str, excel_download_url: str = '', exit_criteria_eval: dict = None) -> bool:
    """
    Sends a QA Consult report via Gmail SMTP.
    Optionally includes an Excel report download link and Exit Criteria Gate evaluation.
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

        # Exit Criteria HTML Section
        exit_criteria_html = ''
        if exit_criteria_eval:
            status = exit_criteria_eval.get('status', 'PASSED')
            score = exit_criteria_eval.get('score_percentage', 100)
            passed_cnt = exit_criteria_eval.get('passed_items', 0)
            failed_cnt = exit_criteria_eval.get('failed_items', 0)
            na_cnt = exit_criteria_eval.get('na_items', 0)
            
            badge_bg = '#10B981'
            badge_text = 'PASSED (ผ่านบริบูรณ์)'
            if status == 'CONDITIONAL_PASSED':
                badge_bg = '#F59E0B'
                badge_text = 'CONDITIONAL PASSED (ผ่านแบบมีเงื่อนไข)'
            elif status == 'REJECTED':
                badge_bg = '#EF4444'
                badge_text = 'REJECTED (ไม่ผ่าน - ต้องส่งตรวจใหม่)'

            failed_items_html = ''
            failed_list = [i for i in exit_criteria_eval.get('items', []) if i.get('status') == 'FAIL']
            if failed_list:
                failed_items_html += '<div style="margin-top: 12px; text-align: left;"><strong style="color: #991b1b;">⚠️ รายการที่ไม่ผ่านเกณฑ์ (Failed Checklist Items):</strong><ul style="margin: 8px 0; padding-left: 20px;">'
                for fi in failed_list:
                    failed_items_html += f"""
                        <li style="margin-bottom: 6px; color: #4b5563;">
                            <strong style="color: #b91c1C;">[{fi.get('item_code')}] {fi.get('category')}</strong> ({fi.get('severity')}): {fi.get('question_text')}<br>
                            <span style="font-size: 12px; color: #6b7280;">📌 {fi.get('remarks')}</span>
                        </li>
                    """
                failed_items_html += '</ul></div>'
            else:
                failed_items_html = '<p style="margin: 8px 0 0 0; color: #065f46; font-size: 13px;">✅ เอกสารผ่านเกณฑ์มาตรฐานครบทุกรายการ ไม่พบข้อผิดพลาดรุนแรง</p>'

            exit_criteria_html = f"""
                <div style="margin: 20px 0; padding: 20px; background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
                    <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #f3f4f6; padding-bottom: 12px; margin-bottom: 12px;">
                        <h3 style="margin: 0; font-size: 16px; color: #1f2937;">📋 ผลการประเมิน Exit Criteria Review Gate</h3>
                        <span style="display: inline-block; padding: 6px 14px; background: {badge_bg}; color: white; border-radius: 20px; font-weight: bold; font-size: 13px;">{badge_text}</span>
                    </div>
                    <p style="margin: 4px 0; font-size: 14px; color: #4b5563;">
                        คะแนนความสมบูรณ์: <strong style="color: #4f46e5;">{score}%</strong> (ผ่าน {passed_cnt} ข้อ / ไม่ผ่าน {failed_cnt} ข้อ / ข้าม {na_cnt} ข้อ)
                    </p>
                    <p style="margin: 4px 0; font-size: 13px; color: #6b7280; italic;">
                        {exit_criteria_eval.get('summary_remarks', '')}
                    </p>
                    {failed_items_html}
                </div>
            """

        # Excel download section
        excel_section = ''
        if excel_download_url:
            excel_section = f"""
                <div style="margin: 20px 0; padding: 20px; background: linear-gradient(135deg, #7c3aed15, #3b82f615); border: 1px solid #7c3aed30; border-radius: 12px; text-align: center;">
                    <p style="margin: 0 0 12px 0; font-size: 14px; color: #555;">📊 รายงาน QA Report (Excel) พร้อมดาวน์โหลด</p>
                    <a href="{excel_download_url}" 
                       style="display: inline-block; padding: 12px 32px; background: linear-gradient(135deg, #7c3aed, #6d28d9); color: white; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 14px; box-shadow: 0 4px 12px rgba(124, 58, 237, 0.3);">
                        ⬇️ ดาวน์โหลด Excel QA Report (พร้อม Sheet Exit Criteria)
                    </a>
                    <p style="margin: 10px 0 0 0; font-size: 12px; color: #999;">คลิกที่ปุ่มด้านบนเพื่อดาวน์โหลดรายงานในรูปแบบ Excel</p>
                </div>
            """

        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ padding: 20px; }}
                .header {{ background-color: #7c3aed; color: white; padding: 16px 20px; border-radius: 8px 8px 0 0; }}
                .content {{ background-color: #f9fafb; padding: 20px; border: 1px solid #e5e7eb; border-radius: 0 0 8px 8px; }}
                pre {{ white-space: pre-wrap; font-family: inherit; background: #ffffff; padding: 15px; border-radius: 8px; border: 1px solid #e5e7eb; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    {logo_html}
                    <h2 style="display: inline-block; vertical-align: middle; margin: 0;">Spectra QA Consult & Exit Criteria Report</h2>
                </div>
                <div class="content">
                    <p>เรียนผู้ใช้งาน,</p>
                    <p>ระบบ Spectra QA ได้ทำการตรวจสอบเอกสาร <b>{filename}</b> ประเภท <b>{doc_type}</b> เรียบร้อยแล้ว</p>
                    
                    {exit_criteria_html}
                    {excel_section}
                    
                    <hr style="border: 0; border-top: 1px solid #e5e7eb; margin: 20px 0;">
                    <h4 style="margin: 0 0 10px 0; color: #374151;">📝 รายงานผลการวิเคราะห์ QA Consult (Detailed Findings):</h4>
                    <pre>{report_content}</pre>
                    <hr style="border: 0; border-top: 1px solid #e5e7eb; margin: 20px 0;">
                    <p><small style="color: #9ca3af;">สร้างโดย Spectra QA Intelligent Analysis System | Powered by Gemini AI</small></p>
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

