"""
Services Package

This package contains service classes for document processing, 
vector storage, and other backend operations.

Services are designed to be:
- Stateless and reusable
- Independent of Django views
- Easily testable
"""

from .document_processor import DocumentProcessor
from .vector_store import VectorStoreService

__all__ = [
    'DocumentProcessor',
    'VectorStoreService',
]
