"""
Quiz 앱을 위한 CQRS 명령과 조회 정의

퀴즈 관련 명령(Command)과 조회(Query)를 분리하여 성능과 확장성을 향상시킵니다.
"""

import hashlib
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime

from studymate_api.cqrs import (
    Command, Query, CommandHandler, QueryHandler, CommandResult, QueryResult,
    command_handler, query_handler, CommandStatus, QueryType
)
from .models import Quiz, QuizAttempt, QuizSession, QuizProgress
from .serializers import (
    QuizSerializer, QuizAttemptSerializer, QuizSessionSerializer,
    QuizProgressSerializer
)
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Q, Count, Avg, Sum, F
from django.utils import timezone

User = get_user_model()

# ============================================================================
# 명령 (Commands) - 상태를 변경하는 작업들
# ============================================================================

@dataclass
class CreateQuizCommand(Command):
    """퀴즈 생성 명령"""
    subject_id: int
    title: str
    question_text: str
    quiz_type: str
    difficulty_level: str
    choices: List[Dict[str, Any]] = None
    correct_answer: str = ""
    explanation: str = ""
    points: int = 10
    time_limit_seconds: Optional[int] = None
    
    def validate(self) -> bool:
        return bool(
            self.subject_id and 
            self.title and 
            self.question_text and
            self.quiz_type in ['multiple_choice', 'true_false', 'short_answer', 'essay'] and
            self.difficulty_level in ['beginner', 'intermediate', 'advanced']
        )
    
    def _get_data(self) -> Dict[str, Any]:
        return {
            'subject_id': self.subject_id,
            'title': self.title,
            'question_text': self.question_text,
            'quiz_type': self.quiz_type,
            'difficulty_level': self.difficulty_level,
            'choices': self.choices or [],
            'correct_answer': self.correct_answer,
            'explanation': self.explanation,
            'points': self.points,
            'time_limit_seconds': self.time_limit_seconds
        }


@dataclass
class UpdateQuizCommand(Command):
    """퀴즈 수정 명령"""
    quiz_id: int
    title: Optional[str] = None
    question_text: Optional[str] = None
    choices: Optional[List[Dict[str, Any]]] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    points: Optional[int] = None
    difficulty_level: Optional[str] = None
    
    def validate(self) -> bool:
        return bool(self.quiz_id)
    
    def _get_data(self) -> Dict[str, Any]:
        data = {'quiz_id': self.quiz_id}
        for field in ['title', 'question_text', 'choices', 'correct_answer', 
                     'explanation', 'points', 'difficulty_level']:
            value = getattr(self, field, None)
            if value is not None:
                data[field] = value
        return data


@dataclass
class AttemptQuizCommand(Command):
    """퀴즈 시도 명령"""
    quiz_id: int
    user_answer: str
    time_spent_seconds: Optional[int] = None
    session_id: Optional[int] = None
    
    def validate(self) -> bool:
        return bool(self.quiz_id and self.user_id and self.user_answer)
    
    def _get_data(self) -> Dict[str, Any]:
        return {
            'quiz_id': self.quiz_id,
            'user_answer': self.user_answer,
            'time_spent_seconds': self.time_spent_seconds,
            'session_id': self.session_id
        }


@dataclass
class CreateQuizSessionCommand(Command):
    """퀴즈 세션 생성 명령"""
    subject_id: Optional[int] = None
    difficulty_level: Optional[str] = None
    quiz_count: int = 10
    time_limit_minutes: Optional[int] = None
    
    def validate(self) -> bool:
        return bool(self.user_id and self.quiz_count > 0)
    
    def _get_data(self) -> Dict[str, Any]:
        return {
            'subject_id': self.subject_id,
            'difficulty_level': self.difficulty_level,
            'quiz_count': self.quiz_count,
            'time_limit_minutes': self.time_limit_minutes
        }


@dataclass
class CompleteQuizSessionCommand(Command):
    """퀴즈 세션 완료 명령"""
    session_id: int
    
    def validate(self) -> bool:
        return bool(self.session_id and self.user_id)
    
    def _get_data(self) -> Dict[str, Any]:
        return {'session_id': self.session_id}


# ============================================================================
# 조회 (Queries) - 데이터를 읽는 작업들
# ============================================================================

