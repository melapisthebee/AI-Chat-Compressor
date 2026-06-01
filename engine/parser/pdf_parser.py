"""
PDF Parser Module - Dedicated parsing logic for PDF documents
"""

from typing import List, Dict
from pypdf import PdfReader

from .base_parser import BaseParser


class PDFParser(BaseParser):
    """Parser specifically designed for PDF files."""
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = ['.pdf']
        
    def _extract_text_from_pdf(self, filepath: str) -> str:
        """Extracts raw text strings across all pages of a PDF file."""
        try:
            reader = PdfReader(filepath)
            text_content = []
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text_content.append(extracted)
            return "\n".join(text_content)
        except Exception as e:
            raise RuntimeError(f"Failed to extract text from PDF '{filepath}': {type(e).__name__}: {str(e)}")
    
    def parse(self, filepath: str) -> List[Dict[str, str]]:
        """
        Parse PDF file extracting and processing text content.
        
        Args:
            filepath: Path to the PDF file
            
        Returns:
            List of normalized message dictionaries with 'role' and 'content' keys
        """
        # Step 1: Extract raw text from PDF
        try:
            raw_text = self._extract_text_from_pdf(filepath)
        except Exception as e:
            raise RuntimeError(f"Error extracting text from PDF {filepath}: {str(e)}")
        
        if not raw_text.strip():
            return [{"role": "user", "content": self._clean_and_truncate_content("PDF file contained no extractable text.", skip_truncation=True)}]
        
        # Step 2: Apply thought block removal and credential masking
        raw_text = self._strip_thought_blocks_safely(raw_text)

        # Step 3: Check for role-based structure (common in chat exports formatted as PDFs)
        import re
        pattern = re.compile(r'(?mi)^(###\s+)?(user|assistant|ai|system|human|bot):\s*')
        all_matches = list(pattern.finditer(raw_text))

        if not all_matches:
            # No role markers - treat entire PDF content as a single user message
            # For PDFs, skip truncation to preserve full document context
            cleaned_content = self._clean_and_truncate_content(raw_text.strip(), skip_truncation=True)
            return [{"role": "user", "content": cleaned_content}]

        # Step 4: Parse role-based structure if detected
        cleaned_messages = []
        
        for i in range(len(all_matches)):
            start_idx = all_matches[i].end()
            end_idx = all_matches[i+1].start() if i + 1 < len(all_matches) else len(raw_text)
            
            role = all_matches[i].group(2).lower()
            # Normalize role names
            if role in ('human', 'user'): 
                role = 'user'
            elif role in ('ai', 'bot', 'assistant'): 
                role = 'assistant'
                
            msg_content = raw_text[start_idx:end_idx].strip()
            
            # For PDFs, generally skip truncation to preserve full document context
            msg_content = self._clean_and_truncate_content(msg_content, skip_truncation=True)
            
            if msg_content:
                cleaned_messages.append({"role": role, "content": msg_content})

        if not cleaned_messages:
            # Fallback: entire PDF as single user message
            cleaned_content = self._clean_and_truncate_content(raw_text.strip(), skip_truncation=True)
            return [{"role": "user", "content": cleaned_content}]

        return cleaned_messages
