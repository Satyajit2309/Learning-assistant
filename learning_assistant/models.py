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


class Quiz(models.Model):
    """
    Model for storing generated quizzes.
    
    Each quiz is generated from a document with configurable difficulty
    and question count. Tracks user score and XP earned.
    """
    
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='quizzes'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='quizzes'
    )
    
    title = models.CharField(max_length=255)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='medium')
    question_count = models.PositiveIntegerField(default=5)
    
    # Quiz results
    score = models.PositiveIntegerField(null=True, blank=True)
    xp_earned = models.PositiveIntegerField(default=0)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Generation metadata
    model_used = models.CharField(max_length=100, blank=True)
    generation_time = models.FloatField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Quiz'
        verbose_name_plural = 'Quizzes'
    
    def __str__(self):
        return f"{self.difficulty.title()} quiz on {self.document.title}"
    
    @property
    def correct_count(self):
        """Get number of correctly answered questions."""
        return self.questions.filter(user_answer=models.F('correct_answer')).count()
    
    @property
    def percentage_score(self):
        """Get score as percentage."""
        if self.question_count == 0:
            return 0
        return round((self.score or 0) / self.question_count * 100)
    
    def calculate_xp(self):
        """Calculate XP earned based on difficulty and score."""
        if not self.is_completed or self.score is None:
            return 0
        
        # Base XP per correct answer by difficulty
        xp_per_correct = {
            'easy': 5,
            'medium': 10,
            'hard': 15,
        }
        
        base_xp = self.score * xp_per_correct.get(self.difficulty, 10)
        
        # Perfect score bonus (25%)
        if self.score == self.question_count:
            base_xp = int(base_xp * 1.25)
        
        return base_xp


