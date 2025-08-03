# backend/utils/rag_system.py

import chromadb
from chromadb.utils import embedding_functions
# If using sentence-transformers locally:
# from sentence_transformers import SentenceTransformer
import google.generativeai as genai
import os
# import numpy as np # Might not need if using Chroma's built-in search
# from sklearn.metrics.pairwise import cosine_similarity # Not needed for Chroma search

class RAGSystem:
    def __init__(self, model_name="gemini-1.5-flash", chroma_db_path="./chroma_db"):
        """
        Initializes the RAG system with ChromaDB.
        """
        # --- 1. Initialize Gemini ---
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        self.model_name = model_name # Store for potential later use

        # --- 2. Initialize ChromaDB Client ---
        # Persistent storage on disk
        self.client = chromadb.PersistentClient(path=chroma_db_path)
        # You can also use EphemeralClient() for in-memory, non-persistent storage for testing.

        # --- 3. Create or Get Collection ---
        # A collection is like a table in a database, holding related documents/chunks.
        # We'll use the default embedding function (Sentence Transformers all-MiniLM-L6-v2)
        # You can specify a different one if needed.
        self.sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        # Collection name
        self.collection_name = "sc4_0_documents"
        # Get or create the collection. If it exists, it loads it. If not, it creates it.
        # We pass the embedding function here so Chroma knows how to embed documents/queries.
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.sentence_transformer_ef
            # metadata={"hnsw:space": "cosine"} # Optional: specify distance metric
        )

        print(f"Initialized RAGSystem with ChromaDB collection '{self.collection_name}' at {chroma_db_path}")

    # --- Methods for adding documents/chunks ---

    def add_document_chunks(self, chunks: list[dict]):
        """
        Adds document chunks to the ChromaDB collection.
        Expected chunk format: {'id': str, 'doc_id': str, 'content': str, 'source': str, 'chunk_index': int}
        """
        if not chunks:
            print("No chunks provided to add.")
            return

        # Prepare data for ChromaDB
        # ChromaDB expects lists for ids, documents (the text), metadatas
        ids = [chunk['id'] for chunk in chunks]
        documents = [chunk['content'] for chunk in chunks]
        metadatas = [
            {
                'doc_id': chunk['doc_id'],
                'source': chunk['source'],
                'chunk_index': chunk['chunk_index']
                # Add any other metadata you want to filter by later
            }
            for chunk in chunks
        ]

        try:
            # Add to ChromaDB collection
            # Chroma will automatically embed the 'documents' using the specified embedding function
            self.collection.add(
                ids=ids,
                documents=documents, # The text content to embed
                metadatas=metadatas   # Metadata associated with each document
                # embeddings=... # Optional: You can provide pre-computed embeddings
            )
            print(f"Added {len(chunks)} chunks to ChromaDB collection '{self.collection_name}'.")
        except Exception as e:
            print(f"Error adding chunks to ChromaDB: {e}")
            # Depending on requirements, you might want to raise the exception
            # raise e

    # --- Method for retrieving relevant chunks ---

    def retrieve_relevant_chunks(self, query: str, top_k: int = 3, doc_ids_filter: list[str] | None = None) -> list[dict]:
        """
        Retrieves relevant chunks based on the query using ChromaDB's search.
        Optionally filter by a list of document IDs.
        """
        try:
            # Prepare filters for ChromaDB query
            # ChromaDB uses a dict for 'where' clauses
            where_clause = None
            if doc_ids_filter:
                # Filter by doc_id using 'in' operator
                # Metadata field 'doc_id' should be in the provided list
                where_clause = {"doc_id": {"$in": doc_ids_filter}}

            # Perform the search using ChromaDB
            # 'query_texts' is a list of query strings
            # 'n_results' specifies how many results to return
            # 'where' applies metadata filters
            results = self.collection.query(
                query_texts=[query], # The user's question
                n_results=top_k,    # Number of relevant chunks to retrieve
                where=where_clause   # Optional filter
            )

            # --- Process Results ---
            # ChromaDB returns results in a specific structure:
            # results = {
            #   'ids': [[...]],          # List of lists of IDs
            #   'distances': [[...]],    # List of lists of distances/similarities
            #   'metadatas': [[...]],    # List of lists of metadata dicts
            #   'documents': [[...]],    # List of lists of document texts
            #   'embeddings': [...]      # (Optional) Embeddings if requested
            # }
            # We are primarily interested in documents, metadatas, and potentially distances/ids

            relevant_chunks = []
            # Check if results are present (results dict keys exist and have data in the first [0] list)
            if results['ids'] and results['ids'][0]: # Check if any results were found
                num_results = len(results['ids'][0])
                for i in range(num_results):
                    chunk_data = {
                        'id': results['ids'][0][i],
                        'content': results['documents'][0][i],
                        'source': results['metadatas'][0][i].get('source', 'Unknown Source'),
                        'doc_id': results['metadatas'][0][i].get('doc_id', 'Unknown Doc ID'),
                        'chunk_index': results['metadatas'][0][i].get('chunk_index', -1),
                        # 'distance': results['distances'][0][i] # Optional: Include distance if needed for ranking/debugging
                    }
                    relevant_chunks.append(chunk_data)

            print(f"Retrieved {len(relevant_chunks)} relevant chunks from ChromaDB for query: '{query[:50]}...'")
            return relevant_chunks

        except Exception as e:
            print(f"Error retrieving chunks from ChromaDB: {e}")
            # Return empty list or handle error as appropriate
            return []


    # --- Method for generating response (mostly unchanged) ---

    def generate_response(self, query: str, relevant_chunks: list[dict]) -> dict:
        """Generate response using Gemini with relevant context"""
        if not relevant_chunks:
            return {
                'answer': "I couldn't find any relevant information in the uploaded documents to answer your question.",
                'sources': [],
                'confidence': 'low' # Indicate low confidence
            }

        # Prepare context from relevant chunks
        context = "\n\n".join([
            f"Source: {chunk['source']}\nContent: {chunk['content']}"
            for chunk in relevant_chunks
        ])

        prompt = f"""
        You are a helpful AI assistant that answers questions based on provided documents.
        Use the following context to answer the question at the end.
        If you don't know the answer based *only* on the context, say so clearly. Do not make up an answer.
        Provide a concise and informative response.

        Context:
        {context}

        Question: {query}

        Answer:
        """

        try:
            response = self.model.generate_content(prompt)
            answer = response.text.strip() # Clean up potential leading/trailing whitespace

            # Include source information
            sources = [
                {
                    'source': chunk['source'],
                    'content': chunk['content'][:200] + '...' if len(chunk['content']) > 200 else chunk['content']
                }
                for chunk in relevant_chunks
            ]

            # Basic check for relevance in response (very basic)
            # A more sophisticated check could be implemented later
            confidence = 'high'
            if "I couldn't find" in answer or "not found in the provided context" in answer or "based on the context" not in answer.lower():
                 confidence = 'low'

            return {
                'answer': answer,
                'sources': sources,
                'confidence': confidence # Add confidence indicator
            }

        except Exception as e:
            print(f"Error generating response with Gemini: {e}")
            raise Exception(f"Error generating response: {str(e)}")

    # --- Optional: Method to list documents (based on metadata) ---
    def list_documents(self) -> list[dict]:
        """List unique documents based on metadata in the collection."""
        try:
            # Get all unique 'doc_id' and 'source' from metadatas
            # ChromaDB's get method can retrieve items, potentially with filters
            # However, getting unique docs requires some processing.
            # A simple way is to query a sample and extract metadata, or use collection info if available.

            # Let's try to get a sample or all items to extract unique docs
            # This might be inefficient for very large collections, consider metadata indexing if needed later.
            all_data = self.collection.get(include=['metadatas']) # Get only metadatas

            unique_docs = {}
            if 'metadatas' in all_data and all_data['metadatas']:
                for metadata in all_data['metadatas']:
                    doc_id = metadata.get('doc_id')
                    source = metadata.get('source')
                    if doc_id and source and doc_id not in unique_docs:
                        unique_docs[doc_id] = {'id': doc_id, 'name': source} # Or include chunk count if tracked differently

            return list(unique_docs.values())
        except Exception as e:
            print(f"Error listing documents from ChromaDB: {e}")
            return []

    # --- Optional: Method to clear/reset the collection ---
    def clear_collection(self):
        """Clears all data from the ChromaDB collection."""
        try:
            self.collection.delete(ids=None) # Passing None or an empty list might delete all, check Chroma docs.
            # Safer approach: Get all IDs and delete them
            all_data = self.collection.get(include=[]) # Get only IDs
            if 'ids' in all_data and all_data['ids']:
                 self.collection.delete(ids=all_data['ids'])
            print(f"Cleared all data from ChromaDB collection '{self.collection_name}'.")
        except Exception as e:
            print(f"Error clearing ChromaDB collection: {e}")

# Example usage (if running this file directly for testing):
# if __name__ == "__main__":
#     rag = RAGSystem()
#     # Example adding chunks (would normally come from PDF processing)
#     test_chunks = [
#         {'id': 'test-1', 'doc_id': 'doc1', 'content': 'This is about machine learning and artificial intelligence.', 'source': 'TestDoc.pdf', 'chunk_index': 0},
#         {'id': 'test-2', 'doc_id': 'doc1', 'content': 'Natural language processing is a subfield of AI.', 'source': 'TestDoc.pdf', 'chunk_index': 1},
#         {'id': 'test-3', 'doc_id': 'doc2', 'content': 'Open source software development practices.', 'source': 'OSSGuide.pdf', 'chunk_index': 0},
#     ]
#     rag.add_document_chunks(test_chunks)
#
#     # Example query
#     results = rag.retrieve_relevant_chunks("What is NLP?")
#     print("Retrieved Chunks:", results)
#
#     # Example generation (if chunks found)
#     if results:
#         response = rag.generate_response("What is NLP?", results)
#         print("Generated Response:", response)
