from django.contrib import admin
from django.db import models
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from typing import Any

from .models import (
    Quiz, QuizChoice, QuizAttempt, QuizSession, 
    QuizProgress, QuizCategory
)


class QuizChoiceInline(admin.TabularInline):
    """Inline admin for quiz choices"""
    model = QuizChoice
    extra = 0
    fields = ['choice_text', 'is_correct', 'order', 'explanation', 'selection_count']
    readonly_fields = ['selection_count']
    ordering = ['order']


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    """Enhanced Quiz admin with comprehensive management"""
    
    list_display = [
        'title', 'subject', 'quiz_type', 'difficulty_level', 'status',
        'success_rate_display', 'total_attempts', 'points', 'is_active', 'created_at'
    ]
    list_filter = [
        'quiz_type', 'difficulty_level', 'status', 'is_active', 'requires_premium',
        'ai_generated', 'subject__category', 'created_at'
    ]
    search_fields = ['title', 'question', 'explanation', 'subject__name']
    readonly_fields = [
        'total_attempts', 'correct_attempts', 'average_time_spent',
        'difficulty_rating', 'last_attempted_at', 'success_rate_display'
    ]
    list_per_page = 25
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'subject', 'title', 'question', 'quiz_type', 'difficulty_level', 'status'
            )
        }),
        ('Content', {
            'fields': (
                'explanation', 'related_knowledge', 'hints', 'tags', 'topics_covered'
            )
        }),
        ('Settings', {
            'fields': (
                'estimated_time_seconds', 'points', 'is_active', 'requires_premium',
                'allow_multiple_attempts', 'shuffle_choices'
            )
        }),
        ('AI Generation', {
            'fields': (
                'ai_generated', 'ai_model_used', 'generation_prompt'
            ),
            'classes': ['collapse']
        }),
        ('Statistics', {
            'fields': (
                'total_attempts', 'correct_attempts', 'success_rate_display',
                'average_time_spent', 'difficulty_rating', 'last_attempted_at'
            ),
            'classes': ['collapse']
        }),
    )
    
    inlines = [QuizChoiceInline]
    
    actions = ['activate_quizzes', 'deactivate_quizzes', 'reset_statistics']
    
    def success_rate_display(self, obj):
        """Display success rate with color coding"""
        rate = obj.success_rate
        if rate >= 80:
            color = 'green'
        elif rate >= 60:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color,
            rate
        )
    success_rate_display.short_description = 'Success Rate'
    success_rate_display.admin_order_field = 'correct_attempts'
    
    def activate_quizzes(self, request, queryset):
        """Bulk activate quizzes"""
        updated = queryset.update(is_active=True, status='active')
        self.message_user(request, f'{updated}개의 퀴즈가 활성화되었습니다.')
    activate_quizzes.short_description = '선택된 퀴즈 활성화'
    
    def deactivate_quizzes(self, request, queryset):
        """Bulk deactivate quizzes"""
        updated = queryset.update(is_active=False, status='inactive')
        self.message_user(request, f'{updated}개의 퀴즈가 비활성화되었습니다.')
    deactivate_quizzes.short_description = '선택된 퀴즈 비활성화'
    
    def reset_statistics(self, request, queryset):
        """Reset quiz statistics"""
        for quiz in queryset:
            quiz.total_attempts = 0
            quiz.correct_attempts = 0
            quiz.average_time_spent = 0.0
            quiz.difficulty_rating = 0.0
            quiz.last_attempted_at = None
            quiz.save()
        
        self.message_user(request, f'{queryset.count()}개의 퀴즈 통계가 초기화되었습니다.')
    reset_statistics.short_description = '통계 초기화'


