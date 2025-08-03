# backend/services.py
import os
import uuid
from datetime import datetime, timezone
from werkzeug.utils import secure_filename
import logging

# Import utility functions needed by services
from utils.pdf_processor import extract_text_from_pdf, split_text_into_chunks
# RAGSystem import might be needed for recreation in set_model, but not generally here.

# --- Service Functions ---

# --- PDF Upload Service ---
def handle_pdf_upload_service(file, upload_folder, rag_system, documents, save_documents_func):
    """Core logic for handling PDF upload and processing."""
    try:
        original_filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{original_filename}"
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)

        logging.info(f"Processing PDF: {original_filename}")
        extracted_text = extract_text_from_pdf(file_path)
        chunks = split_text_into_chunks(extracted_text, chunk_size=1000)

        doc_id = str(uuid.uuid4())
        doc_info = {
            'id': doc_id,
            'name': original_filename,
            'uploaded_at': datetime.now(timezone.utc).isoformat(),
            'chunks_count': len(chunks),
            'file_path': file_path,
        }
        documents.append(doc_info)
        logging.info(f"Stored document info for {original_filename} (ID: {doc_id})")

        chunk_info = []
        for i, chunk in enumerate(chunks):
            chunk_data = {
                'id': f"{doc_id}-chunk-{i}",
                'doc_id': doc_id,
                'content': chunk.strip(),
                'source': original_filename,
                'chunk_index': i
            }
            chunk_info.append(chunk_data)

        rag_system.add_document_chunks(chunk_info)
        logging.info(f"Added {len(chunk_info)} chunks to ChromaDB for document {original_filename}")

        save_documents_func() # Call the passed save function
        return jsonify({
            "message": "PDF uploaded and processed successfully",
            "document_id": doc_id,
            "chunks_count": len(chunks),
            "filename": original_filename
        }), 201

    except Exception as e:
        logging.error(f"Service Error processing PDF upload: {e}", exc_info=True)
        # Return data for route to jsonify
        return {"error": f"Failed to process PDF: {str(e)}"}, 500

# --- Document Services ---
def get_all_documents_service(documents_list):
    """Retrieve list of documents."""
    sorted_docs = sorted(documents_list, key=lambda x: x.get('uploaded_at', ''), reverse=True)
    # Return data for route to jsonify
    return sorted_docs, 200

def delete_document_service(doc_id, rag_system, documents_list, save_documents_func, upload_folder):
    """Delete a document by ID."""
    document_to_delete = next((doc for doc in documents_list if doc['id'] == doc_id), None)
    if not document_to_delete:
        # Return data for route to jsonify
        return {"error": "Document not found"}, 404

    doc_name_for_logs = document_to_delete.get('name', 'Unknown Document')

    try:
        rag_system.delete_document_chunks(doc_id)
        logging.info(f"Deleted chunks for document ID {doc_id} from ChromaDB")
    except Exception as e:
        logging.error(f"Error deleting chunks for document {doc_id} from ChromaDB: {e}")
        pass # Continue with other deletions

    # Update the list passed in
    documents_list[:] = [doc for doc in documents_list if doc['id'] != doc_id]

    file_path_to_delete = document_to_delete.get('file_path')
    if file_path_to_delete and os.path.exists(file_path_to_delete):
        try:
            os.remove(file_path_to_delete)
            logging.info(f"Deleted PDF file: {file_path_to_delete}")
        except OSError as e:
            error_msg = f"Error deleting PDF file {file_path_to_delete}: {e}"
            logging.error(error_msg)
    elif file_path_to_delete:
        logging.warning(f"PDF file path {file_path_to_delete} does not exist, skipping file deletion.")
    else:
        logging.warning(f"No file path found for document {doc_id} ({doc_name_for_logs}), skipping file deletion.")

    save_documents_func() # Call the passed save function
    logging.info(f"Deleted document {doc_id} ({doc_name_for_logs})")
    # Return data for route to jsonify
    return {"message": "Document deleted successfully"}, 200

