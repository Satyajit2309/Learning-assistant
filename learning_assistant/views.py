"""
Learning Assistant Views

Views for the main learning features: Summary, Quiz, Flashcards, Flowcharts, Analytics.
"""

import json
import time
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings

from .models import Document, Summary
from .services import DocumentProcessor, VectorStoreService
from .agents import get_agent


def home(request):
    """Home page view with feature cards"""
    return render(request, 'pages/home.html')


@login_required
def summaries(request):
    """AI Summary hub - upload documents and generate learning materials"""
    # Get user's documents
    documents = Document.objects.filter(user=request.user).order_by('-created_at')[:10]
    
    context = {
        'documents': documents,
        'max_upload_size_mb': settings.MAX_UPLOAD_SIZE // (1024 * 1024),
        'allowed_extensions': ', '.join(settings.ALLOWED_UPLOAD_EXTENSIONS),
    }
    return render(request, 'pages/summary.html', context)


@login_required
@require_http_methods(["POST"])
def upload_document(request):
    """Handle document upload via AJAX"""
    try:
        if 'file' not in request.FILES:
            return JsonResponse({
                'success': False,
                'error': 'No file uploaded'
            }, status=400)
        
        uploaded_file = request.FILES['file']
        
        # Validate file size
        if uploaded_file.size > settings.MAX_UPLOAD_SIZE:
            max_mb = settings.MAX_UPLOAD_SIZE // (1024 * 1024)
            return JsonResponse({
                'success': False,
                'error': f'File too large. Maximum size is {max_mb}MB.'
            }, status=400)
        
        # Process the document
        processor = DocumentProcessor()
        file_type = processor.get_file_type(uploaded_file.name)
        
        if not file_type:
            return JsonResponse({
                'success': False,
                'error': f'Unsupported file type. Allowed: {", ".join(settings.ALLOWED_UPLOAD_EXTENSIONS)}'
            }, status=400)
        
        # Extract text
        extraction_result = processor.extract_text(uploaded_file)
        
        if not extraction_result['success']:
            return JsonResponse({
                'success': False,
                'error': extraction_result['error']
            }, status=400)
        
        # Reset file position for saving
        uploaded_file.seek(0)
        
        # Create document record
        document = Document.objects.create(
            user=request.user,
            title=request.POST.get('title', uploaded_file.name),
            file=uploaded_file,
            file_type=file_type,
            file_size=uploaded_file.size,
            extracted_text=extraction_result['text'],
            page_count=extraction_result.get('page_count', 1),
        )
        
        # Note: Skipping FAISS indexing to save API quota
        # The raw extracted text will be used directly for generation
        # FAISS can be enabled later for large documents by uncommenting below:
        # vector_service = VectorStoreService()
        # index_result = vector_service.add_document(
        #     document.vector_doc_id,
        #     extraction_result['text']
        # )
        # if index_result['success']:
        #     document.is_indexed = True
        #     document.chunk_count = index_result['chunk_count']
        #     document.save()
        
        return JsonResponse({
            'success': True,
            'document': {
                'id': str(document.id),
                'title': document.title,
                'file_type': document.file_type,
                'page_count': document.page_count,
                'is_indexed': document.is_indexed,
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def generate_summary(request):
    """Generate summary for a document via AJAX"""
    try:
        data = json.loads(request.body)
        document_id = data.get('document_id')
        summary_type = data.get('summary_type', 'detailed')
        
        if not document_id:
            return JsonResponse({
                'success': False,
                'error': 'Document ID required'
            }, status=400)
        
        # Get document
        document = get_object_or_404(Document, id=document_id, user=request.user)
        
        # Check if API key is configured
        if not settings.GEMINI_API_KEY:
            return JsonResponse({
                'success': False,
                'error': 'AI features not configured. Please set GEMINI_API_KEY.'
            }, status=500)
        
        # Use extracted text directly (saves API quota vs FAISS embeddings)
        context = document.extracted_text
        
        # Limit context size to avoid hitting token limits (roughly 8000 chars ~ 2000 tokens)
        MAX_CONTEXT_CHARS = 8000
        if len(context) > MAX_CONTEXT_CHARS:
            context = context[:MAX_CONTEXT_CHARS] + "\n\n[... Content truncated for processing ...]"        
        if not context:
            return JsonResponse({
                'success': False,
                'error': 'No content available for this document'
            }, status=400)
        
        # Generate summary
        try:
            start_time = time.time()
            agent = get_agent('summary')
            result = agent.generate_sync(context, summary_type=summary_type)
            generation_time = time.time() - start_time
        except ValueError as e:
            # API key not configured
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
        except Exception as e:
            # Other generation errors
            import traceback
            print(traceback.format_exc())  # Log to server console
            return JsonResponse({
                'success': False,
                'error': f'Generation failed: {str(e)}'
            }, status=500)
        
        if not result.get('success'):
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Failed to generate summary')
            }, status=500)
        
        # Save summary
        summary = Summary.objects.create(
            document=document,
            content=result['summary'],
            summary_type=summary_type,
            word_count=result.get('word_count', 0),
            model_used=agent.model_name,
            generation_time=generation_time,
        )
        
        return JsonResponse({
            'success': True,
            'summary': {
                'id': str(summary.id),
                'content': summary.content,
                'type': summary.summary_type,
                'word_count': summary.word_count,
                'generation_time': round(generation_time, 2),
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def document_detail(request, document_id):
    """View a specific document and its summaries"""
    document = get_object_or_404(Document, id=document_id, user=request.user)
    summaries = document.summaries.all()
    
    context = {
        'document': document,
        'summaries': summaries,
    }
    return render(request, 'pages/document_detail.html', context)


@login_required
@require_http_methods(["DELETE"])
def delete_document(request, document_id):
    """Delete a document"""
    document = get_object_or_404(Document, id=document_id, user=request.user)
    
    # Delete from vector store
    vector_service = VectorStoreService()
    vector_service.delete_document(document.vector_doc_id)
    
    # Delete file and record
    if document.file:
        document.file.delete(save=False)
    document.delete()
    
    return JsonResponse({'success': True})


# Placeholder views for other features
def quizzes(request):
    """Quiz generation and taking page"""
    context = {
        'title': 'Quiz Generation',
        'description': 'Auto-generate quizzes from your materials with multiple question types and instant feedback.'
    }
    return render(request, 'pages/placeholder.html', context)


def flashcards(request):
    """Flashcard study page"""
    context = {
        'title': 'Smart Flashcards',
        'description': 'Create flashcards automatically from key concepts with spaced repetition for optimal learning.'
    }
    return render(request, 'pages/placeholder.html', context)


def flowcharts(request):
    """Concept flowcharts page"""
    context = {
        'title': 'Concept Flowcharts',
        'description': 'Visualize complex topics with auto-generated mind maps and flowcharts.'
    }
    return render(request, 'pages/placeholder.html', context)


def analytics(request):
    """Progress analytics dashboard"""
    context = {
        'title': 'Progress Analytics',
        'description': 'Track your learning journey with detailed analytics and identify areas needing focus.'
    }
    return render(request, 'pages/placeholder.html', context)
