# backend/app.py

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime, timezone # Use timezone-aware datetime
import json # Added for JSON persistence

# Import the updated RAGSystem
from utils.pdf_processor import extract_text_from_pdf, split_text_into_chunks
from utils.rag_system import RAGSystem # This now points to the ChromaDB version

load_dotenv()  # Load environment variables from .env file

app = Flask(__name__)
CORS(app)

# --- Configuration ---
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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
            # Potentially validate data structure here
            documents.clear() # Clear existing in-memory list
            documents.extend(documents_data) # Populate with loaded data
        app.logger.info(f"Loaded {len(documents)} documents from {DOCUMENTS_FILE}")
    except FileNotFoundError:
        app.logger.info(f"{DOCUMENTS_FILE} not found. Starting with an empty documents list.")
        documents.clear() # Ensure it's empty if file not found
    except json.JSONDecodeError as e:
        app.logger.error(f"Error decoding {DOCUMENTS_FILE}: {e}. Starting with an empty documents list.")
        documents.clear()
    except Exception as e:
        app.logger.error(f"Unexpected error loading documents: {e}. Starting with an empty documents list.")
        documents.clear()

def save_documents():
    """Save the current documents list to a JSON file."""
    try:
        # Sort documents by upload time for consistency (optional)
        sorted_docs = sorted(documents, key=lambda x: x.get('uploaded_at', ''), reverse=True)
        with open(DOCUMENTS_FILE, 'w') as f:
            json.dump(sorted_docs, f, indent=4) # Use indent for readability
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
            # Potentially validate data structure here
            chat_sessions.clear()
            chat_sessions.update(chat_sessions_data) # Populate with loaded data
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
            # default=str handles datetime serialization if needed, though isoformat strings should work
            json.dump(chat_sessions, f, indent=4, default=str)
        app.logger.info(f"Saved {len(chat_sessions)} chat sessions to {CHAT_SESSIONS_FILE}")
    except Exception as e:
        app.logger.error(f"Error saving chat sessions to {CHAT_SESSIONS_FILE}: {e}")

# --- Model Management ---
# Define available models (you can expand this list)
AVAILABLE_MODELS = ["gemini-1.5-flash", "gemini-1.5-pro"]
# Store the currently configured model name in a global variable
# This should initially match the model_name passed to RAGSystem()
CURRENT_MODEL_NAME = "gemini-1.5-flash" # Default, should match RAGSystem init

# --- Initialize RAG System ---
# Pass the path where you want ChromaDB data persisted
# Make sure this directory exists or Chroma can create it
# You can make the model name configurable later if desired
# IMPORTANT: Use the global variable for the initial model name
rag_system = RAGSystem(model_name=CURRENT_MODEL_NAME, chroma_db_path="./chroma_db")

# --- In-memory storage for high-level document info ---
# This is kept for quick responses to /api/documents if needed.
# ChromaDB handles the persistent storage of chunks and metadata.
documents = []

# --- Global Storage for Chat Sessions (In-Memory, persisted to disk) ---
# Structure: { session_id: { "messages": [...], "created_at": "ISO_TIMESTAMP", "title": "..." } }
chat_sessions = {}

# --- Load persisted data on startup ---
# Use app context for logging
with app.app_context():
    load_documents()
    load_chat_sessions()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def home():
    return jsonify({"message": "SC4.0 AI Chatbot API Running with ChromaDB"})

