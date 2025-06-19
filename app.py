
from flask import Flask, request, jsonify, render_template, send_file
from werkzeug.utils import secure_filename
import os
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.question_answering import load_qa_chain
from langchain.llms import Groq
from pyngrok import ngrok
from dotenv import load_dotenv
from PyPDF2 import PdfReader

# Load environment variables from .env file
load_dotenv()

# Retrieve environment variables
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
NGROK_TOKEN = os.getenv('NGROK_TOKEN')
NGROK_DOMAIN = os.getenv('NGROK_DOMAIN')
PASSWORD = os.getenv('PASSWORD')

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'pdf'}

# Ensure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'})
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'})
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return jsonify({'success': 'File uploaded successfully'})
    return jsonify({'error': 'Invalid file format'})

@app.route('/ask', methods=['POST'])
def ask_question():
    data = request.get_json()
    question = data.get('question')
    filename = data.get('filename')
    password = data.get('password')

    if password != PASSWORD:
        return jsonify({'error': 'Invalid password'})

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'})

    # Extract text from PDF
    with open(file_path, 'rb') as f:
        reader = PdfReader(f)
        text = ''
        for page in reader.pages:
            text += page.extract_text()

    # Split text into chunks
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    texts = text_splitter.split_text(text)

    # Embed text chunks
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vectorstore = FAISS.from_texts(texts, embeddings)

    # Perform semantic search
    docs = vectorstore.similarity_search(question, k=5)

    # Answer question using LLM
    llm = Groq(api_key=GROQ_API_KEY)
    chain = load_qa_chain(llm, chain_type="map_reduce")
    answer = chain.run(input_documents=docs, question=question)

    return jsonify({'answer': answer})

@app.route('/ask-form', methods=['GET'])
def ask_form():
    return render_template('ask_form.html')

@app.route('/status', methods=['GET'])
def status():
    return jsonify({'status': 'running'})

if __name__ == '__main__':
    # Start ngrok tunnel
    ngrok.set_auth_token(NGROK_TOKEN)
    public_url = ngrok.connect(5000)
    print(f" * ngrok tunnel opened at {public_url}")

    # Run Flask app
    app.run(debug=True, port=5000)
