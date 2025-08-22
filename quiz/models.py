from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.db.models import Q, Count, Avg
from typing import Dict, Any, List, Optional
from datetime import timedelta
import json
import random

from study.models import Subject


class Quiz(models.Model):
    """Enhanced Quiz model with comprehensive features and analytics"""
    
    QUIZ_TYPE_CHOICES = [
        ('multiple_choice', '객관식'),
        ('short_answer', '주관식'),
        ('true_false', 'True/False'),
        ('fill_blank', '빈칸 채우기'),
        ('matching', '매칭'),
    ]
    
    DIFFICULTY_CHOICES = [
        ('beginner', '초급'),
        ('intermediate', '중급'),
        ('advanced', '고급'),
        ('expert', '전문가'),
    ]
    
    STATUS_CHOICES = [
        ('active', '활성'),
        ('inactive', '비활성'),
        ('draft', '초안'),
        ('review', '검토중'),
    ]
    
    # Basic information
    subject = models.ForeignKey(
        Subject, 
        on_delete=models.CASCADE,
        related_name='quizzes'
    )
    title = models.CharField(
        max_length=200,
        help_text="퀴즈 제목"
    )
    question = models.TextField(
        help_text="퀴즈 질문 내용"
    )
    quiz_type = models.CharField(
        max_length=20, 
        choices=QUIZ_TYPE_CHOICES,
        default='multiple_choice'
    )
    difficulty_level = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default='beginner'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )
    
    # Content and learning
    explanation = models.TextField(
        help_text="정답 해설"
    )
    related_knowledge = models.TextField(
        blank=True,
        help_text="관련된 추가 지식 정보"
    )
    hints = models.JSONField(
        default=list,
        blank=True,
        help_text="힌트 목록"
    )
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="태그 목록"
    )
    topics_covered = models.JSONField(
        default=list,
        blank=True,
        help_text="다루는 주제들"
    )
    
    # Difficulty and timing
    estimated_time_seconds = models.PositiveIntegerField(
        default=60,
        validators=[MinValueValidator(10), MaxValueValidator(3600)],
        help_text="예상 소요 시간 (초)"
    )
    points = models.PositiveIntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="배점"
    )
    
    # Analytics
    total_attempts = models.PositiveIntegerField(
        default=0,
        help_text="총 시도 횟수"
    )
    correct_attempts = models.PositiveIntegerField(
        default=0,
        help_text="정답 횟수"
    )
    average_time_spent = models.FloatField(
        default=0.0,
        help_text="평균 소요 시간 (초)"
    )
    difficulty_rating = models.FloatField(
        default=0.0,
        help_text="실제 체감 난이도 (0.0-5.0)"
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
    allow_multiple_attempts = models.BooleanField(
        default=True,
        help_text="중복 시도 허용"
    )
    shuffle_choices = models.BooleanField(
        default=True,
        help_text="선택지 순서 섞기"
    )
    
    # AI generation metadata
    ai_generated = models.BooleanField(
        default=False,
        help_text="AI로 생성된 퀴즈 여부"
    )
    ai_model_used = models.CharField(
        max_length=50,
        blank=True,
        help_text="사용된 AI 모델"
    )
    generation_prompt = models.TextField(
        blank=True,
        help_text="생성에 사용된 프롬프트"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_attempted_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="마지막 시도 시간"
    )
    
    class Meta:
        db_table = 'quiz_quiz'
        indexes = [
            models.Index(fields=['subject', 'is_active']),
            models.Index(fields=['difficulty_level', 'quiz_type']),
            models.Index(fields=['total_attempts']),
            models.Index(fields=['correct_attempts']),
            models.Index(fields=['created_at']),
            models.Index(fields=['status']),
        ]
        ordering = ['-created_at']
        verbose_name = '퀴즈'
        verbose_name_plural = '퀴즈들'
    
    def __str__(self) -> str:
        return f"{self.title} ({self.get_quiz_type_display()}) - {self.subject.name}"
    
    @property
    def success_rate(self) -> float:
        """정답률 계산"""
        if self.total_attempts == 0:
            return 0.0
        return (self.correct_attempts / self.total_attempts) * 100
    
    @property
    def estimated_time_minutes(self) -> float:
        """예상 소요 시간 (분)"""
        return self.estimated_time_seconds / 60
    
    def increment_attempt(self, is_correct: bool, time_spent: Optional[int] = None) -> None:
        """시도 횟수 증가 및 통계 업데이트"""
        self.total_attempts += 1
        if is_correct:
            self.correct_attempts += 1
        
        # Update average time spent
        if time_spent:
            if self.average_time_spent == 0:
                self.average_time_spent = time_spent
            else:
                # Moving average
                self.average_time_spent = (
                    (self.average_time_spent * (self.total_attempts - 1) + time_spent) / 
                    self.total_attempts
                )
        
        self.last_attempted_at = timezone.now()
        self.save(update_fields=[
            'total_attempts', 'correct_attempts', 'average_time_spent', 'last_attempted_at'
        ])
    
    def get_choices(self, shuffle: bool = None) -> List['QuizChoice']:
        """선택지 가져오기 (선택적으로 순서 섞기)"""
        choices = list(self.choices.all())
        
        if shuffle is None:
            shuffle = self.shuffle_choices
        
        if shuffle and len(choices) > 1:
            random.shuffle(choices)
        else:
            choices.sort(key=lambda x: x.order)
        
        return choices
    
    def get_correct_choices(self) -> List['QuizChoice']:
        """정답 선택지들 가져오기"""
        return list(self.choices.filter(is_correct=True))
    
    def check_answer(self, user_answer: str) -> bool:
        """답안 검증"""
        if self.quiz_type == 'multiple_choice':
            try:
                choice_id = int(user_answer)
                return self.choices.filter(id=choice_id, is_correct=True).exists()
            except (ValueError, TypeError):
                return False
        
        elif self.quiz_type == 'true_false':
            correct_choice = self.choices.filter(is_correct=True).first()
            if correct_choice:
                return user_answer.lower() == correct_choice.choice_text.lower()
            return False
        
        elif self.quiz_type == 'short_answer':
            correct_choices = self.get_correct_choices()
            user_answer_lower = user_answer.lower().strip()
            
            for choice in correct_choices:
                if user_answer_lower == choice.choice_text.lower().strip():
                    return True
            return False
        
        elif self.quiz_type == 'fill_blank':
            # Similar to short answer but might have multiple blanks
            return self.check_answer(user_answer)  # Same logic for now
        
        return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """퀴즈 통계 반환"""
        return {
            'total_attempts': self.total_attempts,
            'correct_attempts': self.correct_attempts,
            'success_rate': self.success_rate,
            'average_time_spent': self.average_time_spent,
            'difficulty_rating': self.difficulty_rating,
            'estimated_time': self.estimated_time_seconds,
            'points': self.points,
            'last_attempted': self.last_attempted_at.isoformat() if self.last_attempted_at else None
        }
    
    def get_hints_list(self) -> List[str]:
        """힌트 목록 반환"""
        return self.hints if isinstance(self.hints, list) else []
    
    def add_hint(self, hint: str) -> None:
        """힌트 추가"""
        hints = self.get_hints_list()
        if hint not in hints:
            hints.append(hint)
            self.hints = hints
            self.save(update_fields=['hints'])
    
    def update_difficulty_rating(self, new_rating: float) -> None:
        """난이도 평점 업데이트 (이동 평균)"""
        if self.difficulty_rating == 0:
            self.difficulty_rating = new_rating
        else:
            # Moving average with weight
            weight = 0.1
            self.difficulty_rating = (
                self.difficulty_rating * (1 - weight) + new_rating * weight
            )
        
        self.save(update_fields=['difficulty_rating'])


class QuizChoice(models.Model):
    """Enhanced Quiz Choice model with additional features"""
    
    quiz = models.ForeignKey(
        Quiz, 
        on_delete=models.CASCADE, 
        related_name='choices'
    )
    choice_text = models.TextField(
        help_text="선택지 텍스트"
    )
    is_correct = models.BooleanField(
        default=False,
        help_text="정답 여부"
    )
    order = models.IntegerField(
        default=0,
        help_text="표시 순서"
    )
    explanation = models.TextField(
        blank=True,
        help_text="이 선택지에 대한 설명"
    )
    
    # Analytics
    selection_count = models.PositiveIntegerField(
        default=0,
        help_text="선택된 횟수"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'quiz_choice'
        indexes = [
            models.Index(fields=['quiz', 'order']),
            models.Index(fields=['is_correct']),
            models.Index(fields=['selection_count']),
        ]
        ordering = ['order']
        verbose_name = '퀴즈 선택지'
        verbose_name_plural = '퀴즈 선택지들'
        unique_together = ['quiz', 'order']
    
    def __str__(self) -> str:
        return f"{self.quiz.title} - {self.choice_text[:50]}..."
    
    def increment_selection(self) -> None:
        """선택 횟수 증가"""
        self.selection_count += 1
        self.save(update_fields=['selection_count'])
    
    @property
    def selection_percentage(self) -> float:
        """이 선택지가 선택된 비율"""
        if self.quiz.total_attempts == 0:
            return 0.0
        return (self.selection_count / self.quiz.total_attempts) * 100


class QuizAttempt(models.Model):
    """Enhanced Quiz Attempt model with detailed tracking"""
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='quiz_attempts'
    )
    quiz = models.ForeignKey(
        Quiz, 
        on_delete=models.CASCADE,
        related_name='attempts'
    )
    session = models.ForeignKey(
        'QuizSession',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='attempts',
        help_text="소속 세션 (옵션)"
    )
    
    # Answer data
    user_answer = models.TextField(
        help_text="사용자 답안"
    )
    selected_choice = models.ForeignKey(
        QuizChoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="선택된 선택지 (객관식의 경우)"
    )
    is_correct = models.BooleanField(
        help_text="정답 여부"
    , default=False)
    
    # Timing
    started_at = models.DateTimeField(
        help_text="시작 시간"
    , null=True, blank=True)
    attempted_at = models.DateTimeField(
        auto_now_add=True,
        help_text="제출 시간"
    )
    time_spent = models.DurationField(
        null=True, 
        blank=True,
        help_text="소요 시간"
    )
    
    # User experience
    difficulty_rating = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="사용자가 느낀 난이도 (1-5)"
    )
    feedback = models.TextField(
        blank=True,
        help_text="사용자 피드백"
    )
    
    # Tracking
    hints_used = models.JSONField(
        default=list,
        blank=True,
        help_text="사용된 힌트들"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP 주소"
    )
    user_agent = models.TextField(
        blank=True,
        help_text="User Agent"
    )
    
    # Points and scoring
    points_earned = models.PositiveIntegerField(
        default=0,
        help_text="획득 점수"
    )
    bonus_points = models.PositiveIntegerField(
        default=0,
        help_text="보너스 점수"
    )
    
    class Meta:
        db_table = 'quiz_attempt'
        indexes = [
            models.Index(fields=['user', 'quiz']),
            models.Index(fields=['user', 'is_correct']),
            models.Index(fields=['quiz', 'is_correct']),
            models.Index(fields=['attempted_at']),
            models.Index(fields=['session']),
        ]
        ordering = ['-attempted_at']
        verbose_name = '퀴즈 시도'
        verbose_name_plural = '퀴즈 시도들'
    
    def __str__(self) -> str:
        return f"{self.user.email} - {self.quiz.title} ({'정답' if self.is_correct else '오답'})"
    
    def save(self, *args, **kwargs):
        """저장 시 점수 계산 및 통계 업데이트"""
        # Calculate time spent if not set
        if not self.time_spent and self.started_at:
            self.time_spent = timezone.now() - self.started_at
        
        # Calculate points
        if self.is_correct and self.points_earned == 0:
            base_points = self.quiz.points
            
            # Time bonus (faster = more points)
            time_bonus = 0
            if self.time_spent and self.quiz.estimated_time_seconds > 0:
                time_ratio = self.time_spent.total_seconds() / self.quiz.estimated_time_seconds
                if time_ratio < 0.5:  # Very fast
                    time_bonus = int(base_points * 0.5)
                elif time_ratio < 0.8:  # Fast
                    time_bonus = int(base_points * 0.2)
            
            # Difficulty bonus
            difficulty_bonus = {
                'beginner': 0,
                'intermediate': int(base_points * 0.1),
                'advanced': int(base_points * 0.2),
                'expert': int(base_points * 0.3),
            }.get(self.quiz.difficulty_level, 0)
            
            self.points_earned = base_points
            self.bonus_points = time_bonus + difficulty_bonus
        
        super().save(*args, **kwargs)
        
        # Update quiz statistics
        time_spent_seconds = self.time_spent.total_seconds() if self.time_spent else None
        self.quiz.increment_attempt(self.is_correct, time_spent_seconds)
        
        # Update choice statistics
        if self.selected_choice:
            self.selected_choice.increment_selection()
    
    @property
    def total_points(self) -> int:
        """총 획득 점수"""
        return self.points_earned + self.bonus_points
    
    @property
    def time_spent_seconds(self) -> Optional[float]:
        """소요 시간 (초)"""
        return self.time_spent.total_seconds() if self.time_spent else None
    
    def get_hints_used_list(self) -> List[str]:
        """사용된 힌트 목록"""
        return self.hints_used if isinstance(self.hints_used, list) else []
    
    def add_hint_used(self, hint: str) -> None:
        """사용된 힌트 추가"""
        hints = self.get_hints_used_list()
        if hint not in hints:
            hints.append(hint)
            self.hints_used = hints
            self.save(update_fields=['hints_used'])


