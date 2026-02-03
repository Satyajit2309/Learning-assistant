"""
OCR Service for Answer Sheet Evaluation

Uses EasyOCR to extract handwritten text from images and PDFs.
EasyOCR provides good handwriting recognition with numpy 2.x compatibility.
"""

import os
import tempfile
from typing import Optional
from PIL import Image
import io


class OCRService:
    """Service for extracting text from images and PDFs using EasyOCR."""
    
    def __init__(self):
        self._reader = None
        self._languages = ['en']  # Can add more languages if needed
    
    @property
    def reader(self):
        """Lazy-load EasyOCR reader to avoid import overhead."""
        if self._reader is None:
            try:
                import easyocr
                self._reader = easyocr.Reader(self._languages, gpu=False)
            except ImportError:
                raise ImportError(
                    "EasyOCR is not installed. Install it with: pip install easyocr"
                )
        return self._reader
    
    def extract_from_image(self, image_path: str) -> str:
        """
        Extract text from a single image file.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Extracted text as a string
        """
        results = self.reader.readtext(image_path)
        
        # EasyOCR returns list of (bbox, text, confidence) tuples
        # Sort by vertical position (y-coordinate) for proper reading order
        results_sorted = sorted(results, key=lambda x: x[0][0][1])
        
        # Extract just the text
        text_lines = [result[1] for result in results_sorted]
        return '\n'.join(text_lines)
    
    def extract_from_pdf(self, pdf_path: str) -> str:
        """
        Extract text from a PDF file by converting pages to images.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Extracted text from all pages as a string
        """
        try:
            from pdf2image import convert_from_path
        except ImportError:
            raise ImportError(
                "pdf2image is not installed. Install it with: pip install pdf2image\n"
                "Also ensure Poppler is installed on your system."
            )
        
        # Convert PDF pages to images
        images = convert_from_path(pdf_path)
        
        all_text = []
        for i, image in enumerate(images, 1):
            # Save image temporarily
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                image.save(tmp.name, 'PNG')
                tmp_path = tmp.name
            
            try:
                page_text = self.extract_from_image(tmp_path)
                all_text.append(f"--- Page {i} ---\n{page_text}")
            finally:
                # Clean up temp file
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
        
        return '\n\n'.join(all_text)
    
    def extract_from_django_file(self, uploaded_file) -> str:
        """
        Extract text from a Django UploadedFile object.
        
        Args:
            uploaded_file: Django uploaded file object
            
        Returns:
            Extracted text as a string
        """
        file_ext = uploaded_file.name.lower().split('.')[-1]
        
        # Reset file position
        uploaded_file.seek(0)
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix=f'.{file_ext}', delete=False) as tmp:
            for chunk in uploaded_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name
        
        try:
            if file_ext == 'pdf':
                return self.extract_from_pdf(tmp_path)
            elif file_ext in ['png', 'jpg', 'jpeg']:
                return self.extract_from_image(tmp_path)
            else:
                raise ValueError(f"Unsupported file type: {file_ext}")
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


# Singleton instance
ocr_service = OCRService()
