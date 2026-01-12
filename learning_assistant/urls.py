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
    
    # Other features
    path('quizzes/', views.quizzes, name='quizzes'),
    path('flashcards/', views.flashcards, name='flashcards'),
    path('flowcharts/', views.flowcharts, name='flowcharts'),
    path('analytics/', views.analytics, name='analytics'),
]
