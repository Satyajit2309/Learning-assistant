"""
Learning Assistant Views

Views for the main learning features: Summary, Quiz, Flashcards, Flowcharts, Evaluations, Analytics.
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

from .models import Document, Summary, Quiz, QuizQuestion, FlashcardSet, Flashcard, Flowchart, FlowchartNode, FlowchartEdge, AnswerSheetEvaluation, EvaluatedQuestion, Podcast, ChatSession, ChatMessage
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

@login_required
def analytics(request):
    """
    Progress analytics dashboard.
    
    Aggregates data across all features to give the user
    a comprehensive view of their learning journey.
    """
    from django.db.models import Avg, Count, Sum, Q
    from django.db.models.functions import TruncDate
    import json as json_lib
    from datetime import timedelta
    
    user = request.user
    profile = user.profile
    
    # ── Overview Stats ──
    total_documents = Document.objects.filter(user=user).count()
    total_summaries = Summary.objects.filter(document__user=user).count()
    total_quizzes = Quiz.objects.filter(user=user, is_completed=True).count()
    total_flashcard_sets = FlashcardSet.objects.filter(document__user=user).count()
    total_flowcharts = Flowchart.objects.filter(document__user=user).count()
    total_podcasts = Podcast.objects.filter(document__user=user).count()
    total_evaluations = AnswerSheetEvaluation.objects.filter(user=user, is_evaluated=True).count()
    total_chats = ChatSession.objects.filter(user=user).count()
    
    # ── Quiz Performance ──
    completed_quizzes = Quiz.objects.filter(
        user=user, is_completed=True
    ).order_by('completed_at')
    
    quiz_scores = []
    quiz_labels = []
    quiz_difficulties = {'easy': 0, 'medium': 0, 'hard': 0}
    
    for q in completed_quizzes:
        pct = q.percentage_score
        quiz_scores.append(pct)
        label = q.completed_at.strftime('%b %d') if q.completed_at else q.created_at.strftime('%b %d')
        quiz_labels.append(label)
        if q.difficulty in quiz_difficulties:
            quiz_difficulties[q.difficulty] += 1
    
    avg_quiz_score = round(sum(quiz_scores) / len(quiz_scores), 1) if quiz_scores else 0
    
    # ── Flashcard Mastery ──
    flashcard_sets_data = FlashcardSet.objects.filter(
        document__user=user
    ).annotate(
        total_cards=Count('cards'),
        mastered_cards=Count('cards', filter=Q(cards__is_mastered=True)),
    )
    
    fc_names = []
    fc_mastered = []
    fc_remaining = []
    total_cards_all = 0
    total_mastered_all = 0
    
    for fs in flashcard_sets_data:
        title = fs.title[:20] + '...' if len(fs.title) > 20 else fs.title
        fc_names.append(title)
        fc_mastered.append(fs.mastered_cards)
        fc_remaining.append(fs.total_cards - fs.mastered_cards)
        total_cards_all += fs.total_cards
        total_mastered_all += fs.mastered_cards
    
    flashcard_mastery_pct = round((total_mastered_all / total_cards_all) * 100, 1) if total_cards_all > 0 else 0
    
    # ── Evaluation Scores ──
    evaluations_data = AnswerSheetEvaluation.objects.filter(
        user=user, is_evaluated=True
    ).order_by('created_at')
    
    eval_scores = []
    eval_labels = []
    for ev in evaluations_data:
        score = ev.overall_score if hasattr(ev, 'overall_score') and ev.overall_score else 0
        eval_scores.append(round(score, 1))
        eval_labels.append(ev.created_at.strftime('%b %d'))
    
    avg_eval_score = round(sum(eval_scores) / len(eval_scores), 1) if eval_scores else 0
    
    # ── Activity over last 30 days ──
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    # Quizzes per day
    quiz_activity = (
        Quiz.objects.filter(user=user, created_at__gte=thirty_days_ago)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    
    # Documents per day
    doc_activity = (
        Document.objects.filter(user=user, created_at__gte=thirty_days_ago)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    
    # Build a 30-day timeline
    activity_labels = []
    activity_quiz_counts = []
    activity_doc_counts = []
    
    quiz_by_day = {item['day']: item['count'] for item in quiz_activity}
    doc_by_day = {item['day']: item['count'] for item in doc_activity}
    
    for i in range(30):
        day = (timezone.now() - timedelta(days=29 - i)).date()
        activity_labels.append(day.strftime('%b %d'))
        activity_quiz_counts.append(quiz_by_day.get(day, 0))
        activity_doc_counts.append(doc_by_day.get(day, 0))
    
    # ── Feature Usage Breakdown ──
    feature_usage = {
        'Summaries': total_summaries,
        'Quizzes': total_quizzes,
        'Flashcards': total_flashcard_sets,
        'Flowcharts': total_flowcharts,
        'Podcasts': total_podcasts,
        'Evaluations': total_evaluations,
        'Chat Sessions': total_chats,
    }
    
    # ── XP & Level ──
    xp_for_next = ((profile.level) * 1000) - profile.xp_points
    xp_progress_pct = round((profile.xp_points % 1000) / 10, 1)
    
    context = {
        # Overview
        'total_documents': total_documents,
        'total_quizzes': total_quizzes,
        'total_flashcard_sets': total_flashcard_sets,
        'total_evaluations': total_evaluations,
        'total_chats': total_chats,
        
        # Profile stats
        'profile': profile,
        'xp_for_next': max(xp_for_next, 0),
        'xp_progress_pct': xp_progress_pct,
        
        # Quiz charts (JSON)
        'quiz_scores_json': json_lib.dumps(quiz_scores),
        'quiz_labels_json': json_lib.dumps(quiz_labels),
        'quiz_difficulties_json': json_lib.dumps(quiz_difficulties),
        'avg_quiz_score': avg_quiz_score,
        
        # Flashcard charts (JSON)
        'fc_names_json': json_lib.dumps(fc_names),
        'fc_mastered_json': json_lib.dumps(fc_mastered),
        'fc_remaining_json': json_lib.dumps(fc_remaining),
        'flashcard_mastery_pct': flashcard_mastery_pct,
        'total_cards_all': total_cards_all,
        'total_mastered_all': total_mastered_all,
        
        # Evaluation charts (JSON)
        'eval_scores_json': json_lib.dumps(eval_scores),
        'eval_labels_json': json_lib.dumps(eval_labels),
        'avg_eval_score': avg_eval_score,
        
        # Activity timeline (JSON)
        'activity_labels_json': json_lib.dumps(activity_labels),
        'activity_quiz_json': json_lib.dumps(activity_quiz_counts),
        'activity_doc_json': json_lib.dumps(activity_doc_counts),
        
        # Feature usage (JSON)
        'feature_usage_json': json_lib.dumps(feature_usage),
    }
    return render(request, 'pages/analytics.html', context)


# ========== Answer Sheet Evaluation Views ==========

@login_required
def evaluations(request):
    """Evaluation hub - upload answer sheets for AI evaluation"""
    return render(request, 'pages/evaluations.html')


@login_required
@require_http_methods(["POST"])
def upload_answer_sheet(request):
    """Upload answer sheet image for AI evaluation"""
    try:
        if 'file' not in request.FILES:
            return JsonResponse({
                'success': False,
                'error': 'No file uploaded'
            }, status=400)
        
        uploaded_file = request.FILES['file']
        title = request.POST.get('title', uploaded_file.name)
        
        # Validate file type - only images for Gemini Vision
        file_ext = uploaded_file.name.lower().split('.')[-1]
        if file_ext not in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
            return JsonResponse({
                'success': False,
                'error': 'Only image files (PNG, JPG, GIF, WebP) are supported'
            }, status=400)
        
        # Validate file size (max 10MB for vision API)
        max_size = 10 * 1024 * 1024
        if uploaded_file.size > max_size:
            return JsonResponse({
                'success': False,
                'error': 'File too large. Maximum size is 10MB.'
            }, status=400)
        
        # Create evaluation record and save file
        evaluation = AnswerSheetEvaluation.objects.create(
            user=request.user,
            title=title,
            answer_sheet_file=uploaded_file,
        )
        
        return JsonResponse({
            'success': True,
            'evaluation': {
                'id': str(evaluation.id),
                'title': evaluation.title,
                'file_name': uploaded_file.name,
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def evaluate_answer_sheet(request):
    """Run AI evaluation on an uploaded answer sheet"""
    try:
        data = json.loads(request.body)
        evaluation_id = data.get('evaluation_id')
        difficulty = int(data.get('difficulty', 5))
        reference_content = data.get('reference_content')  # Direct content from uploaded file
        
        if not evaluation_id:
            return JsonResponse({
                'success': False,
                'error': 'Evaluation ID required'
            }, status=400)
        
        # Get evaluation
        evaluation = get_object_or_404(AnswerSheetEvaluation, id=evaluation_id, user=request.user)
        
        if evaluation.is_evaluated:
            return JsonResponse({
                'success': False,
                'error': 'This answer sheet has already been evaluated'
            }, status=400)
        
        # Check that file exists
        if not evaluation.answer_sheet_file:
            return JsonResponse({
                'success': False,
                'error': 'No answer sheet file found. Please re-upload.'
            }, status=400)
        
        # Check API key
        if not settings.GEMINI_API_KEY:
            return JsonResponse({
                'success': False,
                'error': 'AI features not configured. Please set GEMINI_API_KEY.'
            }, status=500)
        
        # Update difficulty
        evaluation.difficulty = max(1, min(10, difficulty))
        evaluation.save()
        
        # Run evaluation with Gemini Vision
        try:
            start_time = time.time()
            agent = get_agent('evaluation')
            # Get the absolute path to the uploaded image
            image_path = evaluation.answer_sheet_file.path
            result = agent.generate_sync(
                image_path,
                difficulty=difficulty,
                reference_content=reference_content,
            )
            evaluation_time = time.time() - start_time
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
                'error': f'Evaluation failed: {str(e)}'
            }, status=500)
        
        if not result.get('success'):
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Failed to evaluate answer sheet')
            }, status=500)
        
        # Save evaluation results
        evaluation.overall_score = result.get('overall_score', 0)
        evaluation.question_count = len(result.get('questions', []))
        evaluation.general_feedback = result.get('general_feedback', '')
        evaluation.model_used = agent.model_name
        evaluation.evaluation_time = evaluation_time
        evaluation.is_evaluated = True
        
        # Calculate and save XP
        xp_earned = evaluation.calculate_xp()
        evaluation.xp_earned = xp_earned
        evaluation.save()
        
        # Create evaluated questions
        for q_data in result.get('questions', []):
            EvaluatedQuestion.objects.create(
                evaluation=evaluation,
                question_text=q_data['question_text'],
                student_answer=q_data['student_answer'],
                ideal_answer=q_data['ideal_answer'],
                score_percentage=q_data['score_percentage'],
                feedback=q_data['feedback'],
                order=q_data.get('order', 0),
            )
        
        # Update user profile
        profile = request.user.profile
        profile.add_xp(xp_earned)
        profile.update_streak()
        profile.save()
        
        return JsonResponse({
            'success': True,
            'result': {
                'evaluation_id': str(evaluation.id),
                'overall_score': evaluation.overall_score,
                'question_count': evaluation.question_count,
                'xp_earned': xp_earned,
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
def view_evaluation(request, evaluation_id):
    """Display detailed evaluation results"""
    evaluation = get_object_or_404(AnswerSheetEvaluation, id=evaluation_id, user=request.user)
    
    if not evaluation.is_evaluated:
        messages.warning(request, 'This answer sheet has not been evaluated yet.')
        return redirect('evaluations')
    
    questions = evaluation.questions.all()
    
    context = {
        'evaluation': evaluation,
        'questions': questions,
    }
    return render(request, 'pages/view_evaluation.html', context)


# ========== Podcast Views ==========

@login_required
def podcasts(request):
    """Podcast hub - select documents and generate AI podcasts"""
    documents = Document.objects.filter(user=request.user).order_by('-created_at')[:10]
    recent_podcasts = Podcast.objects.filter(user=request.user).order_by('-created_at')[:5]
    
    context = {
        'documents': documents,
        'recent_podcasts': recent_podcasts,
    }
    return render(request, 'pages/podcast.html', context)


@login_required
@require_http_methods(["POST"])
def generate_podcast(request):
    """Generate a podcast from a document via AJAX"""
    try:
        data = json.loads(request.body)
        document_id = data.get('document_id')
        level = data.get('level', 'beginner')
        
        if not document_id:
            return JsonResponse({
                'success': False,
                'error': 'Document ID required'
            }, status=400)
        
        if level not in ('beginner', 'intermediate', 'advanced'):
            level = 'beginner'
        
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
        
        # Step 1: Generate podcast script
        try:
            start_time = time.time()
            agent = get_agent('podcast')
            result = agent.generate_sync(context, level=level)
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
                'error': f'Script generation failed: {str(e)}'
            }, status=500)
        
        if not result.get('success'):
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Failed to generate podcast script')
            }, status=500)
        
        script = result['script']
        
        # Step 2: Convert script to audio using edge-tts
        try:
            import edge_tts
            import asyncio
            import tempfile
            import os
            
            # Parse script into speaker segments
            segments = []
            for line in script.split('\n'):
                line = line.strip()
                if line.startswith('ALEX:'):
                    segments.append(('alex', line[5:].strip()))
                elif line.startswith('SAM:'):
                    segments.append(('sam', line[4:].strip()))
            
            if not segments:
                return JsonResponse({
                    'success': False,
                    'error': 'Failed to parse podcast script into dialogue segments'
                }, status=500)
            
            # Voice mapping - newer multilingual neural voices sound more natural
            voices = {
                'alex': 'en-US-AndrewMultilingualNeural',
                'sam': 'en-US-AvaMultilingualNeural',
            }
            
            async def generate_audio_segments():
                """Generate audio for each segment and concatenate."""
                audio_parts = []
                
                for speaker, text in segments:
                    if not text:
                        continue
                    voice = voices[speaker]
                    # Slightly slower rate for more natural conversational pacing
                    communicate = edge_tts.Communicate(
                        text, voice, rate='-5%', pitch='+0Hz'
                    )
                    
                    # Create temp file for this segment
                    temp_file = tempfile.NamedTemporaryFile(
                        suffix='.mp3', delete=False
                    )
                    temp_path = temp_file.name
                    temp_file.close()
                    
                    await communicate.save(temp_path)
                    
                    with open(temp_path, 'rb') as f:
                        audio_parts.append(f.read())
                    
                    os.unlink(temp_path)
                
                return b''.join(audio_parts)
            
            # Run async TTS generation
            audio_data = asyncio.run(generate_audio_segments())
            generation_time = time.time() - start_time
            
            # Save audio file
            import uuid as uuid_lib
            from django.core.files.base import ContentFile
            
            audio_filename = f"podcast_{uuid_lib.uuid4().hex[:8]}.mp3"
            
            # Create podcast record
            podcast = Podcast.objects.create(
                document=document,
                user=request.user,
                title=f"Podcast: {document.title}",
                level=level,
                script=script,
                model_used=agent.model_name,
                generation_time=generation_time,
            )
            
            # Save audio file to the model
            podcast.audio_file.save(
                audio_filename,
                ContentFile(audio_data),
                save=True
            )
            
            # Estimate duration (rough: ~150 words per minute for TTS)
            word_count = result.get('word_count', len(script.split()))
            estimated_duration = int(word_count / 150 * 60)
            podcast.duration_seconds = estimated_duration
            podcast.save(update_fields=['duration_seconds'])
            
            return JsonResponse({
                'success': True,
                'podcast': {
                    'id': str(podcast.id),
                    'title': podcast.title,
                    'level': podcast.level,
                    'duration': podcast.duration_display,
                    'audio_url': podcast.audio_file.url,
                    'script': podcast.script,
                    'generation_time': round(generation_time, 2),
                    'view_url': f'/podcast/{podcast.id}/',
                    'download_url': f'/podcast/{podcast.id}/download/',
                }
            })
            
        except ImportError:
            return JsonResponse({
                'success': False,
                'error': 'edge-tts is not installed. Run: pip install edge-tts'
            }, status=500)
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return JsonResponse({
                'success': False,
                'error': f'Audio generation failed: {str(e)}'
            }, status=500)
        
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
def download_podcast(request, podcast_id):
    """Serve podcast audio file for download"""
    from django.http import FileResponse
    
    podcast = get_object_or_404(Podcast, id=podcast_id, user=request.user)
    
    if not podcast.audio_file:
        messages.error(request, 'Podcast audio file not found.')
        return redirect('podcasts')
    
    response = FileResponse(
        podcast.audio_file.open('rb'),
        content_type='audio/mpeg'
    )
    safe_title = podcast.title.replace(' ', '_').replace(':', '')[:50]
    response['Content-Disposition'] = f'attachment; filename="{safe_title}.mp3"'
    return response


@login_required
def view_podcast(request, podcast_id):
    """Display detailed podcast view with script, player, and download"""
    podcast = get_object_or_404(Podcast, id=podcast_id, user=request.user)
    
    # Parse script into structured lines for the template
    script_lines = []
    if podcast.script:
        for line in podcast.script.split('\n'):
            line = line.strip()
            if not line:
                continue
            if line.startswith('ALEX:'):
                script_lines.append({'speaker': 'alex', 'text': line[5:].strip()})
            elif line.startswith('SAM:'):
                script_lines.append({'speaker': 'sam', 'text': line[4:].strip()})
            else:
                script_lines.append({'speaker': 'narrator', 'text': line})
    
    context = {
        'podcast': podcast,
        'script_lines': script_lines,
    }
    return render(request, 'pages/view_podcast.html', context)


# ========== RAG Chatbot Views ==========


@login_required
def chatbot(request):
    """Chatbot hub - main page with document selector and chat sessions."""
    # Get user's uploaded documents for the document selector dropdown
    documents = Document.objects.filter(user=request.user).order_by('-created_at')
    
    # Get user's existing chat sessions for the sidebar
    chat_sessions = ChatSession.objects.filter(
        user=request.user
    ).select_related('document').order_by('-updated_at')[:20]
    
    context = {
        'documents': documents,
        'chat_sessions': chat_sessions,
        'active_session': None,
        'messages': [],
    }
    return render(request, 'pages/chatbot.html', context)


@login_required
def chatbot_session(request, session_id):
    """Load a specific chat session with its full message history."""
    # Get the requested session (must belong to the current user)
    session = get_object_or_404(ChatSession, id=session_id, user=request.user)
    
    # Get all messages in this session, ordered chronologically
    session_messages = session.messages.all().order_by('created_at')
    
    # Get all user data for sidebar and document selector
    documents = Document.objects.filter(user=request.user).order_by('-created_at')
    chat_sessions = ChatSession.objects.filter(
        user=request.user
    ).select_related('document').order_by('-updated_at')[:20]
    
    context = {
        'documents': documents,
        'chat_sessions': chat_sessions,
        'active_session': session,
        'messages': session_messages,
    }
    return render(request, 'pages/chatbot.html', context)


@login_required
@require_http_methods(["POST"])
def create_chat_session(request):
    """Create a new chat session for a selected document via AJAX."""
    try:
        data = json.loads(request.body)
        document_id = data.get('document_id')
        
        if not document_id:
            return JsonResponse({
                'success': False,
                'error': 'Please select a document to chat with.'
            }, status=400)
        
        # Verify the document belongs to the current user
        document = get_object_or_404(Document, id=document_id, user=request.user)
        
        # Check that the document has extracted text to chat about
        if not document.extracted_text:
            return JsonResponse({
                'success': False,
                'error': 'This document has no extracted text. Please re-upload it.'
            }, status=400)
        
        # Create a new chat session
        session = ChatSession.objects.create(
            user=request.user,
            document=document,
            title=f"Chat: {document.title[:50]}",
        )
        
        return JsonResponse({
            'success': True,
            'session': {
                'id': str(session.id),
                'title': session.title,
                'document_title': document.title,
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid request data.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def send_chat_message(request):
    """
    Send a message in a chat session via AJAX.
    
    Flow:
    1. Save the user's message
    2. Retrieve relevant context from the document (via vector store or raw text)
    3. Build chat history from previous messages
    4. Call the ChatbotAgent to generate a response
    5. Save the assistant's response
    6. Return the response to the frontend
    """
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        user_message = data.get('message', '').strip()
        
        # Validate inputs
        if not session_id:
            return JsonResponse({
                'success': False,
                'error': 'Session ID is required.'
            }, status=400)
        
        if not user_message:
            return JsonResponse({
                'success': False,
                'error': 'Message cannot be empty.'
            }, status=400)
        
        # Get the chat session
        session = get_object_or_404(ChatSession, id=session_id, user=request.user)
        document = session.document
        
        # Check if API key is configured
        if not settings.GEMINI_API_KEY:
            return JsonResponse({
                'success': False,
                'error': 'AI features not configured. Please set GEMINI_API_KEY.'
            }, status=500)
        
        # Step 1: Save the user's message
        user_msg = ChatMessage.objects.create(
            session=session,
            role='user',
            content=user_message,
        )
        
        # Step 2: Retrieve relevant context from the document
        # We use FAISS semantic search for accurate retrieval.
        # If the document hasn't been indexed yet, index it now (lazy indexing).
        context = ""
        vector_service = VectorStoreService()
        
        # Lazy indexing: auto-index the document if it hasn't been indexed yet
        if not vector_service.document_exists(document.vector_doc_id):
            if document.extracted_text:
                index_result = vector_service.add_document(
                    document.vector_doc_id,
                    document.extracted_text
                )
                if index_result['success']:
                    document.is_indexed = True
                    document.chunk_count = index_result['chunk_count']
                    document.save(update_fields=['is_indexed', 'chunk_count'])
        
        # Now try semantic search (should work after indexing)
        if vector_service.document_exists(document.vector_doc_id):
            search_result = vector_service.search(
                document.vector_doc_id,
                user_message,
                top_k=5
            )
            if search_result['success'] and search_result['chunks']:
                context = "\n\n---\n\n".join(search_result['chunks'])
        
        # Ultimate fallback: use raw text if indexing failed or no results found
        if not context:
            raw_text = document.extracted_text
            MAX_CONTEXT_CHARS = 8000
            if len(raw_text) > MAX_CONTEXT_CHARS:
                context = raw_text[:MAX_CONTEXT_CHARS] + "\n\n[... Document truncated ...]"
            else:
                context = raw_text

        
        # Step 3: Build chat history from previous messages in this session
        previous_messages = session.messages.exclude(
            id=user_msg.id
        ).order_by('created_at').values('role', 'content')
        
        chat_history = list(previous_messages)
        
        # Step 4: Call the ChatbotAgent
        try:
            agent = get_agent('chatbot')
            result = agent.generate_sync(
                context,
                user_message=user_message,
                chat_history=chat_history,
            )
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return JsonResponse({
                'success': False,
                'error': f'AI generation failed: {str(e)}'
            }, status=500)
        
        if not result.get('success'):
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Failed to generate response.')
            }, status=500)
        
        # Step 5: Save the assistant's response
        assistant_msg = ChatMessage.objects.create(
            session=session,
            role='assistant',
            content=result['response'],
            sources_used=result.get('sources_used', False),
        )
        
        # Update session metadata
        session.message_count = session.messages.count()
        
        # Auto-title the session from the first user message
        if session.message_count <= 2 and session.title.startswith('Chat:'):
            # Use the first ~50 chars of the first question as the title
            session.title = user_message[:50] + ('...' if len(user_message) > 50 else '')
        
        session.save()
        
        # Step 6: Return the response
        return JsonResponse({
            'success': True,
            'response': {
                'id': str(assistant_msg.id),
                'content': assistant_msg.content,
                'sources_used': assistant_msg.sources_used,
                'session_title': session.title,
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid request data.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST", "DELETE"])
def delete_chat_session(request, session_id):
    """Delete a chat session and all its messages via AJAX."""
    try:
        session = get_object_or_404(ChatSession, id=session_id, user=request.user)
        session.delete()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