class QuizQuestion(models.Model):
    """
    Individual MCQ question within a quiz.
    
    Stores the question text, four options (A-D), correct answer,
    explanation, and user's selected answer.
    """
    
    ANSWER_CHOICES = [
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
        ('D', 'D'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='questions'
    )
    
    question_text = models.TextField()
    option_a = models.CharField(max_length=500)
    option_b = models.CharField(max_length=500)
    option_c = models.CharField(max_length=500)
    option_d = models.CharField(max_length=500)
    correct_answer = models.CharField(max_length=1, choices=ANSWER_CHOICES)
    explanation = models.TextField(blank=True)
    
    # User's answer
    user_answer = models.CharField(max_length=1, choices=ANSWER_CHOICES, null=True, blank=True)
    
    # Display order
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['order']
        verbose_name = 'Quiz Question'
        verbose_name_plural = 'Quiz Questions'
    
    def __str__(self):
        return f"Q{self.order + 1}: {self.question_text[:50]}..."
    
    @property
    def is_correct(self):
        """Check if user answered correctly."""
        return self.user_answer == self.correct_answer
    
    def get_options_list(self):
        """Return options as a list of tuples (letter, text)."""
        return [
            ('A', self.option_a),
            ('B', self.option_b),
            ('C', self.option_c),
            ('D', self.option_d),
        ]


class FlashcardSet(models.Model):
    """
    Model for storing a set of flashcards generated from a document.
    
    Each set contains multiple flashcards with priority-based ordering
    to help users focus on the most important concepts first.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='flashcard_sets'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='flashcard_sets'
    )
    
    title = models.CharField(max_length=255)
    card_count = models.PositiveIntegerField(default=10)
    
    # Study progress
    cards_studied = models.PositiveIntegerField(default=0)
    cards_mastered = models.PositiveIntegerField(default=0)
    last_studied_at = models.DateTimeField(null=True, blank=True)
    
    # Generation metadata
    model_used = models.CharField(max_length=100, blank=True)
    generation_time = models.FloatField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Flashcard Set'
        verbose_name_plural = 'Flashcard Sets'
    
    def __str__(self):
        return f"Flashcards: {self.document.title}"
    
    @property
    def progress_percentage(self):
        """Calculate study progress as percentage."""
        if self.card_count == 0:
            return 0
        return round((self.cards_mastered / self.card_count) * 100)
    
    @property
    def is_completed(self):
        """Check if all cards have been mastered."""
        return self.cards_mastered >= self.card_count


class Flashcard(models.Model):
    """
    Individual flashcard within a set.
    
    Contains a front (concept/question) and back (explanation/answer),
    with priority scoring for importance-based ordering.
    """
    
    PRIORITY_CHOICES = [
        (1, 'Critical'),
        (2, 'Very Important'),
        (3, 'Important'),
        (4, 'Helpful'),
        (5, 'Supplementary'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    flashcard_set = models.ForeignKey(
        FlashcardSet,
        on_delete=models.CASCADE,
        related_name='cards'
    )
    
    front = models.TextField(help_text="The concept, term, or question")
    back = models.TextField(help_text="The explanation, definition, or answer")
    priority = models.PositiveIntegerField(
        choices=PRIORITY_CHOICES, 
        default=3,
        help_text="1 = most important, 5 = least important"
    )
    
    # Study tracking
    is_mastered = models.BooleanField(default=False)
    times_reviewed = models.PositiveIntegerField(default=0)
    
    # Display order
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['priority', 'order']
        verbose_name = 'Flashcard'
        verbose_name_plural = 'Flashcards'
    
    def __str__(self):
        return f"Card {self.order + 1}: {self.front[:50]}..."
    
    def mark_reviewed(self):
        """Increment the review counter."""
        self.times_reviewed += 1
        self.save(update_fields=['times_reviewed'])
    
    def toggle_mastered(self):
        """Toggle mastered status and update parent set."""
        self.is_mastered = not self.is_mastered
        self.save(update_fields=['is_mastered'])
        
        # Update parent set's mastered count
        mastered_count = self.flashcard_set.cards.filter(is_mastered=True).count()
        self.flashcard_set.cards_mastered = mastered_count
        self.flashcard_set.save(update_fields=['cards_mastered'])


class Flowchart(models.Model):
    """
    Model for storing generated flowcharts.
    
    Each flowchart is generated from a document and contains
    nodes and edges representing concepts and their relationships.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='flowcharts'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='flowcharts'
    )
    
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    node_count = models.PositiveIntegerField(default=0)
    edge_count = models.PositiveIntegerField(default=0)
    
    # Generation metadata
    model_used = models.CharField(max_length=100, blank=True)
    generation_time = models.FloatField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Flowchart'
        verbose_name_plural = 'Flowcharts'
    
    def __str__(self):
        return f"Flowchart: {self.title}"


