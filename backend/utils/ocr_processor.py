# backend/utils/ocr_processor.py

import pytesseract
from PIL import Image
import logging

logger = logging.getLogger(__name__)

def ocr_image(image_path: str, lang: str = 'eng') -> str:
    """
    Extracts text from an image using Tesseract OCR.

    Args:
        image_path (str): The path to the image file.
        lang (str, optional): The language code for OCR (e.g., 'eng', 'deu').
                              Defaults to 'eng'.

    Returns:
        str: The extracted text, or an empty string if an error occurs.
    """
    try:
        logger.info(f"Performing OCR on image: {image_path} with language: {lang}")
        # Open the image using Pillow
        img = Image.open(image_path)

        # Optional: Preprocess the image for better OCR accuracy
        # Example preprocessing (uncomment if needed):
        # img = img.convert('L')  # Convert to grayscale
        # img = img.point(lambda x: 0 if x < 128 else 255, '1') # Thresholding (binarization)

        # Perform OCR using Tesseract
        # The 'config' parameter can be used for advanced Tesseract options
        # e.g., config='--psm 6' for uniform block of text
        extracted_text = pytesseract.image_to_string(img, lang=lang)
        cleaned_text = extracted_text.strip()
        logger.info(f"OCR completed. Extracted {len(cleaned_text)} characters.")
        return cleaned_text

    except FileNotFoundError:
        logger.error(f"OCR Error: Image file not found at {image_path}")
        return ""
    except pytesseract.TesseractNotFoundError:
        logger.error("OCR Error: Tesseract executable not found. Check TESSERACT_CMD configuration.")
        return ""
    except Exception as e:
        logger.error(f"OCR Error processing image {image_path}: {e}", exc_info=True)
        return ""

# Example usage (if running this file directly for testing):
# if __name__ == "__main__":
#     import os
#     logging.basicConfig(level=logging.INFO)
#     # Make sure TESSERACT_CMD is set correctly in environment or pytesseract.tesseract_cmd
#     test_image_path = "path/to/your/test_image.png"
#     if os.path.exists(test_image_path):
#         text = ocr_image(test_image_path)
#         print(f"Extracted Text:\n{text}")
#     else:
#         print(f"Test image not found at {test_image_path}")
