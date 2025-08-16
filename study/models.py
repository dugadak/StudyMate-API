from django.db import models
from django.conf import settings


class Subject(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class StudySettings(models.Model):
    DIFFICULTY_CHOICES = [
        ('beginner', '초급'),
        ('intermediate', '중급'),
        ('advanced', '고급'),
        ('expert', '전문가'),
    ]
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='study_settings')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    difficulty_level = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='beginner')
    current_knowledge = models.TextField(help_text="현재 알고 있는 지식 수준")
    learning_goal = models.TextField(help_text="학습 목표")
    preferred_depth = models.CharField(
        max_length=20, 
        choices=DIFFICULTY_CHOICES, 
        default='intermediate',
        help_text="원하는 학습 깊이"
    )
    daily_summary_count = models.IntegerField(default=3, help_text="하루 요약 제공 횟수")
    notification_times = models.JSONField(
        default=list,
        help_text="알림 시간 목록 (예: ['09:00', '12:00', '21:00'])"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - {self.subject.name}"


class StudySummary(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    content = models.TextField()
    difficulty_level = models.CharField(max_length=20)
    generated_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        return f"{self.title} - {self.user.email}"


class StudyProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    topics_learned = models.JSONField(default=list)
    total_summaries_read = models.IntegerField(default=0)
    total_quizzes_completed = models.IntegerField(default=0)
    current_streak = models.IntegerField(default=0)
    last_activity_date = models.DateField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'subject']

    def __str__(self):
        return f"{self.user.email} - {self.subject.name} Progress"