class GetQuizzesQuery(Query[List[Dict[str, Any]]]):
    """퀴즈 목록 조회"""
    
    def __init__(self, user_id: Optional[int] = None, subject_id: Optional[int] = None,
                 difficulty_level: Optional[str] = None, quiz_type: Optional[str] = None,
                 exclude_attempted: bool = False, limit: int = 20, offset: int = 0,
                 use_cache: bool = True):
        super().__init__(user_id, use_cache)
        self.subject_id = subject_id
        self.difficulty_level = difficulty_level
        self.quiz_type = quiz_type
        self.exclude_attempted = exclude_attempted
        self.limit = limit
        self.offset = offset
    
    def get_cache_key(self) -> str:
        key_parts = [
            'quizzes',
            f'user_{self.user_id}' if self.user_id else 'all',
            f'subject_{self.subject_id}' if self.subject_id else 'all_subjects',
            f'diff_{self.difficulty_level}' if self.difficulty_level else 'all_diff',
            f'type_{self.quiz_type}' if self.quiz_type else 'all_types',
            f'exclude_{self.exclude_attempted}',
            f'limit_{self.limit}',
            f'offset_{self.offset}'
        ]
        return 'cqrs:' + ':'.join(key_parts)
    
    def get_cache_timeout(self) -> int:
        return 300  # 5분


class GetQuizDetailQuery(Query[Dict[str, Any]]):
    """퀴즈 상세 조회"""
    
    def __init__(self, quiz_id: int, user_id: Optional[int] = None, use_cache: bool = True):
        super().__init__(user_id, use_cache)
        self.quiz_id = quiz_id
    
    def get_cache_key(self) -> str:
        return f'cqrs:quiz_detail:{self.quiz_id}:user_{self.user_id or "anonymous"}'
    
    def get_cache_timeout(self) -> int:
        return 600  # 10분


class GetQuizAttemptsQuery(Query[List[Dict[str, Any]]]):
    """퀴즈 시도 내역 조회"""
    
    def __init__(self, user_id: int, quiz_id: Optional[int] = None,
                 limit: int = 50, offset: int = 0, use_cache: bool = True):
        super().__init__(user_id, use_cache)
        self.quiz_id = quiz_id
        self.limit = limit
        self.offset = offset
    
    def get_cache_key(self) -> str:
        key_parts = [
            'quiz_attempts',
            f'user_{self.user_id}',
            f'quiz_{self.quiz_id}' if self.quiz_id else 'all_quizzes',
            f'limit_{self.limit}',
            f'offset_{self.offset}'
        ]
        return 'cqrs:' + ':'.join(key_parts)
    
    def get_cache_timeout(self) -> int:
        return 180  # 3분


class GetQuizStatisticsQuery(Query[Dict[str, Any]]):
    """퀴즈 통계 조회"""
    
    def __init__(self, user_id: int, subject_id: Optional[int] = None,
                 days: int = 30, use_cache: bool = True):
        super().__init__(user_id, use_cache)
        self.subject_id = subject_id
        self.days = days
    
    def get_cache_key(self) -> str:
        return f'cqrs:quiz_stats:{self.user_id}:subject_{self.subject_id or "all"}:days_{self.days}'
    
    def get_cache_timeout(self) -> int:
        return 1800  # 30분


class GetQuizSessionsQuery(Query[List[Dict[str, Any]]]):
    """퀴즈 세션 목록 조회"""
    
    def __init__(self, user_id: int, status: Optional[str] = None,
                 limit: int = 20, offset: int = 0, use_cache: bool = True):
        super().__init__(user_id, use_cache)
        self.status = status
        self.limit = limit
        self.offset = offset
    
    def get_cache_key(self) -> str:
        key_parts = [
            'quiz_sessions',
            f'user_{self.user_id}',
            f'status_{self.status}' if self.status else 'all_status',
            f'limit_{self.limit}',
            f'offset_{self.offset}'
        ]
        return 'cqrs:' + ':'.join(key_parts)
    
    def get_cache_timeout(self) -> int:
        return 120  # 2분


# ============================================================================
# 명령 핸들러들 (Command Handlers)
# ============================================================================

