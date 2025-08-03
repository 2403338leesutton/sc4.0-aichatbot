# backend/app.py
from flask import Flask, jsonify # Import jsonify here for global error handler
from flask_cors import CORS
import os
from dotenv import load_dotenv
import json
import uuid # Might be needed for init if loading fails

# Import the updated RAGSystem
from utils.pdf_processor import extract_text_from_pdf, split_text_into_chunks # Might still be used in init or services
from utils.rag_system import RAGSystem

load_dotenv()  # Load environment variables from .env file

app = Flask(__name__)
CORS(app)

# --- Configuration ---
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = ALLOWED_EXTENSIONS # Add to config for access in routes/services

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
# Ensure ChromaDB directory exists (handled by Chroma, but good to know)
os.makedirs("./chroma_db", exist_ok=True)

# --- Persistence for Document List ---
DOCUMENTS_FILE = 'documents.json'

def load_documents():
    """Load documents list from a JSON file."""
    global documents
    try:
        with open(DOCUMENTS_FILE, 'r') as f:
            documents_data = json.load(f)
            documents.clear()
            documents.extend(documents_data)
        app.logger.info(f"Loaded {len(documents)} documents from {DOCUMENTS_FILE}")
    except FileNotFoundError:
        app.logger.info(f"{DOCUMENTS_FILE} not found. Starting with an empty documents list.")
        documents.clear()
    except json.JSONDecodeError as e:
        app.logger.error(f"Error decoding {DOCUMENTS_FILE}: {e}. Starting with an empty documents list.")
        documents.clear()
    except Exception as e:
        app.logger.error(f"Unexpected error loading documents: {e}. Starting with an empty documents list.")
        documents.clear()

def save_documents():
    """Save the current documents list to a JSON file."""
    try:
        sorted_docs = sorted(documents, key=lambda x: x.get('uploaded_at', ''), reverse=True)
        with open(DOCUMENTS_FILE, 'w') as f:
            json.dump(sorted_docs, f, indent=4)
        app.logger.info(f"Saved {len(documents)} documents to {DOCUMENTS_FILE}")
    except Exception as e:
        app.logger.error(f"Error saving documents to {DOCUMENTS_FILE}: {e}")

# --- Persistence for Chat Sessions ---
CHAT_SESSIONS_FILE = 'chat_sessions.json'

def load_chat_sessions():
    """Load chat sessions from a JSON file."""
    global chat_sessions
    try:
        with open(CHAT_SESSIONS_FILE, 'r') as f:
            chat_sessions_data = json.load(f)
            chat_sessions.clear()
            chat_sessions.update(chat_sessions_data)
        app.logger.info(f"Loaded chat sessions from {CHAT_SESSIONS_FILE}")
    except FileNotFoundError:
        app.logger.info(f"{CHAT_SESSIONS_FILE} not found. Starting with no chat sessions.")
        chat_sessions.clear()
    except json.JSONDecodeError as e:
        app.logger.error(f"Error decoding {CHAT_SESSIONS_FILE}: {e}. Starting with no chat sessions.")
        chat_sessions.clear()
    except Exception as e:
        app.logger.error(f"Unexpected error loading chat sessions: {e}. Starting with no chat sessions.")
        chat_sessions.clear()

def save_chat_sessions():
    """Save the current chat sessions to a JSON file."""
    try:
        with open(CHAT_SESSIONS_FILE, 'w') as f:
            json.dump(chat_sessions, f, indent=4, default=str)
        app.logger.info(f"Saved {len(chat_sessions)} chat sessions to {CHAT_SESSIONS_FILE}")
    except Exception as e:
        app.logger.error(f"Error saving chat sessions to {CHAT_SESSIONS_FILE}: {e}")

# --- Model Management ---
AVAILABLE_MODELS = ["gemini-1.5-flash", "gemini-1.5-pro"]
CURRENT_MODEL_NAME = "gemini-1.5-flash"

# --- Helper to update model name ---
def update_current_model_name(new_name):
    """Updates the global CURRENT_MODEL_NAME variable."""
    global CURRENT_MODEL_NAME
    CURRENT_MODEL_NAME = new_name
    app.logger.info(f"Global CURRENT_MODEL_NAME updated to: {new_name}")

# --- Initialize RAG System ---
rag_system = RAGSystem(model_name=CURRENT_MODEL_NAME, chroma_db_path="./chroma_db")

# --- In-memory storage ---
documents = []
chat_sessions = {}

# --- Load persisted data on startup ---
with app.app_context():
    load_documents()
    load_chat_sessions()

# --- Global Error Handler ---
@app.errorhandler(Exception)
def handle_exception(e):
    # Pass through HTTP errors
    if hasattr(e, 'code'):
        return e, e.code
    # Now you're handling non-HTTP exceptions only
    app.logger.error(f"Unhandled Exception: {e}", exc_info=True)
    return jsonify({"error": "An unexpected error occurred."}), 500

# --- Register Routes AFTER global variables are defined ---
# Pass the necessary dependencies to the route initializer
# Import the route initializer function
from routes.main_routes import init_routes
# Call the initializer, passing the app instance and necessary global variables/objects
init_routes(app)

if __name__ == '__main__':
    print("Starting SC4.0 AI Chatbot Backend with ChromaDB...")
    print(f"ChromaDB Path: ./chroma_db")
    print(f"Uploads Path: {UPLOAD_FOLDER}")
    print(f"Documents List Persistence File: {DOCUMENTS_FILE}")
    print(f"Chat Sessions Persistence File: {CHAT_SESSIONS_FILE}")
    print(f"Available Models: {AVAILABLE_MODELS}")
    print(f"Initial Model: {CURRENT_MODEL_NAME}")
    app.run(debug=True, port=5000)
