from rest_framework import serializers
from .models import QuizRoom, RoomParticipant, RoomQuestion, ParticipantAnswer, RoomChat
from study.models import Subject


class CreateRoomSerializer(serializers.Serializer):
    """룸 생성 시리얼라이저"""
    title = serializers.CharField(max_length=100)
    subject_id = serializers.IntegerField()
    max_participants = serializers.IntegerField(min_value=2, max_value=50, default=10)
    password = serializers.CharField(max_length=20, required=False, allow_blank=True)
    timer_seconds = serializers.IntegerField(min_value=10, max_value=300, default=30)
    quiz_count = serializers.IntegerField(min_value=5, max_value=50, default=10)


class RoomListSerializer(serializers.ModelSerializer):
    """룸 목록 시리얼라이저"""
    host_name = serializers.CharField(source='host.username', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    current_participants = serializers.SerializerMethodField()
    is_password_protected = serializers.SerializerMethodField()
    
    class Meta:
        model = QuizRoom
        fields = ['id', 'room_id', 'title', 'subject_name', 'host_name', 
                 'max_participants', 'current_participants', 'is_password_protected',
                 'status', 'created_at']
    
    def get_current_participants(self, obj):
        return obj.participants.filter(is_active=True).count()
    
    def get_is_password_protected(self, obj):
        return bool(obj.password)


class ParticipantSerializer(serializers.ModelSerializer):
    """참가자 시리얼라이저"""
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = RoomParticipant
        fields = ['id', 'username', 'is_ready', 'is_active', 'score', 'correct_count', 'rank']


class RoomDetailSerializer(serializers.ModelSerializer):
    """룸 상세 시리얼라이저"""
    participants = ParticipantSerializer(many=True, read_only=True)
    host_name = serializers.CharField(source='host.username', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    
    class Meta:
        model = QuizRoom
        fields = ['id', 'room_id', 'title', 'subject_name', 'host_name',
                 'max_participants', 'timer_seconds', 'quiz_count',
                 'status', 'current_question_index', 'participants',
                 'started_at', 'ended_at', 'created_at']


class QuestionSerializer(serializers.ModelSerializer):
    """문제 시리얼라이저"""
    
    class Meta:
        model = RoomQuestion
        fields = ['id', 'question_index', 'question_text', 'question_type',
                 'options', 'points', 'started_at']
        read_only_fields = ['correct_answer', 'explanation']  # 정답은 숨김


class AnswerSubmitSerializer(serializers.Serializer):
    """답안 제출 시리얼라이저"""
    answer = serializers.CharField(max_length=500)
    answer_time_seconds = serializers.FloatField(min_value=0)


class ChatMessageSerializer(serializers.ModelSerializer):
    """채팅 메시지 시리얼라이저"""
    sender_name = serializers.CharField(source='sender.username', read_only=True)
    
    class Meta:
        model = RoomChat
        fields = ['id', 'sender_name', 'message_type', 'message', 'created_at']


class LiveStatusSerializer(serializers.Serializer):
    """실시간 상태 시리얼라이저"""
    rankings = ParticipantSerializer(many=True)
    current_question = QuestionSerializer(allow_null=True)
    time_remaining = serializers.IntegerField()
    total_questions = serializers.IntegerField()
    completed_questions = serializers.IntegerField()