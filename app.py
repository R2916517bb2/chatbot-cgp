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
from pyngrok import conf, ngrok
from datetime import datetime
import traceback
import fitz # PyMuPDF
import pytesseract
from PIL import Image
import io
from langchain.docstore.document import Document # Import Document for manual creation

# --- Configuration ---
UPLOAD_FOLDER = "/tmp/uploads"
VECTOR_STORE_PATH = "/tmp/vector_store"
ALLOWED_EXTENSIONS = {'pdf'}
PASSWORD = "654321"  # Password for upload access

# IMPORTANT: Replace with your actual API keys
GROQ_API_KEY = "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" # Get from console.groq.com
NGROK_TOKEN = "2yenKU83I2XYvjBDKhkkMSwua3p_8gFQkz3EsUPRSMYpoHwW" # Get from ngrok.com/dashboard/auth
NGROK_DOMAIN = "my-pdf-qa.ngrok.app" # Optional: Custom domain for ngrok (requires paid plan)

# Optimized Text Splitting and Retrieval Parameters
CHUNK_SIZE = 1500  # Increased chunk size for more context
CHUNK_OVERLAP = 200 # Maintained or slightly increased overlap
TOP_K_RETRIEVAL = 6 # Number of top relevant documents to retrieve

# --- Setup ---
# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(VECTOR_STORE_PATH, exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configure Tesseract Path (Uncomment and set if Tesseract is not in your system's PATH)
# For Linux (e.g., Render, Ubuntu):
# pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'
# For Windows:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


# --- OCR Function ---
def extract_text_with_ocr(pdf_path):
    """
    Extracts text from a PDF, including performing OCR on images within the PDF.
    """
    full_text_content = []
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)

            # 1. Extract text directly from the page
            text = page.get_text()
            if text.strip():
                full_text_content.append(text)

            # 2. Extract images and perform OCR
            images = page.get_images(full=True)
            for img_index, img_info in enumerate(images):
                xref = img_info[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]

                try:
                    img = Image.open(io.BytesIO(image_bytes))
                    # Perform OCR on the image
                    ocr_text = pytesseract.image_to_string(img)
                    if ocr_text.strip(): # Only add if OCR found text
                        full_text_content.append(f"\n[OCR from Image {img_index+1} on Page {page_num+1}]:\n")
                        full_text_content.append(ocr_text)
                except Exception as img_err:
                    logging.warning(f"Could not process image {img_index} on page {page_num}: {img_err}")
                    continue
        doc.close()
    except Exception as e:
        logging.error(f"Error processing PDF with OCR: {e}", exc_info=True)
        return "" # Return empty string if there's an error

    return "\n".join(full_text_content)

# --- Utility Functions ---
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Flask App Setup ---
app = Flask(__name__)

# --- Embeddings and LLM Setup (Initialized once) ---
# Load Sentence Transformer model for embeddings
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# Initialize Groq LLM
llm = ChatGroq(temperature=0, groq_api_key=GROQ_API_KEY, model_name="mixtral-8x7b-32768")

# Initialize vector store (load existing or prepare for new)
db = None
if os.path.exists(VECTOR_STORE_PATH) and os.listdir(VECTOR_STORE_PATH):
    try:
        db = FAISS.load_local(VECTOR_STORE_PATH, embeddings, allow_dangerous_deserialization=True)
        logging.info("Vector store loaded successfully from existing path.")
    except Exception as e:
        logging.error(f"Error loading existing vector store: {e}. Starting fresh.", exc_info=True)
        db = None # Reset db if loading fails
else:
    logging.info("No existing vector store found or it's empty. A new one will be created upon first upload.")


# --- Routes ---

