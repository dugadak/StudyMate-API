from rest_framework import serializers
from .models import Subject, StudySettings, StudySummary, StudyProgress


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name', 'description', 'created_at']
        read_only_fields = ['id', 'created_at']


class StudySettingsSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    subject_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = StudySettings
        fields = [
            'id', 'subject', 'subject_id', 'difficulty_level', 
            'current_knowledge', 'learning_goal', 'preferred_depth',
            'daily_summary_count', 'notification_times', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_notification_times(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("알림 시간은 리스트 형태여야 합니다.")
        
        for time_str in value:
            try:
                hour, minute = time_str.split(':')
                hour, minute = int(hour), int(minute)
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError
            except (ValueError, AttributeError):
                raise serializers.ValidationError(f"잘못된 시간 형식입니다: {time_str}")
        
        return value


class StudySummarySerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = StudySummary
        fields = [
            'id', 'user_email', 'subject', 'title', 'content',
            'difficulty_level', 'generated_at', 'is_read'
        ]
        read_only_fields = ['id', 'user_email', 'generated_at']


class StudyProgressSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = StudyProgress
        fields = [
            'id', 'user_email', 'subject', 'topics_learned',
            'total_summaries_read', 'total_quizzes_completed',
            'current_streak', 'last_activity_date', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user_email', 'created_at', 'updated_at']