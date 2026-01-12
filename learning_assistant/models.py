"""
Learning Assistant Models

Models for documents, summaries, and other learning content.
"""

import uuid
from django.db import models
from django.conf import settings


def document_upload_path(instance, filename):
    """Generate upload path for documents."""
    return f'documents/{instance.user.id}/{filename}'


class Document(models.Model):
    """
    Model for storing uploaded documents.
    
    Each document can have multiple summaries, quizzes, flashcards, etc.
    generated from it.
    """
    
    FILE_TYPE_CHOICES = [
        ('pdf', 'PDF Document'),
        ('word', 'Word Document'),
        ('text', 'Text File'),
        ('image', 'Image'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to=document_upload_path)
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES)
    file_size = models.PositiveIntegerField(default=0)  # in bytes
    
    # Extracted content
    extracted_text = models.TextField(blank=True)
    page_count = models.PositiveIntegerField(default=0)
    
    # Vector store info
    is_indexed = models.BooleanField(default=False)
    chunk_count = models.PositiveIntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'
    
    def __str__(self):
        return self.title
    
    @property
    def vector_doc_id(self):
        """Get the document ID used for vector storage."""
        return str(self.id)
    
    def get_file_size_display(self):
        """Return human-readable file size."""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


class Summary(models.Model):
    """
    Model for storing generated summaries.
    """
    
    SUMMARY_TYPE_CHOICES = [
        ('brief', 'Brief Summary'),
        ('detailed', 'Detailed Summary'),
        ('bullet', 'Bullet Points'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='summaries'
    )
    
    content = models.TextField()
    summary_type = models.CharField(max_length=20, choices=SUMMARY_TYPE_CHOICES)
    word_count = models.PositiveIntegerField(default=0)
    
    # Generation metadata
    model_used = models.CharField(max_length=100, blank=True)
    generation_time = models.FloatField(default=0)  # in seconds
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Summary'
        verbose_name_plural = 'Summaries'
    
    def __str__(self):
        return f"{self.summary_type.title()} summary of {self.document.title}"