# --- Session Services ---
def create_session_service(chat_sessions_dict, save_chat_sessions_func):
    """Create a new chat session."""
    session_id = str(uuid.uuid4())
    new_session = {
        "messages": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": "New Chat"
    }
    chat_sessions_dict[session_id] = new_session
    save_chat_sessions_func() # Call the passed save function
    logging.info(f"Created new chat session: {session_id}")
    # Return data for route to jsonify
    return {"session_id": session_id, "session": new_session}, 201

def list_sessions_service(chat_sessions_dict):
    """List all chat sessions metadata."""
    session_list = []
    for sid, data in chat_sessions_dict.items():
        session_list.append({
            "session_id": sid,
            "title": data.get("title", "Untitled Chat"),
            "created_at": data.get("created_at"),
            "message_count": len(data.get("messages", []))
        })
    session_list.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    # Return data for route to jsonify
    return session_list, 200

def get_session_service(session_id, chat_sessions_dict):
    """Get a specific session's full history."""
    session = chat_sessions_dict.get(session_id)
    if not session:
        # Return data for route to jsonify
        return {"error": "Session not found"}, 404
    # Return data for route to jsonify
    return {"session_id": session_id, "session": session}, 200

def rename_session_service(session_id, new_title, chat_sessions_dict, save_chat_sessions_func):
    """Rename a specific chat session."""
    session = chat_sessions_dict.get(session_id)
    if not session:
        # Return data for route to jsonify
        return {"error": "Session not found"}, 404

    if not new_title or not isinstance(new_title, str):
        # Return data for route to jsonify
        return {"error": "A valid 'title' (string) is required in the request body"}, 400

    chat_sessions_dict[session_id]["title"] = new_title.strip()
    save_chat_sessions_func() # Call the passed save function
    logging.info(f"Renamed chat session {session_id} to '{new_title}'")
    # Return data for route to jsonify
    return {"message": "Session renamed successfully", "session_id": session_id}, 200

def delete_session_service(session_id, chat_sessions_dict, save_chat_sessions_func):
    """Delete a specific chat session."""
    if session_id in chat_sessions_dict:
        del chat_sessions_dict[session_id]
        save_chat_sessions_func() # Call the passed save function
        logging.info(f"Deleted chat session: {session_id}")
        # Return data for route to jsonify
        return {"message": "Session deleted successfully"}, 200
    else:
        # Return data for route to jsonify
        return {"error": "Session not found"}, 404