# HTML for file upload form and ask form
UPLOAD_FORM_HTML = """
<!doctype html>
<html>
<head><title>Upload PDF</title>
<style>
body { font-family: sans-serif; margin: 2em; }
form { margin-bottom: 2em; padding: 1em; border: 1px solid #ccc; border-radius: 8px; }
input[type="file"], input[type="password"], input[type="text"], textarea {
    padding: 0.5em; margin-bottom: 1em; border: 1px solid #ddd; border-radius: 4px; width: 100%; box-sizing: border-box;
}
input[type="submit"] {
    background-color: #4CAF50; color: white; padding: 0.7em 1.5em; border: none; border-radius: 4px; cursor: pointer;
}
input[type="submit"]:hover { background-color: #45a049; }
h2, h3 { color: #333; }
.error { color: red; }
.success { color: green; }
pre { background-color: #eee; padding: 1em; border-radius: 4px; overflow-x: auto; }
</style>
</head>
<body>
    <h1>PDF QA System</h1>

    <h2>Upload PDF</h2>
    <form method="post" action="/upload" enctype="multipart/form-data">
        Password: <input type="password" name="password" required><br>
        <input type="file" name="file" accept=".pdf" required><br>
        <input type="submit" value="Upload PDF">
    </form>

    <h2>Ask a Question</h2>
    <form method="post" action="/ask-form">
        Question: <input type="text" name="question" required><br>
        <input type="submit" value="Ask">
    </form>
    
    <h3>API Endpoints:</h3>
    <ul>
        <li>POST /upload - Upload a PDF file. Requires 'password' and 'file' (multipart/form-data).</li>
        <li>POST /ask - Ask a question via API. Requires 'question' (application/json).</li>
        <li>GET /status - Check system status.</li>
        <li>GET /api-docs - View API documentation (this page).</li>
    </ul>

    <h3>Current Status:</h3>
    <p>Vector store loaded: {{ 'Yes' if vector_store_loaded else 'No' }}</p>
    <p>Last update: {{ last_update }}</p>
</body>
</html>
"""

@app.route('/')
@app.route('/api-docs')
def api_docs():
    vector_store_loaded = db is not None
    last_update_time = os.path.getmtime(VECTOR_STORE_PATH) if os.path.exists(VECTOR_STORE_PATH) else None
    last_update = datetime.fromtimestamp(last_update_time).strftime('%Y-%m-%d %H:%M:%S') if last_update_time else "N/A"
    return render_template_string(UPLOAD_FORM_HTML, vector_store_loaded=vector_store_loaded, last_update=last_update)

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    global db # Declare global to modify the global db variable
    if request.method == 'POST':
        if request.form.get('password') != PASSWORD:
            return jsonify({"status": "error", "message": "Invalid password"}), 403

        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file part"}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({"status": "error", "message": "No selected file"}), 400
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            logging.info(f"File {filename} uploaded successfully to {filepath}")

            try:
                # Use the custom function to extract text with OCR
                combined_pdf_text = extract_text_with_ocr(filepath)
                
                if not combined_pdf_text.strip(): # Check if any meaningful text was extracted
                    return jsonify({"status": "error", "message": "Failed to extract text from PDF, potentially due to issues with PDF content or OCR."}), 500

                # Create a single Document object from the combined text
                doc_to_split = [Document(page_content=combined_pdf_text, metadata={"source": filename})]
                
                # Split the combined text into smaller chunks
                text_splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
                docs = text_splitter.split_documents(doc_to_split)

                if not docs:
                    return jsonify({"status": "error", "message": "No text could be extracted or split from the PDF for vectorization. Please ensure the PDF contains readable content."}), 500

                # Create or update vector store
                if db is None or not os.path.exists(VECTOR_STORE_PATH) or not os.listdir(VECTOR_STORE_PATH):
                    db = FAISS.from_documents(docs, embeddings)
                    db.save_local(VECTOR_STORE_PATH)
                    logging.info(f"New vector store created for {filename}")
                else:
                    # Load existing vector store
                    try:
                        existing_db = FAISS.load_local(VECTOR_STORE_PATH, embeddings, allow_dangerous_deserialization=True)
                        # Add new documents to the existing store
                        existing_db.add_documents(docs)
                        existing_db.save_local(VECTOR_STORE_PATH)
                        db = existing_db # Update the global db reference
                        logging.info(f"Documents from {filename} added to existing vector store.")
                    except Exception as e:
                        logging.error(f"Error updating existing vector store: {e}. Attempting to create new.", exc_info=True)
                        db = FAISS.from_documents(docs, embeddings)
                        db.save_local(VECTOR_STORE_PATH)
                        logging.info(f"New vector store created after failure to update existing for {filename}")


                return jsonify({"status": "success", "message": f"File {filename} processed and vector store updated/created."})

            except Exception as e:
                logging.error(f"Error processing PDF: {traceback.format_exc()}", exc_info=True)
                return jsonify({"status": "error", "message": f"Error processing PDF: {str(e)}"}), 500
        else:
            return jsonify({"status": "error", "message": "Invalid file type. Only PDFs are allowed."}), 400
    return redirect('/api-docs') # For GET request, show the form

