# ingestion/chunking.py
import re
import requests
from io import BytesIO
from urllib.parse import urlparse

# ──────────────────────────────────────────────
# 1. TEXT CHUNKING (Shared)
# ──────────────────────────────────────────────
# ingestion/chunking.py

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list:
    """Split text into overlapping chunks at sentence boundaries."""
    if not text:
        return []

    if len(text) < chunk_size:
        return [text.strip()]

    chunks = []
    start = 0
    max_iterations = 10000  # Safety limit
    iterations = 0

    while start < len(text) and iterations < max_iterations:
        iterations += 1
        end = min(start + chunk_size, len(text))

        if end < len(text):
            search_start = max(start, end - 50)
            boundary = max(
                text.rfind('. ', search_start, end),
                text.rfind('? ', search_start, end),
                text.rfind('! ', search_start, end),
                text.rfind('\n', search_start, end),
                text.rfind('.', search_start, end),
                text.rfind('?', search_start, end),
                text.rfind('!', search_start, end)
            )
            if boundary != -1 and boundary > start:
                end = boundary + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Safety: prevent infinite loop
        new_start = end - overlap
        if new_start <= start:
            # If overlap causes no progress, break
            new_start = end
        start = new_start

        if start >= len(text):
            break

    if iterations >= max_iterations:
        print(f"⚠️ Max iterations reached. Processed {len(chunks)} chunks.")

    return chunks
# ──────────────────────────────────────────────
# 2. PDF EXTRACTION (pypdf — no OCR)
# ──────────────────────────────────────────────
def extract_pdf(file_path: str) -> str:
    """Extract text from PDF using pypdf (digital PDFs only, no OCR)."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text
    except ImportError:
        print("pypdf not installed. Run: pip install pypdf")
        return ""
    except Exception as e:
        print(f"PDF extraction error: {e}")
        return ""


# ──────────────────────────────────────────────
# 3. DOCX EXTRACTION
# ──────────────────────────────────────────────
def extract_docx(file_path: str) -> str:
    """Extract text from DOCX file."""
    try:
        from docx import Document
        doc = Document(file_path)
        text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
        return text
    except ImportError:
        print("python-docx not installed. Run: pip install python-docx")
        return ""
    except Exception as e:
        print(f"DOCX extraction error: {e}")
        return ""


# ──────────────────────────────────────────────
# 4. URL EXTRACTION (Web Scraping)
# ──────────────────────────────────────────────
def extract_url(url: str) -> str:
    """Extract text content from a URL using requests + BeautifulSoup."""
    try:
        from bs4 import BeautifulSoup
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)

    except ImportError:
        print("BeautifulSoup not installed. Run: pip install beautifulsoup4")
        return ""
    except requests.exceptions.RequestException as e:
        print(f"URL extraction error: {e}")
        return ""


# ──────────────────────────────────────────────
# 5. MAIN EXTRACTION FUNCTION (Auto-detect)
# ──────────────────────────────────────────────
def extract_content(source: str) -> str:
    """
    Auto-detect source type and extract text.

    Args:
        source: File path (PDF/DOCX) or URL string

    Returns:
        str: Extracted text
    """
    # Check if it's a URL
    if source.startswith(('http://', 'https://')):
        return extract_url(source)

    # Check file extension
    if source.endswith('.pdf'):
        return extract_pdf(source)
    elif source.endswith('.docx'):
        return extract_docx(source)
    else:
        # Try as plain text
        try:
            with open(source, 'r', encoding='utf-8') as f:
                return f.read()
        except:
            return f"Unsupported file type: {source}"


# ──────────────────────────────────────────────
# 6. CHUNK A SOURCE (File or URL)
# ──────────────────────────────────────────────
def chunk_source(source: str, chunk_size: int = 500, overlap: int = 50) -> list:
    """Extract text from a source and chunk it."""
    text = extract_content(source)
    if not text:
        return []
    return chunk_text(text, chunk_size, overlap)