@command_handler(CreateQuizCommand)
class CreateQuizHandler(CommandHandler[CreateQuizCommand]):
    """퀴즈 생성 핸들러"""
    
    def handle(self, command: CreateQuizCommand) -> CommandResult:
        try:
            from study.models import Subject
            
            # 과목 존재 확인
            subject = Subject.objects.get(id=command.subject_id)
            
            # 퀴즈 생성
            quiz = Quiz.objects.create(
                subject=subject,
                title=command.title,
                question_text=command.question_text,
                quiz_type=command.quiz_type,
                difficulty_level=command.difficulty_level,
                correct_answer=command.correct_answer,
                explanation=command.explanation,
                points=command.points,
                time_limit_seconds=command.time_limit_seconds
            )
            
            # 선택지 생성 (객관식인 경우)
            if command.choices and command.quiz_type == 'multiple_choice':
                from .models import QuizChoice
                for choice_data in command.choices:
                    QuizChoice.objects.create(
                        quiz=quiz,
                        choice_text=choice_data.get('text', ''),
                        is_correct=choice_data.get('is_correct', False),
                        order=choice_data.get('order', 0)
                    )
            
            # 관련 캐시 무효화
            cache.delete_many([
                'cqrs:quizzes:*',
                f'cqrs:quiz_detail:{quiz.id}:*'
            ])
            
            return CommandResult(
                command_id=command.command_id,
                status=CommandStatus.SUCCESS,
                result=QuizSerializer(quiz).data
            )
            
        except Subject.DoesNotExist:
            return CommandResult(
                command_id=command.command_id,
                status=CommandStatus.FAILED,
                error_message=f"Subject with id {command.subject_id} not found"
            )
        except Exception as e:
            return CommandResult(
                command_id=command.command_id,
                status=CommandStatus.FAILED,
                error_message=str(e)
            )


@command_handler(AttemptQuizCommand)
class AttemptQuizHandler(CommandHandler[AttemptQuizCommand]):
    """퀴즈 시도 핸들러"""
    
    def handle(self, command: AttemptQuizCommand) -> CommandResult:
        try:
            # 퀴즈와 사용자 확인
            quiz = Quiz.objects.get(id=command.quiz_id)
            user = User.objects.get(id=command.user_id)
            
            # 중복 시도 확인 (중복 허용하지 않는 경우)
            if not quiz.allow_multiple_attempts:
                existing_attempt = QuizAttempt.objects.filter(
                    user=user, quiz=quiz
                ).first()
                if existing_attempt:
                    return CommandResult(
                        command_id=command.command_id,
                        status=CommandStatus.FAILED,
                        error_message="이 퀴즈는 중복 시도가 허용되지 않습니다."
                    )
            
            # 정답 확인
            is_correct = self._check_answer(quiz, command.user_answer)
            
            # 점수 계산
            points_earned = quiz.points if is_correct else 0
            
            # 시간 보너스 계산
            bonus_points = 0
            if is_correct and command.time_spent_seconds and quiz.time_limit_seconds:
                time_ratio = command.time_spent_seconds / quiz.time_limit_seconds
                if time_ratio < 0.5:  # 절반 시간 내 완료
                    bonus_points = int(quiz.points * 0.2)  # 20% 보너스
            
            # 퀴즈 시도 기록 생성
            attempt = QuizAttempt.objects.create(
                user=user,
                quiz=quiz,
                user_answer=command.user_answer,
                is_correct=is_correct,
                points_earned=points_earned,
                bonus_points=bonus_points,
                time_spent_seconds=command.time_spent_seconds or 0,
                attempted_at=timezone.now()
            )
            
            # 세션에 연결 (세션 ID가 있는 경우)
            if command.session_id:
                try:
                    session = QuizSession.objects.get(id=command.session_id, user=user)
                    attempt.session = session
                    attempt.save()
                except QuizSession.DoesNotExist:
                    pass
            
            # 진도 업데이트
            self._update_progress(user, quiz, attempt)
            
            # 관련 캐시 무효화
            cache.delete_many([
                f'cqrs:quiz_attempts:user_{command.user_id}:*',
                f'cqrs:quiz_stats:{command.user_id}:*',
                f'cqrs:quiz_sessions:user_{command.user_id}:*'
            ])
            
            return CommandResult(
                command_id=command.command_id,
                status=CommandStatus.SUCCESS,
                result={
                    'attempt': QuizAttemptSerializer(attempt).data,
                    'is_correct': is_correct,
                    'points_earned': points_earned + bonus_points,
                    'explanation': quiz.explanation if not is_correct else None
                }
            )
            
        except (Quiz.DoesNotExist, User.DoesNotExist) as e:
            return CommandResult(
                command_id=command.command_id,
                status=CommandStatus.FAILED,
                error_message=str(e)
            )
        except Exception as e:
            return CommandResult(
                command_id=command.command_id,
                status=CommandStatus.FAILED,
                error_message=str(e)
            )
    
    def _check_answer(self, quiz: Quiz, user_answer: str) -> bool:
        """정답 확인"""
        if quiz.quiz_type == 'multiple_choice':
            # 객관식: 선택지 ID 비교
            try:
                from .models import QuizChoice
                correct_choice = QuizChoice.objects.get(quiz=quiz, is_correct=True)
                return str(correct_choice.id) == str(user_answer)
            except QuizChoice.DoesNotExist:
                return False
        elif quiz.quiz_type == 'true_false':
            # T/F: 정답과 비교
            return quiz.correct_answer.lower() == user_answer.lower()
        else:
            # 주관식, 서술형: 정확한 비교 (추후 AI 기반 채점 가능)
            return quiz.correct_answer.strip().lower() == user_answer.strip().lower()
    
    def _update_progress(self, user: User, quiz: Quiz, attempt: QuizAttempt):
        """퀴즈 진도 업데이트"""
        progress, created = QuizProgress.objects.get_or_create(
            user=user,
            subject=quiz.subject,
            defaults={
                'total_quizzes_attempted': 0,
                'total_quizzes_correct': 0,
                'total_points_earned': 0,
                'current_streak': 0,
                'best_streak': 0
            }
        )
        
        progress.total_quizzes_attempted += 1
        progress.total_points_earned += attempt.total_points
        
        if attempt.is_correct:
            progress.total_quizzes_correct += 1
            progress.current_streak += 1
            progress.best_streak = max(progress.best_streak, progress.current_streak)
        else:
            progress.current_streak = 0
        
        progress.last_attempted_at = timezone.now()
        progress.save()