@app.route('/ask-form', methods=['POST'])
def ask_question_form():
    question = request.form.get('question')
    if not question:
        return jsonify({"status": "error", "message": "Question is required"}), 400

    if db is None:
        return jsonify({"status": "error", "message": "No PDF loaded. Please upload a PDF first."}), 400

    try:
        # Create the RetrievalQA chain (re-create each time to ensure latest db is used)
        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=db.as_retriever(search_kwargs={"k": TOP_K_RETRIEVAL}), # <<< --- Optimized k value
            return_source_documents=True
        )
        response = qa_chain.invoke({"query": question})

        answer = response.get("result", "No answer found.")
        source_documents = response.get("source_documents", [])
        
        sources_list = []
        for doc in source_documents:
            # Check if page_content exists before trying to slice
            snippet = doc.page_content[:200] + "..." if doc.page_content else "Content not available"
            sources_list.append({
                "source": doc.metadata.get("source", "N/A"),
                "page": doc.metadata.get("page", "N/A"),
                "snippet": snippet
            })

        return render_template_string(
            """
            <!doctype html>
            <html>
            <head><title>Answer</title>
            <style>
            body { font-family: sans-serif; margin: 2em; }
            h2, h3 { color: #333; }
            pre { background-color: #eee; padding: 1em; border-radius: 4px; overflow-x: auto; }
            </style>
            </head>
            <body>
                <h1>Your Question: {{ question }}</h1>
                <h2>Answer:</h2>
                <pre>{{ answer }}</pre>
                <h3>Sources:</h3>
                {% if sources %}
                    <ul>
                    {% for source in sources %}
                        <li><strong>File:</strong> {{ source.source }}, <strong>Page:</strong> {{ source.page }}<br>
                            <pre>{{ source.snippet }}</pre>
                        </li>
                    {% endfor %}
                    </ul>
                {% else %}
                    <p>No source documents found.</p>
                {% endif %}
                <p><a href="/api-docs">Ask another question or upload PDF</a></p>
            </body>
            </html>
            """,
            question=question,
            answer=answer,
            sources=sources_list
        )
    except Exception as e:
        logging.error(f"Error answering question: {traceback.format_exc()}", exc_info=True)
        return jsonify({"status": "error", "message": f"Error processing question: {str(e)}"}), 500