@app.route('/api/upload', methods=['POST'])
def upload_pdf():
    try:
        # --- File Handling ---
        if 'pdf' not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files['pdf']

        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400

        if not allowed_file(file.filename):
            return jsonify({"error": "Only PDF files are allowed"}), 400

        # --- Save File ---
        original_filename = secure_filename(file.filename)
        # Prepend a UUID to avoid filename conflicts
        unique_filename = f"{uuid.uuid4()}_{original_filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path) # <-- Save the file first

        # --- Process PDF ---
        app.logger.info(f"Processing PDF: {original_filename}")
        extracted_text = extract_text_from_pdf(file_path)
        # Consider refining chunking strategy (e.g., overlapping)
        chunks = split_text_into_chunks(extracted_text, chunk_size=1000)

        # --- Store Document Info (In-Memory List) ---
        doc_id = str(uuid.uuid4())
        doc_info = {
            'id': doc_id,
            'name': original_filename,  # Use original name for user display
            'uploaded_at': datetime.now(timezone.utc).isoformat(), # Updated to use timezone.utc
            'chunks_count': len(chunks),
            # --- Store the full path for later deletion ---
            'file_path': file_path,
            # --- End Store Path ---
            # Note: Storing full 'content' here might be memory-intensive for large PDFs.
            # Consider if it's strictly necessary for the /api/documents endpoint.
            # 'content': extracted_text,
        }
        documents.append(doc_info)
        app.logger.info(f"Stored document info for {original_filename} (ID: {doc_id})")

        # --- Add Chunks to ChromaDB (via RAG System) ---
        chunk_info = []
        for i, chunk in enumerate(chunks):
            chunk_data = {
                'id': f"{doc_id}-chunk-{i}", # Unique ID for the chunk within ChromaDB
                'doc_id': doc_id,             # Link back to the document
                'content': chunk.strip(),     # The text content of the chunk (strip whitespace)
                'source': original_filename,           # Source document name (original)
                'chunk_index': i              # Index of the chunk within the document
            }
            chunk_info.append(chunk_data)

        rag_system.add_document_chunks(chunk_info)
        app.logger.info(f"Added {len(chunk_info)} chunks to ChromaDB for document {original_filename}")

        # --- Save document list persistently ---
        save_documents() # <-- Added this line

        return jsonify({
            "message": "PDF uploaded and processed successfully",
            "document_id": doc_id,
            "chunks_count": len(chunks),
            "filename": original_filename # Return original name
        }), 201 # 201 Created is more appropriate for successful creation/upload

    except Exception as e:
        app.logger.error(f"Error processing PDF upload: {e}")
        return jsonify({"error": f"Failed to process PDF: {str(e)}"}), 500

@app.route('/api/documents', methods=['GET'])
def get_documents():
    """
    Retrieves the list of uploaded documents.
    Currently uses the in-memory 'documents' list.
    Could be enhanced to fetch from ChromaDB metadata for guaranteed consistency.
    """
    try:
        # Option 1: Return the in-memory list (might miss docs if backend restarted and list not repopulated)
        # Make sure to sort or format as needed
        sorted_docs = sorted(documents, key=lambda x: x.get('uploaded_at', ''), reverse=True)
        return jsonify(sorted_docs)

        # Option 2 (Alternative): Fetch unique document list directly from ChromaDB
        # This would be more robust if 'documents' list isn't perfectly synchronized.
        # Requires the RAGSystem.list_documents() method to be implemented correctly.
        # Uncomment the lines below and comment the lines above if preferred.
        # doc_list = rag_system.list_documents()
        # sorted_docs = sorted(doc_list, key=lambda x: x.get('uploaded_at', x.get('id', '')), reverse=True)
        # return jsonify(sorted_docs)

    except Exception as e:
        app.logger.error(f"Error fetching documents: {e}")
        return jsonify({"error": "Failed to fetch documents"}), 500