class QuizSession(models.Model):
    """Enhanced Quiz Session model with comprehensive tracking"""
    
    SESSION_TYPE_CHOICES = [
        ('practice', '연습'),
        ('test', '시험'),
        ('review', '복습'),
        ('adaptive', '적응형'),
    ]
    
    STATUS_CHOICES = [
        ('active', '진행중'),
        ('completed', '완료'),
        ('paused', '일시정지'),
        ('abandoned', '중단'),
    ]
    
    # Basic information
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='quiz_sessions'
    )
    subject = models.ForeignKey(
        Subject, 
        on_delete=models.CASCADE,
        related_name='quiz_sessions'
    )
    
    # Session configuration
    session_type = models.CharField(
        max_length=20,
        choices=SESSION_TYPE_CHOICES,
        default='practice'
    )
    difficulty_level = models.CharField(
        max_length=20,
        choices=Quiz.DIFFICULTY_CHOICES,
        null=True,
        blank=True,
        help_text="세션 난이도 (필터링용)"
    )
    target_questions = models.PositiveIntegerField(
        help_text="목표 문제 수"
    )
    time_limit = models.DurationField(
        null=True,
        blank=True,
        help_text="제한 시간 (옵션)"
    )
    
    # Progress tracking
    total_questions = models.PositiveIntegerField(
        default=0,
        help_text="실제 출제된 문제 수"
    )
    answered_questions = models.PositiveIntegerField(
        default=0,
        help_text="답변한 문제 수"
    )
    correct_answers = models.PositiveIntegerField(
        default=0,
        help_text="정답 수"
    )
    
    # Scoring
    total_points = models.PositiveIntegerField(
        default=0,
        help_text="총 획득 점수"
    )
    max_possible_points = models.PositiveIntegerField(
        default=0,
        help_text="최대 가능 점수"
    )
    
    # Status and timing
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )
    started_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    completed_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="완료 시간"
    )
    paused_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="일시정지 시간"
    )
    total_pause_time = models.DurationField(
        default=timedelta(0),
        help_text="총 일시정지 시간"
    )
    
    # Analytics
    average_time_per_question = models.FloatField(
        default=0.0,
        help_text="문제당 평균 소요 시간 (초)"
    )
    difficulty_feedback = models.JSONField(
        default=dict,
        blank=True,
        help_text="난이도별 피드백"
    )
    topics_covered = models.JSONField(
        default=list,
        blank=True,
        help_text="다룬 주제들"
    )
    
    # Settings
    settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="세션 설정 (힌트 허용, 재시도 등)"
    )
    
    class Meta:
        db_table = 'quiz_session'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['subject', 'session_type']),
            models.Index(fields=['started_at']),
            models.Index(fields=['completed_at']),
            models.Index(fields=['status']),
        ]
        ordering = ['-started_at']
        verbose_name = '퀴즈 세션'
        verbose_name_plural = '퀴즈 세션들'
    
    def __str__(self) -> str:
        return f"{self.user.email} - {self.subject.name} {self.get_session_type_display()} ({self.correct_answers}/{self.total_questions})"
    
    @property
    def score_percentage(self) -> float:
        """정답률"""
        if self.total_questions == 0:
            return 0.0
        return (self.correct_answers / self.total_questions) * 100
    
    @property
    def points_percentage(self) -> float:
        """점수 비율"""
        if self.max_possible_points == 0:
            return 0.0
        return (self.total_points / self.max_possible_points) * 100
    
    @property
    def is_completed(self) -> bool:
        """완료 여부"""
        return self.status == 'completed'
    
    @property
    def duration(self) -> Optional[timedelta]:
        """실제 소요 시간 (일시정지 시간 제외)"""
        if not self.completed_at:
            return None
        
        total_time = self.completed_at - self.started_at
        return total_time - self.total_pause_time
    
    @property
    def remaining_questions(self) -> int:
        """남은 문제 수"""
        return max(0, self.target_questions - self.answered_questions)
    
    def add_attempt(self, attempt: 'QuizAttempt') -> None:
        """시도 추가 및 통계 업데이트"""
        self.answered_questions += 1
        if attempt.is_correct:
            self.correct_answers += 1
        
        self.total_points += attempt.total_points
        self.max_possible_points += attempt.quiz.points
        
        # Update average time
        if attempt.time_spent:
            if self.average_time_per_question == 0:
                self.average_time_per_question = attempt.time_spent.total_seconds()
            else:
                # Moving average
                total_time = self.average_time_per_question * (self.answered_questions - 1)
                total_time += attempt.time_spent.total_seconds()
                self.average_time_per_question = total_time / self.answered_questions
        
        # Add topics
        if attempt.quiz.topics_covered:
            current_topics = set(self.topics_covered)
            new_topics = set(attempt.quiz.topics_covered)
            self.topics_covered = list(current_topics.union(new_topics))
        
        self.save(update_fields=[
            'answered_questions', 'correct_answers', 'total_points', 
            'max_possible_points', 'average_time_per_question', 'topics_covered'
        ])
    
    def complete_session(self) -> None:
        """세션 완료 처리"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.total_questions = self.answered_questions
        self.save(update_fields=['status', 'completed_at', 'total_questions'])
    
    def pause_session(self) -> None:
        """세션 일시정지"""
        if self.status == 'active':
            self.status = 'paused'
            self.paused_at = timezone.now()
            self.save(update_fields=['status', 'paused_at'])
    
    def resume_session(self) -> None:
        """세션 재개"""
        if self.status == 'paused' and self.paused_at:
            pause_duration = timezone.now() - self.paused_at
            self.total_pause_time += pause_duration
            self.status = 'active'
            self.paused_at = None
            self.save(update_fields=['status', 'paused_at', 'total_pause_time'])
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """세션 성과 요약"""
        return {
            'score_percentage': self.score_percentage,
            'points_percentage': self.points_percentage,
            'total_points': self.total_points,
            'correct_answers': self.correct_answers,
            'total_questions': self.total_questions,
            'average_time_per_question': self.average_time_per_question,
            'duration_minutes': self.duration.total_seconds() / 60 if self.duration else 0,
            'topics_covered': len(self.topics_covered),
            'session_type': self.get_session_type_display(),
            'difficulty_level': self.get_difficulty_level_display() if self.difficulty_level else None
        }
    
    def get_recommended_next_difficulty(self) -> str:
        """다음 권장 난이도"""
        if self.score_percentage >= 90:
            difficulty_levels = ['beginner', 'intermediate', 'advanced', 'expert']
            current_index = difficulty_levels.index(self.difficulty_level or 'beginner')
            next_index = min(current_index + 1, len(difficulty_levels) - 1)
            return difficulty_levels[next_index]
        elif self.score_percentage < 60:
            difficulty_levels = ['beginner', 'intermediate', 'advanced', 'expert']
            current_index = difficulty_levels.index(self.difficulty_level or 'beginner')
            next_index = max(current_index - 1, 0)
            return difficulty_levels[next_index]
        else:
            return self.difficulty_level or 'beginner'


class QuizProgress(models.Model):
    """User's overall quiz progress tracking"""
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='quiz_progress'
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='quiz_progress'
    )
    
    # Overall statistics
    total_quizzes_attempted = models.PositiveIntegerField(
        default=0,
        help_text="총 시도한 퀴즈 수"
    )
    total_quizzes_correct = models.PositiveIntegerField(
        default=0,
        help_text="정답 퀴즈 수"
    )
    total_sessions = models.PositiveIntegerField(
        default=0,
        help_text="총 세션 수"
    )
    total_points_earned = models.PositiveIntegerField(
        default=0,
        help_text="총 획득 점수"
    )
    
    # Streaks and consistency
    current_streak = models.PositiveIntegerField(
        default=0,
        help_text="현재 연속 정답 수"
    )
    longest_streak = models.PositiveIntegerField(
        default=0,
        help_text="최장 연속 정답 수"
    )
    
    # Difficulty progress
    difficulty_levels_mastered = models.JSONField(
        default=list,
        blank=True,
        help_text="마스터한 난이도 레벨들"
    )
    current_difficulty = models.CharField(
        max_length=20,
        choices=Quiz.DIFFICULTY_CHOICES,
        default='beginner',
        help_text="현재 난이도"
    )
    
    # Time tracking
    total_study_time = models.DurationField(
        default=timedelta(0),
        help_text="총 학습 시간"
    )
    average_session_duration = models.FloatField(
        default=0.0,
        help_text="평균 세션 지속 시간 (분)"
    )
    
    # Performance tracking
    recent_performance = models.JSONField(
        default=list,
        blank=True,
        help_text="최근 성과 기록 (최근 10개)"
    )
    weak_topics = models.JSONField(
        default=list,
        blank=True,
        help_text="취약한 주제들"
    )
    strong_topics = models.JSONField(
        default=list,
        blank=True,
        help_text="강한 주제들"
    )
    
    # Achievements
    badges_earned = models.JSONField(
        default=list,
        blank=True,
        help_text="획득한 배지들"
    )
    milestones_reached = models.JSONField(
        default=list,
        blank=True,
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
        db_table = 'quiz_progress'
        unique_together = ['user', 'subject']
        indexes = [
            models.Index(fields=['user', 'subject']),
            models.Index(fields=['current_streak']),
            models.Index(fields=['total_points_earned']),
            models.Index(fields=['last_activity_date']),
        ]
        verbose_name = '퀴즈 진도'
        verbose_name_plural = '퀴즈 진도들'
    
    def __str__(self) -> str:
        return f"{self.user.email} - {self.subject.name} Quiz Progress"
    
    @property
    def overall_accuracy(self) -> float:
        """전체 정답률"""
        if self.total_quizzes_attempted == 0:
            return 0.0
        return (self.total_quizzes_correct / self.total_quizzes_attempted) * 100
    
    def update_progress(self, attempt: QuizAttempt) -> None:
        """시도 결과를 바탕으로 진도 업데이트"""
        self.total_quizzes_attempted += 1
        self.total_points_earned += attempt.total_points
        
        if attempt.is_correct:
            self.total_quizzes_correct += 1
            self.current_streak += 1
            if self.current_streak > self.longest_streak:
                self.longest_streak = self.current_streak
        else:
            self.current_streak = 0
        
        # Update recent performance
        performance_entry = {
            'date': attempt.attempted_at.date().isoformat(),
            'is_correct': attempt.is_correct,
            'points': attempt.total_points,
            'difficulty': attempt.quiz.difficulty_level,
            'time_spent': attempt.time_spent_seconds
        }
        
        recent = self.recent_performance[:9]  # Keep last 9
        recent.insert(0, performance_entry)  # Add new at beginning
        self.recent_performance = recent
        
        self.save()
    
    def get_recommendations(self) -> Dict[str, Any]:
        """학습 추천사항 생성"""
        recommendations = {
            'next_difficulty': self.current_difficulty,
            'focus_topics': [],
            'practice_suggestions': [],
            'time_recommendations': []
        }
        
        # Difficulty recommendations
        if self.overall_accuracy >= 85 and len(self.recent_performance) >= 5:
            recent_accuracy = sum(1 for p in self.recent_performance[:5] if p['is_correct']) / 5
            if recent_accuracy >= 0.8:
                difficulty_levels = ['beginner', 'intermediate', 'advanced', 'expert']
                current_index = difficulty_levels.index(self.current_difficulty)
                if current_index < len(difficulty_levels) - 1:
                    recommendations['next_difficulty'] = difficulty_levels[current_index + 1]
        
        # Topic recommendations
        if self.weak_topics:
            recommendations['focus_topics'] = self.weak_topics[:3]
        
        return recommendations


class QuizCategory(models.Model):
    """Quiz categories for better organization"""
    
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="카테고리 이름"
    )
    description = models.TextField(
        blank=True,
        help_text="카테고리 설명"
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcategories',
        help_text="상위 카테고리"
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="아이콘 클래스"
    )
    color_code = models.CharField(
        max_length=7,
        blank=True,
        help_text="색상 코드"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="활성화 상태"
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text="정렬 순서"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'quiz_category'
        indexes = [
            models.Index(fields=['parent', 'order']),
            models.Index(fields=['is_active']),
        ]
        ordering = ['order', 'name']
        verbose_name = '퀴즈 카테고리'
        verbose_name_plural = '퀴즈 카테고리들'
    
    def __str__(self) -> str:
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name
    
    @property
    def full_path(self) -> str:
        """전체 경로 반환"""
        path = [self.name]
        parent = self.parent
        while parent:
            path.insert(0, parent.name)
            parent = parent.parent
        return ' > '.join(path)
    
    def get_quiz_count(self) -> int:
        """카테고리의 퀴즈 수 (하위 카테고리 포함)"""
        # This would need to be implemented based on how categories are linked to quizzes
        return 0