@app.route('/ask', methods=['POST'])
def ask_question_api():
    data = request.get_json()
    question = data.get('question')

    if not question:
        return jsonify({"status": "error", "message": "Question is required"}), 400

    if db is None:
        return jsonify({"status": "error", "message": "No PDF loaded. Please upload a PDF first."}), 400

    try:
        # Create the RetrievalQA chain (re-create each time to ensure latest db is used)
        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=db.as_retriever(search_kwargs={"k": TOP_K_RETRIEVAL}), # <<< --- Optimized k value
            return_source_documents=True
        )
        response = qa_chain.invoke({"query": question})

        answer = response.get("result", "No answer found.")
        source_documents = response.get("source_documents", [])
        
        sources_list = []
        for doc in source_documents:
            # Check if page_content exists before trying to slice
            snippet = doc.page_content[:200] + "..." if doc.page_content else "Content not available"
            sources_list.append({
                "source": doc.metadata.get("source", "N/A"),
                "page": doc.metadata.get("page", "N/A"),
                "snippet": snippet
            })

        return jsonify({
            "status": "success",
            "question": question,
            "answer": answer,
            "sources": sources_list
        })
    except Exception as e:
        logging.error(f"Error answering question via API: {traceback.format_exc()}", exc_info=True)
        return jsonify({"status": "error", "message": f"Error processing question: {str(e)}"}), 500

@app.route('/status', methods=['GET'])
def get_status():
    vector_store_exists = os.path.exists(VECTOR_STORE_PATH) and os.listdir(VECTOR_STORE_PATH)
    last_modified_time = None
    if vector_store_exists:
        try:
            # Get the modification time of the vector store directory
            last_modified_time = os.path.getmtime(VECTOR_STORE_PATH)
            last_modified_time_str = datetime.fromtimestamp(last_modified_time).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            last_modified_time_str = "N/A (Error getting time)"
    else:
        last_modified_time_str = "N/A (No vector store)"

    return jsonify({
        "status": "operational",
        "vector_store_loaded_in_memory": db is not None,
        "vector_store_on_disk_exists": vector_store_exists,
        "last_vector_store_update": last_modified_time_str,
        "upload_folder_path": UPLOAD_FOLDER,
        "vector_store_path": VECTOR_STORE_PATH
    })

# --- Main Execution ---
if __name__ == '__main__':
    # ngrok setup
    conf.get_default().auth_token = NGROK_TOKEN
    conf.get_default().log_level = logging.INFO
    conf.get_default().log_format = "logfmt"
    conf.get_default().log_event_type = "web"

    try:
        logging.info("🚀 Starting PDF QA System...")
        logging.info("📡 Initializing ngrok tunnel...")

        # Connect to ngrok
        # If you have a free ngrok account, the domain parameter might not work
        # In that case, remove `domain=NGROK_DOMAIN` and ngrok will assign a random one.
        # e.g., public_url = ngrok.connect(5000, bind_tls=True)
        public_url = ngrok.connect(5000, bind_tls=True, domain=NGROK_DOMAIN)

        logging.info("\n" + "="*60)
        logging.info("🎉 PDF QA SYSTEM READY!")
        logging.info("="*60)
        logging.info(f"🌐 Public URL: {public_url.public_url}")
        logging.info(f"🔒 Upload PDF: {public_url.public_url}/upload")
        logging.info(f"❓ Ask Questions: {public_url.public_url}/ask-form")
        logging.info(f"🔌 API Endpoint: {public_url.public_url}/ask")
        logging.info(f"📊 System Status: {public_url.public_url}/status")
        logging.info(f"📚 API Documentation: {public_url.public_url}/api-docs")
        logging.info("="*60)
        logging.info(f"💡 Password for upload: {PASSWORD}")
        logging.info("="*60)

        app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)

    except Exception as e:
        logging.error(f"Failed to start application or ngrok tunnel: {e}", exc_info=True)
        # Handle ngrok connection errors specifically
        if "Authentication failed" in str(e):
            logging.error("NGROK_TOKEN is invalid. Please check your token on ngrok.com/dashboard/auth.")
        elif "Tunnel 'my-pdf-qa.ngrok.app' is not found" in str(e) or "Domain 'my-pdf-qa.ngrok.app' is not registered" in str(e):
             logging.error("NGROK_DOMAIN is not correctly configured or requires a paid ngrok plan. Try removing the 'domain' parameter.")
        logging.critical("Application startup failed. Exiting.")
        os._exit(1) # Exit with an error code