from django.db import models
from django.conf import settings
from study.models import Subject


class Quiz(models.Model):
    QUIZ_TYPE_CHOICES = [
        ('multiple_choice', '객관식'),
        ('short_answer', '주관식'),
    ]
    
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    question = models.TextField()
    quiz_type = models.CharField(max_length=20, choices=QUIZ_TYPE_CHOICES)
    difficulty_level = models.CharField(max_length=20)
    explanation = models.TextField()
    related_knowledge = models.TextField(help_text="관련된 추가 지식 정보")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.get_quiz_type_display()})"


class QuizChoice(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='choices')
    choice_text = models.CharField(max_length=200)
    is_correct = models.BooleanField(default=False)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.quiz.title} - {self.choice_text}"


class QuizAttempt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    user_answer = models.TextField()
    is_correct = models.BooleanField()
    attempted_at = models.DateTimeField(auto_now_add=True)
    time_spent = models.DurationField(null=True, blank=True)

    class Meta:
        ordering = ['-attempted_at']

    def __str__(self):
        return f"{self.user.email} - {self.quiz.title} ({'정답' if self.is_correct else '오답'})"


class QuizSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    total_questions = models.IntegerField()
    correct_answers = models.IntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.user.email} - {self.subject.name} Session ({self.correct_answers}/{self.total_questions})"

    @property
    def score_percentage(self):
        if self.total_questions == 0:
            return 0
        return (self.correct_answers / self.total_questions) * 100