@command_handler(CreateQuizSessionCommand)
class CreateQuizSessionHandler(CommandHandler[CreateQuizSessionCommand]):
    """퀴즈 세션 생성 핸들러"""
    
    def handle(self, command: CreateQuizSessionCommand) -> CommandResult:
        try:
            user = User.objects.get(id=command.user_id)
            
            # 퀴즈 필터링
            quizzes_query = Quiz.objects.filter(is_active=True)
            
            if command.subject_id:
                quizzes_query = quizzes_query.filter(subject_id=command.subject_id)
            
            if command.difficulty_level:
                quizzes_query = quizzes_query.filter(difficulty_level=command.difficulty_level)
            
            # 사용자가 시도하지 않은 퀴즈 우선 선택
            attempted_quiz_ids = QuizAttempt.objects.filter(
                user=user
            ).values_list('quiz_id', flat=True)
            
            unattempted_quizzes = quizzes_query.exclude(id__in=attempted_quiz_ids)
            
            # 요청된 개수만큼 퀴즈 선택
            selected_quizzes = list(unattempted_quizzes[:command.quiz_count])
            
            # 부족한 경우 시도했던 퀴즈에서 보충
            if len(selected_quizzes) < command.quiz_count:
                remaining_count = command.quiz_count - len(selected_quizzes)
                additional_quizzes = list(
                    quizzes_query.exclude(
                        id__in=[q.id for q in selected_quizzes]
                    )[:remaining_count]
                )
                selected_quizzes.extend(additional_quizzes)
            
            if not selected_quizzes:
                return CommandResult(
                    command_id=command.command_id,
                    status=CommandStatus.FAILED,
                    error_message="조건에 맞는 퀴즈가 없습니다."
                )
            
            # 세션 생성
            session = QuizSession.objects.create(
                user=user,
                total_quizzes=len(selected_quizzes),
                time_limit_minutes=command.time_limit_minutes,
                started_at=timezone.now()
            )
            
            # 세션에 퀴즈 연결
            session.quizzes.set(selected_quizzes)
            
            # 관련 캐시 무효화
            cache.delete_many([
                f'cqrs:quiz_sessions:user_{command.user_id}:*'
            ])
            
            return CommandResult(
                command_id=command.command_id,
                status=CommandStatus.SUCCESS,
                result=QuizSessionSerializer(session).data
            )
            
        except User.DoesNotExist:
            return CommandResult(
                command_id=command.command_id,
                status=CommandStatus.FAILED,
                error_message=f"User with id {command.user_id} not found"
            )
        except Exception as e:
            return CommandResult(
                command_id=command.command_id,
                status=CommandStatus.FAILED,
                error_message=str(e)
            )


# ============================================================================
# 조회 핸들러들 (Query Handlers)
# ============================================================================

