# backend/utils/pdf_processor.py

import pdfplumber
from typing import List

def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from PDF file using pdfplumber"""
    try:
        with pdfplumber.open(file_path) as pdf:
            text = ""
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
            return text
    except Exception as e:
        raise Exception(f"Error extracting text from PDF: {str(e)}")

def split_text_into_chunks(text: str, chunk_size: int = 1000, overlap: int = 150) -> List[str]:
    """
    Split text into overlapping chunks.

    Args:
        text (str): The text to split.
        chunk_size (int): The desired size of each chunk. Defaults to 1000 characters.
        overlap (int): The number of characters to overlap between chunks. Defaults to 150 characters.

    Returns:
        List[str]: A list of text chunks.
    """
    if not text:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if overlap < 0:
        raise ValueError("overlap must be non-negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be less than chunk_size")

    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        # Calculate the end index for the current chunk
        end = start + chunk_size
        # Extract the chunk
        chunk = text[start:end]
        chunks.append(chunk)

        # If this is the last chunk, break
        if end >= text_length:
            break

        # Move the start position forward by (chunk_size - overlap)
        # Ensure we make progress even if overlap is large relative to chunk_size
        start += chunk_size - overlap
        # Prevent potential infinite loop if calculations go wrong
        if start >= text_length:
            break

    return chunks

# Example usage (if running this file directly for testing):
# if __name__ == "__main__":
#     sample_text = "a" * 2500 # Create a sample text longer than 2 chunks
#     chunks = split_text_into_chunks(sample_text, chunk_size=1000, overlap=150)
#     print(f"Number of chunks: {len(chunks)}")
#     for i, chunk in enumerate(chunks):
#         print(f"Chunk {i+1} (len {len(chunk)}): {repr(chunk[:50])}...")
#     # Check overlap for first two chunks
#     if len(chunks) > 1:
#         print(f"\nFirst chunk ends with: {repr(chunks[0][-20:])}")
#         print(f"Second chunk starts with: {repr(chunks[1][:20])}")
#         print("Notice the overlap in characters.")
