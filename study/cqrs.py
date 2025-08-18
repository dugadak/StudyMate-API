"""
Study 앱을 위한 CQRS 명령과 조회 정의

학습 관련 명령(Command)과 조회(Query)를 분리하여 성능과 확장성을 향상시킵니다.
"""

import hashlib
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime

from studymate_api.cqrs import (
    Command, Query, CommandHandler, QueryHandler, CommandResult, QueryResult,
    command_handler, query_handler, CommandStatus, QueryType
)
from .models import Subject, StudySummary, StudyProgress, StudyGoal, StudySettings
from .serializers import (
    SubjectSerializer, StudySummarySerializer, StudyProgressSerializer,
    StudyGoalSerializer, StudySettingsSerializer
)
from .services import StudySummaryService
from studymate_api.advanced_cache import smart_cache
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Q, Count, Avg

User = get_user_model()

# ============================================================================
# 명령 (Commands) - 상태를 변경하는 작업들
# ============================================================================

@dataclass
class CreateSubjectCommand(Command):
    """과목 생성 명령"""
    name: str
    description: str
    category: str
    difficulty_level: str = "intermediate"
    tags: List[str] = None
    keywords: List[str] = None
    
    def validate(self) -> bool:
        return bool(self.name and self.description and self.category)
    
    def _get_data(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'difficulty_level': self.difficulty_level,
            'tags': self.tags or [],
            'keywords': self.keywords or []
        }


@dataclass
class UpdateSubjectCommand(Command):
    """과목 수정 명령"""
    subject_id: int
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    difficulty_level: Optional[str] = None
    tags: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    
    def validate(self) -> bool:
        return bool(self.subject_id)
    
    def _get_data(self) -> Dict[str, Any]:
        data = {'subject_id': self.subject_id}
        if self.name is not None:
            data['name'] = self.name
        if self.description is not None:
            data['description'] = self.description
        if self.category is not None:
            data['category'] = self.category
        if self.difficulty_level is not None:
            data['difficulty_level'] = self.difficulty_level
        if self.tags is not None:
            data['tags'] = self.tags
        if self.keywords is not None:
            data['keywords'] = self.keywords
        return data


@dataclass
class DeleteSubjectCommand(Command):
    """과목 삭제 명령"""
    subject_id: int
    
    def validate(self) -> bool:
        return bool(self.subject_id)
    
    def _get_data(self) -> Dict[str, Any]:
        return {'subject_id': self.subject_id}


@dataclass
class GenerateSummaryCommand(Command):
    """학습 요약 생성 명령"""
    subject_id: int
    custom_prompt: Optional[str] = None
    ai_provider: str = "openai"
    difficulty_level: str = "intermediate"
    
    def validate(self) -> bool:
        return bool(self.subject_id and self.user_id)
    
    def _get_data(self) -> Dict[str, Any]:
        return {
            'subject_id': self.subject_id,
            'custom_prompt': self.custom_prompt,
            'ai_provider': self.ai_provider,
            'difficulty_level': self.difficulty_level
        }


@dataclass
class UpdateStudyProgressCommand(Command):
    """학습 진도 업데이트 명령"""
    subject_id: int
    progress_percentage: float
    time_spent_minutes: int
    completed_sections: List[str] = None
    notes: Optional[str] = None
    
    def validate(self) -> bool:
        return bool(
            self.subject_id and 
            self.user_id and 
            0 <= self.progress_percentage <= 100 and
            self.time_spent_minutes >= 0
        )
    
    def _get_data(self) -> Dict[str, Any]:
        return {
            'subject_id': self.subject_id,
            'progress_percentage': self.progress_percentage,
            'time_spent_minutes': self.time_spent_minutes,
            'completed_sections': self.completed_sections or [],
            'notes': self.notes
        }


@dataclass
class CreateStudyGoalCommand(Command):
    """학습 목표 생성 명령"""
    subject_id: int
    title: str
    description: str
    target_date: datetime
    target_progress: float = 100.0
    is_active: bool = True
    
    def validate(self) -> bool:
        return bool(
            self.subject_id and 
            self.user_id and 
            self.title and 
            self.target_date and
            0 <= self.target_progress <= 100
        )
    
    def _get_data(self) -> Dict[str, Any]:
        return {
            'subject_id': self.subject_id,
            'title': self.title,
            'description': self.description,
            'target_date': self.target_date.isoformat(),
            'target_progress': self.target_progress,
            'is_active': self.is_active
        }


# ============================================================================
# 조회 (Queries) - 데이터를 읽는 작업들
# ============================================================================

