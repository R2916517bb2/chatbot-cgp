import os
import time
import logging
from flask import Flask, request, jsonify, render_template_string, redirect
from werkzeug.utils import secure_filename
from langchain.vectorstores import FAISS
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.chains import RetrievalQA
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_groq import ChatGroq
from datetime import datetime
import traceback
import fitz  # PyMuPDF
from PIL import Image
import io
import hashlib
from langchain.docstore.document import Document
from typing import List, Dict, Any
import json
import shutil

# Optional OCR import - gracefully handle if not available
OCR_AVAILABLE = False
try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    logging.warning("OCR not available - pytesseract not installed")

# Optional ngrok import for local development
NGROK_AVAILABLE = False
try:
    from pyngrok import conf, ngrok
    NGROK_AVAILABLE = True
except ImportError:
    logging.info("ngrok not available - running without tunnel")

# --- Configuration ---
UPLOAD_FOLDER = "/tmp/uploads"
VECTOR_STORE_PATH = "/tmp/vector_store"
ALLOWED_EXTENSIONS = {'pdf'}
PASSWORD = "654321"  # Password for upload access

# IMPORTANT: Replace with your actual API keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")
NGROK_TOKEN = os.getenv("NGROK_TOKEN", "2yenKU83I2XYvjBDKhkkMSwua3p_8gFQkz3EsUPRSMYpoHwW")
NGROK_DOMAIN = os.getenv("NGROK_DOMAIN", "my-pdf-qa.ngrok.app")  # Optional: Custom domain

# Optimized Text Splitting and Retrieval Parameters
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200
TOP_K_RETRIEVAL = 6
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB limit

# --- Setup ---
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(VECTOR_STORE_PATH, exist_ok=True)

# Configure logging with better formatting
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/pdf_qa.log')
    ]
)
logger = logging.getLogger(__name__)

