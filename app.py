<<<<<<< HEAD
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import os
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.question_answering import load_qa_chain
from langchain_groq import ChatGroq
from PyPDF2 import PdfReader
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Retrieve environment variables
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
PASSWORD = os.getenv('PASSWORD')

if not GROQ_API_KEY:
    logger.error("GROQ_API_KEY not found in environment variables")
if not PASSWORD:
    logger.error("PASSWORD not found in environment variables")

# Flask App Configuration
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'pdf'}
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Ensure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy'}), 200

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part in request'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Add timestamp to avoid filename conflicts
            import time
            timestamp = str(int(time.time()))
            name, ext = os.path.splitext(filename)
            filename = f"{name}_{timestamp}{ext}"
            
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            logger.info(f"File uploaded successfully: {filename}")
            return jsonify({'success': 'File uploaded successfully', 'filename': filename}), 200

        return jsonify({'error': 'Invalid file format. Only PDF is allowed.'}), 400
    
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/ask', methods=['POST'])
def ask_question():
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        filename = data.get('filename', '').strip()
        password = data.get('password', '')

        # Validation
        if not question:
            return jsonify({'error': 'Question is required'}), 400
        
        if not filename:
            return jsonify({'error': 'Filename is required'}), 400
            
        if password != PASSWORD:
            return jsonify({'error': 'Invalid password'}), 403

        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404

        # Extract text from PDF with page tracking
        documents = []
        try:
            with open(file_path, 'rb') as f:
                reader = PdfReader(f)
                for i, page in enumerate(reader.pages):
                    page_text = page.extract_text()
                    if page_text.strip():  # Only add non-empty pages
                        documents.append(f"[Page {i+1}]\n{page_text}")
        except Exception as e:
            logger.error(f"PDF reading error: {str(e)}")
            return jsonify({'error': f'Error reading PDF: {str(e)}'}), 500

        if not documents:
            return jsonify({'error': 'No readable text found in the PDF.'}), 400

        # Split text into semantically aware chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, 
            chunk_overlap=200,
            separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
        )
        texts = text_splitter.split_text("\n".join(documents))

        if not texts:
            return jsonify({'error': 'Failed to process document text.'}), 400

        # Embed chunks
        try:
            embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )
            vectorstore = FAISS.from_texts(texts, embeddings)
        except Exception as e:
            logger.error(f"Embedding error: {str(e)}")
            return jsonify({'error': f'Error creating embeddings: {str(e)}'}), 500

        # Retrieve relevant chunks
        try:
            retrieved_docs = vectorstore.similarity_search(question, k=5)
        except Exception as e:
            logger.error(f"Similarity search error: {str(e)}")
            return jsonify({'error': f'Error searching documents: {str(e)}'}), 500

        # Construct system prompt
        system_prompt = (
            "You are a document-based assistant. Answer the question based ONLY on the content provided from the PDF.\n"
            "If the answer is not in the document, respond with 'Not found in the document.'\n"
            "Provide your response in both Arabic and English if possible.\n"
            "Be concise and accurate.\n"
        )
        formatted_question = f"{system_prompt}\n\nQuestion: {question}"

        # Run LLM chain
        try:
            llm = ChatGroq(
                groq_api_key=GROQ_API_KEY, 
                model_name="llama3-8b-8192",
                temperature=0.1,
                max_tokens=1000
            )
            chain = load_qa_chain(llm=llm, chain_type="stuff")
            answer = chain.run(input_documents=retrieved_docs, question=formatted_question)
            
            logger.info(f"Question answered successfully for file: {filename}")
            return jsonify({'answer': answer})
            
        except Exception as e:
            logger.error(f"LLM error: {str(e)}")
            return jsonify({'error': f'Error generating answer: {str(e)}'}), 500

    except Exception as e:
        logger.error(f"Unexpected error in ask_question: {str(e)}")
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500

@app.errorhandler(413)
def file_too_large(error):
    return jsonify({'error': 'File too large. Maximum size is 50MB.'}), 413

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
=======
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import os
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.question_answering import load_qa_chain
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from PyPDF2 import PdfReader

# Load environment variables
load_dotenv()

# Retrieve environment variables
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
PASSWORD = os.getenv('PASSWORD')

# Flask configuration
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'pdf'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in request'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        return jsonify({'success': 'File uploaded successfully', 'filename': filename}), 200

    return jsonify({'error': 'Invalid file format. Only PDF is allowed.'}), 400

@app.route('/ask', methods=['POST'])
def ask_question():
    data = request.get_json()
    question = data.get('question')
    filename = data.get('filename')
    password = data.get('password', '').strip()

    # Compare with environment password
    if password != (PASSWORD or '').strip():
        return jsonify({'error': 'Invalid password'}), 403

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404

    # Extract text from PDF
    try:
        with open(file_path, 'rb') as f:
            reader = PdfReader(f)
            documents = []
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    documents.append(f"[Page {i+1}]\n{page_text}")
    except Exception as e:
        return jsonify({'error': f'Error reading PDF: {str(e)}'}), 500

    if not documents:
        return jsonify({'error': 'No readable text found in the PDF.'}), 400

    # Split and embed chunks
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    texts = text_splitter.split_text("\n".join(documents))
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vectorstore = FAISS.from_texts(texts, embeddings)
    docs = vectorstore.similarity_search(question, k=5)

    # System prompt + LLM call
    llm = ChatGroq(groq_api_key=GROQ_API_KEY, model_name="llama3-8b-8192")
    system_prompt = (
        "You are a helpful assistant. Answer only using content from the provided PDF. "
        "If not found, say 'Not found in the document'. Respond in both Arabic and English."
    )
    prompt = f"{system_prompt}\n\nQuestion: {question}"

    try:
        chain = load_qa_chain(llm=llm, chain_type="stuff")
        answer = chain.run(input_documents=docs, question=prompt)
        return jsonify({'answer': answer})
    except Exception as e:
        return jsonify({'error': f'LLM error: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True)
>>>>>>> 801936c935c8f84e30a848a7e41a116360589f2f