class FlowchartNode(models.Model):
    """
    Individual node within a flowchart.
    
    Nodes represent concepts, actions, decisions, or start/end points.
    Each node has a type that determines its visual appearance.
    """
    
    NODE_TYPE_CHOICES = [
        ('start', 'Start'),
        ('end', 'End'),
        ('concept', 'Concept'),
        ('action', 'Action'),
        ('decision', 'Decision'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    flowchart = models.ForeignKey(
        Flowchart,
        on_delete=models.CASCADE,
        related_name='nodes'
    )
    
    node_id = models.CharField(max_length=50, help_text="String identifier for connections")
    label = models.CharField(max_length=255)
    node_type = models.CharField(max_length=20, choices=NODE_TYPE_CHOICES, default='concept')
    
    # Optional positioning (can be calculated client-side)
    position_x = models.FloatField(null=True, blank=True)
    position_y = models.FloatField(null=True, blank=True)
    
    # Display order
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['order']
        verbose_name = 'Flowchart Node'
        verbose_name_plural = 'Flowchart Nodes'
    
    def __str__(self):
        return f"[{self.node_type}] {self.label}"


class FlowchartEdge(models.Model):
    """
    Edge connecting two nodes in a flowchart.
    
    Represents relationships or flow between concepts.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    flowchart = models.ForeignKey(
        Flowchart,
        on_delete=models.CASCADE,
        related_name='edges'
    )
    
    from_node = models.CharField(max_length=50, help_text="Source node_id")
    to_node = models.CharField(max_length=50, help_text="Target node_id")
    label = models.CharField(max_length=100, blank=True)
    
    class Meta:
        verbose_name = 'Flowchart Edge'
        verbose_name_plural = 'Flowchart Edges'
    
    def __str__(self):
        return f"{self.from_node} → {self.to_node}"


def answer_sheet_upload_path(instance, filename):
    """Generate upload path for answer sheets."""
    return f'answer_sheets/{instance.user.id}/{filename}'


class AnswerSheetEvaluation(models.Model):
    """
    Model for storing answer sheet evaluations.
    
    Users upload handwritten answer sheet PDFs, the system extracts text via OCR,
    and an AI agent evaluates answers with percentage-based scoring.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='evaluations'
    )
    
    # Upload info
    title = models.CharField(max_length=255)
    answer_sheet_file = models.FileField(upload_to=answer_sheet_upload_path)
    
    # OCR result
    extracted_text = models.TextField(blank=True)
    
    # Optional reference document
    reference_document = models.ForeignKey(
        Document,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='evaluations'
    )
    
    # Difficulty slider (1=lenient, 10=strict)
    difficulty = models.PositiveIntegerField(
        default=5,
        help_text="1=very lenient, 10=very strict"
    )
    
    # Results
    overall_score = models.FloatField(null=True, blank=True)  # Percentage 0-100
    question_count = models.PositiveIntegerField(default=0)
    xp_earned = models.PositiveIntegerField(default=0)
    is_evaluated = models.BooleanField(default=False)
    general_feedback = models.TextField(blank=True)
    
    # Generation metadata
    model_used = models.CharField(max_length=100, blank=True)
    evaluation_time = models.FloatField(default=0)  # in seconds
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Answer Sheet Evaluation'
        verbose_name_plural = 'Answer Sheet Evaluations'
    
    def __str__(self):
        return f"Evaluation: {self.title}"
    
    @property
    def difficulty_label(self):
        """Return human-readable difficulty label."""
        if self.difficulty <= 3:
            return "Lenient"
        elif self.difficulty <= 6:
            return "Standard"
        else:
            return "Strict"
    
    def calculate_xp(self):
        """Calculate XP earned based on score and difficulty."""
        if not self.is_evaluated or self.overall_score is None:
            return 0
        
        # Base XP: 1 point per percentage point of score
        base_xp = int(self.overall_score)
        
        # Difficulty multiplier: 0.8x for lenient, 1x for standard, 1.5x for strict
        if self.difficulty <= 3:
            multiplier = 0.8
        elif self.difficulty <= 6:
            multiplier = 1.0
        else:
            multiplier = 1.5
        
        return int(base_xp * multiplier)


class EvaluatedQuestion(models.Model):
    """
    Individual evaluated question within an answer sheet evaluation.
    
    Stores the question, student's answer, ideal answer, score, and feedback.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    evaluation = models.ForeignKey(
        AnswerSheetEvaluation,
        on_delete=models.CASCADE,
        related_name='questions'
    )
    
    question_text = models.TextField()
    student_answer = models.TextField()
    ideal_answer = models.TextField()
    
    score_percentage = models.FloatField(help_text="Score as percentage 0-100")
    feedback = models.TextField()
    
    # Display order
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['order']
        verbose_name = 'Evaluated Question'
        verbose_name_plural = 'Evaluated Questions'
    
    def __str__(self):
        return f"Q{self.order + 1}: {self.question_text[:50]}..."
    
    @property
    def score_color(self):
        """Return a color based on the score for UI."""
        if self.score_percentage >= 80:
            return "success"
        elif self.score_percentage >= 50:
            return "warning"
        else:
            return "danger"

