import os
import time
import logging
from flask import Flask, request, jsonify, render_template_string, redirect
from werkzeug.utils import secure_filename
from langchain.vectorstores import FAISS
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.chains import RetrievalQA
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_groq import ChatGroq
from pyngrok import conf, ngrok
from datetime import datetime
import traceback

# Configuration
UPLOAD_FOLDER = "/tmp/uploads"
VECTOR_STORE_PATH = "/tmp/vector_store"
ALLOWED_EXTENSIONS = {'pdf'}
PASSWORD = "654321"  # Password for upload access
# IMPORTANT: Replace with your actual API keys
GROQ_API_KEY = "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" # Get from console.groq.com
NGROK_TOKEN = "2yenKU83I2XYvjBDKhkkMSwua3p_8gFQkz3EsUPRSMYpoHwW" # Get from ngrok.com/dashboard/auth
NGROK_DOMAIN = "my-pdf-qa.ngrok.app" # Optional: Custom domain for ngrok (requires paid plan)

# Setup
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(VECTOR_STORE_PATH, exist_ok=True)import os
import time
import logging
from flask import Flask, request, jsonify, render_template_string, redirect
from werkzeug.utils import secure_filename
from langchain.vectorstores import FAISS
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.chains import RetrievalQA
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_groq import ChatGroq
from pyngrok import conf, ngrok
from datetime import datetime
import traceback

# Configuration
UPLOAD_FOLDER = "/tmp/uploads"
VECTOR_STORE_PATH = "/tmp/vector_store"
ALLOWED_EXTENSIONS = {'pdf'}
PASSWORD = "654321"  # Password for upload access
# IMPORTANT: Replace with your actual API keys
GROQ_API_KEY = "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" # Get from console.groq.com
NGROK_TOKEN = "2yenKU83I2XYvjBDKhkkMSwua3p_8gFQkz3EsUPRSMYpoHwW" # Get from ngrok.com/dashboard/auth
NGROK_DOMAIN = "my-pdf-qa.ngrok.app" # Optional: Custom domain for ngrok (requires paid plan)

# Setup
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(VECTOR_STORE_PATH, exist_ok=True)
conf.get_default().auth_token = NGROK_TOKEN

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Global variables
qa_system = None
current_document = None
document_metadata = {}

# --- NEW, SIMPLIFIED, AND PROFESSIONAL HTML TEMPLATES ---

