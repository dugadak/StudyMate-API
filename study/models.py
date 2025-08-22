from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from typing import List, Dict, Any, Optional
from datetime import timedelta, date
import json


def default_study_days():
    """Default study days function for migration compatibility"""
    return ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']


class Subject(models.Model):
    """Enhanced Subject model with metadata and categorization"""
    
    CATEGORY_CHOICES = [
        ('language', '언어'),
        ('science', '과학'),
        ('mathematics', '수학'),
        ('history', '역사'),
        ('arts', '예술'),
        ('technology', '기술'),
        ('business', '비즈니스'),
        ('health', '건강'),
        ('lifestyle', '라이프스타일'),
        ('other', '기타'),
    ]
    
    DIFFICULTY_CHOICES = [
        ('beginner', '초급'),
        ('intermediate', '중급'),
        ('advanced', '고급'),
        ('expert', '전문가'),
    ]
    
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="과목명"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="과목 설명"
    )
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='other',
        help_text="과목 카테고리"
    )
    default_difficulty = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default='beginner',
        help_text="기본 난이도"
    )
    
    # Metadata
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="아이콘 클래스명 또는 이모지"
    )
    color_code = models.CharField(
        max_length=7,
        blank=True,
        help_text="HEX 컬러 코드 (#FFFFFF)"
    )
    
    # Statistics
    total_learners = models.PositiveIntegerField(
        default=0,
        help_text="총 학습자 수"
    )
    total_summaries = models.PositiveIntegerField(
        default=0,
        help_text="총 생성된 요약 수"
    )
    average_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00,
        help_text="평균 평점"
    )
    
    # Settings
    is_active = models.BooleanField(
        default=True,
        help_text="활성화 상태"
    )
    requires_premium = models.BooleanField(
        default=False,
        help_text="프리미엄 구독 필요 여부"
    )
    
    # Tags and keywords for search
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="검색용 태그들"
    )
    keywords = models.JSONField(
        default=list,
        blank=True,
        help_text="관련 키워드들"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'study_subject'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['requires_premium']),
            models.Index(fields=['total_learners']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['name']
        verbose_name = '과목'
        verbose_name_plural = '과목들'
    
    def __str__(self) -> str:
        return f"{self.name} ({self.get_category_display()})"
    
    def increment_learner_count(self) -> None:
        """학습자 수 증가"""
        self.total_learners += 1
        self.save(update_fields=['total_learners'])
    
    def increment_summary_count(self) -> None:
        """요약 생성 수 증가"""
        self.total_summaries += 1
        self.save(update_fields=['total_summaries'])
    
    def update_average_rating(self, new_rating: float) -> None:
        """평균 평점 업데이트"""
        # 간단한 이동 평균 계산 (실제로는 더 정교한 계산 필요)
        current_weight = 0.9
        self.average_rating = (
            self.average_rating * current_weight + 
            new_rating * (1 - current_weight)
        )
        self.save(update_fields=['average_rating'])
    
    def get_statistics(self) -> Dict[str, Any]:
        """과목 통계 반환"""
        return {
            'total_learners': self.total_learners,
            'total_summaries': self.total_summaries,
            'average_rating': float(self.average_rating),
            'category': self.get_category_display(),
            'difficulty': self.get_default_difficulty_display(),
        }


class StudySettings(models.Model):
    """Enhanced StudySettings with more detailed preferences"""
    
    DIFFICULTY_CHOICES = [
        ('beginner', '초급'),
        ('intermediate', '중급'),
        ('advanced', '고급'),
        ('expert', '전문가'),
    ]
    
    LEARNING_STYLE_CHOICES = [
        ('visual', '시각적'),
        ('auditory', '청각적'),
        ('kinesthetic', '체감각적'),
        ('reading', '읽기/쓰기'),
        ('mixed', '혼합형'),
    ]
    
    CONTENT_TYPE_CHOICES = [
        ('summary', '요약 중심'),
        ('example', '예시 중심'),
        ('theory', '이론 중심'),
        ('practical', '실습 중심'),
        ('mixed', '혼합형'),
    ]
    
    # Basic settings
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='study_settings'
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='user_settings'
    )
    
    # Difficulty and knowledge level
    difficulty_level = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default='beginner',
        help_text="현재 지식 수준"
    )
    current_knowledge = models.TextField(
        help_text="현재 알고 있는 지식 수준 상세 설명"
    )
    learning_goal = models.TextField(
        help_text="구체적인 학습 목표"
    )
    preferred_depth = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default='intermediate',
        help_text="원하는 학습 깊이"
    )
    
    # Learning preferences
    learning_style = models.CharField(
        max_length=20,
        choices=LEARNING_STYLE_CHOICES,
        default='mixed',
        help_text="선호하는 학습 스타일"
    )
    content_type_preference = models.CharField(
        max_length=20,
        choices=CONTENT_TYPE_CHOICES,
        default='mixed',
        help_text="선호하는 콘텐츠 유형"
    )
    
    # Daily settings
    daily_summary_count = models.PositiveIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(20)],
        help_text="하루 요약 제공 횟수"
    )
    notification_times = models.JSONField(
        default=list,
        help_text="알림 시간 목록 (예: ['09:00', '12:00', '21:00'])"
    )
    
    # Study schedule
    study_days = models.JSONField(
        default=default_study_days,
        help_text="학습 요일들"
    )
    preferred_study_duration = models.PositiveIntegerField(
        default=30,
        validators=[MinValueValidator(5), MaxValueValidator(180)],
        help_text="선호하는 학습 시간 (분)"
    )
    
    # Content preferences
    include_examples = models.BooleanField(
        default=True,
        help_text="예시 포함 여부"
    )
    include_quizzes = models.BooleanField(
        default=True,
        help_text="퀴즈 포함 여부"
    )
    language_preference = models.CharField(
        max_length=10,
        choices=[
            ('ko', '한국어'),
            ('en', 'English'),
            ('mixed', '혼합'),
        ],
        default='ko',
        help_text="언어 선호도"
    )
    
    # AI model preferences
    preferred_ai_model = models.CharField(
        max_length=50,
        choices=[
            ('gpt-3.5-turbo', 'GPT-3.5 Turbo'),
            ('gpt-4', 'GPT-4'),
            ('claude-3-haiku', 'Claude 3 Haiku'),
            ('claude-3-sonnet', 'Claude 3 Sonnet'),
            ('auto', '자동 선택'),
        ],
        default='auto',
        help_text="선호하는 AI 모델"
    )
    
    # Custom prompt templates
    custom_prompt_template = models.TextField(
        blank=True,
        help_text="사용자 정의 프롬프트 템플릿"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'study_settings'
        unique_together = ['user', 'subject']
        indexes = [
            models.Index(fields=['user', 'subject']),
            models.Index(fields=['difficulty_level']),
            models.Index(fields=['last_used_at']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = '학습 설정'
        verbose_name_plural = '학습 설정들'
    
    def __str__(self) -> str:
        return f"{self.user.email} - {self.subject.name} 설정"
    
    def update_last_used(self) -> None:
        """마지막 사용 시간 업데이트"""
        self.last_used_at = timezone.now()
        self.save(update_fields=['last_used_at'])
    
    def get_notification_times_list(self) -> List[str]:
        """알림 시간 목록 반환"""
        return self.notification_times if isinstance(self.notification_times, list) else []
    
    def add_notification_time(self, time_str: str) -> None:
        """알림 시간 추가"""
        times = self.get_notification_times_list()
        if time_str not in times:
            times.append(time_str)
            times.sort()
            self.notification_times = times
            self.save(update_fields=['notification_times'])
    
    def remove_notification_time(self, time_str: str) -> None:
        """알림 시간 제거"""
        times = self.get_notification_times_list()
        if time_str in times:
            times.remove(time_str)
            self.notification_times = times
            self.save(update_fields=['notification_times'])
    
    def get_study_days_list(self) -> List[str]:
        """학습 요일 목록 반환"""
        return self.study_days if isinstance(self.study_days, list) else []
    
    def is_study_day_today(self) -> bool:
        """오늘이 학습 요일인지 확인"""
        today = timezone.now().strftime('%A').lower()
        study_days = self.get_study_days_list()
        return today in study_days
    
    def get_ai_generation_config(self) -> Dict[str, Any]:
        """AI 생성을 위한 설정 딕셔너리 반환"""
        return {
            'difficulty_level': self.difficulty_level,
            'preferred_depth': self.preferred_depth,
            'learning_style': self.learning_style,
            'content_type_preference': self.content_type_preference,
            'include_examples': self.include_examples,
            'language_preference': self.language_preference,
            'preferred_ai_model': self.preferred_ai_model,
            'study_duration': self.preferred_study_duration,
        }


class StudySummary(models.Model):
    """Enhanced StudySummary with ratings and feedback"""
    
    DIFFICULTY_CHOICES = [
        ('beginner', '초급'),
        ('intermediate', '중급'),
        ('advanced', '고급'),
        ('expert', '전문가'),
    ]
    
    CONTENT_TYPE_CHOICES = [
        ('summary', '요약'),
        ('explanation', '설명'),
        ('example', '예시'),
        ('practice', '연습'),
        ('review', '복습'),
    ]
    
    # Basic info
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='study_summaries'
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='summaries'
    )
    
    # Content
    title = models.CharField(
        max_length=200,
        help_text="요약 제목"
    )
    content = models.TextField(
        help_text="요약 내용"
    )
    content_type = models.CharField(
        max_length=20,
        choices=CONTENT_TYPE_CHOICES,
        default='summary',
        help_text="콘텐츠 유형"
    )
    difficulty_level = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        help_text="난이도"
    )
    
    # AI generation metadata
    ai_model_used = models.CharField(
        max_length=50,
        blank=True,
        help_text="사용된 AI 모델"
    )
    generation_time = models.FloatField(
        null=True,
        blank=True,
        help_text="생성 시간 (초, default=0)"
    )
    token_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="사용된 토큰 수"
    )
    
    # User interaction
    is_read = models.BooleanField(
        default=False,
        help_text="읽음 여부"
    )
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="읽은 시간"
    )
    reading_time = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="읽는데 걸린 시간 (초)"
    )
    
    # Ratings and feedback
    user_rating = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="사용자 평점 (1-5)"
    )
    user_feedback = models.TextField(
        blank=True,
        help_text="사용자 피드백"
    )
    is_bookmarked = models.BooleanField(
        default=False,
        help_text="북마크 여부"
    )
    
    # Topics and tags
    topics_covered = models.JSONField(
        default=list,
        blank=True,
        help_text="다룬 주제들"
    )
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="태그들"
    )
    
    # Related content
    related_summaries = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=False,
        related_name='referenced_by',
        help_text="관련 요약들"
    )
    
    # Timestamps
    generated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'study_summary'
        indexes = [
            models.Index(fields=['user', 'subject']),
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['subject', 'difficulty_level']),
            models.Index(fields=['generated_at']),
            models.Index(fields=['is_bookmarked']),
            models.Index(fields=['user_rating']),
            models.Index(fields=['content_type']),
        ]
        ordering = ['-generated_at']
        verbose_name = '학습 요약'
        verbose_name_plural = '학습 요약들'
    
    def __str__(self) -> str:
        return f"{self.title} - {self.user.email}"
    
    def mark_as_read(self, reading_time: Optional[int] = None) -> None:
        """읽음으로 표시"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            if reading_time:
                self.reading_time = reading_time
            self.save(update_fields=['is_read', 'read_at', 'reading_time'])
    
    def set_rating(self, rating: int, feedback: str = '') -> None:
        """평점 설정"""
        self.user_rating = rating
        self.user_feedback = feedback
        self.save(update_fields=['user_rating', 'user_feedback'])
        
        # Update subject average rating
        self.subject.update_average_rating(rating)
    
    def toggle_bookmark(self) -> bool:
        """북마크 토글"""
        self.is_bookmarked = not self.is_bookmarked
        self.save(update_fields=['is_bookmarked'])
        return self.is_bookmarked
    
    def add_topics(self, topics: List[str]) -> None:
        """주제 추가"""
        current_topics = set(self.topics_covered)
        new_topics = set(topics)
        self.topics_covered = list(current_topics.union(new_topics))
        self.save(update_fields=['topics_covered'])
    
    def get_reading_stats(self) -> Dict[str, Any]:
        """읽기 통계 반환"""
        return {
            'is_read': self.is_read,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'reading_time': self.reading_time,
            'user_rating': self.user_rating,
            'is_bookmarked': self.is_bookmarked,
            'topics_count': len(self.topics_covered),
        }


class StudyProgress(models.Model):
    """Enhanced StudyProgress with detailed analytics"""
    
    # Basic info
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='study_progress'
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='user_progress'
    )
    
    # Learning progress
    topics_learned = models.JSONField(
        default=list,
        help_text="학습한 주제들"
    )
    mastery_levels = models.JSONField(
        default=dict,
        help_text="주제별 숙련도 (topic: level)"
    )
    
    # Activity counters
    total_summaries_read = models.PositiveIntegerField(
        default=0,
        help_text="읽은 요약 수"
    )
    total_quizzes_completed = models.PositiveIntegerField(
        default=0,
        help_text="완료한 퀴즈 수"
    )
    total_study_time = models.DurationField(
        default=timedelta(0),
        help_text="총 학습 시간"
    )
    
    # Streaks and consistency
    current_streak = models.PositiveIntegerField(
        default=0,
        help_text="현재 연속 학습 일수"
    )
    longest_streak = models.PositiveIntegerField(
        default=0,
        help_text="최장 연속 학습 일수"
    )
    study_frequency = models.FloatField(
        default=0.0,
        help_text="주간 학습 빈도 (0.0-7.0)"
    )
    
    # Performance metrics
    average_rating_given = models.FloatField(
        default=0.0,
        help_text="부여한 평균 평점"
    )
    completion_rate = models.FloatField(
        default=0.0,
        help_text="완료율 (0.0-1.0)"
    )
    
    # Goals and targets
    weekly_goal = models.PositiveIntegerField(
        default=7,
        help_text="주간 목표 (요약 읽기 수)"
    )
    monthly_goal = models.PositiveIntegerField(
        default=30,
        help_text="월간 목표 (요약 읽기 수)"
    )
    
    # Study patterns
    preferred_study_hours = models.JSONField(
        default=list,
        help_text="선호하는 학습 시간대"
    )
    study_session_count = models.PositiveIntegerField(
        default=0,
        help_text="총 학습 세션 수"
    )
    average_session_duration = models.FloatField(
        default=0.0,
        help_text="평균 세션 지속 시간 (분)"
    )
    
    # Achievements
    badges_earned = models.JSONField(
        default=list,
        help_text="획득한 배지들"
    )
    milestones_reached = models.JSONField(
        default=list,
        help_text="달성한 마일스톤들"
    )
    
    # Timestamps
    last_activity_date = models.DateField(
        auto_now=True,
        help_text="마지막 활동 날짜"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'study_progress'
        unique_together = ['user', 'subject']
        indexes = [
            models.Index(fields=['user', 'subject']),
            models.Index(fields=['current_streak']),
            models.Index(fields=['total_summaries_read']),
            models.Index(fields=['last_activity_date']),
            models.Index(fields=['completion_rate']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = '학습 진도'
        verbose_name_plural = '학습 진도들'
    
    def __str__(self) -> str:
        return f"{self.user.email} - {self.subject.name} 진도"
    
    def update_streak(self, increment: bool = True) -> None:
        """연속 학습 일수 업데이트"""
        if increment:
            self.current_streak += 1
            if self.current_streak > self.longest_streak:
                self.longest_streak = self.current_streak
        else:
            self.current_streak = 0
        
        self.save(update_fields=['current_streak', 'longest_streak'])
    
    def add_study_time(self, duration: timedelta) -> None:
        """학습 시간 추가"""
        self.total_study_time += duration
        self.study_session_count += 1
        
        # Update average session duration
        total_minutes = self.total_study_time.total_seconds() / 60
        self.average_session_duration = total_minutes / self.study_session_count
        
        self.save(update_fields=['total_study_time', 'study_session_count', 'average_session_duration'])
    
    def update_mastery_level(self, topic: str, level: float) -> None:
        """주제별 숙련도 업데이트"""
        if not isinstance(self.mastery_levels, dict):
            self.mastery_levels = {}
        
        self.mastery_levels[topic] = max(0.0, min(1.0, level))  # 0.0-1.0 범위로 제한
        self.save(update_fields=['mastery_levels'])
    
    def add_badge(self, badge_name: str) -> None:
        """배지 추가"""
        if badge_name not in self.badges_earned:
            self.badges_earned.append(badge_name)
            self.save(update_fields=['badges_earned'])
    
    def calculate_completion_rate(self) -> float:
        """완료율 계산"""
        if self.total_summaries_read == 0:
            return 0.0
        
        # 읽은 요약 중 평점을 부여한 비율
        rated_summaries = StudySummary.objects.filter(
            user=self.user,
            subject=self.subject,
            user_rating__isnull=False
        ).count()
        
        self.completion_rate = rated_summaries / self.total_summaries_read
        self.save(update_fields=['completion_rate'])
        return self.completion_rate
    
    def get_weekly_progress(self) -> Dict[str, Any]:
        """주간 진도 반환"""
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        
        weekly_summaries = StudySummary.objects.filter(
            user=self.user,
            subject=self.subject,
            generated_at__date__gte=week_start,
            is_read=True
        ).count()
        
        return {
            'weekly_target': self.weekly_goal,
            'weekly_completed': weekly_summaries,
            'progress_percentage': min((weekly_summaries / self.weekly_goal) * 100, 100) if self.weekly_goal > 0 else 0,
            'days_left_in_week': 7 - today.weekday(),
            'on_track': weekly_summaries >= (self.weekly_goal * (today.weekday() + 1) / 7)
        }
    
    def get_learning_insights(self) -> Dict[str, Any]:
        """학습 인사이트 반환"""
        return {
            'total_topics': len(self.topics_learned),
            'mastery_average': sum(self.mastery_levels.values()) / len(self.mastery_levels) if self.mastery_levels else 0,
            'study_consistency': self.current_streak,
            'performance_trend': self.average_rating_given,
            'weekly_frequency': self.study_frequency,
            'badges_count': len(self.badges_earned),
            'total_study_hours': self.total_study_time.total_seconds() / 3600,
            'average_session_minutes': self.average_session_duration,
        }


class StudyGoal(models.Model):
    """Study goals and targets for users"""
    
    GOAL_TYPE_CHOICES = [
        ('daily', '일일'),
        ('weekly', '주간'),
        ('monthly', '월간'),
        ('custom', '사용자 정의'),
    ]
    
    STATUS_CHOICES = [
        ('active', '활성'),
        ('completed', '완료'),
        ('paused', '일시정지'),
        ('cancelled', '취소'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='study_goals'
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="특정 과목 (null이면 전체)"
    )
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    goal_type = models.CharField(max_length=20, choices=GOAL_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Target metrics
    target_summaries = models.PositiveIntegerField(default=0)
    target_quizzes = models.PositiveIntegerField(default=0)
    target_study_time = models.DurationField(default=timedelta(0))
    
    # Progress tracking
    current_summaries = models.PositiveIntegerField(default=0)
    current_quizzes = models.PositiveIntegerField(default=0)
    current_study_time = models.DurationField(default=timedelta(0))
    
    # Timeline
    start_date = models.DateField()
    end_date = models.DateField()
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'study_goal'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['end_date']),
            models.Index(fields=['goal_type']),
        ]
        verbose_name = '학습 목표'
        verbose_name_plural = '학습 목표들'
    
    def __str__(self) -> str:
        return f"{self.user.email} - {self.title}"
    
    def calculate_progress(self) -> Dict[str, float]:
        """목표 달성 진도 계산"""
        progress = {}
        
        if self.target_summaries > 0:
            progress['summaries'] = min((self.current_summaries / self.target_summaries) * 100, 100)
        
        if self.target_quizzes > 0:
            progress['quizzes'] = min((self.current_quizzes / self.target_quizzes) * 100, 100)
        
        if self.target_study_time.total_seconds() > 0:
            progress['study_time'] = min(
                (self.current_study_time.total_seconds() / self.target_study_time.total_seconds()) * 100, 100
            )
        
        return progress
    
    def is_completed(self) -> bool:
        """목표 완료 여부 확인"""
        progress = self.calculate_progress()
        return all(p >= 100 for p in progress.values()) if progress else False
    
    def days_remaining(self) -> int:
        """남은 일수"""
        today = timezone.now().date()
        return max((self.end_date - today).days, 0)