# --- Updated Delete Document Endpoint ---
@app.route('/api/documents/<doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    """Delete a specific document and its chunks."""
    global documents # Access the in-memory list
    try:
        # 1. Find the document in the in-memory list
        document_to_delete = next((doc for doc in documents if doc['id'] == doc_id), None)
        if not document_to_delete:
            return jsonify({"error": "Document not found"}), 404

        doc_name_for_logs = document_to_delete.get('name', 'Unknown Document')

        # 2. Delete associated chunks from ChromaDB
        # The RAGSystem needs a method for this. Add it to utils/rag_system.py
        try:
            rag_system.delete_document_chunks(doc_id)
            app.logger.info(f"Deleted chunks for document ID {doc_id} from ChromaDB")
        except Exception as e:
            app.logger.error(f"Error deleting chunks for document {doc_id} from ChromaDB: {e}")
            # Depending on requirements, you might want to return an error here
            # or try to continue deleting other references.
            # For now, let's log and continue to remove from documents list.
            pass # Or handle error as appropriate

        # 3. Remove the document from the in-memory list
        documents = [doc for doc in documents if doc['id'] != doc_id]

        # 4. Delete the original PDF file from the uploads folder
        # Use the stored file path
        file_path_to_delete = document_to_delete.get('file_path')
        if file_path_to_delete and os.path.exists(file_path_to_delete):
            try:
                os.remove(file_path_to_delete)
                app.logger.info(f"Deleted PDF file: {file_path_to_delete}")
            except OSError as e:
                error_msg = f"Error deleting PDF file {file_path_to_delete}: {e}"
                app.logger.error(error_msg)
                # Optionally, return an error or just log it depending on requirements
                # return jsonify({"error": error_msg}), 500
        elif file_path_to_delete:
             app.logger.warning(f"PDF file path {file_path_to_delete} does not exist, skipping file deletion.")
        else:
             app.logger.warning(f"No file path found for document {doc_id} ({doc_name_for_logs}), skipping file deletion.")


        # 5. Persist the change to documents.json
        save_documents()

        app.logger.info(f"Deleted document {doc_id} ({doc_name_for_logs})")
        return jsonify({"message": "Document deleted successfully"}), 200

    except Exception as e:
        app.logger.error(f"Error deleting document {doc_id}: {e}")
        return jsonify({"error": f"Failed to delete document: {str(e)}"}), 500
# --- End Updated Delete Document Endpoint ---


# --- New Chat Session Endpoints ---

@app.route('/api/sessions', methods=['POST'])
def create_session():
    """Create a new chat session."""
    try:
        session_id = str(uuid.uuid4())
        new_session = {
            "messages": [],
            "created_at": datetime.now(timezone.utc).isoformat(), # Use timezone.utc
            "title": "New Chat" # Default title, can be updated based on first message
        }
        chat_sessions[session_id] = new_session
        save_chat_sessions() # Persist immediately
        app.logger.info(f"Created new chat session: {session_id}")
        return jsonify({"session_id": session_id, "session": new_session}), 201
    except Exception as e:
        app.logger.error(f"Error creating session: {e}")
        return jsonify({"error": "Failed to create session"}), 500

@app.route('/api/sessions', methods=['GET'])
def list_sessions():
    """List all chat sessions (metadata only for efficiency)."""
    try:
        # Return session metadata, not full message history
        session_list = []
        for sid, data in chat_sessions.items():
            session_list.append({
                "session_id": sid,
                "title": data.get("title", "Untitled Chat"),
                "created_at": data.get("created_at"),
                "message_count": len(data.get("messages", []))
            })
        # Sort by creation time, newest first
        session_list.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return jsonify(session_list)
    except Exception as e:
        app.logger.error(f"Error listing sessions: {e}")
        return jsonify({"error": "Failed to list sessions"}), 500

@app.route('/api/sessions/<session_id>', methods=['GET'])
def get_session(session_id):
    """Get the full history of a specific chat session."""
    try:
        session = chat_sessions.get(session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404
        return jsonify({"session_id": session_id, "session": session})
    except Exception as e:
        app.logger.error(f"Error fetching session {session_id}: {e}")
        return jsonify({"error": f"Failed to fetch session {session_id}"}), 500

# --- New Endpoint: Rename a Chat Session ---
@app.route('/api/sessions/<session_id>', methods=['PUT'])
def rename_session(session_id):
    """Rename a specific chat session."""
    try:
        session = chat_sessions.get(session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404

        data = request.get_json()
        new_title = data.get('title')
        if not new_title or not isinstance(new_title, str):
            return jsonify({"error": "A valid 'title' (string) is required in the request body"}), 400

        # Update the session title
        chat_sessions[session_id]["title"] = new_title.strip()
        save_chat_sessions() # Persist the change
        app.logger.info(f"Renamed chat session {session_id} to '{new_title}'")

        return jsonify({"message": "Session renamed successfully", "session_id": session_id}), 200

    except Exception as e:
        app.logger.error(f"Error renaming session {session_id}: {e}")
        return jsonify({"error": f"Failed to rename session: {str(e)}"}), 500
# --- End New Endpoint ---

@app.route('/api/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """Delete a specific chat session."""
    try:
        if session_id in chat_sessions:
            del chat_sessions[session_id]
            save_chat_sessions() # Persist the deletion
            app.logger.info(f"Deleted chat session: {session_id}")
            return jsonify({"message": "Session deleted successfully"}), 200
        else:
            return jsonify({"error": "Session not found"}), 404
    except Exception as e:
        app.logger.error(f"Error deleting session {session_id}: {e}")
        return jsonify({"error": f"Failed to delete session {session_id}"}), 500

# --- Modified Chat Endpoint ---
@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Handles chat requests. Accepts message, session_id, and optional document_ids filter.
    """
    try:
        data = request.get_json()
        # --- Fixed Syntax Error ---
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400

        message = data.get('message', '').strip()
        session_id = data.get('session_id') # Required now
        # Expect a list of document IDs to limit the search scope, or None/empty list for all
        document_ids_filter = data.get('document_ids', None)

        if not message:
            return jsonify({"error": "Message is required"}), 400
        if not session_id:
            return jsonify({"error": "Session ID is required"}), 400
        if session_id not in chat_sessions:
             return jsonify({"error": "Invalid Session ID"}), 404

        app.logger.info(f"[Session: {session_id}] Received chat message: '{message[:50]}...' with document filter: {document_ids_filter}")

        # --- Add user message to session history ---
        user_message = {
            "role": "user",
            "content": message,
            "timestamp": datetime.now(timezone.utc).isoformat() # Use timezone.utc
        }
        chat_sessions[session_id]["messages"].append(user_message)
        # Update session title if it's the first message
        if len(chat_sessions[session_id]["messages"]) == 1:
            # Use first few words of the message as the title
            title = message[:30] + ("..." if len(message) > 30 else "")
            chat_sessions[session_id]["title"] = title
        save_chat_sessions() # Save after adding user message

        # --- Retrieve relevant chunks using ChromaDB ---
        MAX_TOP_K = 20 # Define a reasonable upper limit
        if isinstance(document_ids_filter, list) and len(document_ids_filter) > 0:
            # E.g., retrieve 1 chunk per doc, but cap it
            dynamic_top_k = min(len(document_ids_filter) * 5, MAX_TOP_K)
        else:
            # If no filter or empty filter, use default
            dynamic_top_k = 5

        relevant_chunks = rag_system.retrieve_relevant_chunks(
            query=message,
            top_k=dynamic_top_k, # Use the dynamic value
            doc_ids_filter=document_ids_filter # This can be None, a list, or an empty list
        )

        # --- Generate response ---
        response_data = rag_system.generate_response(message, relevant_chunks)

        # --- Add bot response to session history ---
        bot_message = {
            "role": "assistant",
            "content": response_data.get('answer', ''), # Ensure we use 'answer' key
            "sources": response_data.get('sources', []),
            "confidence": response_data.get('confidence', 'unknown'),
            "timestamp": datetime.now(timezone.utc).isoformat() # Use timezone.utc
        }
        chat_sessions[session_id]["messages"].append(bot_message)
        save_chat_sessions() # Save after adding bot message

        app.logger.info(f"[Session: {session_id}] Generated response (confidence: {bot_message.get('confidence')})")
        # Return the new bot message to the frontend
        return jsonify(bot_message)

    except Exception as e:
        app.logger.error(f"Chat Error: {e}", exc_info=True) # Log full traceback
        return jsonify({"error": f"Failed to generate response: {str(e)}"}), 500

# --- New Model Management Endpoints ---

@app.route('/api/models', methods=['GET'])
def get_models():
    """Get available models and the currently selected one."""
    try:
        return jsonify({
            "available_models": AVAILABLE_MODELS,
            "current_model": CURRENT_MODEL_NAME
        })
    except Exception as e:
        app.logger.error(f"Error fetching models: {e}")
        return jsonify({"error": "Failed to fetch models"}), 500

@app.route('/api/models', methods=['POST'])
def set_model():
    """Set the current model. This will recreate the RAG system."""
    global rag_system, CURRENT_MODEL_NAME # We need to modify the global rag_system instance

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400

        new_model_name = data.get('model_name')

        if not new_model_name:
            return jsonify({"error": "Missing 'model_name' in request body"}), 400

        if new_model_name not in AVAILABLE_MODELS:
            return jsonify({
                "error": f"Model '{new_model_name}' is not available.",
                "available_models": AVAILABLE_MODELS
            }), 400

        if new_model_name == CURRENT_MODEL_NAME:
            # No change needed
            return jsonify({
                "message": f"Model is already set to '{new_model_name}'.",
                "current_model": CURRENT_MODEL_NAME
            }), 200

        # --- Recreate the RAG System with the new model ---
        # Get the current ChromaDB path (assuming it's consistent)
        # Accessing _path is generally not recommended, but it works for chromadb.PersistentClient
        # A more robust way might be to pass it explicitly or store it in a global/config.
        current_chroma_path = "./chroma_db" # Default path, or retrieve it more safely if needed
        if hasattr(rag_system, 'client') and hasattr(rag_system.client, '_path'):
             current_chroma_path = rag_system.client._path

        app.logger.info(f"Recreating RAG System with model: {new_model_name} and path: {current_chroma_path}")

        # Create a new RAGSystem instance with the new model
        # Note: This will re-initialize the ChromaDB client and collection access,
        # but it will *not* reload the documents/chunks already stored in ChromaDB.
        # It will only change the LLM used for response generation.
        new_rag_system = RAGSystem(model_name=new_model_name, chroma_db_path=current_chroma_path)

        # Replace the global instance
        rag_system = new_rag_system
        CURRENT_MODEL_NAME = new_model_name

        app.logger.info(f"RAG System model changed to: {CURRENT_MODEL_NAME}")

        return jsonify({
            "message": f"Model successfully changed to '{new_model_name}'.",
            "current_model": CURRENT_MODEL_NAME
        }), 200

    except Exception as e:
        app.logger.error(f"Error setting model: {e}", exc_info=True) # Log full traceback
        return jsonify({"error": f"Failed to set model: {str(e)}"}), 500


# --- Optional: Endpoint to clear the ChromaDB collection (Use with caution!) ---
@app.route('/api/admin/clear', methods=['POST']) # Consider auth for admin endpoints
def clear_data():
    try:
        rag_system.clear_collection()
        # Clear in-memory document list
        global documents
        documents = []
        # Also clear the persistent document list file
        save_documents() # Save the now-empty list

        # Clear chat sessions too
        global chat_sessions
        chat_sessions = {}
        save_chat_sessions() # Save the now-empty sessions

        # Reset model to default if needed (optional, or just keep the current one)
        # global CURRENT_MODEL_NAME
        # CURRENT_MODEL_NAME = "gemini-1.5-flash"
        # rag_system = RAGSystem(model_name=CURRENT_MODEL_NAME, chroma_db_path="./chroma_db")

        return jsonify({"message": "All document and chat data cleared successfully."})
    except Exception as e:
        app.logger.error(f"Error clearing  {e}")
        return jsonify({"error": f"Failed to clear  {str(e)}"}), 500

# --- Optional: Health check endpoint ---
@app.route('/api/health')
def health_check():
    return jsonify({"status": "healthy", "service": "SC4.0 AI Chatbot API"})

# --- New Route: Export Chat ---
@app.route('/api/sessions/<session_id>/export', methods=['GET'])
def export_chat(session_id):
    """Generate exportable chat data for the given session."""
    try:
        # 1. Find the session in the chat_sessions dictionary (it's a dict, keyed by session_id)
        # --- CORRECT WAY TO ACCESS ---
        session = chat_sessions.get(session_id)
        # --- END CORRECT WAY ---
        if not session:
            return jsonify({"error": "Session not found"}), 404

        # 2. Prepare chat data for export (plain text format)
        # --- CORRECTLY ACCESS MESSAGES FROM THE SESSION DICTIONARY ---
        chat_messages = session.get("messages", [])
        lines = []
        for msg in chat_messages:
            # Safely get role and content, defaulting to 'Unknown'/'[No Content]' if missing
            role = msg.get('role', 'Unknown').capitalize()
            content = msg.get('content', '[No Content]')
            lines.append(f"{role}: {content}")
        chat_data_as_text = "\n\n".join(lines) # Separate messages with blank lines
        # --- END CORRECT ACCESS ---

        # 3. Return the formatted text data
        # The frontend expects a JSON response with a 'chat_data' key containing the string.
        return jsonify({"chat_data": chat_data_as_text}), 200

    except Exception as e:
        app.logger.error(f"Error exporting chat for session {session_id}: {e}", exc_info=True) # Log full traceback
        return jsonify({"error": f"Failed to export chat: {str(e)}"}), 500
# --- End New Route ---


if __name__ == '__main__':
    # Optional: Log startup info or perform initial checks
    print("Starting SC4.0 AI Chatbot Backend with ChromaDB...")
    print(f"ChromaDB Path: ./chroma_db")
    print(f"Uploads Path: {UPLOAD_FOLDER}")
    print(f"Documents List Persistence File: {DOCUMENTS_FILE}")
    print(f"Chat Sessions Persistence File: {CHAT_SESSIONS_FILE}")
    print(f"Available Models: {AVAILABLE_MODELS}")
    print(f"Initial Model: {CURRENT_MODEL_NAME}")
    app.run(debug=True, port=5000) # Ensure debug=True for development, consider False for production
