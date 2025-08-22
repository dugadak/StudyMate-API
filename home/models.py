from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from typing import Dict, Any


class Dashboard(models.Model):
    """사용자 대시보드 통계 및 데이터"""
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='dashboard'
    )
    
    # 학습 통계
    streak_days = models.PositiveIntegerField(default=0, help_text="연속 학습 일수")
    total_study_minutes = models.PositiveIntegerField(default=0, help_text="총 학습 시간(분)")
    total_quizzes_taken = models.PositiveIntegerField(default=0, help_text="총 퀴즈 응시 수")
    average_accuracy = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="평균 정답률")
    achievement_score = models.PositiveIntegerField(default=0, help_text="성취도 점수")
    
    # 최근 활동
    last_study_date = models.DateField(null=True, blank=True, help_text="마지막 학습 날짜")
    last_quiz_date = models.DateField(null=True, blank=True, help_text="마지막 퀴즈 날짜")
    daily_goal_minutes = models.PositiveIntegerField(default=30, help_text="일일 목표 학습 시간(분)")
    daily_completed_minutes = models.PositiveIntegerField(default=0, help_text="오늘 완료한 학습 시간(분)")
    
    # 타임스탬프
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'home_dashboard'
        verbose_name = '대시보드'
        verbose_name_plural = '대시보드'
    
    def __str__(self):
        return f"{self.user.email} 대시보드"
    
    def update_streak(self):
        """연속 학습 일수 업데이트"""
        today = timezone.now().date()
        if self.last_study_date:
            if self.last_study_date == today - timedelta(days=1):
                self.streak_days += 1
            elif self.last_study_date < today - timedelta(days=1):
                self.streak_days = 1
        else:
            self.streak_days = 1
        self.last_study_date = today
        self.save()
    
    def get_progress_percentage(self) -> int:
        """오늘의 목표 달성률 계산"""
        if self.daily_goal_minutes == 0:
            return 100
        return min(100, int((self.daily_completed_minutes / self.daily_goal_minutes) * 100))
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """대시보드 데이터 반환"""
        return {
            'streak_days': self.streak_days,
            'total_study_minutes': self.total_study_minutes,
            'total_quizzes_taken': self.total_quizzes_taken,
            'average_accuracy': float(self.average_accuracy),
            'achievement_score': self.achievement_score,
            'daily_progress': self.get_progress_percentage(),
            'daily_completed_minutes': self.daily_completed_minutes,
            'daily_goal_minutes': self.daily_goal_minutes,
        }


class StudyPattern(models.Model):
    """학습 패턴 분석 데이터"""
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='study_patterns'
    )
    
    date = models.DateField(help_text="날짜")
    hour = models.PositiveSmallIntegerField(help_text="시간 (0-23)")
    study_minutes = models.PositiveIntegerField(default=0, help_text="학습 시간(분)")
    quiz_count = models.PositiveIntegerField(default=0, help_text="퀴즈 응시 수")
    accuracy_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="정답률")
    focus_score = models.PositiveIntegerField(default=0, help_text="집중도 점수 (0-100)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'home_study_pattern'
        unique_together = [['user', 'date', 'hour']]
        indexes = [
            models.Index(fields=['user', 'date']),
            models.Index(fields=['date', 'hour']),
        ]
        verbose_name = '학습 패턴'
        verbose_name_plural = '학습 패턴'
    
    def __str__(self):
        return f"{self.user.email} - {self.date} {self.hour}시"


class DailyGoal(models.Model):
    """일일 학습 목표"""
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='daily_goals'
    )
    
    date = models.DateField(help_text="목표 날짜")
    target_minutes = models.PositiveIntegerField(default=30, help_text="목표 학습 시간(분)")
    target_quizzes = models.PositiveIntegerField(default=5, help_text="목표 퀴즈 수")
    completed_minutes = models.PositiveIntegerField(default=0, help_text="완료한 학습 시간(분)")
    completed_quizzes = models.PositiveIntegerField(default=0, help_text="완료한 퀴즈 수")
    is_achieved = models.BooleanField(default=False, help_text="목표 달성 여부")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'home_daily_goal'
        unique_together = [['user', 'date']]
        indexes = [
            models.Index(fields=['user', 'date']),
            models.Index(fields=['is_achieved']),
        ]
        verbose_name = '일일 목표'
        verbose_name_plural = '일일 목표'
    
    def __str__(self):
        return f"{self.user.email} - {self.date} 목표"
    
    def check_achievement(self):
        """목표 달성 여부 확인 및 업데이트"""
        if (self.completed_minutes >= self.target_minutes and 
            self.completed_quizzes >= self.target_quizzes):
            self.is_achieved = True
            self.save()
            return True
        return False