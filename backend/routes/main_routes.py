# backend/routes/main_routes.py
from flask import request, jsonify, current_app
import os
from werkzeug.utils import secure_filename
import logging

# --- Import service functions using ABSOLUTE imports ---
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

# --- Import global variables/functions from app.py ---
# We need these within the route handlers.
# These will be available in the global scope when app.py runs and calls these routes.
# We access them inside the route functions.
# from app import rag_system, documents, chat_sessions, save_documents, save_chat_sessions, AVAILABLE_MODELS, CURRENT_MODEL_NAME, UPLOAD_FOLDER # Don't import globally here, access inside functions

def init_routes(app):
    """Register all routes with the Flask app instance."""

    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config.get('ALLOWED_EXTENSIONS', {'pdf'})

    @app.route('/')
    def home():
        return jsonify({"message": "SC4.0 AI Chatbot API Running with ChromaDB"})

    @app.route('/api/upload', methods=['POST'])
    def upload_pdf():
        try:
            if 'pdf' not in request.files:
                return jsonify({"error": "No file provided"}), 400
            file = request.files['pdf']
            if file.filename == '':
                return jsonify({"error": "No file selected"}), 400
            if not allowed_file(file.filename):
                return jsonify({"error": "Only PDF files are allowed"}), 400

            # Access global variables needed by the service
            from app import rag_system, documents, save_documents, UPLOAD_FOLDER

            return handle_pdf_upload_service(
                file, UPLOAD_FOLDER, rag_system, documents, save_documents
            )

        except Exception as e:
            current_app.logger.error(f"Error processing PDF upload: {e}")
            return jsonify({"error": f"Failed to process PDF: {str(e)}"}), 500

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
            result_data, status_code = delete_document_service(
                doc_id, rag_system, documents, save_documents, UPLOAD_FOLDER
            )
            return jsonify(result_data), status_code
        except Exception as e:
            current_app.logger.error(f"Error deleting document {doc_id}: {e}")
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
            return jsonify({"error": f"Failed to fetch session {session_id}"}), 500

    @app.route('/api/sessions/<session_id>', methods=['PUT'])
    def rename_session(session_id):
        try:
            data = request.get_json()
            new_title = data.get('title') if data else None
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
            if not data:
                return jsonify({"error": "Invalid JSON data"}), 400

            message = data.get('message', '').strip()
            session_id = data.get('session_id')
            document_ids_filter = data.get('document_ids', None)

            # Access global variables
            from app import rag_system, chat_sessions, save_chat_sessions
            result_data, status_code = handle_chat_interaction_service(
                message, session_id, document_ids_filter, rag_system, chat_sessions, save_chat_sessions
            )
            return jsonify(result_data), status_code

        except Exception as e:
            current_app.logger.error(f"Chat Error: {e}", exc_info=True)
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

            result_data, status_code = set_current_model_service(
                new_model_name, AVAILABLE_MODELS, rag_system, RAGSystem, current_app.logger, CURRENT_MODEL_NAME
            )
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
            # Access global variable
            from app import chat_sessions
            result_data, status_code = export_session_chat_service(session_id, chat_sessions)
            return jsonify(result_data), status_code
        except Exception as e:
            current_app.logger.error(f"Error exporting chat for session {session_id}: {e}", exc_info=True)
            return jsonify({"error": f"Failed to export chat: {str(e)}"}), 500