class GetSubjectsQuery(Query[List[Dict[str, Any]]]):
    """과목 목록 조회"""
    
    def __init__(self, user_id: Optional[int] = None, category: Optional[str] = None, 
                 difficulty_level: Optional[str] = None, search: Optional[str] = None,
                 limit: int = 50, offset: int = 0, use_cache: bool = True):
        super().__init__(user_id, use_cache)
        self.category = category
        self.difficulty_level = difficulty_level
        self.search = search
        self.limit = limit
        self.offset = offset
    
    def get_cache_key(self) -> str:
        key_parts = [
            'subjects',
            f'user_{self.user_id}' if self.user_id else 'all',
            f'cat_{self.category}' if self.category else 'all_cat',
            f'diff_{self.difficulty_level}' if self.difficulty_level else 'all_diff',
            f'search_{hashlib.md5(self.search.encode()).hexdigest()[:8]}' if self.search else 'no_search',
            f'limit_{self.limit}',
            f'offset_{self.offset}'
        ]
        return 'cqrs:' + ':'.join(key_parts)
    
    def get_cache_timeout(self) -> int:
        return 300  # 5분


class GetSubjectDetailQuery(Query[Dict[str, Any]]):
    """과목 상세 조회"""
    
    def __init__(self, subject_id: int, user_id: Optional[int] = None, use_cache: bool = True):
        super().__init__(user_id, use_cache)
        self.subject_id = subject_id
    
    def get_cache_key(self) -> str:
        return f'cqrs:subject_detail:{self.subject_id}:user_{self.user_id or "anonymous"}'
    
    def get_cache_timeout(self) -> int:
        return 600  # 10분


class GetStudySummariesQuery(Query[List[Dict[str, Any]]]):
    """학습 요약 목록 조회"""
    
    def __init__(self, user_id: int, subject_id: Optional[int] = None, 
                 limit: int = 20, offset: int = 0, use_cache: bool = True):
        super().__init__(user_id, use_cache)
        self.subject_id = subject_id
        self.limit = limit
        self.offset = offset
    
    def get_cache_key(self) -> str:
        key_parts = [
            'study_summaries',
            f'user_{self.user_id}',
            f'subject_{self.subject_id}' if self.subject_id else 'all_subjects',
            f'limit_{self.limit}',
            f'offset_{self.offset}'
        ]
        return 'cqrs:' + ':'.join(key_parts)
    
    def get_cache_timeout(self) -> int:
        return 180  # 3분


class GetStudyProgressQuery(Query[Dict[str, Any]]):
    """학습 진도 조회"""
    
    def __init__(self, user_id: int, subject_id: Optional[int] = None, use_cache: bool = True):
        super().__init__(user_id, use_cache)
        self.subject_id = subject_id
    
    def get_cache_key(self) -> str:
        if self.subject_id:
            return f'cqrs:study_progress:{self.user_id}:subject_{self.subject_id}'
        return f'cqrs:study_progress:{self.user_id}:all'
    
    def get_cache_timeout(self) -> int:
        return 120  # 2분


class GetStudyAnalyticsQuery(Query[Dict[str, Any]]):
    """학습 분석 데이터 조회"""
    
    def __init__(self, user_id: int, days: int = 30, use_cache: bool = True):
        super().__init__(user_id, use_cache)
        self.days = days
    
    def get_cache_key(self) -> str:
        return f'cqrs:study_analytics:{self.user_id}:days_{self.days}'
    
    def get_cache_timeout(self) -> int:
        return 3600  # 1시간


# ============================================================================
# 명령 핸들러들 (Command Handlers)
# ============================================================================

@command_handler(CreateSubjectCommand)
class CreateSubjectHandler(CommandHandler[CreateSubjectCommand]):
    """과목 생성 핸들러"""
    
    def handle(self, command: CreateSubjectCommand) -> CommandResult:
        try:
            subject = Subject.objects.create(
                name=command.name,
                description=command.description,
                category=command.category,
                difficulty_level=command.difficulty_level,
                tags=command.tags or [],
                keywords=command.keywords or []
            )
            
            # 관련 캐시 무효화
            cache.delete_many([
                'cqrs:subjects:all:*',
                f'cqrs:subjects:cat_{command.category}:*'
            ])
            
            return CommandResult(
                command_id=command.command_id,
                status=CommandStatus.SUCCESS,
                result=SubjectSerializer(subject).data
            )
            
        except Exception as e:
            return CommandResult(
                command_id=command.command_id,
                status=CommandStatus.FAILED,
                error_message=str(e)
            )


