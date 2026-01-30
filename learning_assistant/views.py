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
from django.utils import timezone

from .models import Document, Summary, Quiz, QuizQuestion, FlashcardSet, Flashcard, Flowchart, FlowchartNode, FlowchartEdge
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


# ========== Quiz Views ==========

@login_required
def quizzes(request):
    """Quiz hub - select documents and generate quizzes"""
    # Get user's documents
    documents = Document.objects.filter(user=request.user).order_by('-created_at')[:10]
    
    # Get user's recent quizzes
    recent_quizzes = Quiz.objects.filter(user=request.user).order_by('-created_at')[:5]
    
    context = {
        'documents': documents,
        'recent_quizzes': recent_quizzes,
    }
    return render(request, 'pages/quiz.html', context)


@login_required
@require_http_methods(["POST"])
def generate_quiz(request):
    """Generate a quiz from a document via AJAX"""
    try:
        data = json.loads(request.body)
        document_id = data.get('document_id')
        difficulty = data.get('difficulty', 'medium')
        question_count = int(data.get('question_count', 5))
        
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
        
        # Get document content
        context = document.extracted_text
        
        # Limit context size
        MAX_CONTEXT_CHARS = 8000
        if len(context) > MAX_CONTEXT_CHARS:
            context = context[:MAX_CONTEXT_CHARS] + "\n\n[... Content truncated for processing ...]"
        
        if not context:
            return JsonResponse({
                'success': False,
                'error': 'No content available for this document'
            }, status=400)
        
        # Generate quiz
        try:
            start_time = time.time()
            agent = get_agent('quiz')
            result = agent.generate_sync(
                context, 
                difficulty=difficulty, 
                question_count=question_count
            )
            generation_time = time.time() - start_time
        except ValueError as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return JsonResponse({
                'success': False,
                'error': f'Generation failed: {str(e)}'
            }, status=500)
        
        if not result.get('success'):
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Failed to generate quiz')
            }, status=500)
        
        # Create quiz and questions
        quiz = Quiz.objects.create(
            document=document,
            user=request.user,
            title=f"Quiz on {document.title}",
            difficulty=difficulty,
            question_count=len(result['questions']),
            model_used=agent.model_name,
            generation_time=generation_time,
        )
        
        # Create questions
        for q_data in result['questions']:
            QuizQuestion.objects.create(
                quiz=quiz,
                question_text=q_data['question'],
                option_a=q_data['option_a'],
                option_b=q_data['option_b'],
                option_c=q_data['option_c'],
                option_d=q_data['option_d'],
                correct_answer=q_data['correct_answer'],
                explanation=q_data.get('explanation', ''),
                order=q_data.get('order', 0),
            )
        
        return JsonResponse({
            'success': True,
            'quiz': {
                'id': str(quiz.id),
                'title': quiz.title,
                'difficulty': quiz.difficulty,
                'question_count': quiz.question_count,
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
def take_quiz(request, quiz_id):
    """Display a quiz for the user to take"""
    quiz = get_object_or_404(Quiz, id=quiz_id, user=request.user)
    
    # If already completed, redirect to results
    if quiz.is_completed:
        return redirect('quiz_result', quiz_id=quiz.id)
    
    questions = quiz.questions.all()
    
    context = {
        'quiz': quiz,
        'questions': questions,
    }
    return render(request, 'pages/take_quiz.html', context)


@login_required
@require_http_methods(["POST"])
def submit_quiz(request, quiz_id):
    """Submit quiz answers and calculate score"""
    try:
        quiz = get_object_or_404(Quiz, id=quiz_id, user=request.user)
        
        if quiz.is_completed:
            return JsonResponse({
                'success': False,
                'error': 'Quiz already completed'
            }, status=400)
        
        data = json.loads(request.body)
        answers = data.get('answers', {})
        
        # Process answers
        correct_count = 0
        questions = quiz.questions.all()
        
        for question in questions:
            user_answer = answers.get(str(question.id), '').upper()
            if user_answer in ['A', 'B', 'C', 'D']:
                question.user_answer = user_answer
                question.save()
                
                if user_answer == question.correct_answer:
                    correct_count += 1
        
        # Update quiz
        quiz.score = correct_count
        quiz.is_completed = True
        quiz.completed_at = timezone.now()
        
        # Calculate XP
        xp_earned = quiz.calculate_xp()
        quiz.xp_earned = xp_earned
        quiz.save()
        
        # Update user profile
        profile = request.user.profile
        profile.add_xp(xp_earned)
        profile.total_quizzes_taken += 1
        if quiz.percentage_score >= 70:  # Pass threshold
            profile.total_quizzes_passed += 1
        profile.total_questions_answered += quiz.question_count
        profile.total_correct_answers += correct_count
        profile.update_streak()
        profile.save()
        
        return JsonResponse({
            'success': True,
            'result': {
                'quiz_id': str(quiz.id),
                'score': correct_count,
                'total': quiz.question_count,
                'percentage': quiz.percentage_score,
                'xp_earned': xp_earned,
                'passed': quiz.percentage_score >= 70,
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
def quiz_result(request, quiz_id):
    """Display quiz results"""
    quiz = get_object_or_404(Quiz, id=quiz_id, user=request.user)
    
    if not quiz.is_completed:
        return redirect('take_quiz', quiz_id=quiz.id)
    
    questions = quiz.questions.all()
    
    context = {
        'quiz': quiz,
        'questions': questions,
    }
    return render(request, 'pages/quiz_result.html', context)


# ========== Flashcard Views ==========

@login_required
def flashcards(request):
    """Flashcard hub - select documents and generate flashcards"""
    # Get user's documents
    documents = Document.objects.filter(user=request.user).order_by('-created_at')[:10]
    
    # Get user's recent flashcard sets
    recent_sets = FlashcardSet.objects.filter(user=request.user).order_by('-created_at')[:5]
    
    context = {
        'documents': documents,
        'recent_sets': recent_sets,
    }
    return render(request, 'pages/flashcards.html', context)


@login_required
@require_http_methods(["POST"])
def generate_flashcards(request):
    """Generate flashcards from a document via AJAX"""
    try:
        data = json.loads(request.body)
        document_id = data.get('document_id')
        card_count = int(data.get('card_count', 10))
        
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
        
        # Get document content
        context = document.extracted_text
        
        # Limit context size
        MAX_CONTEXT_CHARS = 10000  # Slightly larger for better flashcard coverage
        if len(context) > MAX_CONTEXT_CHARS:
            context = context[:MAX_CONTEXT_CHARS] + "\n\n[... Content truncated for processing ...]"
        
        if not context:
            return JsonResponse({
                'success': False,
                'error': 'No content available for this document'
            }, status=400)
        
        # Generate flashcards
        try:
            start_time = time.time()
            agent = get_agent('flashcard')
            result = agent.generate_sync(
                context, 
                card_count=card_count
            )
            generation_time = time.time() - start_time
        except ValueError as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return JsonResponse({
                'success': False,
                'error': f'Generation failed: {str(e)}'
            }, status=500)
        
        if not result.get('success'):
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Failed to generate flashcards')
            }, status=500)
        
        # Create flashcard set and cards
        flashcard_set = FlashcardSet.objects.create(
            document=document,
            user=request.user,
            title=f"Flashcards: {document.title}",
            card_count=len(result['flashcards']),
            model_used=agent.model_name,
            generation_time=generation_time,
        )
        
        # Create flashcards
        for card_data in result['flashcards']:
            Flashcard.objects.create(
                flashcard_set=flashcard_set,
                front=card_data['front'],
                back=card_data['back'],
                priority=card_data.get('priority', 3),
                order=card_data.get('order', 0),
            )
        
        return JsonResponse({
            'success': True,
            'flashcard_set': {
                'id': str(flashcard_set.id),
                'title': flashcard_set.title,
                'card_count': flashcard_set.card_count,
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
def study_flashcards(request, set_id):
    """Display flashcards for studying"""
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user)
    cards = flashcard_set.cards.all()
    
    # Update last studied time
    flashcard_set.last_studied_at = timezone.now()
    flashcard_set.save(update_fields=['last_studied_at'])
    
    context = {
        'flashcard_set': flashcard_set,
        'cards': cards,
        'cards_json': json.dumps([{
            'id': str(card.id),
            'front': card.front,
            'back': card.back,
            'priority': card.priority,
            'is_mastered': card.is_mastered,
            'order': card.order,
        } for card in cards]),
    }
    return render(request, 'pages/study_flashcards.html', context)


@login_required
@require_http_methods(["POST"])
def toggle_flashcard_mastery(request, card_id):
    """Toggle the mastered status of a flashcard"""
    try:
        card = get_object_or_404(Flashcard, id=card_id, flashcard_set__user=request.user)
        card.toggle_mastered()
        
        return JsonResponse({
            'success': True,
            'is_mastered': card.is_mastered,
            'set_progress': card.flashcard_set.progress_percentage,
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ========== Flowchart Views ==========

@login_required
def flowcharts(request):
    """Flowchart hub - select documents and generate flowcharts"""
    # Get user's documents
    documents = Document.objects.filter(user=request.user).order_by('-created_at')[:10]
    
    # Get user's recent flowcharts
    recent_flowcharts = Flowchart.objects.filter(user=request.user).order_by('-created_at')[:5]
    
    context = {
        'documents': documents,
        'recent_flowcharts': recent_flowcharts,
    }
    return render(request, 'pages/flowchart.html', context)


@login_required
@require_http_methods(["POST"])
def generate_flowchart(request):
    """Generate a flowchart from a document via AJAX"""
    try:
        data = json.loads(request.body)
        document_id = data.get('document_id')
        detail_level = data.get('detail_level', 'medium')
        
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
        
        # Get document content
        context = document.extracted_text
        
        # Limit context size
        MAX_CONTEXT_CHARS = 10000
        if len(context) > MAX_CONTEXT_CHARS:
            context = context[:MAX_CONTEXT_CHARS] + "\n\n[... Content truncated for processing ...]"
        
        if not context:
            return JsonResponse({
                'success': False,
                'error': 'No content available for this document'
            }, status=400)
        
        # Generate flowcharts
        try:
            start_time = time.time()
            agent = get_agent('flowchart')
            result = agent.generate_sync(
                context, 
                detail_level=detail_level
            )
            generation_time = time.time() - start_time
        except ValueError as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return JsonResponse({
                'success': False,
                'error': f'Generation failed: {str(e)}'
            }, status=500)
        
        if not result.get('success'):
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Failed to generate flowcharts')
            }, status=500)
        
        created_flowcharts = []
        
        # Create flowcharts
        for fc_data in result.get('flowcharts', []):
            flowchart = Flowchart.objects.create(
                document=document,
                user=request.user,
                title=fc_data.get('title', f"Flowchart: {document.title}"),
                description=fc_data.get('description', ''),
                node_count=fc_data.get('node_count', 0),
                edge_count=fc_data.get('edge_count', 0),
                model_used=agent.model_name,
                generation_time=generation_time,
            )
            
            # Create nodes
            for i, node_data in enumerate(fc_data['nodes']):
                FlowchartNode.objects.create(
                    flowchart=flowchart,
                    node_id=node_data['id'],
                    label=node_data['label'],
                    node_type=node_data['type'],
                    order=i,
                )
            
            # Create edges
            for edge_data in fc_data['edges']:
                FlowchartEdge.objects.create(
                    flowchart=flowchart,
                    from_node=edge_data['from'],
                    to_node=edge_data['to'],
                    label=edge_data.get('label', ''),
                )
            
            created_flowcharts.append({
                'id': str(flowchart.id),
                'title': flowchart.title,
                'node_count': flowchart.node_count
            })
        
        return JsonResponse({
            'success': True,
            'count': len(created_flowcharts),
            'flowcharts': created_flowcharts
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
def view_flowchart(request, flowchart_id):
    """Display an interactive flowchart"""
    flowchart = get_object_or_404(Flowchart, id=flowchart_id, user=request.user)
    nodes = flowchart.nodes.all()
    edges = flowchart.edges.all()
    
    # Prepare JSON data for JavaScript visualization
    nodes_data = [{
        'id': node.node_id,
        'label': node.label,
        'type': node.node_type,
        'x': node.position_x,
        'y': node.position_y,
    } for node in nodes]
    
    edges_data = [{
        'from': edge.from_node,
        'to': edge.to_node,
        'label': edge.label,
    } for edge in edges]
    
    context = {
        'flowchart': flowchart,
        'nodes': nodes,
        'edges': edges,
        'nodes_json': nodes_data,
        'edges_json': edges_data,
    }
    return render(request, 'pages/view_flowchart.html', context)


# ========== Other Feature Placeholders ==========

def analytics(request):
    """Progress analytics dashboard"""
    context = {
        'title': 'Progress Analytics',
        'description': 'Track your learning journey with detailed analytics and identify areas needing focus.'
    }
    return render(request, 'pages/placeholder.html', context)
