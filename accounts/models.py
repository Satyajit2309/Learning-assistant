from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class User(AbstractUser):
    """
    Custom User model with email as the primary authentication field.
    """
    email = models.EmailField(unique=True, verbose_name='Email Address')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    
    # Make email the login field instead of username
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return self.email
    
    def get_display_name(self):
        """Return full name if available, otherwise username"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        return self.username


class UserProfile(models.Model):
    """
    Extended user profile with rewards, progress tracking, and preferences.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Gamification & Rewards
    xp_points = models.IntegerField(default=0, verbose_name='XP Points')
    level = models.IntegerField(default=1)
    streak_days = models.IntegerField(default=0, verbose_name='Current Streak')
    longest_streak = models.IntegerField(default=0, verbose_name='Longest Streak')
    last_activity_date = models.DateField(null=True, blank=True)
    
    # Progress Statistics
    total_quizzes_taken = models.IntegerField(default=0)
    total_quizzes_passed = models.IntegerField(default=0)
    total_questions_answered = models.IntegerField(default=0)
    total_correct_answers = models.IntegerField(default=0)
    total_flashcards_reviewed = models.IntegerField(default=0)
    total_documents_uploaded = models.IntegerField(default=0)
    total_study_time_minutes = models.IntegerField(default=0)
    
    # Preferences
    preferred_difficulty = models.CharField(
        max_length=20,
        choices=[('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')],
        default='medium'
    )
    daily_goal_minutes = models.IntegerField(default=30)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
    
    def __str__(self):
        return f"Profile of {self.user.email}"
    
    @property
    def accuracy_percentage(self):
        """Calculate quiz accuracy percentage"""
        if self.total_questions_answered == 0:
            return 0
        return round((self.total_correct_answers / self.total_questions_answered) * 100, 1)
    
    @property
    def quiz_pass_rate(self):
        """Calculate quiz pass rate percentage"""
        if self.total_quizzes_taken == 0:
            return 0
        return round((self.total_quizzes_passed / self.total_quizzes_taken) * 100, 1)
    
    def add_xp(self, points):
        """Add XP points and check for level up"""
        self.xp_points += points
        # Level up every 1000 XP
        new_level = (self.xp_points // 1000) + 1
        if new_level > self.level:
            self.level = new_level
        self.save()
    
    def update_streak(self):
        """Update daily streak based on last activity"""
        today = timezone.now().date()
        
        if self.last_activity_date is None:
            self.streak_days = 1
        elif self.last_activity_date == today:
            pass  # Already logged activity today
        elif (today - self.last_activity_date).days == 1:
            self.streak_days += 1
            if self.streak_days > self.longest_streak:
                self.longest_streak = self.streak_days
        else:
            self.streak_days = 1  # Reset streak
        
        self.last_activity_date = today
        self.save()


# Signal to create profile when user is created
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a UserProfile when a new User is created"""
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save the UserProfile when the User is saved"""
    if hasattr(instance, 'profile'):
        instance.profile.save()
