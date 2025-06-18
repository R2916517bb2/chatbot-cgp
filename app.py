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
GROQ_API_KEY = "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"  # Get from console.groq.com
NGROK_TOKEN = "2yenKU83I2XYvjBDKhkkMSwua3p_8gFQkz3EsUPRSMYpo
