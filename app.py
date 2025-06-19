
from flask import Flask, request, jsonify, render_template, send_file
from werkzeug.utils import secure_filename
import os
import faiss
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.question_answering import load_qa_chain
from langchain.llms import Groq
from pyngrok import ngrok
from dotenv import load_dotenv
import PyPDF2

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
    jsonify({'error': 'Invalid password'})

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'})

    # Extract text from PDF
    with open(file_path, 'rb') as f:
        reader = PyPDF2.PdfFileReader(f)
        text = ''
        for page_num in range(reader.numPages):
            text += reader.getPage(page_num).extract_text()

    # Split text into chunks
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    texts = text_splitter.split_text(text)

    # Embed text chunks
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vectorstore = FAISS.from_texts(texts, embeddings)

    # Perform semantic search
    query_vector = embeddings.embed_query(question)
    D, I = vectorstore.search(query_vector, k=5)
    relevant_texts = [texts[i] for i in I[0]]

    # Answer question using LLM
    llm = Groq(api_key=GROQ_API_KEY)
    chain = load_qa_chain(llm, chain_type="map_reduce")
    answer = chain.run(input_documents=relevant_texts, question=question)

    return jsonify({'answer': answer})

@app.route('/ask-form', methods=['GET'])
def ask_form():
    return render_template('ask_form.html')

@app.route('/status', methods=['GET'])
def status():
    return jsonify({'status': 'running'})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    ngrok.set_auth_token(NGROK_TOKEN)
    public_url = ngrok.connect(port)
    print(f" * ngrok tunnel opened at {public_url}")
    app.run(host="0.0.0.0", port=port)