html_upload_form = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Upload PDF - AI QA System</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary-color: #4CAF50; /* Green for success/primary action */
            --primary-dark: #388E3C;
            --accent-color: #2196F3; /* Blue for info/links */
            --text-color: #333;
            --secondary-text-color: #666;
            --border-color: #e0e0e0;
            --background-light: #f7f9fc;
            --background-dark: #e8f0f7;
            --card-background: #ffffff;
            --shadow-light: rgba(0, 0, 0, 0.08);
            --shadow-medium: rgba(0, 0, 0, 0.12);
        }
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, var(--background-light) 0%, var(--background-dark) 100%);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
            box-sizing: border-box;
            color: var(--text-color);
        }
        .container {
            background: var(--card-background);
            padding: 2.5rem 3rem;
            border-radius: 12px;
            box-shadow: 0 8px 25px var(--shadow-medium);
            max-width: 480px;
            width: 100%;
            text-align: center;
            transition: all 0.3s ease;
        }
        h2 {
            margin-bottom: 1.8rem;
            color: var(--text-color);
            font-size: 1.9rem;
            font-weight: 700;
        }
        .current-doc {
            background: #e8f5e8; /* Lighter green */
            padding: 1.2rem;
            border-radius: 8px;
            margin-bottom: 1.8rem;
            border-left: 5px solid var(--primary-color);
            text-align: left;
            font-size: 0.95rem;
            line-height: 1.5;
            color: var(--secondary-text-color);
        }
        .current-doc strong {
            color: var(--primary-dark);
            font-weight: 600;
        }
        label {
            display: block;
            text-align: left;
            margin-bottom: 0.6rem;
            font-weight: 600;
            color: var(--text-color);
            font-size: 0.95rem;
        }
        input[type="password"],
        input[type="file"] {
            width: 100%;
            padding: 0.9rem 1.2rem;
            margin-bottom: 1.5rem;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            font-size: 1rem;
            transition: all 0.3s ease;
            box-sizing: border-box;
            background-color: var(--background-light);
            color: var(--text-color);
        }
        input[type="password"]:focus,
        input[type="file"]:focus {
            outline: none;
            border-color: var(--accent-color);
            box-shadow: 0 0 0 3px rgba(33, 150, 243, 0.15); /* Softer blue shadow */
            background-color: var(--card-background);
        }
        input[type="file"] {
            padding: 0.7rem 1.2rem; /* Adjusted for file input */
        }
        input[type="submit"] {
            background: var(--primary-color);
            color: white;
            padding: 1rem 2.2rem;
            font-size: 1.1rem;
            font-weight: 700;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s ease;
            width: 100%;
            letter-spacing: 0.5px;
            box-shadow: 0 4px 15px rgba(76, 175, 80, 0.2); /* Green shadow */
        }
        input[type="submit"]:hover:not(:disabled) {
            background: var(--primary-dark);
            transform: translateY(-3px);
            box-shadow: 0 6px 20px rgba(76, 175, 80, 0.3);
        }
        input[type="submit"]:active {
            transform: translateY(0);
            box-shadow: 0 2px 10px rgba(76, 175, 80, 0.2);
        }
        input[type="submit"]:disabled {
            background: #ccc;
            cursor: not-allowed;
            box-shadow: none;
        }
        .message {
            margin-top: 1.8rem;
            padding: 1.2rem;
            border-radius: 8px;
            font-weight: 600;
            min-height: 1.2em;
            text-align: left;
            font-size: 0.95rem;
        }
        .message.success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .message.error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .nav-link {
            display: inline-block;
            margin-top: 1.5rem;
            color: var(--accent-color);
            text-decoration: none;
            font-weight: 600;
            transition: color 0.3s ease;
            font-size: 0.95rem;
        }
        .nav-link:hover {
            color: #1976D2; /* Darker blue */
        }
        .processing {
            display: none;
            margin-top: 1.5rem;
            color: var(--accent-color);
            font-weight: 600;
            font-size: 1rem;
        }
        .spinner {
            display: inline-block;
            width: 22px;
            height: 22px;
            border: 3px solid rgba(33, 150, 243, 0.2);
            border-top: 3px solid var(--accent-color);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 12px;
            vertical-align: middle;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .action-links {
            margin-top: 2rem;
            display: flex;
            flex-direction: column; /* Stack links vertically */
            gap: 0.8rem;
        }
        .action-links .nav-link {
            display: block; /* Make links take full width */
            margin-top: 0; /* Reset margin */
            padding: 0.8rem 1.5rem;
            background: #f0f4f8; /* Light background for secondary links */
            border-radius: 8px;
            text-decoration: none;
            color: var(--accent-color);
            font-weight: 600;
            transition: all 0.2s ease-in-out;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }
        .action-links .nav-link:hover {
            background: #e5eaf1;
            color: #1976D2;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
    </style>
    <script>
        function showProcessing() {
            document.getElementById('processing').style.display = 'block';
            document.querySelector('input[type="submit"]').disabled = true;
        }
    </script>
</head>
<body>
    <div class="container">
        <h2>Upload PDF & Start QA</h2>

        {% if current_doc %}
        <div class="current-doc">
            <strong>📄 Current Document:</strong> {{ current_doc.name }}<br>
            <strong>⏰ Uploaded:</strong> {{ current_doc.upload_time }}<br>
            <strong>📊 Chunks:</strong> {{ current_doc.chunks }}
        </div>
        {% endif %}

        <form method="post" enctype="multipart/form-data" onsubmit="showProcessing()">
            <label for="password">🔑 Security Password</label>
            <input type="password" id="password" name="password" required placeholder="Enter password to upload" />

            <label for="file">⬆️ Choose PDF File</label>
            <input type="file" id="file" name="file" accept="application/pdf" required />

            <input type="submit" value="Upload & Process PDF" />
        </form>

        <div id="processing" class="processing">
            <div class="spinner"></div>Processing document... This may take a moment.
        </div>

        {% if message %}
            <div class="message {{ message_type }}">{{ message }}</div>
        {% endif %}

        {% if current_doc %}
        <div class="action-links">
            <a href="/ask-form" class="nav-link">🚀 Go to Question Answering</a>
        </div>
        {% else %}
        <a href="/ask-form" class="nav-link">← Return to Question Page</a>
        {% endif %}
    </div>
</body>
</html>
"""

html_question_form = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Ask Your PDF - AI QA System</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary-color: #4CAF50; /* Green for success/primary action */
            --primary-dark: #388E3C;
            --accent-color: #2196F3; /* Blue for info/links */
            --text-color: #333;
            --secondary-text-color: #666;
            --border-color: #e0e0e0;
            --background-light: #f7f9fc;
            --background-dark: #e8f0f7;
            --card-background: #ffffff;
            --shadow-light: rgba(0, 0, 0, 0.08);
            --shadow-medium: rgba(0, 0, 0, 0.12);
        }
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, var(--background-light) 0%, var(--background-dark) 100%);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
            box-sizing: border-box;
            color: var(--text-color);
        }
        .container {
            background: var(--card-background);
            padding: 2.5rem 3rem;
            border-radius: 12px;
            box-shadow: 0 8px 25px var(--shadow-medium);
            max-width: 700px;
            width: 100%;
            text-align: center;
            transition: all 0.3s ease;
        }
        h2 {
            margin-bottom: 1.8rem;
            color: var(--text-color);
            font-size: 1.9rem;
            font-weight: 700;
        }
        .status {
            padding: 1.2rem;
            border-radius: 8px;
            margin-bottom: 1.8rem;
            font-weight: 600;
            font-size: 0.95rem;
            text-align: left;
            line-height: 1.5;
        }
        .status.ready {
            background: #e8f5e8;
            color: #2e7d32;
            border-left: 5px solid var(--primary-color);
        }
        .status.not-ready {
            background: #fff3cd;
            color: #856404;
            border-left: 5px solid #ffc107;
        }
        form {
            display: flex;
            gap: 1rem;
            margin-bottom: 2rem;
            align-items: center;
            flex-wrap: wrap; /* Allow wrapping on smaller screens */
        }
        form input[type="text"] {
            flex: 1;
            padding: 0.9rem 1.2rem;
            font-size: 1rem;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            transition: all 0.3s ease;
            background-color: var(--background-light);
            color: var(--text-color);
        }
        form input[type="text"]:focus {
            outline: none;
            border-color: var(--accent-color);
            box-shadow: 0 0 0 3px rgba(33, 150, 243, 0.15);
            background-color: var(--card-background);
        }
        form input[type="submit"] {
            background: var(--accent-color);
            color: white;
            padding: 0.9rem 2rem;
            font-size: 1.05rem;
            font-weight: 700;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(33, 150, 243, 0.2); /* Blue shadow */
            flex-shrink: 0; /* Prevent button from shrinking */
        }
        form input[type="submit"]:hover:not(:disabled) {
            background: #1976D2; /* Darker blue */
            transform: translateY(-3px);
            box-shadow: 0 6px 20px rgba(33, 150, 243, 0.3);
        }
        form input[type="submit"]:active {
            transform: translateY(0);
            box-shadow: 0 2px 10px rgba(33, 150, 243, 0.2);
        }
        form input[type="submit"]:disabled {
            background: #ccc;
            cursor: not-allowed;
            box-shadow: none;
        }
        .answer-container {
            background: #f8f9ff;
            border-radius: 10px;
            padding: 2rem;
            margin-top: 1.5rem;
            border-left: 5px solid var(--accent-color);
            text-align: left;
            box-shadow: 0 4px 15px var(--shadow-light);
        }
        .question {
            font-weight: 700;
            color: var(--text-color);
            margin-bottom: 1rem;
            font-size: 1.1rem;
            display: flex;
            align-items: center;
            gap: 0.8rem;
        }
        .question::before {
            content: '❓';
            font-size: 1.2em;
        }
        .answer {
            color: var(--secondary-text-color);
            line-height: 1.7;
            white-space: pre-wrap;
            font-size: 1rem;
            display: flex;
            align-items: flex-start;
            gap: 0.8rem;
        }
        .answer::before {
            content: '🤖';
            font-size: 1.2em;
            flex-shrink: 0;
        }
        .nav-links {
            margin-top: 2.5rem;
            display: flex;
            justify-content: center;
            gap: 1.5rem; /* Reduced gap */
            flex-wrap: wrap;
        }
        .nav-link {
            color: var(--accent-color);
            text-decoration: none;
            font-weight: 600;
            transition: all 0.3s ease;
            font-size: 0.95rem;
            padding: 0.8rem 1.5rem;
            background: #f0f4f8; /* Light background for secondary links */
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }
        .nav-link:hover {
            color: #1976D2; /* Darker blue */
            background: #e5eaf1;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        .loading {
            display: none;
            color: var(--accent-color);
            font-weight: 600;
            margin-top: 1.5rem;
            font-size: 1rem;
        }
        .spinner {
            display: inline-block;
            width: 22px;
            height: 22px;
            border: 3px solid rgba(33, 150, 243, 0.2);
            border-top: 3px solid var(--accent-color);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 12px;
            vertical-align: middle;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        @media (max-width: 600px) {
            form {
                flex-direction: column;
            }
            form input[type="submit"] {
                width: 100%;
            }
            .container {
                padding: 1.8rem 1.5rem;
            }
            h2 {
                font-size: 1.7rem;
            }
        }
    </style>
    <script>
        function showLoading() {
            document.getElementById('loading').style.display = 'block';
            document.getElementById('submit-btn').disabled = true;
        }
    </script>
</head>
<body>
    <div class="container">
        <h2>Ask Your Document</h2>

        {% if has_document %}
        <div class="status ready">
            ✅ Document Ready: <strong>{{ doc_info.name }}</strong> ({{ doc_info.chunks }} chunks loaded)
        </div>
        {% else %}
        <div class="status not-ready">
            ⚠️ No Document Loaded: Please <a href="/upload" style="color: inherit; text-decoration: underline; font-weight: 700;">upload a PDF</a> first to enable questions.
        </div>
        {% endif %}

        <form method="post" onsubmit="showLoading()">
            <input
                type="text"
                name="question"
                placeholder="Type your question here..."
                required
                autocomplete="off"
                {% if not has_document %}disabled{% endif %}
            />
            <input
                type="submit"
                id="submit-btn"
                value="Ask AI"
                {% if not has_document %}disabled{% endif %}
            />
        </form>

        <div id="loading" class="loading">
            <div class="spinner"></div>AI is thinking... Please wait.
        </div>

        {% if answer %}
        <div class="answer-container">
            <div class="question">Question: {{ question }}</div>
            <div class="answer">Answer: {{ answer }}</div>
        </div>
        {% endif %}

        <div class="nav-links">
            <a href="/upload" class="nav-link">⬆️ Upload New PDF</a>
            <a href="/status" class="nav-link">📊 System Status</a>
            <a href="/api-docs" class="nav-link">📚 API Documentation</a>
        </div>
    </div>
</body>
</html>
"""

html_api_docs = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>API Documentation - PDF QA System</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Roboto+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary-color: #4CAF50; /* Green */
            --accent-color: #2196F3; /* Blue */
            --text-color: #333;
            --secondary-text-color: #666;
            --background-light: #f7f9fc;
            --background-dark: #e8f0f7;
            --card-background: #ffffff;
            --code-bg: #2d3748;
            --code-text: #e2e8f0;
            --shadow-light: rgba(0, 0, 0, 0.08);
            --shadow-medium: rgba(0, 0, 0, 0.12);
        }
        body {
            font-family: 'Inter', sans-serif;
            background: var(--background-light);
            margin: 0;
            padding: 2rem;
            line-height: 1.6;
            color: var(--text-color);
        }
        .container {
            max-width: 960px;
            margin: 0 auto;
            background: var(--card-background);
            padding: 3rem;
            border-radius: 12px;
            box-shadow: 0 8px 30px var(--shadow-medium);
        }
        h1, h2, h3 {
            color: var(--text-color);
            font-weight: 700;
        }
        h1 {
            text-align: center;
            margin-bottom: 2.5rem;
            font-size: 2.2rem;
        }
        h2 {
            margin-top: 2.5rem;
            margin-bottom: 1.5rem;
            font-size: 1.8rem;
        }
        h3 {
            font-size: 1.4rem;
            margin-bottom: 1rem;
        }
        p {
            margin-bottom: 1rem;
            color: var(--secondary-text-color);
        }
        strong {
            color: var(--text-color);
        }
        .endpoint {
            background: #f8f9ff; /* Light blueish background */
            padding: 2rem;
            margin: 2.5rem 0;
            border-radius: 10px;
            border-left: 5px solid var(--accent-color);
            box-shadow: 0 3px 12px var(--shadow-light);
        }
        .endpoint h3 {
            display: flex;
            align-items: center;
            margin-bottom: 1.5rem;
            gap: 1rem;
        }
        .method {
            padding: 0.4rem 1rem;
            border-radius: 6px;
            font-size: 0.9rem;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .method.get {
            background: #28a745; /* Green */
            color: white;
        }
        .method.post {
            background: #007bff; /* Blue */
            color: white;
        }
        pre {
            background: var(--code-bg);
            color: var(--code-text);
            padding: 1.5rem;
            border-radius: 8px;
            overflow-x: auto;
            font-size: 0.95rem;
            line-height: 1.5;
            font-family: 'Roboto Mono', monospace;
            margin-top: 1rem;
            box-shadow: inset 0 2px 5px rgba(0,0,0,0.2);
        }
        code {
            background: #e9ecef;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-family: 'Roboto Mono', monospace;
            color: #c7254e; /* For inline code */
            font-size: 0.9em;
        }
        .nav-link {
            display: inline-block;
            margin-top: 2.5rem;
            color: var(--accent-color);
            text-decoration: none;
            font-weight: 600;
            transition: all 0.3s ease;
            font-size: 1rem;
            padding: 0.8rem 1.5rem;
            background: #f0f4f8;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }
        .nav-link:hover {
            color: #1976D2;
            background: #e5eaf1;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        @media (max-width: 768px) {
            .container {
                padding: 2rem 1.5rem;
            }
            h1 {
                font-size: 2rem;
            }
            .endpoint {
                padding: 1.5rem;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📚 PDF QA System API Documentation</h1>

        <p>This document outlines the available API endpoints for interacting with the PDF Question Answering System. The system allows you to upload a PDF document and then query it using natural language.</p>

        <h2>Endpoints</h2>

        <div class="endpoint">
            <h3><span class="method post">POST</span> <code>/ask</code></h3>
            <p>Submit a question about the currently loaded PDF document and receive an AI-generated answer.</p>

            <strong>Request Body:</strong> (<code>application/json</code>)
            <pre>{
    "question": "What is the main topic of this document?"
}</pre>
            <strong>Response:</strong> (<code>application/json</code>)
            <pre>{
    "answer": "The document primarily discusses...",
    "success": true,
    "document": "your_document.pdf",
    "question": "What is the main topic..."
}</pre>
            <p><strong>Error Response (No Document Loaded):</strong></p>
            <pre>{
    "error": "QA system not ready. Please upload a PDF first.",
    "success": false
}</pre>
        </div>

        <div class="endpoint">
            <h3><span class="method get">GET</span> <code>/status</code></h3>
            <p>Check the current status of the AI QA system, including whether a PDF is loaded and its metadata.</p>

            <strong>Response:</strong> (<code>application/json</code>)
            <pre>{
    "ready": true,
    "document": "document.pdf",
    "metadata": {
        "name": "document.pdf",
        "upload_time": "2025-06-18 15:30:45",
        "chunks": 42,
        "file_path": "/content/uploads/1718712645_document.pdf"
    }
}</pre>
            <p><strong>Response (No Document Loaded):</strong></p>
            <pre>{
    "ready": false,
    "document": null,
    "metadata": null
}</pre>
        </div>

        <h2>Code Examples</h2>

        <h3>🐍 Python Example</h3>
        <pre><code>import requests
import json

base_url = "{{ base_url }}" # This will be your ngrok URL

# --- 1. Check System Status ---
print("Checking system status...")
try:
    response = requests.get(f"{{base_url}}/status")
    response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
    status_data = response.json()
    print("Status Response:", json.dumps(status_data, indent=2))
    if not status_data.get('ready'):
        print("System is not ready. Please upload a PDF via the web interface first.")
except requests.exceptions.RequestException as e:
    print(f"Error checking status: {e}")

# --- 2. Ask a Question (if ready) ---
if status_data.get('ready', False):
    print("\nAsking a question...")
    question = "What are the key findings discussed in the report?"
    try:
        response = requests.post(
            f"{{base_url}}/ask",
            headers={'Content-Type': 'application/json'},
            json={"question": question}
        )
        response.raise_for_status()
        answer_data = response.json()
        print(f"Question: {question}")
        print("Answer Response:", json.dumps(answer_data, indent=2))
    except requests.exceptions.RequestException as e:
        print(f"Error asking question: {e}")
else:
    print("\nSkipping question: Document not loaded.")
</code></pre>

        <h3>🌐 JavaScript (Fetch API) Example</h3>
        <pre><code>const baseUrl = "{{ base_url }}"; // This will be your ngrok URL

// --- 1. Check System Status ---
console.log('Checking system status...');
fetch(`${baseUrl}/status`)
  .then(response => {
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  })
  .then(data => {
    console.log('Status:', data);
    if (!data.ready) {
      console.log('System is not ready. Please upload a PDF via the web interface first.');
    } else {
      // --- 2. Ask a Question (if ready) ---
      console.log('\nAsking a question...');
      const question = "What are the key features of the new product?";
      fetch(`${baseUrl}/ask`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ question: question })
      })
      .then(response => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
      })
      .then(data => {
        console.log(`Question: ${question}`);
        console.log('Answer:', data);
      })
      .catch(error => {
        console.error('Error asking question:', error);
      });
    }
  })
  .catch(error => {
    console.error('Error checking status:', error);
  });
</code></pre>

        <a href="/ask-form" class="nav-link">← Back to Main Page</a>
    </div>
</body>
</html>
"""

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_document(file_path):
    """Load and split PDF document into chunks with enhanced processing."""
    try:
        loader = PyPDFLoader(file_path)
        docs = loader.load()

        # Enhanced text splitter for better context
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
        )

        chunks = splitter.split_documents(docs)
        logger.info(f"Document processed: {len(chunks)} chunks created")
        return chunks
    except Exception as e:
        logger.error(f"Error loading document: {str(e)}")
        raise

def embed_documents(docs):
    """Create FAISS vector store from document chunks."""
    try:
        embed_model = HuggingFaceEmbeddings(
            model_name='sentence-transformers/all-MiniLM-L6-v2',
            model_kwargs={'device': 'cpu'}
        )
        vector_store = FAISS.from_documents(docs, embed_model)

        # Save vector store for persistence
        vector_store.save_local(VECTOR_STORE_PATH)
        logger.info("Vector embeddings created and saved")
        return vector_store
    except Exception as e:
        logger.error(f"Error creating embeddings: {str(e)}")
        raise

def build_qa_system(faiss_index):
    """Build QA system with enhanced retrieval."""
    try:
        llm = ChatGroq(
            api_key=GROQ_API_KEY,
            model_name="llama3-8b-8192",
            temperature=0.1
        )

        retriever = faiss_index.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 4, "fetch_k": 8}
        )

        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=retriever,
            return_source_documents=True
        )

        logger.info("QA system built successfully")
        return qa_chain
    except Exception as e:
        logger.error(f"Error building QA system: {str(e)}")
        raise

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    global qa_system, current_document, document_metadata
    message = None
    message_type = "info"

    if request.method == 'POST':
        try:
            if request.form.get("password") != PASSWORD:
                message = "❌ Incorrect password. Access denied."
                message_type = "error"
            elif 'file' not in request.files:
                message = "❌ No file selected. Please choose a PDF file."
                message_type = "error"
            else:
                file = request.files['file']
                if file and allowed_file(file.filename):
                    # Use timestamp to avoid collisions (your smart approach!)
                    filename = secure_filename(file.filename)
                    filename = f"{int(time.time())}_{filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)

                    logger.info(f"Processing uploaded file: {filename}")

                    # Process document with enhanced pipeline
                    docs = load_document(file_path)
                    faiss_index = embed_documents(docs)
                    qa_system = build_qa_system(faiss_index)

                    # Update metadata
                    current_document = filename
                    document_metadata = {
                        'name': file.filename,  # Original name for display
                        'upload_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'chunks': len(docs),
                        'file_path': file_path
                    }

                    message = f"✅ Successfully processed '{file.filename}' into {len(docs)} searchable chunks!"
                    message_type = "success"
                    logger.info(f"Document processed successfully: {len(docs)} chunks")
                else:
                    message = "❌ Invalid file type. Please upload a PDF file only."
                    message_type = "error"
        except Exception as e:
            message = f"❌ Error processing file: {str(e)}"
            message_type = "error"
            logger.error(f"Upload error: {traceback.format_exc()}")

    return render_template_string(
        html_upload_form,
        message=message,
        message_type=message_type,
        current_doc=document_metadata if current_document else None
    )

@app.route('/ask-form', methods=['GET', 'POST'])
def ask_form():
    answer = None
    question = ""

    if request.method == 'POST':
        question = request.form.get("question", "").strip()
        if question and qa_system:
            try:
                logger.info(f"Processing question: {question}")
                result = qa_system.invoke({"query": question})
                answer = result.get('result', 'No relevant answer found in the document.')
            except Exception as e:
                answer = f"Error processing your question: {str(e)}"
                logger.error(f"Question processing error: {traceback.format_exc()}")
        elif not qa_system:
            answer = "Please upload a PDF document first to start asking questions."

    return render_template_string(
        html_question_form,
        answer=answer,
        question=question,
        has_document=qa_system is not None,
        doc_info=document_metadata if current_document else None
    )

@app.route('/ask', methods=['POST'])
def ask_api():
    """Enhanced API endpoint for asking questions."""
    if not qa_system:
        return jsonify({
            "error": "QA system not ready. Please upload a PDF first.",
            "success": False
        }), 503

    try:
        data = request.get_json()
        if not data or not data.get("question"):
            return jsonify({
                "error": "Missing 'question' in request body.",
                "success": False
            }), 400

        question = data["question"].strip()
        logger.info(f"API question received: {question}")

        result = qa_system.invoke({"query": question})

        return jsonify({
            "answer": result.get('result', 'No relevant answer found.'),
            "success": True,
            "document": document_metadata.get('name', current_document),
            "question": question
        })

    except Exception as e:
        logger.error(f"API error: {traceback.format_exc()}")
        return jsonify({
            "error": str(e),
            "success": False
        }), 500

@app.route('/status', methods=['GET'])
def status():
    """API endpoint to check system status."""
    return jsonify({
        "ready": qa_system is not None,
        "document": document_metadata.get('name', current_document),
        "metadata": document_metadata if current_document else None
    })

@app.route('/api-docs')
def api_docs():
    """API documentation page."""
    base_url = request.url_root.rstrip('/')
    return render_template_string(html_api_docs, base_url=base_url)

@app.route('/')
def home():
    return redirect('/ask-form')

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    try:
        print("🚀 Starting PDF QA System...")
        print("📡 Initializing ngrok tunnel...")

        # Connect to ngrok
        # If you have a free ngrok account, the domain parameter might not work
        # In that case, remove `domain=NGROK_DOMAIN` and ngrok will assign a random one.
        # e.g., public_url = ngrok.connect(5000, bind_tls=True)
        public_url = ngrok.connect(5000, bind_tls=True, domain=NGROK_DOMAIN)

        print("\n" + "="*60)
        print("🎉 PDF QA SYSTEM READY!")
        print("="*60)
        print(f"🌐 Public URL: {public_url.public_url}")
        print(f"🔒 Upload PDF: {public_url.public_url}/upload")
        print(f"❓ Ask Questions: {public_url.public_url}/ask-form")
        print(f"🔌 API Endpoint: {public_url.public_url}/ask")
        print(f"📊 System Status: {public_url.public_url}/status")
        print(f"📚 API Documentation: {public_url.public_url}/api-docs")
        print("="*60)
        print("💡 Password for upload:", PASSWORD)
        print("="*60)

        app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)

    except Exception as e:
        logger.error(f"Startup error: {str(e)}")
        print(f"❌ Error starting application: {str(e)}")
    except KeyboardInterrupt:
        print("\n🛑 Shutting down gracefully...")
        # Ensure ngrok tunnel is closed
        if 'public_url' in locals() and public_url:
            ngrok.disconnect(public_url.public_url)
        ngrok.kill()
conf.get_default().auth_token = NGROK_TOKEN

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Global variables
qa_system = None
current_document = None
document_metadata = {}

# --- NEW, SIMPLIFIED, AND PROFESSIONAL HTML TEMPLATES ---

html_upload_form = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Upload PDF - AI QA System</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary-color: #4CAF50; /* Green for success/primary action */
            --primary-dark: #388E3C;
            --accent-color: #2196F3; /* Blue for info/links */
            --text-color: #333;
            --secondary-text-color: #666;
            --border-color: #e0e0e0;
            --background-light: #f7f9fc;
            --background-dark: #e8f0f7;
            --card-background: #ffffff;
            --shadow-light: rgba(0, 0, 0, 0.08);
            --shadow-medium: rgba(0, 0, 0, 0.12);
        }
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, var(--background-light) 0%, var(--background-dark) 100%);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
            box-sizing: border-box;
            color: var(--text-color);
        }
        .container {
            background: var(--card-background);
            padding: 2.5rem 3rem;
            border-radius: 12px;
            box-shadow: 0 8px 25px var(--shadow-medium);
            max-width: 480px;
            width: 100%;
            text-align: center;
            transition: all 0.3s ease;
        }
        h2 {
            margin-bottom: 1.8rem;
            color: var(--text-color);
            font-size: 1.9rem;
            font-weight: 700;
        }
        .current-doc {
            background: #e8f5e8; /* Lighter green */
            padding: 1.2rem;
            border-radius: 8px;
            margin-bottom: 1.8rem;
            border-left: 5px solid var(--primary-color);
            text-align: left;
            font-size: 0.95rem;
            line-height: 1.5;
            color: var(--secondary-text-color);
        }
        .current-doc strong {
            color: var(--primary-dark);
            font-weight: 600;
        }
        label {
            display: block;
            text-align: left;
            margin-bottom: 0.6rem;
            font-weight: 600;
            color: var(--text-color);
            font-size: 0.95rem;
        }
        input[type="password"],
        input[type="file"] {
            width: 100%;
            padding: 0.9rem 1.2rem;
            margin-bottom: 1.5rem;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            font-size: 1rem;
            transition: all 0.3s ease;
            box-sizing: border-box;
            background-color: var(--background-light);
            color: var(--text-color);
        }
        input[type="password"]:focus,
        input[type="file"]:focus {
            outline: none;
            border-color: var(--accent-color);
            box-shadow: 0 0 0 3px rgba(33, 150, 243, 0.15); /* Softer blue shadow */
            background-color: var(--card-background);
        }
        input[type="file"] {
            padding: 0.7rem 1.2rem; /* Adjusted for file input */
        }
        input[type="submit"] {
            background: var(--primary-color);
            color: white;
            padding: 1rem 2.2rem;
            font-size: 1.1rem;
            font-weight: 700;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s ease;
            width: 100%;
            letter-spacing: 0.5px;
            box-shadow: 0 4px 15px rgba(76, 175, 80, 0.2); /* Green shadow */
        }
        input[type="submit"]:hover:not(:disabled) {
            background: var(--primary-dark);
            transform: translateY(-3px);
            box-shadow: 0 6px 20px rgba(76, 175, 80, 0.3);
        }
        input[type="submit"]:active {
            transform: translateY(0);
            box-shadow: 0 2px 10px rgba(76, 175, 80, 0.2);
        }
        input[type="submit"]:disabled {
            background: #ccc;
            cursor: not-allowed;
            box-shadow: none;
        }
        .message {
            margin-top: 1.8rem;
            padding: 1.2rem;
            border-radius: 8px;
            font-weight: 600;
            min-height: 1.2em;
            text-align: left;
            font-size: 0.95rem;
        }
        .message.success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .message.error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .nav-link {
            display: inline-block;
            margin-top: 1.5rem;
            color: var(--accent-color);
            text-decoration: none;
            font-weight: 600;
            transition: color 0.3s ease;
            font-size: 0.95rem;
        }
        .nav-link:hover {
            color: #1976D2; /* Darker blue */
        }
        .processing {
            display: none;
            margin-top: 1.5rem;
            color: var(--accent-color);
            font-weight: 600;
            font-size: 1rem;
        }
        .spinner {
            display: inline-block;
            width: 22px;
            height: 22px;
            border: 3px solid rgba(33, 150, 243, 0.2);
            border-top: 3px solid var(--accent-color);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 12px;
            vertical-align: middle;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .action-links {
            margin-top: 2rem;
            display: flex;
            flex-direction: column; /* Stack links vertically */
            gap: 0.8rem;
        }
        .action-links .nav-link {
            display: block; /* Make links take full width */
            margin-top: 0; /* Reset margin */
            padding: 0.8rem 1.5rem;
            background: #f0f4f8; /* Light background for secondary links */
            border-radius: 8px;
            text-decoration: none;
            color: var(--accent-color);
            font-weight: 600;
            transition: all 0.2s ease-in-out;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }
        .action-links .nav-link:hover {
            background: #e5eaf1;
            color: #1976D2;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
    </style>
    <script>
        function showProcessing() {
            document.getElementById('processing').style.display = 'block';
            document.querySelector('input[type="submit"]').disabled = true;
        }
    </script>
</head>
<body>
    <div class="container">
        <h2>Upload PDF & Start QA</h2>

        {% if current_doc %}
        <div class="current-doc">
            <strong>📄 Current Document:</strong> {{ current_doc.name }}<br>
            <strong>⏰ Uploaded:</strong> {{ current_doc.upload_time }}<br>
            <strong>📊 Chunks:</strong> {{ current_doc.chunks }}
        </div>
        {% endif %}

        <form method="post" enctype="multipart/form-data" onsubmit="showProcessing()">
            <label for="password">🔑 Security Password</label>
            <input type="password" id="password" name="password" required placeholder="Enter password to upload" />

            <label for="file">⬆️ Choose PDF File</label>
            <input type="file" id="file" name="file" accept="application/pdf" required />

            <input type="submit" value="Upload & Process PDF" />
        </form>

        <div id="processing" class="processing">
            <div class="spinner"></div>Processing document... This may take a moment.
        </div>

        {% if message %}
            <div class="message {{ message_type }}">{{ message }}</div>
        {% endif %}

        {% if current_doc %}
        <div class="action-links">
            <a href="/ask-form" class="nav-link">🚀 Go to Question Answering</a>
        </div>
        {% else %}
        <a href="/ask-form" class="nav-link">← Return to Question Page</a>
        {% endif %}
    </div>
</body>
</html>
"""

html_question_form = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Ask Your PDF - AI QA System</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary-color: #4CAF50; /* Green for success/primary action */
            --primary-dark: #388E3C;
            --accent-color: #2196F3; /* Blue for info/links */
            --text-color: #333;
            --secondary-text-color: #666;
            --border-color: #e0e0e0;
            --background-light: #f7f9fc;
            --background-dark: #e8f0f7;
            --card-background: #ffffff;
            --shadow-light: rgba(0, 0, 0, 0.08);
            --shadow-medium: rgba(0, 0, 0, 0.12);
        }
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, var(--background-light) 0%, var(--background-dark) 100%);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
            box-sizing: border-box;
            color: var(--text-color);
        }
        .container {
            background: var(--card-background);
            padding: 2.5rem 3rem;
            border-radius: 12px;
            box-shadow: 0 8px 25px var(--shadow-medium);
            max-width: 700px;
            width: 100%;
            text-align: center;
            transition: all 0.3s ease;
        }
        h2 {
            margin-bottom: 1.8rem;
            color: var(--text-color);
            font-size: 1.9rem;
            font-weight: 700;
        }
        .status {
            padding: 1.2rem;
            border-radius: 8px;
            margin-bottom: 1.8rem;
            font-weight: 600;
            font-size: 0.95rem;
            text-align: left;
            line-height: 1.5;
        }
        .status.ready {
            background: #e8f5e8;
            color: #2e7d32;
            border-left: 5px solid var(--primary-color);
        }
        .status.not-ready {
            background: #fff3cd;
            color: #856404;
            border-left: 5px solid #ffc107;
        }
        form {
            display: flex;
            gap: 1rem;
            margin-bottom: 2rem;
            align-items: center;
            flex-wrap: wrap; /* Allow wrapping on smaller screens */
        }
        form input[type="text"] {
            flex: 1;
            padding: 0.9rem 1.2rem;
            font-size: 1rem;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            transition: all 0.3s ease;
            background-color: var(--background-light);
            color: var(--text-color);
        }
        form input[type="text"]:focus {
            outline: none;
            border-color: var(--accent-color);
            box-shadow: 0 0 0 3px rgba(33, 150, 243, 0.15);
            background-color: var(--card-background);
        }
        form input[type="submit"] {
            background: var(--accent-color);
            color: white;
            padding: 0.9rem 2rem;
            font-size: 1.05rem;
            font-weight: 700;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(33, 150, 243, 0.2); /* Blue shadow */
            flex-shrink: 0; /* Prevent button from shrinking */
        }
        form input[type="submit"]:hover:not(:disabled) {
            background: #1976D2; /* Darker blue */
            transform: translateY(-3px);
            box-shadow: 0 6px 20px rgba(33, 150, 243, 0.3);
        }
        form input[type="submit"]:active {
            transform: translateY(0);
            box-shadow: 0 2px 10px rgba(33, 150, 243, 0.2);
        }
        form input[type="submit"]:disabled {
            background: #ccc;
            cursor: not-allowed;
            box-shadow: none;
        }
        .answer-container {
            background: #f8f9ff;
            border-radius: 10px;
            padding: 2rem;
            margin-top: 1.5rem;
            border-left: 5px solid var(--accent-color);
            text-align: left;
            box-shadow: 0 4px 15px var(--shadow-light);
        }
        .question {
            font-weight: 700;
            color: var(--text-color);
            margin-bottom: 1rem;
            font-size: 1.1rem;
            display: flex;
            align-items: center;
            gap: 0.8rem;
        }
        .question::before {
            content: '❓';
            font-size: 1.2em;
        }
        .answer {
            color: var(--secondary-text-color);
            line-height: 1.7;
            white-space: pre-wrap;
            font-size: 1rem;
            display: flex;
            align-items: flex-start;
            gap: 0.8rem;
        }
        .answer::before {
            content: '🤖';
            font-size: 1.2em;
            flex-shrink: 0;
        }
        .nav-links {
            margin-top: 2.5rem;
            display: flex;
            justify-content: center;
            gap: 1.5rem; /* Reduced gap */
            flex-wrap: wrap;
        }
        .nav-link {
            color: var(--accent-color);
            text-decoration: none;
            font-weight: 600;
            transition: all 0.3s ease;
            font-size: 0.95rem;
            padding: 0.8rem 1.5rem;
            background: #f0f4f8; /* Light background for secondary links */
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }
        .nav-link:hover {
            color: #1976D2; /* Darker blue */
            background: #e5eaf1;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        .loading {
            display: none;
            color: var(--accent-color);
            font-weight: 600;
            margin-top: 1.5rem;
            font-size: 1rem;
        }
        .spinner {
            display: inline-block;
            width: 22px;
            height: 22px;
            border: 3px solid rgba(33, 150, 243, 0.2);
            border-top: 3px solid var(--accent-color);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 12px;
            vertical-align: middle;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        @media (max-width: 600px) {
            form {
                flex-direction: column;
            }
            form input[type="submit"] {
                width: 100%;
            }
            .container {
                padding: 1.8rem 1.5rem;
            }
            h2 {
                font-size: 1.7rem;
            }
        }
    </style>
    <script>
        function showLoading() {
            document.getElementById('loading').style.display = 'block';
            document.getElementById('submit-btn').disabled = true;
        }
    </script>
</head>
<body>
    <div class="container">
        <h2>Ask Your Document</h2>

        {% if has_document %}
        <div class="status ready">
            ✅ Document Ready: <strong>{{ doc_info.name }}</strong> ({{ doc_info.chunks }} chunks loaded)
        </div>
        {% else %}
        <div class="status not-ready">
            ⚠️ No Document Loaded: Please <a href="/upload" style="color: inherit; text-decoration: underline; font-weight: 700;">upload a PDF</a> first to enable questions.
        </div>
        {% endif %}

        <form method="post" onsubmit="showLoading()">
            <input
                type="text"
                name="question"
                placeholder="Type your question here..."
                required
                autocomplete="off"
                {% if not has_document %}disabled{% endif %}
            />
            <input
                type="submit"
                id="submit-btn"
                value="Ask AI"
                {% if not has_document %}disabled{% endif %}
            />
        </form>

        <div id="loading" class="loading">
            <div class="spinner"></div>AI is thinking... Please wait.
        </div>

        {% if answer %}
        <div class="answer-container">
            <div class="question">Question: {{ question }}</div>
            <div class="answer">Answer: {{ answer }}</div>
        </div>
        {% endif %}

        <div class="nav-links">
            <a href="/upload" class="nav-link">⬆️ Upload New PDF</a>
            <a href="/status" class="nav-link">📊 System Status</a>
            <a href="/api-docs" class="nav-link">📚 API Documentation</a>
        </div>
    </div>
</body>
</html>
"""

html_api_docs = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>API Documentation - PDF QA System</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Roboto+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary-color: #4CAF50; /* Green */
            --accent-color: #2196F3; /* Blue */
            --text-color: #333;
            --secondary-text-color: #666;
            --background-light: #f7f9fc;
            --background-dark: #e8f0f7;
            --card-background: #ffffff;
            --code-bg: #2d3748;
            --code-text: #e2e8f0;
            --shadow-light: rgba(0, 0, 0, 0.08);
            --shadow-medium: rgba(0, 0, 0, 0.12);
        }
        body {
            font-family: 'Inter', sans-serif;
            background: var(--background-light);
            margin: 0;
            padding: 2rem;
            line-height: 1.6;
            color: var(--text-color);
        }
        .container {
            max-width: 960px;
            margin: 0 auto;
            background: var(--card-background);
            padding: 3rem;
            border-radius: 12px;
            box-shadow: 0 8px 30px var(--shadow-medium);
        }
        h1, h2, h3 {
            color: var(--text-color);
            font-weight: 700;
        }
        h1 {
            text-align: center;
            margin-bottom: 2.5rem;
            font-size: 2.2rem;
        }
        h2 {
            margin-top: 2.5rem;
            margin-bottom: 1.5rem;
            font-size: 1.8rem;
        }
        h3 {
            font-size: 1.4rem;
            margin-bottom: 1rem;
        }
        p {
            margin-bottom: 1rem;
            color: var(--secondary-text-color);
        }
        strong {
            color: var(--text-color);
        }
        .endpoint {
            background: #f8f9ff; /* Light blueish background */
            padding: 2rem;
            margin: 2.5rem 0;
            border-radius: 10px;
            border-left: 5px solid var(--accent-color);
            box-shadow: 0 3px 12px var(--shadow-light);
        }
        .endpoint h3 {
            display: flex;
            align-items: center;
            margin-bottom: 1.5rem;
            gap: 1rem;
        }
        .method {
            padding: 0.4rem 1rem;
            border-radius: 6px;
            font-size: 0.9rem;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .method.get {
            background: #28a745; /* Green */
            color: white;
        }
        .method.post {
            background: #007bff; /* Blue */
            color: white;
        }
        pre {
            background: var(--code-bg);
            color: var(--code-text);
            padding: 1.5rem;
            border-radius: 8px;
            overflow-x: auto;
            font-size: 0.95rem;
            line-height: 1.5;
            font-family: 'Roboto Mono', monospace;
            margin-top: 1rem;
            box-shadow: inset 0 2px 5px rgba(0,0,0,0.2);
        }
        code {
            background: #e9ecef;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-family: 'Roboto Mono', monospace;
            color: #c7254e; /* For inline code */
            font-size: 0.9em;
        }
        .nav-link {
            display: inline-block;
            margin-top: 2.5rem;
            color: var(--accent-color);
            text-decoration: none;
            font-weight: 600;
            transition: all 0.3s ease;
            font-size: 1rem;
            padding: 0.8rem 1.5rem;
            background: #f0f4f8;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }
        .nav-link:hover {
            color: #1976D2;
            background: #e5eaf1;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        @media (max-width: 768px) {
            .container {
                padding: 2rem 1.5rem;
            }
            h1 {
                font-size: 2rem;
            }
            .endpoint {
                padding: 1.5rem;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📚 PDF QA System API Documentation</h1>

        <p>This document outlines the available API endpoints for interacting with the PDF Question Answering System. The system allows you to upload a PDF document and then query it using natural language.</p>

        <h2>Endpoints</h2>

        <div class="endpoint">
            <h3><span class="method post">POST</span> <code>/ask</code></h3>
            <p>Submit a question about the currently loaded PDF document and receive an AI-generated answer.</p>

            <strong>Request Body:</strong> (<code>application/json</code>)
            <pre>{
    "question": "What is the main topic of this document?"
}</pre>
            <strong>Response:</strong> (<code>application/json</code>)
            <pre>{
    "answer": "The document primarily discusses...",
    "success": true,
    "document": "your_document.pdf",
    "question": "What is the main topic..."
}</pre>
            <p><strong>Error Response (No Document Loaded):</strong></p>
            <pre>{
    "error": "QA system not ready. Please upload a PDF first.",
    "success": false
}</pre>
        </div>

        <div class="endpoint">
            <h3><span class="method get">GET</span> <code>/status</code></h3>
            <p>Check the current status of the AI QA system, including whether a PDF is loaded and its metadata.</p>

            <strong>Response:</strong> (<code>application/json</code>)
            <pre>{
    "ready": true,
    "document": "document.pdf",
    "metadata": {
        "name": "document.pdf",
        "upload_time": "2025-06-18 15:30:45",
        "chunks": 42,
        "file_path": "/content/uploads/1718712645_document.pdf"
    }
}</pre>
            <p><strong>Response (No Document Loaded):</strong></p>
            <pre>{
    "ready": false,
    "document": null,
    "metadata": null
}</pre>
        </div>

        <h2>Code Examples</h2>

        <h3>🐍 Python Example</h3>
        <pre><code>import requests
import json

base_url = "{{ base_url }}" # This will be your ngrok URL

# --- 1. Check System Status ---
print("Checking system status...")
try:
    response = requests.get(f"{{base_url}}/status")
    response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
    status_data = response.json()
    print("Status Response:", json.dumps(status_data, indent=2))
    if not status_data.get('ready'):
        print("System is not ready. Please upload a PDF via the web interface first.")
except requests.exceptions.RequestException as e:
    print(f"Error checking status: {e}")

# --- 2. Ask a Question (if ready) ---
if status_data.get('ready', False):
    print("\nAsking a question...")
    question = "What are the key findings discussed in the report?"
    try:
        response = requests.post(
            f"{{base_url}}/ask",
            headers={'Content-Type': 'application/json'},
            json={"question": question}
        )
        response.raise_for_status()
        answer_data = response.json()
        print(f"Question: {question}")
        print("Answer Response:", json.dumps(answer_data, indent=2))
    except requests.exceptions.RequestException as e:
        print(f"Error asking question: {e}")
else:
    print("\nSkipping question: Document not loaded.")
</code></pre>

        <h3>🌐 JavaScript (Fetch API) Example</h3>
        <pre><code>const baseUrl = "{{ base_url }}"; // This will be your ngrok URL

// --- 1. Check System Status ---
console.log('Checking system status...');
fetch(`${baseUrl}/status`)
  .then(response => {
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  })
  .then(data => {
    console.log('Status:', data);
    if (!data.ready) {
      console.log('System is not ready. Please upload a PDF via the web interface first.');
    } else {
      // --- 2. Ask a Question (if ready) ---
      console.log('\nAsking a question...');
      const question = "What are the key features of the new product?";
      fetch(`${baseUrl}/ask`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ question: question })
      })
      .then(response => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
      })
      .then(data => {
        console.log(`Question: ${question}`);
        console.log('Answer:', data);
      })
      .catch(error => {
        console.error('Error asking question:', error);
      });
    }
  })
  .catch(error => {
    console.error('Error checking status:', error);
  });
</code></pre>

        <a href="/ask-form" class="nav-link">← Back to Main Page</a>
    </div>
</body>
</html>
"""

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_document(file_path):
    """Load and split PDF document into chunks with enhanced processing."""
    try:
        loader = PyPDFLoader(file_path)
        docs = loader.load()

        # Enhanced text splitter for better context
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
        )

        chunks = splitter.split_documents(docs)
        logger.info(f"Document processed: {len(chunks)} chunks created")
        return chunks
    except Exception as e:
        logger.error(f"Error loading document: {str(e)}")
        raise