@admin.register(QuizChoice)
class QuizChoiceAdmin(admin.ModelAdmin):
    """Quiz Choice admin"""
    
    list_display = [
        'quiz', 'choice_text_short', 'is_correct', 'order', 
        'selection_count', 'selection_percentage_display'
    ]
    list_filter = ['is_correct', 'quiz__subject', 'quiz__difficulty_level']
    search_fields = ['choice_text', 'quiz__title']
    readonly_fields = ['selection_count', 'selection_percentage_display']
    list_per_page = 50
    
    def choice_text_short(self, obj):
        """Display shortened choice text"""
        return obj.choice_text[:50] + ('...' if len(obj.choice_text) > 50 else '')
    choice_text_short.short_description = 'Choice Text'
    
    def selection_percentage_display(self, obj):
        """Display selection percentage"""
        return f"{obj.selection_percentage:.1f}%"
    selection_percentage_display.short_description = 'Selection %'


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    """Quiz Attempt admin with analytics"""
    
    list_display = [
        'user', 'quiz_title_short', 'is_correct', 'points_display',
        'time_spent_display', 'difficulty_rating', 'attempted_at'
    ]
    list_filter = [
        'is_correct', 'quiz__difficulty_level', 'quiz__quiz_type',
        'quiz__subject', 'difficulty_rating', 'attempted_at'
    ]
    search_fields = ['user__email', 'quiz__title', 'user_answer']
    readonly_fields = [
        'quiz', 'user', 'is_correct', 'points_earned', 'bonus_points',
        'total_points', 'time_spent_seconds', 'attempted_at'
    ]
    date_hierarchy = 'attempted_at'
    list_per_page = 25
    
    fieldsets = (
        ('Attempt Information', {
            'fields': (
                'user', 'quiz', 'session', 'started_at', 'attempted_at'
            )
        }),
        ('Answer Data', {
            'fields': (
                'user_answer', 'selected_choice', 'is_correct'
            )
        }),
        ('Scoring', {
            'fields': (
                'points_earned', 'bonus_points', 'total_points'
            )
        }),
        ('Timing', {
            'fields': (
                'time_spent', 'time_spent_seconds'
            )
        }),
        ('Feedback', {
            'fields': (
                'difficulty_rating', 'feedback'
            )
        }),
        ('Tracking', {
            'fields': (
                'hints_used', 'ip_address', 'user_agent'
            ),
            'classes': ['collapse']
        }),
    )
    
    def quiz_title_short(self, obj):
        """Display shortened quiz title"""
        return obj.quiz.title[:30] + ('...' if len(obj.quiz.title) > 30 else '')
    quiz_title_short.short_description = 'Quiz'
    
    def points_display(self, obj):
        """Display total points with bonus"""
        total = obj.total_points
        if obj.bonus_points > 0:
            return f"{total} (+{obj.bonus_points})"
        return str(total)
    points_display.short_description = 'Points'
    
    def time_spent_display(self, obj):
        """Display time spent in readable format"""
        if obj.time_spent_seconds:
            if obj.time_spent_seconds < 60:
                return f"{obj.time_spent_seconds:.1f}s"
            else:
                minutes = obj.time_spent_seconds / 60
                return f"{minutes:.1f}m"
        return "-"
    time_spent_display.short_description = 'Time'


@admin.register(QuizSession)
class QuizSessionAdmin(admin.ModelAdmin):
    """Quiz Session admin"""
    
    list_display = [
        'user', 'subject', 'session_type', 'status', 'score_display',
        'progress_display', 'duration_display', 'started_at'
    ]
    list_filter = [
        'session_type', 'status', 'difficulty_level', 'subject', 'started_at'
    ]
    search_fields = ['user__email', 'subject__name']
    readonly_fields = [
        'total_questions', 'answered_questions', 'correct_answers',
        'total_points', 'max_possible_points', 'score_percentage',
        'points_percentage', 'duration_display', 'average_time_per_question'
    ]
    date_hierarchy = 'started_at'
    list_per_page = 25
    
    fieldsets = (
        ('Session Information', {
            'fields': (
                'user', 'subject', 'session_type', 'difficulty_level', 'status'
            )
        }),
        ('Configuration', {
            'fields': (
                'target_questions', 'time_limit'
            )
        }),
        ('Progress', {
            'fields': (
                'total_questions', 'answered_questions', 'correct_answers'
            )
        }),
        ('Scoring', {
            'fields': (
                'total_points', 'max_possible_points', 'score_percentage', 'points_percentage'
            )
        }),
        ('Timing', {
            'fields': (
                'started_at', 'completed_at', 'paused_at', 'total_pause_time',
                'duration_display', 'average_time_per_question'
            )
        }),
        ('Analytics', {
            'fields': (
                'difficulty_feedback', 'topics_covered'
            ),
            'classes': ['collapse']
        }),
    )
    
    def score_display(self, obj):
        """Display score with color coding"""
        score = obj.score_percentage
        if score >= 80:
            color = 'green'
        elif score >= 60:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color,
            score
        )
    score_display.short_description = 'Score'
    
    def progress_display(self, obj):
        """Display progress fraction"""
        return f"{obj.answered_questions}/{obj.target_questions}"
    progress_display.short_description = 'Progress'
    
    def duration_display(self, obj):
        """Display session duration"""
        if obj.duration:
            total_minutes = obj.duration.total_seconds() / 60
            if total_minutes < 60:
                return f"{total_minutes:.1f}m"
            else:
                hours = total_minutes / 60
                return f"{hours:.1f}h"
        return "-"
    duration_display.short_description = 'Duration'


