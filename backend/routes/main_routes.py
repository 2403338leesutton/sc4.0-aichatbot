# backend/routes/main_routes.py

from flask import request, jsonify, current_app
import os
import uuid
from datetime import datetime, timezone
from werkzeug.utils import secure_filename
import logging

# --- Import OCR and Chunking Utilities ---
from utils.ocr_processor import ocr_image
from utils.pdf_processor import split_text_into_chunks # Assuming this is where split_text_into_chunks lives
# --- End Import Utilities ---

# - Import service functions using ABSOLUTE imports -
# Assuming the Flask app is run from the 'backend' directory,
# the absolute path from there is 'services'
from services import (
    handle_pdf_upload_service,
    get_all_documents_service,
    delete_document_service,
    create_session_service,
    list_sessions_service,
    get_session_service,
    rename_session_service,
    delete_session_service,
    handle_chat_interaction_service,
    get_available_models_service,
    set_current_model_service,
    clear_all_data_service,
    export_session_chat_service
)
# - End Import Service Functions -

# - Import global variables/functions from app.py -
# We need these within the route handlers.
# These will be available in the global scope when app.py runs and calls these routes.
# We access them inside the route functions.
# DO NOT import them globally here; access them inside functions using `from app import ...`
# - End Import Globals -

def init_routes(app):
    """Register all routes with the Flask app instance."""

    def allowed_file(filename):
        # Access ALLOWED_EXTENSIONS from app config
        # Ensure app.config['ALLOWED_EXTENSIONS'] includes image types
        # This should be updated in app.py or services as needed.
        # Example update in app.py config: {'pdf', 'png', 'jpg', 'jpeg'}
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in app.config.get('ALLOWED_EXTENSIONS', {'pdf'})

    # --- Route Definitions ---

    @app.route('/')
    def home():
        return jsonify({"message": "SC4.0 AI Chatbot API Running with ChromaDB"})

    # --- Modified PDF Upload Route (Ensure it uses updated allowed_file) ---
    @app.route('/api/upload', methods=['POST'])
    def upload_pdf():
        try:
            if 'pdf' not in request.files:
                return jsonify({"error": "No file provided"}), 400

            file = request.files['pdf']

            if file.filename == '':
                return jsonify({"error": "No file selected"}), 400

            # Use the updated allowed_file function
            if not allowed_file(file.filename):
                # Improve error message to reflect allowed types
                allowed_exts = app.config.get('ALLOWED_EXTENSIONS', {'pdf'})
                return jsonify({"error": f"File type not allowed. Allowed types: {', '.join(allowed_exts)}"}), 400

            # Access global variables needed by the service
            from app import rag_system, documents, save_documents, UPLOAD_FOLDER
            return handle_pdf_upload_service(file, UPLOAD_FOLDER, rag_system, documents, save_documents)
        except Exception as e:
            current_app.logger.error(f"Error processing PDF upload: {e}")
            return jsonify({"error": f"Failed to process PDF: {str(e)}"}), 500
    # --- End Modified PDF Upload Route ---

    # --- New Route: Upload and Process Image ---
    @app.route('/api/upload/image', methods=['POST'])
    def upload_image():
        """Handle image upload, perform OCR, and add text to RAG system."""
        try:
            # --- 1. Validate Request ---
            if 'image' not in request.files:
                return jsonify({"error": "No image file provided"}), 400

            file = request.files['image']

            if file.filename == '':
                return jsonify({"error": "No image file selected"}), 400

            # Use the updated allowed_file function which now includes image types
            if not allowed_file(file.filename):
                # Improve error message
                allowed_exts = app.config.get('ALLOWED_EXTENSIONS', {'pdf'})
                return jsonify({"error": f"File type not allowed. Allowed types: {', '.join(allowed_exts)}"}), 400

            # --- 2. Save File ---
            filename = secure_filename(file.filename)
            # Prepend a UUID to avoid filename conflicts
            unique_filename = f"{uuid.uuid4()}_{filename}"
            # Access UPLOAD_FOLDER from app config
            upload_folder = current_app.config['UPLOAD_FOLDER']
            file_path = os.path.join(upload_folder, unique_filename)
            file.save(file_path)
            current_app.logger.info(f"Saved uploaded image: {filename} -> {file_path}")

            # --- 3. Perform OCR ---
            # Use default language 'eng', or make it configurable via request param if needed
            # Access Tesseract configuration via pytesseract (configured in app.py)
            extracted_text = ocr_image(file_path, lang='eng')

            if not extracted_text.strip():
                # If no text is found, clean up and inform user
                os.remove(file_path) # Delete the uploaded image file
                current_app.logger.warning(f"No text detected in image: {filename}")
                return jsonify({"error": "No text could be detected in the uploaded image."}), 400

            current_app.logger.info(f"OCR successful for {filename}. Extracted {len(extracted_text)} characters.")

            # --- 4. Process Text (Chunking) ---
            # Use the same chunking logic as PDFs, imported from utils.pdf_processor
            chunks = split_text_into_chunks(extracted_text, chunk_size=1000)

            # --- 5. Prepare Document Info and Chunks for RAG ---
            doc_id = str(uuid.uuid4())
            doc_info = {
                'id': doc_id,
                'name': filename, # Use original name for user display
                'uploaded_at': datetime.now(timezone.utc).isoformat(),
                'chunks_count': len(chunks),
                'file_path': file_path, # Store path for potential future deletion or reference
                'type': 'image' # Optional: Mark as image type
            }

            chunk_info = []
            for i, chunk in enumerate(chunks):
                chunk_data = {
                    'id': f"{doc_id}-chunk-{i}",
                    'doc_id': doc_id,
                    'content': chunk.strip(),
                    'source': filename,
                    'chunk_index': i
                }
                chunk_info.append(chunk_data)

            # --- 6. Add to RAG System and Document List ---
            # Access global variables from app.py
            from app import rag_system, documents, save_documents # Import needed globals

            rag_system.add_document_chunks(chunk_info)
            documents.append(doc_info) # Add to in-memory list
            save_documents() # Persist the document list

            current_app.logger.info(f"Added OCR-processed image '{filename}' (ID: {doc_id}) with {len(chunks)} chunks to RAG system.")

            return jsonify({
                "message": "Image uploaded, processed with OCR, and added successfully.",
                "document_id": doc_id,
                "chunks_count": len(chunks),
                "filename": filename
            }), 201 # 201 Created is appropriate

        except Exception as e:
            current_app.logger.error(f"Error processing image upload: {e}", exc_info=True)
            # Attempt to clean up the uploaded file if it exists and an error occurred after saving
            try:
                if 'file_path' in locals() and os.path.exists(locals()['file_path']):
                    os.remove(locals()['file_path'])
                    current_app.logger.info(f"Cleaned up failed upload: {locals()['file_path']}")
            except:
                pass # Ignore cleanup errors
            return jsonify({"error": f"Failed to process image: {str(e)}"}), 500
    # --- End New Route ---

    @app.route('/api/documents', methods=['GET'])
    def get_documents():
        try:
            # Access global variable
            from app import documents
            sorted_docs_data, status_code = get_all_documents_service(documents)
            return jsonify(sorted_docs_data), status_code
        except Exception as e:
            current_app.logger.error(f"Error fetching documents: {e}")
            return jsonify({"error": "Failed to fetch documents"}), 500

    @app.route('/api/documents/<doc_id>', methods=['DELETE'])
    def delete_document(doc_id):
        try:
            # Access global variables needed by the service
            from app import rag_system, documents, save_documents, UPLOAD_FOLDER
            result_data, status_code = delete_document_service(doc_id, rag_system, documents, save_documents, UPLOAD_FOLDER)
            return jsonify(result_data), status_code
        except Exception as e:
            current_app.logger.error(f"Error deleting document {doc_id}: {e}")
            # Return a generic error to the frontend
            return jsonify({"error": f"Failed to delete document: {str(e)}"}), 500

    @app.route('/api/sessions', methods=['POST'])
    def create_session():
        try:
            # Access global variables
            from app import chat_sessions, save_chat_sessions
            result_data, status_code = create_session_service(chat_sessions, save_chat_sessions)
            return jsonify(result_data), status_code
        except Exception as e:
            current_app.logger.error(f"Error creating session: {e}")
            return jsonify({"error": "Failed to create session"}), 500

    @app.route('/api/sessions', methods=['GET'])
    def list_sessions():
        try:
            # Access global variable
            from app import chat_sessions
            session_list_data, status_code = list_sessions_service(chat_sessions)
            return jsonify(session_list_data), status_code
        except Exception as e:
            current_app.logger.error(f"Error listing sessions: {e}")
            return jsonify({"error": "Failed to list sessions"}), 500

    @app.route('/api/sessions/<session_id>', methods=['GET'])
    def get_session(session_id):
        try:
            # Access global variable
            from app import chat_sessions
            result_data, status_code = get_session_service(session_id, chat_sessions)
            return jsonify(result_data), status_code
        except Exception as e:
            current_app.logger.error(f"Error fetching session {session_id}: {e}")
            # Return a generic error to the frontend
            return jsonify({"error": f"Failed to fetch session {session_id}"}), 500

    @app.route('/api/sessions/<session_id>', methods=['PUT'])
    def rename_session(session_id):
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "Invalid JSON data"}), 400

            new_title = data.get('title')
            # Access global variables
            from app import chat_sessions, save_chat_sessions
            result_data, status_code = rename_session_service(session_id, new_title, chat_sessions, save_chat_sessions)
            return jsonify(result_data), status_code
        except Exception as e:
            current_app.logger.error(f"Error renaming session {session_id}: {e}")
            return jsonify({"error": f"Failed to rename session: {str(e)}"}), 500

    @app.route('/api/sessions/<session_id>', methods=['DELETE'])
    def delete_session(session_id):
        try:
            # Access global variables
            from app import chat_sessions, save_chat_sessions
            result_data, status_code = delete_session_service(session_id, chat_sessions, save_chat_sessions)
            return jsonify(result_data), status_code
        except Exception as e:
            current_app.logger.error(f"Error deleting session {session_id}: {e}")
            return jsonify({"error": f"Failed to delete session {session_id}"}), 500

    @app.route('/api/chat', methods=['POST'])
    def chat():
        try:
            data = request.get_json()
            # --- Fixed Syntax Error ---
            if not data:
                return jsonify({"error": "Invalid JSON data"}), 400

            message = data.get('message', '').strip()
            session_id = data.get('session_id')
            document_ids_filter = data.get('document_ids', None)

            # Access global variables needed by the service
            from app import rag_system, chat_sessions, save_chat_sessions

            # --- Pass the new parameter to the service ---
            result_data, status_code = handle_chat_interaction_service(
                message, session_id, document_ids_filter, rag_system, chat_sessions, save_chat_sessions
            )
            return jsonify(result_data), status_code

        except Exception as e:
            current_app.logger.error(f"Chat Error: {e}", exc_info=True) # Log full traceback
            return jsonify({"error": f"Failed to generate response: {str(e)}"}), 500

    @app.route('/api/models', methods=['GET'])
    def get_models():
        try:
            # Access global variables
            from app import AVAILABLE_MODELS, CURRENT_MODEL_NAME
            result_data, status_code = get_available_models_service(AVAILABLE_MODELS, CURRENT_MODEL_NAME)
            return jsonify(result_data), status_code
        except Exception as e:
            current_app.logger.error(f"Error fetching models: {e}")
            return jsonify({"error": "Failed to fetch models"}), 500

    @app.route('/api/models', methods=['POST'])
    def set_model():
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "Invalid JSON data"}), 400

            new_model_name = data.get('model_name')
            # Access global variables and classes
            from app import AVAILABLE_MODELS, rag_system, CURRENT_MODEL_NAME
            from utils.rag_system import RAGSystem # Import here for recreation
            result_data, status_code = set_current_model_service(new_model_name, AVAILABLE_MODELS, rag_system, RAGSystem, current_app.logger, CURRENT_MODEL_NAME)
            # If the model was successfully changed, the service should update the global rag_system
            # We might need to signal back to app.py to update CURRENT_MODEL_NAME if the service doesn't do it directly
            # Or, the service could return the new CURRENT_MODEL_NAME
            if status_code == 200 and 'successfully changed' in result_data.get('message', ''):
                # Update the global CURRENT_MODEL_NAME in app.py context
                from app import update_current_model_name # Assume you add this helper to app.py
                update_current_model_name(new_model_name) # Implement this function in app.py
            return jsonify(result_data), status_code
        except Exception as e:
            current_app.logger.error(f"Error setting model: {e}", exc_info=True)
            return jsonify({"error": f"Failed to set model: {str(e)}"}), 500

    @app.route('/api/admin/clear', methods=['POST'])
    def clear_data_route():
        try:
            # Access global variables
            from app import rag_system, documents, chat_sessions, save_documents, save_chat_sessions
            result_data, status_code = clear_all_data_service(rag_system, documents, chat_sessions, save_documents, save_chat_sessions)
            return jsonify(result_data), status_code
        except Exception as e:
            current_app.logger.error(f"Error clearing data: {e}")
            return jsonify({"error": f"Failed to clear data: {str(e)}"}), 500

    @app.route('/api/health')
    def health_check():
        return jsonify({"status": "healthy", "service": "SC4.0 AI Chatbot API"})

    @app.route('/api/sessions/<session_id>/export', methods=['GET'])
    def export_chat(session_id):
        try:
            # Access global chat sessions dictionary
            from app import chat_sessions # Make sure chat_sessions is accessible

            # --- Use the service function (if you have services.py) ---
            # from services import export_session_chat_service
            # result_data, status_code = export_session_chat_service(session_id, chat_sessions)
            # return jsonify(result_data), status_code
            # --- OR, implement the logic directly here (simpler for now) ---

            session = chat_sessions.get(session_id)
            if not session:
                return jsonify({"error": "Session not found"}), 404

            chat_messages = session.get("messages", [])
            lines = []
            for msg in chat_messages:
                role = msg.get('role', 'Unknown').capitalize()
                content = msg.get('content', '[No Content]')
                lines.append(f"{role}: {content}")
            chat_data_as_text = "\n\n".join(lines)

            # Return the chat data as plain text or in a JSON structure
            # Returning JSON is generally safer for API endpoints
            return jsonify({"chat_data": chat_data_as_text}), 200

        except Exception as e:
            current_app.logger.error(f"Error exporting chat for session {session_id}: {e}", exc_info=True)
            return jsonify({"error": f"Failed to export chat: {str(e)}"}), 500

# --- End Route Definitions ---