def embed_documents(docs):
    """Create FAISS vector store from document chunks."""
    try:
        embed_model = HuggingFaceEmbeddings(
            model_name='sentence-transformers/all-MiniLM-L6-v2',
            model_kwargs={'device': 'cpu'}
        )
        vector_store = FAISS.from_documents(docs, embed_model)

        # Save vector store for persistence
        vector_store.save_local(VECTOR_STORE_PATH)
        logger.info("Vector embeddings created and saved")
        return vector_store
    except Exception as e:
        logger.error(f"Error creating embeddings: {str(e)}")
        raise

def build_qa_system(faiss_index):
    """Build QA system with enhanced retrieval."""
    try:
        llm = ChatGroq(
            api_key=GROQ_API_KEY,
            model_name="llama3-8b-8192",
            temperature=0.1
        )

        retriever = faiss_index.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 4, "fetch_k": 8}
        )

        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=retriever,
            return_source_documents=True
        )

        logger.info("QA system built successfully")
        return qa_chain
    except Exception as e:
        logger.error(f"Error building QA system: {str(e)}")
        raise

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    global qa_system, current_document, document_metadata
    message = None
    message_type = "info"

    if request.method == 'POST':
        try:
            if request.form.get("password") != PASSWORD:
                message = "❌ Incorrect password. Access denied."
                message_type = "error"
            elif 'file' not in request.files:
                message = "❌ No file selected. Please choose a PDF file."
                message_type = "error"
            else:
                file = request.files['file']
                if file and allowed_file(file.filename):
                    # Use timestamp to avoid collisions (your smart approach!)
                    filename = secure_filename(file.filename)
                    filename = f"{int(time.time())}_{filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)

                    logger.info(f"Processing uploaded file: {filename}")

                    # Process document with enhanced pipeline
                    docs = load_document(file_path)
                    faiss_index = embed_documents(docs)
                    qa_system = build_qa_system(faiss_index)

                    # Update metadata
                    current_document = filename
                    document_metadata = {
                        'name': file.filename,  # Original name for display
                        'upload_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'chunks': len(docs),
                        'file_path': file_path
                    }

                    message = f"✅ Successfully processed '{file.filename}' into {len(docs)} searchable chunks!"
                    message_type = "success"
                    logger.info(f"Document processed successfully: {len(docs)} chunks")
                else:
                    message = "❌ Invalid file type. Please upload a PDF file only."
                    message_type = "error"
        except Exception as e:
            message = f"❌ Error processing file: {str(e)}"
            message_type = "error"
            logger.error(f"Upload error: {traceback.format_exc()}")

    return render_template_string(
        html_upload_form,
        message=message,
        message_type=message_type,
        current_doc=document_metadata if current_document else None
    )