@query_handler(GetQuizzesQuery)
class GetQuizzesHandler(QueryHandler[GetQuizzesQuery, List[Dict[str, Any]]]):
    """퀴즈 목록 조회 핸들러"""
    
    def handle(self, query: GetQuizzesQuery) -> QueryResult[List[Dict[str, Any]]]:
        queryset = Quiz.objects.filter(is_active=True)
        
        # 필터 적용
        if query.subject_id:
            queryset = queryset.filter(subject_id=query.subject_id)
        
        if query.difficulty_level:
            queryset = queryset.filter(difficulty_level=query.difficulty_level)
        
        if query.quiz_type:
            queryset = queryset.filter(quiz_type=query.quiz_type)
        
        # 사용자별 필터링
        if query.user_id and query.exclude_attempted:
            attempted_quiz_ids = QuizAttempt.objects.filter(
                user_id=query.user_id
            ).values_list('quiz_id', flat=True)
            queryset = queryset.exclude(id__in=attempted_quiz_ids)
        
        # 사용자별 통계 추가
        if query.user_id:
            queryset = queryset.annotate(
                user_attempts_count=Count(
                    'attempts',
                    filter=Q(attempts__user_id=query.user_id)
                ),
                user_correct_count=Count(
                    'attempts',
                    filter=Q(attempts__user_id=query.user_id, attempts__is_correct=True)
                )
            )
        
        # 관련 데이터 최적화
        queryset = queryset.select_related('subject').prefetch_related('choices')
        
        # 페이징
        queryset = queryset[query.offset:query.offset + query.limit]
        
        quizzes = QuizSerializer(queryset, many=True).data
        
        return QueryResult(
            query_id=query.query_id,
            query_type=QueryType.REAL_TIME,
            data=quizzes
        )


@query_handler(GetQuizDetailQuery)
class GetQuizDetailHandler(QueryHandler[GetQuizDetailQuery, Dict[str, Any]]):
    """퀴즈 상세 조회 핸들러"""
    
    def handle(self, query: GetQuizDetailQuery) -> QueryResult[Dict[str, Any]]:
        try:
            queryset = Quiz.objects.filter(id=query.quiz_id)
            
            # 사용자별 통계 추가
            if query.user_id:
                queryset = queryset.annotate(
                    user_attempts_count=Count(
                        'attempts',
                        filter=Q(attempts__user_id=query.user_id)
                    ),
                    user_best_score=Count(
                        'attempts__total_points',
                        filter=Q(attempts__user_id=query.user_id)
                    )
                )
            
            quiz = queryset.select_related('subject').prefetch_related('choices').first()
            
            if not quiz:
                raise Quiz.DoesNotExist(f"Quiz with id {query.quiz_id} not found")
            
            quiz_data = QuizSerializer(quiz).data
            
            # 사용자별 상세 정보 추가
            if query.user_id:
                user_attempts = QuizAttempt.objects.filter(
                    user_id=query.user_id,
                    quiz=quiz
                ).order_by('-attempted_at')[:5]
                
                quiz_data['user_stats'] = {
                    'attempts_count': user_attempts.count(),
                    'best_score': max([a.total_points for a in user_attempts]) if user_attempts else 0,
                    'last_attempt': QuizAttemptSerializer(user_attempts.first()).data if user_attempts else None,
                    'can_attempt': quiz.allow_multiple_attempts or not user_attempts.exists()
                }
            
            return QueryResult(
                query_id=query.query_id,
                query_type=QueryType.REAL_TIME,
                data=quiz_data
            )
            
        except Quiz.DoesNotExist as e:
            raise ValueError(str(e))


@query_handler(GetQuizAttemptsQuery)
class GetQuizAttemptsHandler(QueryHandler[GetQuizAttemptsQuery, List[Dict[str, Any]]]):
    """퀴즈 시도 내역 조회 핸들러"""
    
    def handle(self, query: GetQuizAttemptsQuery) -> QueryResult[List[Dict[str, Any]]]:
        queryset = QuizAttempt.objects.filter(user_id=query.user_id)
        
        if query.quiz_id:
            queryset = queryset.filter(quiz_id=query.quiz_id)
        
        # 관련 데이터 최적화
        queryset = queryset.select_related('quiz', 'quiz__subject').order_by('-attempted_at')
        
        # 페이징
        queryset = queryset[query.offset:query.offset + query.limit]
        
        attempts = QuizAttemptSerializer(queryset, many=True).data
        
        return QueryResult(
            query_id=query.query_id,
            query_type=QueryType.REAL_TIME,
            data=attempts
        )