@command_handler(UpdateSubjectCommand)
class UpdateSubjectHandler(CommandHandler[UpdateSubjectCommand]):
    """과목 수정 핸들러"""
    
    def handle(self, command: UpdateSubjectCommand) -> CommandResult:
        try:
            subject = Subject.objects.get(id=command.subject_id)
            
            # 필드 업데이트
            if command.name is not None:
                subject.name = command.name
            if command.description is not None:
                subject.description = command.description
            if command.category is not None:
                subject.category = command.category
            if command.difficulty_level is not None:
                subject.difficulty_level = command.difficulty_level
            if command.tags is not None:
                subject.tags = command.tags
            if command.keywords is not None:
                subject.keywords = command.keywords
            
            subject.save()
            
            # 관련 캐시 무효화
            cache.delete_many([
                f'cqrs:subject_detail:{command.subject_id}:*',
                'cqrs:subjects:*'
            ])
            
            return CommandResult(
                command_id=command.command_id,
                status=CommandStatus.SUCCESS,
                result=SubjectSerializer(subject).data
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


@command_handler(GenerateSummaryCommand)
class GenerateSummaryHandler(CommandHandler[GenerateSummaryCommand]):
    """학습 요약 생성 핸들러"""
    
    def handle(self, command: GenerateSummaryCommand) -> CommandResult:
        try:
            # 사용자와 과목 검증
            user = User.objects.get(id=command.user_id)
            subject = Subject.objects.get(id=command.subject_id)
            
            # StudySummaryService 사용
            summary_service = StudySummaryService()
            summary = summary_service.generate_summary(
                user=user,
                subject_id=command.subject_id,
                custom_prompt=command.custom_prompt
            )
            
            # 관련 캐시 무효화
            cache.delete_many([
                f'cqrs:study_summaries:user_{command.user_id}:*',
                f'cqrs:study_progress:{command.user_id}:*'
            ])
            
            return CommandResult(
                command_id=command.command_id,
                status=CommandStatus.SUCCESS,
                result=StudySummarySerializer(summary).data
            )
            
        except (User.DoesNotExist, Subject.DoesNotExist) as e:
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


@command_handler(UpdateStudyProgressCommand)
class UpdateStudyProgressHandler(CommandHandler[UpdateStudyProgressCommand]):
    """학습 진도 업데이트 핸들러"""
    
    def handle(self, command: UpdateStudyProgressCommand) -> CommandResult:
        try:
            user = User.objects.get(id=command.user_id)
            subject = Subject.objects.get(id=command.subject_id)
            
            # 진도 업데이트 또는 생성
            progress, created = StudyProgress.objects.update_or_create(
                user=user,
                subject=subject,
                defaults={
                    'progress_percentage': command.progress_percentage,
                    'time_spent_minutes': command.time_spent_minutes,
                    'completed_sections': command.completed_sections or [],
                    'notes': command.notes or '',
                    'last_studied_at': timezone.now()
                }
            )
            
            if not created:
                # 기존 진도가 있으면 시간 누적
                progress.time_spent_minutes += command.time_spent_minutes
                progress.save()
            
            # 관련 캐시 무효화
            cache.delete_many([
                f'cqrs:study_progress:{command.user_id}:*',
                f'cqrs:study_analytics:{command.user_id}:*'
            ])
            
            return CommandResult(
                command_id=command.command_id,
                status=CommandStatus.SUCCESS,
                result=StudyProgressSerializer(progress).data
            )
            
        except (User.DoesNotExist, Subject.DoesNotExist) as e:
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


# ============================================================================
# 조회 핸들러들 (Query Handlers)
# ============================================================================

@query_handler(GetSubjectsQuery)
class GetSubjectsHandler(QueryHandler[GetSubjectsQuery, List[Dict[str, Any]]]):
    """과목 목록 조회 핸들러"""
    
    def handle(self, query: GetSubjectsQuery) -> QueryResult[List[Dict[str, Any]]]:
        queryset = Subject.objects.filter(is_active=True)
        
        # 필터 적용
        if query.category:
            queryset = queryset.filter(category=query.category)
        
        if query.difficulty_level:
            queryset = queryset.filter(difficulty_level=query.difficulty_level)
        
        if query.search:
            queryset = queryset.filter(
                Q(name__icontains=query.search) |
                Q(description__icontains=query.search) |
                Q(tags__icontains=query.search)
            )
        
        # 사용자별 통계 추가
        if query.user_id:
            queryset = queryset.annotate(
                user_summaries_count=Count(
                    'summaries',
                    filter=Q(summaries__user_id=query.user_id)
                ),
                user_progress=Avg(
                    'progress_records__progress_percentage',
                    filter=Q(progress_records__user_id=query.user_id)
                )
            )
        
        # 페이징 적용
        queryset = queryset[query.offset:query.offset + query.limit]
        
        # 시리얼라이저로 변환
        subjects = SubjectSerializer(queryset, many=True).data
        
        return QueryResult(
            query_id=query.query_id,
            query_type=QueryType.REAL_TIME,
            data=subjects
        )


@query_handler(GetSubjectDetailQuery)
class GetSubjectDetailHandler(QueryHandler[GetSubjectDetailQuery, Dict[str, Any]]):
    """과목 상세 조회 핸들러"""
    
    def handle(self, query: GetSubjectDetailQuery) -> QueryResult[Dict[str, Any]]:
        try:
            queryset = Subject.objects.filter(id=query.subject_id)
            
            # 사용자별 상세 정보 추가
            if query.user_id:
                queryset = queryset.annotate(
                    user_summaries_count=Count(
                        'summaries',
                        filter=Q(summaries__user_id=query.user_id)
                    ),
                    user_progress=Avg(
                        'progress_records__progress_percentage',
                        filter=Q(progress_records__user_id=query.user_id)
                    ),
                    total_study_time=Count(
                        'progress_records__time_spent_minutes',
                        filter=Q(progress_records__user_id=query.user_id)
                    )
                )
            
            subject = queryset.first()
            if not subject:
                raise Subject.DoesNotExist(f"Subject with id {query.subject_id} not found")
            
            subject_data = SubjectSerializer(subject).data
            
            # 추가 통계 정보
            if query.user_id:
                recent_summaries = StudySummary.objects.filter(
                    user_id=query.user_id,
                    subject=subject
                ).order_by('-created_at')[:5]
                
                subject_data.update({
                    'user_stats': {
                        'summaries_count': getattr(subject, 'user_summaries_count', 0),
                        'progress_percentage': getattr(subject, 'user_progress', 0) or 0,
                        'total_study_time': getattr(subject, 'total_study_time', 0),
                        'recent_summaries': StudySummarySerializer(recent_summaries, many=True).data
                    }
                })
            
            return QueryResult(
                query_id=query.query_id,
                query_type=QueryType.REAL_TIME,
                data=subject_data
            )
            
        except Subject.DoesNotExist as e:
            raise ValueError(str(e))


@query_handler(GetStudySummariesQuery)
class GetStudySummariesHandler(QueryHandler[GetStudySummariesQuery, List[Dict[str, Any]]]):
    """학습 요약 목록 조회 핸들러"""
    
    def handle(self, query: GetStudySummariesQuery) -> QueryResult[List[Dict[str, Any]]]:
        queryset = StudySummary.objects.filter(user_id=query.user_id)
        
        if query.subject_id:
            queryset = queryset.filter(subject_id=query.subject_id)
        
        # 관련 데이터 최적화
        queryset = queryset.select_related('subject', 'user').order_by('-created_at')
        
        # 페이징
        queryset = queryset[query.offset:query.offset + query.limit]
        
        summaries = StudySummarySerializer(queryset, many=True).data
        
        return QueryResult(
            query_id=query.query_id,
            query_type=QueryType.REAL_TIME,
            data=summaries
        )


@query_handler(GetStudyProgressQuery)
class GetStudyProgressHandler(QueryHandler[GetStudyProgressQuery, Dict[str, Any]]):
    """학습 진도 조회 핸들러"""
    
    def handle(self, query: GetStudyProgressQuery) -> QueryResult[Dict[str, Any]]:
        queryset = StudyProgress.objects.filter(user_id=query.user_id)
        
        if query.subject_id:
            queryset = queryset.filter(subject_id=query.subject_id)
            progress_list = StudyProgressSerializer(queryset, many=True).data
            return QueryResult(
                query_id=query.query_id,
                query_type=QueryType.REAL_TIME,
                data={'progress': progress_list[0] if progress_list else None}
            )
        
        # 전체 진도 요약
        queryset = queryset.select_related('subject')
        progress_list = StudyProgressSerializer(queryset, many=True).data
        
        # 전체 통계 계산
        total_subjects = len(progress_list)
        total_progress = sum(p['progress_percentage'] for p in progress_list)
        avg_progress = total_progress / total_subjects if total_subjects > 0 else 0
        total_time = sum(p['time_spent_minutes'] for p in progress_list)
        
        return QueryResult(
            query_id=query.query_id,
            query_type=QueryType.REAL_TIME,
            data={
                'progress_list': progress_list,
                'summary': {
                    'total_subjects': total_subjects,
                    'average_progress': avg_progress,
                    'total_study_time': total_time,
                    'completed_subjects': len([p for p in progress_list if p['progress_percentage'] >= 100])
                }
            }
        )