# Set Tesseract path for different environments
def setup_tesseract():
    """Configure Tesseract OCR path based on environment"""
    if not OCR_AVAILABLE:
        logger.info("OCR not available - skipping Tesseract setup")
        return False
        
    possible_paths = [
        '/usr/bin/tesseract',  # Linux/Ubuntu
        '/usr/local/bin/tesseract',  # macOS with Homebrew
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',  # Windows
        '/opt/homebrew/bin/tesseract'  # macOS with Apple Silicon
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            logger.info(f"Tesseract found at: {path}")
            return True
    
    logger.warning("Tesseract not found in common paths. OCR may not work.")
    return False

TESSERACT_AVAILABLE = setup_tesseract()

# --- Enhanced OCR Function ---
def extract_text_with_ocr(pdf_path: str) -> tuple[str, Dict[str, Any]]:
    """
    Extract text from PDF with optional OCR, including metadata about extraction process.
    Returns: (extracted_text, metadata)
    """
    metadata = {
        'total_pages': 0,
        'pages_with_text': 0,
        'pages_with_images': 0,
        'ocr_performed': False,
        'ocr_available': OCR_AVAILABLE and TESSERACT_AVAILABLE,
        'extraction_errors': []
    }
    
    full_text_content = []
    
    try:
        doc = fitz.open(pdf_path)
        metadata['total_pages'] = len(doc)
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_text_parts = []

            # Extract direct text
            text = page.get_text()
            if text.strip():
                page_text_parts.append(text)
                metadata['pages_with_text'] += 1

            # Extract and OCR images (if OCR is available)
            if OCR_AVAILABLE and TESSERACT_AVAILABLE:
                images = page.get_images(full=True)
                if images:
                    metadata['pages_with_images'] += 1
                    
                for img_index, img_info in enumerate(images):
                    try:
                        xref = img_info[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        
                        # Skip very small images (likely decorative)
                        if len(image_bytes) < 1000:
                            continue

                        img = Image.open(io.BytesIO(image_bytes))
                        
                        # Optimize image for OCR
                        if img.mode != 'RGB':
                            img = img.convert('RGB')
                        
                        # Resize if too large (for performance)
                        max_size = 2000
                        if max(img.size) > max_size:
                            ratio = max_size / max(img.size)
                            new_size = tuple(int(dim * ratio) for dim in img.size)
                            img = img.resize(new_size, Image.Resampling.LANCZOS)

                        # Perform OCR
                        ocr_text = pytesseract.image_to_string(img, config='--psm 6')
                        
                        if ocr_text.strip():
                            page_text_parts.append(f"\n[OCR from Image {img_index+1} on Page {page_num+1}]:\n{ocr_text}")
                            metadata['ocr_performed'] = True
                            
                    except Exception as img_err:
                        error_msg = f"Image {img_index} on page {page_num}: {str(img_err)}"
                        metadata['extraction_errors'].append(error_msg)
                        logger.warning(f"Could not process {error_msg}")
            else:
                # Count images even if OCR is not available
                images = page.get_images(full=True)
                if images:
                    metadata['pages_with_images'] += 1

            # Combine page content
            if page_text_parts:
                page_content = "\n".join(page_text_parts)
                full_text_content.append(f"\n--- Page {page_num + 1} ---\n{page_content}")
            elif not text.strip():
                # Add page marker even for empty pages
                full_text_content.append(f"\n--- Page {page_num + 1} (No text extracted) ---\n")

        doc.close()
        
    except Exception as e:
        error_msg = f"Error processing PDF: {str(e)}"
        metadata['extraction_errors'].append(error_msg)
        logger.error(error_msg, exc_info=True)
        return "", metadata

    final_text = "\n".join(full_text_content)
    
    # Add OCR status message if OCR is not available
    if not (OCR_AVAILABLE and TESSERACT_AVAILABLE) and metadata['pages_with_images'] > 0:
        ocr_note = "\n\n[NOTE: OCR is not available. Text extraction from images was skipped.]"
        final_text += ocr_note
    
    logger.info(f"Extraction completed: {len(final_text)} characters, {metadata['pages_with_text']} text pages, {metadata['pages_with_images']} image pages, OCR available: {metadata['ocr_available']}")
    
    return final_text, metadata

# --- Enhanced Utility Functions ---
def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_hash(filepath: str) -> str:
    """Generate MD5 hash of file for duplicate detection"""
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def validate_file_size(file) -> bool:
    """Check if file size is within limits"""
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)  # Reset file pointer
    return size <= MAX_FILE_SIZE

# --- Flask App Setup ---
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# --- Global Variables ---
embeddings = None
llm = None
db = None
processed_files = {}  # Track processed files with metadata

def initialize_models():
    """Initialize embeddings and LLM models"""
    global embeddings, llm
    
    try:
        logger.info("Initializing embedding model...")
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        
        logger.info("Initializing Groq LLM...")
        llm = ChatGroq(
            temperature=0,
            groq_api_key=GROQ_API_KEY,
            model_name="mixtral-8x7b-32768",
            max_tokens=4000
        )
        
        logger.info("Models initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize models: {e}", exc_info=True)
        return False

def load_vector_store():
    """Load existing vector store if available"""
    global db, processed_files
    
    if os.path.exists(VECTOR_STORE_PATH) and os.listdir(VECTOR_STORE_PATH):
        try:
            db = FAISS.load_local(VECTOR_STORE_PATH, embeddings, allow_dangerous_deserialization=True)
            
            # Load processed files metadata
            metadata_path = os.path.join(VECTOR_STORE_PATH, "processed_files.json")
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    processed_files = json.load(f)
                    
            logger.info(f"Vector store loaded with {len(processed_files)} processed files")
            return True
            
        except Exception as e:
            logger.error(f"Error loading vector store: {e}", exc_info=True)
            # Clean up corrupted vector store
            shutil.rmtree(VECTOR_STORE_PATH, ignore_errors=True)
            os.makedirs(VECTOR_STORE_PATH, exist_ok=True)
            
    return False

def save_processed_files_metadata():
    """Save metadata about processed files"""
    metadata_path = os.path.join(VECTOR_STORE_PATH, "processed_files.json")
    try:
        with open(metadata_path, 'w') as f:
            json.dump(processed_files, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to save processed files metadata: {e}")

# Initialize on startup
if not initialize_models():
    logger.critical("Failed to initialize models. Exiting.")
    os._exit(1)

load_vector_store()

# --- Enhanced HTML Templates ---
UPLOAD_FORM_HTML = """
<!doctype html>
<html>
<head>
    <title>PDF QA System</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            margin: 0; padding: 2em; background-color: #f5f5f5; 
        }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 2em; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 0.5em; }
        h2, h3 { color: #555; }
        .form-section { margin-bottom: 2em; padding: 1.5em; border: 1px solid #ddd; border-radius: 8px; background: #fafafa; }
        input[type="file"], input[type="password"], input[type="text"], textarea {
            padding: 0.75em; margin-bottom: 1em; border: 1px solid #ddd; border-radius: 4px; 
            width: 100%; box-sizing: border-box; font-size: 14px;
        }
        input[type="submit"] {
            background: linear-gradient(135deg, #4CAF50, #45a049); color: white; 
            padding: 0.75em 2em; border: none; border-radius: 4px; cursor: pointer; 
            font-size: 16px; transition: all 0.3s;
        }
        input[type="submit"]:hover { transform: translateY(-1px); box-shadow: 0 2px 8px rgba(0,0,0,0.2); }
        .status-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1em; margin: 1em 0; }
        .status-item { padding: 1em; border-radius: 6px; background: #e8f5e8; border-left: 4px solid #4CAF50; }
        .status-item.warning { background: #fff3cd; border-left-color: #ffc107; }
        .api-endpoints { background: #f8f9fa; padding: 1em; border-radius: 6px; margin: 1em 0; }
        .api-endpoints ul { margin: 0; padding-left: 1.5em; }
        .file-info { font-size: 0.9em; color: #666; margin-top: 0.5em; }
        .progress-bar { width: 100%; height: 4px; background: #ddd; border-radius: 2px; overflow: hidden; display: none; }
        .progress-fill { height: 100%; background: #4CAF50; width: 0%; transition: width 0.3s; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 PDF QA System</h1>

        <div class="form-section">
            <h2>📄 Upload PDF</h2>
            <form method="post" action="/upload" enctype="multipart/form-data" id="uploadForm">
                <label for="password">Password:</label>
                <input type="password" name="password" id="password" required>
                
                <label for="file">Select PDF file (max 50MB):</label>
                <input type="file" name="file" id="file" accept=".pdf" required>
                <div class="file-info" id="fileInfo"></div>
                
                <div class="progress-bar" id="progressBar">
                    <div class="progress-fill" id="progressFill"></div>
                </div>
                
                <input type="submit" value="Upload PDF" id="uploadBtn">
            </form>
        </div>

        <div class="form-section">
            <h2>❓ Ask a Question</h2>
            <form method="post" action="/ask-form">
                <label for="question">Your question:</label>
                <input type="text" name="question" id="question" placeholder="What is this document about?" required>
                <input type="submit" value="Ask Question">
            </form>
        </div>
        
        <div class="api-endpoints">
            <h3>🔌 API Endpoints</h3>
            <ul>
                <li><strong>POST /upload</strong> - Upload PDF (requires password + file)</li>
                <li><strong>POST /ask</strong> - Ask question via API (JSON: {"question": "..."})</li>
                <li><strong>GET /status</strong> - System status and stats</li>
                <li><strong>GET /files</strong> - List processed files</li>
            </ul>
        </div>

        <h3>📊 Current Status</h3>
        <div class="status-grid">
            <div class="status-item {{ 'warning' if not vector