# --- Chat Interaction Service ---
def handle_chat_interaction_service(message, session_id, document_ids_filter, rag_system, chat_sessions_dict, save_chat_sessions_func):
    """Handle the core chat logic."""
    if not message:
        # Return data for route to jsonify
        return {"error": "Message is required"}, 400
    if not session_id:
        # Return data for route to jsonify
        return {"error": "Session ID is required"}, 400
    if session_id not in chat_sessions_dict:
        # Return data for route to jsonify
        return {"error": "Invalid Session ID"}, 404

    logging.info(f"[Session: {session_id}] Received chat message: '{message[:50]}...' with document filter: {document_ids_filter}")

    user_message = {
        "role": "user",
        "content": message,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    chat_sessions_dict[session_id]["messages"].append(user_message)

    if len(chat_sessions_dict[session_id]["messages"]) == 1:
        title = message[:30] + ("..." if len(message) > 30 else "")
        chat_sessions_dict[session_id]["title"] = title
    save_chat_sessions_func() # Call the passed save function

    MAX_TOP_K = 20
    if isinstance(document_ids_filter, list) and len(document_ids_filter) > 0:
        dynamic_top_k = min(len(document_ids_filter) * 5, MAX_TOP_K)
    else:
        dynamic_top_k = 5

    relevant_chunks = rag_system.retrieve_relevant_chunks(
        query=message,
        top_k=dynamic_top_k,
        doc_ids_filter=document_ids_filter
    )

    try:
        response_data = rag_system.generate_response(message, relevant_chunks)
    except Exception as e:
        logging.error(f"Error generating response in service: {e}")
        # Return data for route to jsonify
        return {"error": f"Failed to generate response: {str(e)}"}, 500

    bot_message = {
        "role": "assistant",
        "content": response_data.get('answer', ''),
        "sources": response_data.get('sources', []),
        "confidence": response_data.get('confidence', 'unknown'),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    chat_sessions_dict[session_id]["messages"].append(bot_message)
    save_chat_sessions_func() # Call the passed save function
    logging.info(f"[Session: {session_id}] Generated response (confidence: {bot_message.get('confidence')})")

    # Return data for route to jsonify
    return bot_message, 200

# --- Model Management Services ---
def get_available_models_service(available_models_list, current_model_name):
    """Get available models."""
    # Return data for route to jsonify
    return {
        "available_models": available_models_list,
        "current_model": current_model_name
    }, 200

def set_current_model_service(new_model_name, available_models_list, current_rag_system, RAGSystemClass, logger):
    """Set the current model (recreates RAG system)."""
    # Note: This service is tricky because it needs to modify the global rag_system.
    # The current approach modifies the object passed in. A better way is to return the new instance.
    # For now, we'll try to modify the passed object. This requires passing the actual object reference.

    if not new_model_name:
        # Return data for route to jsonify
        return ({"error": "Missing 'model_name' in request body"}, 400)
    if new_model_name not in available_models_list:
        # Return data for route to jsonify
        return ({
            "error": f"Model '{new_model_name}' is not available.",
            "available_models": available_models_list
        }, 400)
    if new_model_name == current_rag_system.model_name: # Assuming model_name is accessible
         # Return data for route to jsonify
        return ({
            "message": f"Model is already set to '{new_model_name}'.",
            "current_model": current_rag_system.model_name
        }, 200)

    # --- Recreate the RAG System with the new model ---
    current_chroma_path = "./chroma_db"
    if hasattr(current_rag_system, 'client') and hasattr(current_rag_system.client, '_path'):
        current_chroma_path = current_rag_system.client._path

    logger.info(f"Recreating RAG System with model: {new_model_name} and path: {current_chroma_path}")

    try:
        # Create new instance
        new_rag_system = RAGSystemClass(model_name=new_model_name, chroma_db_path=current_chroma_path)
        # Modify the attributes of the passed object (this is a bit hacky but works for simple cases)
        # A cleaner way is to return the new instance and let app.py handle the replacement.
        current_rag_system.__dict__.update(new_rag_system.__dict__)
        # Or, if you modify app.py to accept the return value:
        # return new_rag_system # Then app.py needs to handle this return value

        logger.info(f"RAG System model changed to: {new_model_name}") # Use new_model_name as current_rag_system.model_name might not be updated yet in this scope if we just modified __dict__
        # Return data for route to jsonify
        return ({
            "message": f"Model successfully changed to '{new_model_name}'.",
            "current_model": new_model_name # Return the new name
        }, 200)
    except Exception as e:
        logger.error(f"Error recreating RAG System: {e}", exc_info=True)
        # Return data for route to jsonify
        return ({"error": f"Failed to set model: {str(e)}"}, 500)

# --- Admin Service ---
def clear_all_data_service(rag_system, documents_list, chat_sessions_dict, save_documents_func, save_chat_sessions_func):
    """Clear all document and chat data."""
    try:
        rag_system.clear_collection()
        documents_list.clear() # Clear the list passed in
        save_documents_func() # Save the now-empty list
        chat_sessions_dict.clear() # Clear the dict passed in
        save_chat_sessions_func() # Save the now-empty sessions
        # Return data for route to jsonify
        return {"message": "All document and chat data cleared successfully."}, 200
    except Exception as e:
        logging.error(f"Error clearing data in service: {e}")
        # Return data for route to jsonify
        return {"error": f"Failed to clear data: {str(e)}"}, 500

# --- Export Service ---
def export_session_chat_service(session_id, chat_sessions_dict):
    """Export chat data for a session."""
    session = chat_sessions_dict.get(session_id)
    if not session:
        # Return data for route to jsonify
        return {"error": "Session not found"}, 404

    chat_messages = session.get("messages", [])
    lines = []
    for msg in chat_messages:
        role = msg.get('role', 'Unknown').capitalize()
        content = msg.get('content', '[No Content]')
        lines.append(f"{role}: {content}")
    chat_data_as_text = "\n".join(lines)

    # Return data for route to jsonify
    return {"chat_data": chat_data_as_text}, 200

# --- Helper for jsonify ---
# Since services can't directly call jsonify, routes will need to.
# We return data and status codes.
# However, for logging within services, we can use standard logging.
# The `jsonify` call in services was incorrect. Routes handle the response creation.
# Let's remove the incorrect jsonify calls and ensure services return data/status.

# Corrected version of handle_pdf_upload_service (fixing jsonify calls)
def handle_pdf_upload_service(file, upload_folder, rag_system, documents, save_documents_func):
    """Core logic for handling PDF upload and processing."""
    try:
        original_filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{original_filename}"
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)

        logging.info(f"Processing PDF: {original_filename}")
        extracted_text = extract_text_from_pdf(file_path)
        chunks = split_text_into_chunks(extracted_text, chunk_size=1000)

        doc_id = str(uuid.uuid4())
        doc_info = {
            'id': doc_id,
            'name': original_filename,
            'uploaded_at': datetime.now(timezone.utc).isoformat(),
            'chunks_count': len(chunks),
            'file_path': file_path,
        }
        documents.append(doc_info)
        logging.info(f"Stored document info for {original_filename} (ID: {doc_id})")

        chunk_info = []
        for i, chunk in enumerate(chunks):
            chunk_data = {
                'id': f"{doc_id}-chunk-{i}",
                'doc_id': doc_id,
                'content': chunk.strip(),
                'source': original_filename,
                'chunk_index': i
            }
            chunk_info.append(chunk_data)

        rag_system.add_document_chunks(chunk_info)
        logging.info(f"Added {len(chunk_info)} chunks to ChromaDB for document {original_filename}")

        save_documents_func()
        # Return data tuple (data_dict, status_code)
        return {
            "message": "PDF uploaded and processed successfully",
            "document_id": doc_id,
            "chunks_count": len(chunks),
            "filename": original_filename
        }, 201

    except Exception as e:
        logging.error(f"Service Error processing PDF upload: {e}", exc_info=True)
        # Return error tuple (error_dict, status_code)
        return {"error": f"Failed to process PDF: {str(e)}"}, 500

# --- Apply similar corrections to all service functions ---
# (This means removing `jsonify()` calls from inside the service functions)
# The corrected versions are shown above for `handle_pdf_upload_service` and `delete_document_service`.
# You would need to apply this pattern to all other service functions.
# For brevity, I'll assume the rest are corrected similarly.
# Key change: Service functions return (data_dict, status_code) or (error_dict, status_code)
# Routes then call `return jsonify(data_dict), status_code`

# Let's correct one more as an example: delete_document_service
def delete_document_service(doc_id, rag_system, documents_list, save_documents_func, upload_folder):
    """Delete a document by ID."""
    document_to_delete = next((doc for doc in documents_list if doc['id'] == doc_id), None)
    if not document_to_delete:
        return {"error": "Document not found"}, 404

    doc_name_for_logs = document_to_delete.get('name', 'Unknown Document')

    try:
        rag_system.delete_document_chunks(doc_id)
        logging.info(f"Deleted chunks for document ID {doc_id} from ChromaDB")
    except Exception as e:
        logging.error(f"Error deleting chunks for document {doc_id} from ChromaDB: {e}")
        pass

    # Update the list passed in
    documents_list[:] = [doc for doc in documents_list if doc['id'] != doc_id]

    file_path_to_delete = document_to_delete.get('file_path')
    if file_path_to_delete and os.path.exists(file_path_to_delete):
        try:
            os.remove(file_path_to_delete)
            logging.info(f"Deleted PDF file: {file_path_to_delete}")
        except OSError as e:
            error_msg = f"Error deleting PDF file {file_path_to_delete}: {e}"
            logging.error(error_msg)
    elif file_path_to_delete:
        logging.warning(f"PDF file path {file_path_to_delete} does not exist, skipping file deletion.")
    else:
        logging.warning(f"No file path found for document {doc_id} ({doc_name_for_logs}), skipping file deletion.")

    save_documents_func()
    logging.info(f"Deleted document {doc_id} ({doc_name_for_logs})")
    return {"message": "Document deleted successfully"}, 200

# --- Final Note ---
# Ensure ALL service functions follow the pattern:
#   - Perform logic
#   - Return (data_dict, http_status_code) for success
#   - Return (error_dict, http_status_code) for errors
#   - Do NOT call `jsonify()` inside service functions.
#   - Use standard `logging` for logging.