@app.route('/ask-form', methods=['GET', 'POST'])
def ask_form():
    answer = None
    question = ""

    if request.method == 'POST':
        question = request.form.get("question", "").strip()
        if question and qa_system:
            try:
                logger.info(f"Processing question: {question}")
                result = qa_system.invoke({"query": question})
                answer = result.get('result', 'No relevant answer found in the document.')
            except Exception as e:
                answer = f"Error processing your question: {str(e)}"
                logger.error(f"Question processing error: {traceback.format_exc()}")
        elif not qa_system:
            answer = "Please upload a PDF document first to start asking questions."

    return render_template_string(
        html_question_form,
        answer=answer,
        question=question,
        has_document=qa_system is not None,
        doc_info=document_metadata if current_document else None
    )

@app.route('/ask', methods=['POST'])
def ask_api():
    """Enhanced API endpoint for asking questions."""
    if not qa_system:
        return jsonify({
            "error": "QA system not ready. Please upload a PDF first.",
            "success": False
        }), 503

    try:
        data = request.get_json()
        if not data or not data.get("question"):
            return jsonify({
                "error": "Missing 'question' in request body.",
                "success": False
            }), 400

        question = data["question"].strip()
        logger.info(f"API question received: {question}")

        result = qa_system.invoke({"query": question})

        return jsonify({
            "answer": result.get('result', 'No relevant answer found.'),
            "success": True,
            "document": document_metadata.get('name', current_document),
            "question": question
        })

    except Exception as e:
        logger.error(f"API error: {traceback.format_exc()}")
        return jsonify({
            "error": str(e),
            "success": False
        }), 500

