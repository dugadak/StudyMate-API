from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.postgres.fields import ArrayField
import uuid
import random
import string


class QuizRoom(models.Model):
    """라이브 그룹 퀴즈 룸"""
    
    ROOM_STATUS_CHOICES = [
        ('waiting', '대기중'),
        ('in_progress', '진행중'),
        ('finished', '종료'),
    ]
    
    # 기본 정보
    room_id = models.CharField(max_length=10, unique=True, editable=False, help_text="룸 ID")
    title = models.CharField(max_length=100, help_text="룸 제목")
    subject = models.ForeignKey('study.Subject', on_delete=models.SET_NULL, null=True, help_text="과목")
    host = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='hosted_rooms')
    
    # 룸 설정
    max_participants = models.PositiveIntegerField(default=10, help_text="최대 참가 인원")
    password = models.CharField(max_length=20, blank=True, null=True, help_text="룸 비밀번호")
    timer_seconds = models.PositiveIntegerField(default=30, help_text="문제당 제한시간(초)")
    quiz_count = models.PositiveIntegerField(default=10, help_text="퀴즈 문제 수")
    
    # 상태
    status = models.CharField(max_length=20, choices=ROOM_STATUS_CHOICES, default='waiting')
    current_question_index = models.PositiveIntegerField(default=0, help_text="현재 문제 번호")
    started_at = models.DateTimeField(null=True, blank=True, help_text="시작 시간")
    ended_at = models.DateTimeField(null=True, blank=True, help_text="종료 시간")
    
    # 타임스탬프
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'collaboration_quiz_room'
        indexes = [
            models.Index(fields=['room_id']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']
        verbose_name = '퀴즈 룸'
        verbose_name_plural = '퀴즈 룸'
    
    def __str__(self):
        return f"{self.room_id} - {self.title}"
    
    def save(self, *args, **kwargs):
        if not self.room_id:
            self.room_id = self.generate_room_id()
        super().save(*args, **kwargs)
    
    def generate_room_id(self):
        """고유한 룸 ID 생성 (6자리)"""
        while True:
            room_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not QuizRoom.objects.filter(room_id=room_id).exists():
                return room_id
    
    def can_join(self) -> bool:
        """룸에 참가 가능한지 확인"""
        if self.status != 'waiting':
            return False
        current_participants = self.participants.count()
        return current_participants < self.max_participants
    
    def start_quiz(self):
        """퀴즈 시작"""
        self.status = 'in_progress'
        self.started_at = timezone.now()
        self.save()
    
    def end_quiz(self):
        """퀴즈 종료"""
        self.status = 'finished'
        self.ended_at = timezone.now()
        self.save()


class RoomParticipant(models.Model):
    """퀴즈 룸 참가자"""
    
    room = models.ForeignKey(QuizRoom, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='participated_rooms')
    
    # 상태
    is_ready = models.BooleanField(default=False, help_text="준비 완료 여부")
    is_active = models.BooleanField(default=True, help_text="활성 상태 (연결 상태)")
    score = models.PositiveIntegerField(default=0, help_text="점수")
    correct_count = models.PositiveIntegerField(default=0, help_text="정답 수")
    
    # 랭킹
    rank = models.PositiveIntegerField(null=True, blank=True, help_text="최종 순위")
    
    # 타임스탬프
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'collaboration_room_participant'
        unique_together = [['room', 'user']]
        indexes = [
            models.Index(fields=['room', 'score']),
            models.Index(fields=['is_active']),
        ]
        ordering = ['-score', 'joined_at']
        verbose_name = '룸 참가자'
        verbose_name_plural = '룸 참가자'
    
    def __str__(self):
        return f"{self.room.room_id} - {self.user.username}"


class RoomQuestion(models.Model):
    """룸 퀴즈 문제"""
    
    QUESTION_TYPE_CHOICES = [
        ('multiple', '객관식'),
        ('short', '주관식'),
    ]
    
    room = models.ForeignKey(QuizRoom, on_delete=models.CASCADE, related_name='questions')
    question_index = models.PositiveIntegerField(help_text="문제 순서")
    
    # 문제 내용
    question_text = models.TextField(help_text="문제 내용")
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPE_CHOICES, default='multiple')
    options = models.JSONField(null=True, blank=True, help_text="객관식 선택지")
    correct_answer = models.CharField(max_length=500, help_text="정답")
    explanation = models.TextField(blank=True, help_text="해설")
    
    # 점수
    points = models.PositiveIntegerField(default=100, help_text="문제 점수")
    
    # 시간
    started_at = models.DateTimeField(null=True, blank=True, help_text="문제 시작 시간")
    ended_at = models.DateTimeField(null=True, blank=True, help_text="문제 종료 시간")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'collaboration_room_question'
        unique_together = [['room', 'question_index']]
        indexes = [
            models.Index(fields=['room', 'question_index']),
        ]
        ordering = ['question_index']
        verbose_name = '룸 문제'
        verbose_name_plural = '룸 문제'
    
    def __str__(self):
        return f"{self.room.room_id} - Q{self.question_index}"


class ParticipantAnswer(models.Model):
    """참가자 답안"""
    
    participant = models.ForeignKey(RoomParticipant, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(RoomQuestion, on_delete=models.CASCADE, related_name='participant_answers')
    
    # 답안
    answer = models.CharField(max_length=500, help_text="제출한 답")
    is_correct = models.BooleanField(default=False, help_text="정답 여부")
    points_earned = models.PositiveIntegerField(default=0, help_text="획득 점수")
    
    # 시간
    answer_time_seconds = models.FloatField(help_text="답변 소요 시간(초)")
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'collaboration_participant_answer'
        unique_together = [['participant', 'question']]
        indexes = [
            models.Index(fields=['participant', 'question']),
            models.Index(fields=['is_correct']),
        ]
        verbose_name = '참가자 답안'
        verbose_name_plural = '참가자 답안'
    
    def __str__(self):
        return f"{self.participant.user.username} - Q{self.question.question_index}"


class RoomChat(models.Model):
    """룸 채팅 메시지"""
    
    MESSAGE_TYPE_CHOICES = [
        ('chat', '채팅'),
        ('system', '시스템'),
        ('qna', 'Q&A'),
    ]
    
    room = models.ForeignKey(QuizRoom, on_delete=models.CASCADE, related_name='chat_messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, default='chat')
    message = models.TextField(help_text="메시지 내용")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'collaboration_room_chat'
        indexes = [
            models.Index(fields=['room', 'created_at']),
            models.Index(fields=['message_type']),
        ]
        ordering = ['created_at']
        verbose_name = '룸 채팅'
        verbose_name_plural = '룸 채팅'
    
    def __str__(self):
        return f"{self.room.room_id} - {self.sender.username if self.sender else 'System'}"