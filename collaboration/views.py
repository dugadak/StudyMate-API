from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction

from .models import QuizRoom, RoomParticipant, RoomQuestion, ParticipantAnswer, RoomChat
from .serializers import (
    CreateRoomSerializer, RoomListSerializer, RoomDetailSerializer,
    ParticipantSerializer, QuestionSerializer, AnswerSubmitSerializer,
    ChatMessageSerializer, LiveStatusSerializer
)
from study.models import Subject
# from study.services import AIService  # Temporarily commented out


class CollaborationViewSet(viewsets.ViewSet):
    """협업 학습 (라이브 그룹 퀴즈) API"""
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        """룸 목록 조회"""
        # 활성 룸만 조회 (대기중 또는 진행중)
        rooms = QuizRoom.objects.filter(
            status__in=['waiting', 'in_progress']
        ).select_related('host', 'subject')
        
        serializer = RoomListSerializer(rooms, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def create_room(self, request):
        """룸 생성"""
        serializer = CreateRoomSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        # 과목 확인
        subject = get_object_or_404(Subject, id=data['subject_id'])
        
        # 룸 생성
        room = QuizRoom.objects.create(
            title=data['title'],
            subject=subject,
            host=request.user,
            max_participants=data.get('max_participants', 10),
            password=data.get('password', ''),
            timer_seconds=data.get('timer_seconds', 30),
            quiz_count=data.get('quiz_count', 10)
        )
        
        # 호스트를 첫 번째 참가자로 추가
        RoomParticipant.objects.create(
            room=room,
            user=request.user,
            is_ready=True
        )
        
        return Response({
            'room_id': room.room_id,
            'message': '룸이 생성되었습니다.',
            'room': RoomDetailSerializer(room).data
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['post'])
    def join_room(self, request):
        """룸 입장"""
        room_id = request.data.get('room_id')
        password = request.data.get('password', '')
        
        # 룸 확인
        room = get_object_or_404(QuizRoom, room_id=room_id)
        
        # 비밀번호 확인
        if room.password and room.password != password:
            return Response(
                {'error': '비밀번호가 일치하지 않습니다.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # 참가 가능 여부 확인
        if not room.can_join():
            return Response(
                {'error': '룸에 참가할 수 없습니다. (만원 또는 이미 시작됨)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 이미 참가중인지 확인
        participant, created = RoomParticipant.objects.get_or_create(
            room=room,
            user=request.user,
            defaults={'is_active': True}
        )
        
        if not created:
            participant.is_active = True
            participant.save()
        
        return Response({
            'message': '룸에 입장했습니다.',
            'room': RoomDetailSerializer(room).data
        })
    
    @action(detail=True, methods=['get'])
    def room_detail(self, request, pk=None):
        """대기실 정보 조회"""
        room = get_object_or_404(QuizRoom, room_id=pk)
        
        # 참가자인지 확인
        if not room.participants.filter(user=request.user).exists():
            return Response(
                {'error': '룸 참가자만 조회할 수 있습니다.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = RoomDetailSerializer(room)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def toggle_ready(self, request, pk=None):
        """준비 상태 토글"""
        room = get_object_or_404(QuizRoom, room_id=pk)
        participant = get_object_or_404(RoomParticipant, room=room, user=request.user)
        
        participant.is_ready = not participant.is_ready
        participant.save()
        
        return Response({
            'is_ready': participant.is_ready,
            'message': '준비 완료' if participant.is_ready else '준비 취소'
        })
    
    @action(detail=True, methods=['post'])
    def start_quiz(self, request, pk=None):
        """퀴즈 시작 (호스트만)"""
        room = get_object_or_404(QuizRoom, room_id=pk)
        
        # 호스트 확인
        if room.host != request.user:
            return Response(
                {'error': '호스트만 퀴즈를 시작할 수 있습니다.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # 모든 참가자 준비 확인
        if room.participants.filter(is_active=True, is_ready=False).exists():
            return Response(
                {'error': '모든 참가자가 준비되지 않았습니다.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            # 퀴즈 시작
            room.start_quiz()
            
            # AI로 문제 생성 (임시 더미 데이터)
            # ai_service = AIService()
            # questions_data = ai_service.generate_quiz_questions(
            #     subject=room.subject.name,
            #     count=room.quiz_count,
            #     difficulty='intermediate'
            # )
            
            # 임시 더미 문제 데이터
            questions_data = [
                {
                    'question': f'Question {i+1} for {room.subject.name}',
                    'type': 'multiple',
                    'options': ['Option A', 'Option B', 'Option C', 'Option D'],
                    'correct_answer': 'Option A'
                }
                for i in range(room.quiz_count)
            ]
            
            # 문제 저장
            for i, q_data in enumerate(questions_data):
                RoomQuestion.objects.create(
                    room=room,
                    question_index=i + 1,
                    question_text=q_data['question'],
                    question_type=q_data.get('type', 'multiple'),
                    options=q_data.get('options'),
                    correct_answer=q_data['answer'],
                    explanation=q_data.get('explanation', '')
                )
        
        return Response({
            'message': '퀴즈가 시작되었습니다.',
            'room': RoomDetailSerializer(room).data
        })
    
    @action(detail=True, methods=['get'])
    def live_status(self, request, pk=None):
        """실시간 상태 조회"""
        room = get_object_or_404(QuizRoom, room_id=pk)
        
        # 현재 문제
        current_question = None
        if room.status == 'in_progress' and room.current_question_index > 0:
            current_question = room.questions.filter(
                question_index=room.current_question_index
            ).first()
        
        # 실시간 랭킹
        rankings = room.participants.filter(is_active=True).order_by('-score', 'joined_at')
        
        # 남은 시간 계산
        time_remaining = 0
        if current_question and current_question.started_at:
            elapsed = (timezone.now() - current_question.started_at).total_seconds()
            time_remaining = max(0, room.timer_seconds - int(elapsed))
        
        return Response({
            'rankings': ParticipantSerializer(rankings, many=True).data,
            'current_question': QuestionSerializer(current_question).data if current_question else None,
            'time_remaining': time_remaining,
            'total_questions': room.quiz_count,
            'completed_questions': room.current_question_index - 1 if room.current_question_index > 0 else 0
        })
    
    @action(detail=True, methods=['post'])
    def submit_answer(self, request, pk=None):
        """답안 제출"""
        room = get_object_or_404(QuizRoom, room_id=pk)
        participant = get_object_or_404(RoomParticipant, room=room, user=request.user)
        
        serializer = AnswerSubmitSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # 현재 문제 확인
        current_question = room.questions.filter(
            question_index=room.current_question_index
        ).first()
        
        if not current_question:
            return Response(
                {'error': '현재 진행중인 문제가 없습니다.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 이미 답변했는지 확인
        if ParticipantAnswer.objects.filter(
            participant=participant,
            question=current_question
        ).exists():
            return Response(
                {'error': '이미 답변을 제출했습니다.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 정답 확인
        is_correct = serializer.validated_data['answer'].lower() == current_question.correct_answer.lower()
        
        # 점수 계산 (빠르게 답할수록 높은 점수)
        base_points = current_question.points
        time_bonus = max(0, 1 - (serializer.validated_data['answer_time_seconds'] / room.timer_seconds))
        points_earned = int(base_points * (0.5 + 0.5 * time_bonus)) if is_correct else 0
        
        # 답안 저장
        ParticipantAnswer.objects.create(
            participant=participant,
            question=current_question,
            answer=serializer.validated_data['answer'],
            is_correct=is_correct,
            points_earned=points_earned,
            answer_time_seconds=serializer.validated_data['answer_time_seconds']
        )
        
        # 참가자 점수 업데이트
        if is_correct:
            participant.score += points_earned
            participant.correct_count += 1
            participant.save()
        
        return Response({
            'is_correct': is_correct,
            'points_earned': points_earned,
            'total_score': participant.score
        })
    
    @action(detail=True, methods=['post'])
    def send_chat(self, request, pk=None):
        """채팅 메시지 전송"""
        room = get_object_or_404(QuizRoom, room_id=pk)
        message = request.data.get('message', '').strip()
        message_type = request.data.get('type', 'chat')
        
        if not message:
            return Response(
                {'error': '메시지를 입력해주세요.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        chat = RoomChat.objects.create(
            room=room,
            sender=request.user,
            message_type=message_type,
            message=message
        )
        
        return Response(ChatMessageSerializer(chat).data, status=status.HTTP_201_CREATED)