@app.route('/status', methods=['GET'])
def status():
    """API endpoint to check system status."""
    return jsonify({
        "ready": qa_system is not None,
        "document": document_metadata.get('name', current_document),
        "metadata": document_metadata if current_document else None
    })

@app.route('/api-docs')
def api_docs():
    """API documentation page."""
    base_url = request.url_root.rstrip('/')
    return render_template_string(html_api_docs, base_url=base_url)

@app.route('/')
def home():
    return redirect('/ask-form')

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    try:
        print("🚀 Starting PDF QA System...")
        print("📡 Initializing ngrok tunnel...")

        # Connect to ngrok
        # If you have a free ngrok account, the domain parameter might not work
        # In that case, remove `domain=NGROK_DOMAIN` and ngrok will assign a random one.
        # e.g., public_url = ngrok.connect(5000, bind_tls=True)
        public_url = ngrok.connect(5000, bind_tls=True, domain=NGROK_DOMAIN)

        print("\n" + "="*60)
        print("🎉 PDF QA SYSTEM READY!")
        print("="*60)
        print(f"🌐 Public URL: {public_url.public_url}")
        print(f"🔒 Upload PDF: {public_url.public_url}/upload")
        print(f"❓ Ask Questions: {public_url.public_url}/ask-form")
        print(f"🔌 API Endpoint: {public_url.public_url}/ask")
        print(f"📊 System Status: {public_url.public_url}/status")
        print(f"📚 API Documentation: {public_url.public_url}/api-docs")
        print("="*60)
        print("💡 Password for upload:", PASSWORD)
        print("="*60)

        app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)

    except Exception as e:
        logger.error(f"Startup error: {str(e)}")
        print(f"❌ Error starting application: {str(e)}")
    except KeyboardInterrupt:
        print("\n🛑 Shutting down gracefully...")
        # Ensure ngrok tunnel is closed
        if 'public_url' in locals() and public_url:
            ngrok.disconnect(public_url.public_url)
        ngrok.kill()