@admin.register(QuizProgress)
class QuizProgressAdmin(admin.ModelAdmin):
    """Quiz Progress admin"""
    
    list_display = [
        'user', 'subject', 'accuracy_display', 'current_streak',
        'total_points_earned', 'current_difficulty', 'last_activity_date'
    ]
    list_filter = [
        'current_difficulty', 'subject', 'last_activity_date'
    ]
    search_fields = ['user__email', 'subject__name']
    readonly_fields = [
        'total_quizzes_attempted', 'total_quizzes_correct', 'overall_accuracy',
        'total_sessions', 'total_points_earned', 'current_streak', 'longest_streak',
        'total_study_time', 'average_session_duration'
    ]
    list_per_page = 25
    
    fieldsets = (
        ('User Information', {
            'fields': (
                'user', 'subject'
            )
        }),
        ('Statistics', {
            'fields': (
                'total_quizzes_attempted', 'total_quizzes_correct', 'overall_accuracy',
                'total_sessions', 'total_points_earned'
            )
        }),
        ('Streaks', {
            'fields': (
                'current_streak', 'longest_streak'
            )
        }),
        ('Difficulty Progress', {
            'fields': (
                'difficulty_levels_mastered', 'current_difficulty'
            )
        }),
        ('Time Tracking', {
            'fields': (
                'total_study_time', 'average_session_duration'
            )
        }),
        ('Performance Analysis', {
            'fields': (
                'recent_performance', 'weak_topics', 'strong_topics'
            ),
            'classes': ['collapse']
        }),
        ('Achievements', {
            'fields': (
                'badges_earned', 'milestones_reached'
            ),
            'classes': ['collapse']
        }),
    )
    
    def accuracy_display(self, obj):
        """Display accuracy with color coding"""
        accuracy = obj.overall_accuracy
        if accuracy >= 80:
            color = 'green'
        elif accuracy >= 60:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color,
            accuracy
        )
    accuracy_display.short_description = 'Accuracy'


@admin.register(QuizCategory)
class QuizCategoryAdmin(admin.ModelAdmin):
    """Quiz Category admin"""
    
    list_display = [
        'name', 'parent', 'full_path', 'quiz_count_display',
        'is_active', 'order', 'created_at'
    ]
    list_filter = ['is_active', 'parent', 'created_at']
    search_fields = ['name', 'description']
    list_editable = ['order', 'is_active']
    ordering = ['parent', 'order', 'name']
    
    fieldsets = (
        ('Category Information', {
            'fields': (
                'name', 'description', 'parent'
            )
        }),
        ('Display', {
            'fields': (
                'icon', 'color_code', 'order'
            )
        }),
        ('Settings', {
            'fields': (
                'is_active',
            )
        }),
    )
    
    def quiz_count_display(self, obj):
        """Display quiz count"""
        count = obj.get_quiz_count()
        return format_html('<strong>{}</strong>', count)
    quiz_count_display.short_description = 'Quiz Count'
    
    actions = ['activate_categories', 'deactivate_categories']
    
    def activate_categories(self, request, queryset):
        """Bulk activate categories"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated}개의 카테고리가 활성화되었습니다.')
    activate_categories.short_description = '선택된 카테고리 활성화'
    
    def deactivate_categories(self, request, queryset):
        """Bulk deactivate categories"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated}개의 카테고리가 비활성화되었습니다.')
    deactivate_categories.short_description = '선택된 카테고리 비활성화'


# Admin site customization
admin.site.site_header = "StudyMate Quiz 관리"
admin.site.site_title = "StudyMate Quiz Admin"
admin.site.index_title = "Quiz 관리 대시보드"