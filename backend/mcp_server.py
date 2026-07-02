"""
MCP Server สำหรับระบบ Thai OCR
ใช้สำหรับเชื่อมต่อกับ AI Agents (เช่น Claude Desktop, Cursor) ผ่านมาตรฐาน Model Context Protocol
"""
import os
import io
import requests
import logging
from PIL import Image
from urllib.parse import urlparse
from mcp.server.fastmcp import FastMCP

# นำเข้าฟังก์ชัน OCR จาก ocr_engine ของเรา
from ocr_engine import ocr_pdf_bytes, ocr_image

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_ocr_server")

# สร้าง MCP Server
mcp = FastMCP("Thai OCR Server")

import socket
import ipaddress

def _is_url(path: str) -> bool:
    try:
        result = urlparse(path)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def _is_safe_url(url: str) -> bool:
    """ตรวจสอบ SSRF ป้องกันไม่ให้เข้าถึง Private/Local IP"""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False
        
        # Resolve to IP
        ip = socket.gethostbyname(hostname)
        ip_obj = ipaddress.ip_address(ip)
        
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
            logger.warning(f"SSRF Blocked: Attempted to access private IP {ip}")
            return False
            
        return True
    except Exception as e:
        logger.warning(f"URL Resolution failed: {e}")
        return False

@mcp.tool()
def ocr_document(source: str, lang: str = "tha+eng") -> str:
    """
    Extracts text from a document (PDF or Image) using GLM-OCR.
    
    Args:
        source: Absolute path to a local file, or a direct HTTP/HTTPS URL to the file.
        lang: Language for extraction (default 'tha+eng').
        
    Returns:
        The extracted markdown text from the document.
    """
    logger.info(f"Processing OCR request for source: {source}")
    
    file_bytes = None
    is_pdf = False
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
    
    # 1. Load the file (Local or URL)
    if _is_url(source):
        if not _is_safe_url(source):
            return "Error: URL is not safe or accesses a private internal network."
            
        try:
            logger.info("Downloading file from URL...")
            response = requests.get(source, stream=True, timeout=30)
            response.raise_for_status()
            
            # Check Content-Length if provided
            content_length = response.headers.get('Content-Length')
            if content_length and int(content_length) > MAX_FILE_SIZE:
                return f"Error: File size exceeds the 50MB limit."
                
            # Download with stream to enforce limit
            downloaded_bytes = io.BytesIO()
            size = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    downloaded_bytes.write(chunk)
                    size += len(chunk)
                    if size > MAX_FILE_SIZE:
                        return f"Error: File size exceeds the 50MB limit."
            
            file_bytes = downloaded_bytes.getvalue()
            
            # Detect type from headers or URL
            content_type = response.headers.get('Content-Type', '').lower()
            if 'pdf' in content_type or source.lower().endswith('.pdf'):
                is_pdf = True
        except Exception as e:
            return f"Error downloading file from URL: {str(e)}"
    else:
        # Local file
        if not os.path.exists(source):
            return f"Error: Local file not found at path {source}"
            
        try:
            with open(source, 'rb') as f:
                file_bytes = f.read()
            if source.lower().endswith('.pdf'):
                is_pdf = True
        except Exception as e:
            return f"Error reading local file: {str(e)}"
            
    # 2. Process with OCR Engine
    try:
        extracted_text = ""
        
        if is_pdf:
            logger.info("Processing as PDF...")
            # ocr_pdf_bytes returns a list of dicts: [{'page_number': 1, 'text': '...'}, ...]
            results = ocr_pdf_bytes(file_bytes, lang=lang)
            
            for page in results:
                if 'error' in page and page['error']:
                    extracted_text += f"\n\n--- Error on Page {page.get('page_number')} ---\n{page['error']}"
                else:
                    extracted_text += f"\n\n--- Page {page.get('page_number')} ---\n{page.get('text', '')}"
        else:
            logger.info("Processing as Image...")
            # Processing as Image
            image = Image.open(io.BytesIO(file_bytes))
            # ocr_image returns a dict: {'text': '...', 'words': [...]}
            result = ocr_image(image, lang=lang)
            if 'error' in result and result['error']:
                return f"Error during OCR: {result['error']}"
            extracted_text = result.get('text', '')
            
        logger.info("OCR Processing complete.")
        
        # --- Data Ingestion Pipeline Injection ---
        try:
            from db_ingestion import ingest_markdown_document
            # Derive a simple filename based on source
            filename = os.path.basename(source) if not _is_url(source) else source.split('/')[-1]
            if not filename:
                filename = "unknown_document"
                
            logger.info("Triggering data ingestion pipeline...")
            ingest_markdown_document(filename, extracted_text.strip())
        except Exception as ingest_error:
            logger.error(f"Failed to ingest document to database: {ingest_error}")
        # -----------------------------------------
        
        return extracted_text.strip()
        
    except Exception as e:
        return f"Unexpected error during OCR processing: {str(e)}"

if __name__ == "__main__":
    # Start the FastMCP server
    mcp.run()
