from django.contrib import admin
from .models import Subject, StudySettings, StudySummary, StudyProgress


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'created_at']
    search_fields = ['name']


@admin.register(StudySettings)
class StudySettingsAdmin(admin.ModelAdmin):
    list_display = ['user', 'subject', 'difficulty_level', 'preferred_depth', 'daily_summary_count']
    list_filter = ['difficulty_level', 'preferred_depth', 'subject']
    search_fields = ['user__email', 'subject__name']


@admin.register(StudySummary)
class StudySummaryAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'subject', 'difficulty_level', 'generated_at', 'is_read']
    list_filter = ['difficulty_level', 'subject', 'is_read', 'generated_at']
    search_fields = ['title', 'user__email', 'subject__name']
    readonly_fields = ['generated_at']


@admin.register(StudyProgress)
class StudyProgressAdmin(admin.ModelAdmin):
    list_display = ['user', 'subject', 'total_summaries_read', 'total_quizzes_completed', 'current_streak']
    list_filter = ['subject', 'last_activity_date']
    search_fields = ['user__email', 'subject__name']
    readonly_fields = ['created_at', 'updated_at']
