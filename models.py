from django.db import models
import re
from django.core.exceptions import ValidationError
from datetime import datetime
from django.utils import timezone

# User model definition
class User(models.Model):
    user_id = models.AutoField(primary_key=True)  # Automatically increments the user_id as the primary key
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    full_name = models.CharField(max_length=255)
    dob = models.DateField()

    def __str__(self):
        return self.email

    # Password validation
    def clean(self):
        password = self.password
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters long.")
        if not any(char.isdigit() for char in password):
            raise ValidationError("Password must contain at least one number.")
        if not any(char.islower() for char in password):
            raise ValidationError("Password must contain at least one lowercase letter.")
        if not any(char.isupper() for char in password):
            raise ValidationError("Password must contain at least one uppercase letter.")
        if not any(char in "!@#$%^&*()-_=+[]{}|;:'\",.<>?/`~" for char in password):
            raise ValidationError("Password must contain at least one special character.")
        
        super().clean()

class CourseType(models.TextChoices):
    COURSE = 'course', 'Course'
    COURSE_ASSIGNMENT = 'course_assignment', 'Course & Assignment'
    COURSE_ASSIGNMENT_PROJECT = 'course_assignment_project', 'Course, Assignment & Project'

# CoursePlan model definition
class CoursePlan(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # Reference to User model
    course_plan_name = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)  
    learning_goal = models.TextField()
    course_type = models.CharField(max_length=30, choices=CourseType.choices)
    number_of_weeks = models.IntegerField(null=True,blank=True)

    def __str__(self):
        return self.course_plan_name

# CourseTopic model definition
class CourseTopic(models.Model):
    main_topic = models.TextField()
    sub_topic = models.TextField()
    explanation = models.TextField(null=True,blank=True)
    course_plan = models.ForeignKey(CoursePlan, on_delete=models.CASCADE, related_name='topics')
    week = models.TextField(null=True,blank=True)

    def __str__(self):
        return f"{self.main_topic} - {self.sub_topic}"

# CourseProject model definition
class CourseProject(models.Model):
    course_plan = models.ForeignKey(CoursePlan, on_delete=models.CASCADE, related_name='projects')
    project = models.TextField()

    def __str__(self):
        return f"Project for: {self.course_plan.course_plan_name}"

# CourseAssignment model definition
class CourseAssignment(models.Model):
    id = models.AutoField(primary_key=True)
    course_plan = models.ForeignKey(CoursePlan, on_delete=models.CASCADE, related_name='assignments')
    assignment = models.TextField()
    week = models.TextField()

    def __str__(self):
        return f"Assignment for: {self.course_plan.course_plan_name} (Week {self.week})"


# Add to models.py
class ChatContext(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_contexts')
    current_topic = models.CharField(max_length=255, blank=True, null=True)
    last_question = models.TextField(blank=True, null=True)
    conversation_state = models.CharField(max_length=50, default='general')  # 'general', 'explaining', 'recommending', etc.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Chat context for {self.user.email}"
    
    # Add to models.py
# Add this to your existing models.py file

class LearningProgress(models.Model):
    """Model to track user progress in a specific course plan"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='learning_progress')
    course_plan = models.ForeignKey(CoursePlan, on_delete=models.CASCADE, related_name='learning_progress')
    current_topic = models.ForeignKey(CourseTopic, on_delete=models.SET_NULL, null=True, blank=True, related_name='learning_progress')
    progress_percentage = models.FloatField(default=0)
    completed_topics = models.ManyToManyField(CourseTopic, through='TopicCompletion', related_name='completed_by')
    last_updated = models.DateTimeField(auto_now=True)
    last_accessed = models.DateTimeField(default=timezone.now)   # New field to track when course was last accessed
    
    class Meta:
        unique_together = ('user', 'course_plan')  # Each user can only have one progress record per course
        
    def update_progress(self):
        """Calculate and update progress percentage based on completed topics"""
        if not self.course_plan:
            return
            
        total_topics = self.course_plan.topics.count()
        if total_topics == 0:
            self.progress_percentage = 0
            return
            
        completed_count = self.completed_topics.count()
        self.progress_percentage = (completed_count / total_topics) * 100
        self.save()


class TopicCompletion(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    learning_progress = models.ForeignKey('LearningProgress', on_delete=models.CASCADE,null=True)  # Add this line
    topic = models.ForeignKey(CourseTopic, on_delete=models.CASCADE)
    completed_at = models.DateTimeField(auto_now_add=True)
    comprehension_level = models.IntegerField(default=0)  # 0-10 scale of understanding
    
    class Meta:
        unique_together = ('user', 'topic')


# Add to models.py
class CourseCategory(models.Model):
    """Categories of courses (e.g., Programming, Gardening, Languages, etc.)"""
    name = models.CharField(max_length=100)
    keywords = models.TextField(help_text="Comma-separated keywords associated with this category")
    
    def __str__(self):
        return self.name

class TopicTemplate(models.Model):
    """Templates for topic explanations based on category"""
    course_category = models.ForeignKey(CourseCategory, on_delete=models.CASCADE, related_name='templates')
    keyword = models.CharField(max_length=100, help_text="Keyword to match in topic names")
    explanation = models.TextField(blank=True, null=True)
    analogy = models.TextField(blank=True, null=True)
    example = models.TextField(blank=True, null=True)
    metaphor = models.TextField(blank=True, null=True)
    resources = models.TextField(blank=True, null=True, help_text="Comma-separated resource suggestions")
    practice_questions = models.TextField(blank=True, null=True, help_text="Semicolon-separated practice questions")
    
    def __str__(self):
        return f"{self.course_category.name}: {self.keyword}"

class CourseMapper(models.Model):
    course_plan = models.OneToOneField(CoursePlan, on_delete=models.CASCADE)
    category = models.ForeignKey(CourseCategory, on_delete=models.SET_NULL, null=True)
    auto_categorized = models.BooleanField(default=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.course_plan.course_plan_name} -> {self.category.name if self.category else 'Uncategorized'}"