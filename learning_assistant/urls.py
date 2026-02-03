from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    
    # AI Summary
    path('summaries/', views.summaries, name='summaries'),
    path('api/upload/', views.upload_document, name='upload_document'),
    path('api/generate-summary/', views.generate_summary, name='generate_summary'),
    path('document/<uuid:document_id>/', views.document_detail, name='document_detail'),
    path('api/document/<uuid:document_id>/delete/', views.delete_document, name='delete_document'),
    
    # Quiz
    path('quizzes/', views.quizzes, name='quizzes'),
    path('api/generate-quiz/', views.generate_quiz, name='generate_quiz'),
    path('quiz/<uuid:quiz_id>/', views.take_quiz, name='take_quiz'),
    path('api/quiz/<uuid:quiz_id>/submit/', views.submit_quiz, name='submit_quiz'),
    path('quiz/<uuid:quiz_id>/result/', views.quiz_result, name='quiz_result'),
    
    # Flashcards
    path('flashcards/', views.flashcards, name='flashcards'),
    path('api/generate-flashcards/', views.generate_flashcards, name='generate_flashcards'),
    path('flashcards/<uuid:set_id>/study/', views.study_flashcards, name='study_flashcards'),
    path('api/flashcard/<uuid:card_id>/toggle-mastery/', views.toggle_flashcard_mastery, name='toggle_flashcard_mastery'),
    
    # Flowcharts
    path('flowcharts/', views.flowcharts, name='flowcharts'),
    path('api/generate-flowchart/', views.generate_flowchart, name='generate_flowchart'),
    path('flowchart/<uuid:flowchart_id>/', views.view_flowchart, name='view_flowchart'),
    
    # Answer Sheet Evaluation
    path('evaluations/', views.evaluations, name='evaluations'),
    path('api/upload-answer-sheet/', views.upload_answer_sheet, name='upload_answer_sheet'),
    path('api/evaluate-answer-sheet/', views.evaluate_answer_sheet, name='evaluate_answer_sheet'),
    path('evaluation/<uuid:evaluation_id>/', views.view_evaluation, name='view_evaluation'),
    
    # Other features (placeholders)
    path('analytics/', views.analytics, name='analytics'),
]
