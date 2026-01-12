"""
Vector Store Service

Manages FAISS vector database for document embeddings.
Provides storage and retrieval of document vectors for RAG.
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from django.conf import settings

import faiss
import numpy as np

# Langchain for embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter


class VectorStoreService:
    """
    Service for managing FAISS vector storage.
    
    Handles:
    - Creating embeddings from text
    - Storing vectors in FAISS index
    - Retrieving relevant chunks for RAG
    
    Usage:
        service = VectorStoreService()
        service.add_document(doc_id, text)
        chunks = service.search(doc_id, query, top_k=5)
    """
    
    # Embedding model configuration
    EMBEDDING_MODEL = "models/embedding-001"
    
    # Text splitting configuration
    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 200
    
    def __init__(self, store_dir: Optional[str] = None):
        """
        Initialize the vector store service.
        
        Args:
            store_dir: Directory to store vector indices (default: settings.VECTOR_STORE_DIR)
        """
        self.store_dir = Path(store_dir or getattr(settings, 'VECTOR_STORE_DIR', 'vector_store'))
        self.store_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize embeddings model
        api_key = getattr(settings, 'GEMINI_API_KEY', None)
        if api_key:
            self.embeddings = GoogleGenerativeAIEmbeddings(
                model=self.EMBEDDING_MODEL,
                google_api_key=api_key,
            )
        else:
            self.embeddings = None
        
        # Text splitter for chunking documents
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.CHUNK_SIZE,
            chunk_overlap=self.CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
    
    def _get_index_path(self, doc_id: str) -> Path:
        """Get the path for a document's FAISS index."""
        return self.store_dir / f"{doc_id}.index"
    
    def _get_metadata_path(self, doc_id: str) -> Path:
        """Get the path for a document's metadata/chunks."""
        return self.store_dir / f"{doc_id}.json"
    
    def add_document(self, doc_id: str, text: str) -> Dict[str, Any]:
        """
        Process document text, create embeddings, and store in FAISS.
        
        Args:
            doc_id: Unique identifier for the document
            text: Full text content of the document
            
        Returns:
            Dictionary with 'success', 'chunk_count', 'error'
        """
        if not self.embeddings:
            return {
                'success': False,
                'chunk_count': 0,
                'error': 'Embeddings model not configured. Check GEMINI_API_KEY.',
            }
        
        try:
            # Split text into chunks
            chunks = self.text_splitter.split_text(text)
            
            if not chunks:
                return {
                    'success': False,
                    'chunk_count': 0,
                    'error': 'No text chunks created from document.',
                }
            
            # Create embeddings for all chunks
            embeddings_list = self.embeddings.embed_documents(chunks)
            embeddings_array = np.array(embeddings_list).astype('float32')
            
            # Create FAISS index
            dimension = embeddings_array.shape[1]
            index = faiss.IndexFlatL2(dimension)
            index.add(embeddings_array)
            
            # Save index
            index_path = self._get_index_path(doc_id)
            faiss.write_index(index, str(index_path))
            
            # Save chunks metadata
            metadata_path = self._get_metadata_path(doc_id)
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'chunks': chunks,
                    'chunk_count': len(chunks),
                    'dimension': dimension,
                }, f, ensure_ascii=False)
            
            return {
                'success': True,
                'chunk_count': len(chunks),
                'error': None,
            }
            
        except Exception as e:
            return {
                'success': False,
                'chunk_count': 0,
                'error': str(e),
            }
    
    def search(
        self, 
        doc_id: str, 
        query: str, 
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Search for relevant chunks in a document.
        
        Args:
            doc_id: Document identifier
            query: Search query
            top_k: Number of top results to return
            
        Returns:
            Dictionary with 'chunks', 'scores', 'success', 'error'
        """
        if not self.embeddings:
            return {
                'chunks': [],
                'scores': [],
                'success': False,
                'error': 'Embeddings model not configured.',
            }
        
        try:
            index_path = self._get_index_path(doc_id)
            metadata_path = self._get_metadata_path(doc_id)
            
            if not index_path.exists() or not metadata_path.exists():
                return {
                    'chunks': [],
                    'scores': [],
                    'success': False,
                    'error': f'Document index not found for: {doc_id}',
                }
            
            # Load index and metadata
            index = faiss.read_index(str(index_path))
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            chunks = metadata['chunks']
            
            # Create query embedding
            query_embedding = self.embeddings.embed_query(query)
            query_array = np.array([query_embedding]).astype('float32')
            
            # Search
            k = min(top_k, len(chunks))
            distances, indices = index.search(query_array, k)
            
            # Get results
            result_chunks = [chunks[i] for i in indices[0] if i < len(chunks)]
            result_scores = distances[0].tolist()
            
            return {
                'chunks': result_chunks,
                'scores': result_scores,
                'success': True,
                'error': None,
            }
            
        except Exception as e:
            return {
                'chunks': [],
                'scores': [],
                'success': False,
                'error': str(e),
            }
    
    def get_all_chunks(self, doc_id: str) -> Dict[str, Any]:
        """
        Get all chunks for a document (for complete context).
        
        Args:
            doc_id: Document identifier
            
        Returns:
            Dictionary with 'chunks', 'success', 'error'
        """
        try:
            metadata_path = self._get_metadata_path(doc_id)
            
            if not metadata_path.exists():
                return {
                    'chunks': [],
                    'success': False,
                    'error': f'Document not found: {doc_id}',
                }
            
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            return {
                'chunks': metadata['chunks'],
                'success': True,
                'error': None,
            }
            
        except Exception as e:
            return {
                'chunks': [],
                'success': False,
                'error': str(e),
            }
    
    def get_context_for_generation(
        self, 
        doc_id: str, 
        query: Optional[str] = None,
        max_chunks: int = 10
    ) -> str:
        """
        Get combined context from document for AI generation.
        
        If query is provided, uses semantic search.
        Otherwise, returns first N chunks.
        
        Args:
            doc_id: Document identifier
            query: Optional search query for relevant context
            max_chunks: Maximum number of chunks to include
            
        Returns:
            Combined text context
        """
        if query:
            result = self.search(doc_id, query, top_k=max_chunks)
        else:
            result = self.get_all_chunks(doc_id)
            if result['success']:
                result['chunks'] = result['chunks'][:max_chunks]
        
        if not result['success'] or not result['chunks']:
            return ""
        
        return "\n\n---\n\n".join(result['chunks'])
    
    def delete_document(self, doc_id: str) -> bool:
        """
        Delete a document's vector index and metadata.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            index_path = self._get_index_path(doc_id)
            metadata_path = self._get_metadata_path(doc_id)
            
            if index_path.exists():
                index_path.unlink()
            if metadata_path.exists():
                metadata_path.unlink()
            
            return True
        except Exception:
            return False
    
    def document_exists(self, doc_id: str) -> bool:
        """Check if a document has been indexed."""
        return self._get_index_path(doc_id).exists()
