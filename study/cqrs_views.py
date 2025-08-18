"""
CQRS 패턴을 적용한 Study ViewSet

명령과 조회를 분리하여 성능과 확장성을 향상시킨 Study API
"""

from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from typing import Dict, Any
import logging

from studymate_api.cqrs import CQRSMixin, CommandStatus
from studymate_api.metrics import track_user_event, EventType
from .cqrs import (
    # Commands
    CreateSubjectCommand, UpdateSubjectCommand, DeleteSubjectCommand,
    GenerateSummaryCommand, UpdateStudyProgressCommand, CreateStudyGoalCommand,
    # Queries
    GetSubjectsQuery, GetSubjectDetailQuery, GetStudySummariesQuery,
    GetStudyProgressQuery, GetStudyAnalyticsQuery
)
from .models import Subject
from .filters import StudySummaryFilter, StudyProgressFilter
from .pagination import StudyPagination

logger = logging.getLogger(__name__)


class CQRSSubjectViewSet(viewsets.ViewSet, CQRSMixin):
    """CQRS 패턴을 적용한 과목 ViewSet"""
    
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StudyPagination
    
    @extend_schema(
        summary="과목 목록 조회",
        description="CQRS 패턴을 사용한 과목 목록 조회",
        parameters=[
            OpenApiParameter(
                name="category",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="과목 카테고리 필터"
            ),
            OpenApiParameter(
                name="difficulty_level",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="난이도 필터 (beginner, intermediate, advanced)"
            ),
            OpenApiParameter(
                name="search",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="검색 키워드"
            ),
            OpenApiParameter(
                name="limit",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="결과 개수 제한 (기본값: 20)"
            ),
            OpenApiParameter(
                name="offset",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="결과 시작 위치 (기본값: 0)"
            )
        ]
    )
    def list(self, request):
        """과목 목록 조회"""
        try:
            query = GetSubjectsQuery(
                user_id=request.user.id,
                category=request.query_params.get('category'),
                difficulty_level=request.query_params.get('difficulty_level'),
                search=request.query_params.get('search'),
                limit=int(request.query_params.get('limit', 20)),
                offset=int(request.query_params.get('offset', 0))
            )
            
            result = self.dispatch_query(query)
            
            return Response({
                'results': result.data,
                'query_id': result.query_id,
                'cache_hit': result.cache_hit,
                'execution_time': result.execution_time,
                'count': len(result.data)
            })
            
        except Exception as e:
            logger.error(f"Error in subjects list query: {e}")
            return Response(
                {'error': '과목 목록 조회 중 오류가 발생했습니다.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="과목 상세 조회",
        description="특정 과목의 상세 정보와 사용자별 통계를 조회합니다."
    )
    def retrieve(self, request, pk=None):
        """과목 상세 조회"""
        try:
            query = GetSubjectDetailQuery(
                subject_id=int(pk),
                user_id=request.user.id
            )
            
            result = self.dispatch_query(query)
            
            return Response({
                'result': result.data,
                'query_id': result.query_id,
                'cache_hit': result.cache_hit,
                'execution_time': result.execution_time
            })
            
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error in subject detail query: {e}")
            return Response(
                {'error': '과목 상세 조회 중 오류가 발생했습니다.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="과목 생성",
        description="새로운 과목을 생성합니다.",
        request={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "과목명"},
                "description": {"type": "string", "description": "과목 설명"},
                "category": {"type": "string", "description": "카테고리"},
                "difficulty_level": {"type": "string", "description": "난이도"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "태그"},
                "keywords": {"type": "array", "items": {"type": "string"}, "description": "키워드"}
            },
            "required": ["name", "description", "category"]
        }
    )
    def create(self, request):
        """과목 생성"""
        try:
            command = CreateSubjectCommand(
                user_id=request.user.id,
                name=request.data.get('name'),
                description=request.data.get('description'),
                category=request.data.get('category'),
                difficulty_level=request.data.get('difficulty_level', 'intermediate'),
                tags=request.data.get('tags', []),
                keywords=request.data.get('keywords', [])
            )
            
            result = self.dispatch_command(command)
            
            if result.status == CommandStatus.SUCCESS:
                # 성공 메트릭 추적
                track_user_event(EventType.STUDY_SESSION_START, request.user.id, {
                    'action': 'create_subject',
                    'subject_name': command.name,
                    'category': command.category
                })
                
                return Response({
                    'result': result.result,
                    'command_id': result.command_id,
                    'execution_time': result.execution_time,
                    'message': '과목이 성공적으로 생성되었습니다.'
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'error': result.error_message,
                    'command_id': result.command_id
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Error in create subject command: {e}")
            return Response(
                {'error': '과목 생성 중 오류가 발생했습니다.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="과목 수정",
        description="기존 과목 정보를 수정합니다."
    )
    def update(self, request, pk=None):
        """과목 수정"""
        try:
            command = UpdateSubjectCommand(
                user_id=request.user.id,
                subject_id=int(pk),
                name=request.data.get('name'),
                description=request.data.get('description'),
                category=request.data.get('category'),
                difficulty_level=request.data.get('difficulty_level'),
                tags=request.data.get('tags'),
                keywords=request.data.get('keywords')
            )
            
            result = self.dispatch_command(command)
            
            if result.status == CommandStatus.SUCCESS:
                return Response({
                    'result': result.result,
                    'command_id': result.command_id,
                    'execution_time': result.execution_time,
                    'message': '과목이 성공적으로 수정되었습니다.'
                })
            else:
                return Response({
                    'error': result.error_message,
                    'command_id': result.command_id
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Error in update subject command: {e}")
            return Response(
                {'error': '과목 수정 중 오류가 발생했습니다.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="AI 요약 생성",
        description="지정한 과목에 대한 AI 학습 요약을 생성합니다.",
        request={
            "type": "object",
            "properties": {
                "custom_prompt": {"type": "string", "description": "사용자 정의 프롬프트"},
                "ai_provider": {"type": "string", "description": "AI 제공자 (openai, anthropic)"},
                "difficulty_level": {"type": "string", "description": "요약 난이도"}
            }
        }
    )
    @action(detail=True, methods=['post'])
    def generate_summary(self, request, pk=None):
        """AI 학습 요약 생성"""
        try:
            command = GenerateSummaryCommand(
                user_id=request.user.id,
                subject_id=int(pk),
                custom_prompt=request.data.get('custom_prompt'),
                ai_provider=request.data.get('ai_provider', 'openai'),
                difficulty_level=request.data.get('difficulty_level', 'intermediate')
            )
            
            result = self.dispatch_command(command)
            
            if result.status == CommandStatus.SUCCESS:
                # AI 요약 생성 메트릭 추적
                track_user_event(EventType.SUMMARY_GENERATED, request.user.id, {
                    'subject_id': int(pk),
                    'ai_provider': command.ai_provider,
                    'custom_prompt_used': bool(command.custom_prompt)
                })
                
                return Response({
                    'result': result.result,
                    'command_id': result.command_id,
                    'execution_time': result.execution_time,
                    'message': 'AI 요약이 성공적으로 생성되었습니다.'
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'error': result.error_message,
                    'command_id': result.command_id
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Error in generate summary command: {e}")
            return Response(
                {'error': 'AI 요약 생성 중 오류가 발생했습니다.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CQRSStudySummaryViewSet(viewsets.ViewSet, CQRSMixin):
    """CQRS 패턴을 적용한 학습 요약 ViewSet"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        summary="학습 요약 목록 조회",
        description="사용자의 학습 요약 목록을 조회합니다.",
        parameters=[
            OpenApiParameter(
                name="subject_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="특정 과목으로 필터링"
            ),
            OpenApiParameter(
                name="limit",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="결과 개수 제한"
            ),
            OpenApiParameter(
                name="offset",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="결과 시작 위치"
            )
        ]
    )
    def list(self, request):
        """학습 요약 목록 조회"""
        try:
            subject_id = request.query_params.get('subject_id')
            query = GetStudySummariesQuery(
                user_id=request.user.id,
                subject_id=int(subject_id) if subject_id else None,
                limit=int(request.query_params.get('limit', 20)),
                offset=int(request.query_params.get('offset', 0))
            )
            
            result = self.dispatch_query(query)
            
            return Response({
                'results': result.data,
                'query_id': result.query_id,
                'cache_hit': result.cache_hit,
                'execution_time': result.execution_time,
                'count': len(result.data)
            })
            
        except Exception as e:
            logger.error(f"Error in study summaries query: {e}")
            return Response(
                {'error': '학습 요약 목록 조회 중 오류가 발생했습니다.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CQRSStudyProgressViewSet(viewsets.ViewSet, CQRSMixin):
    """CQRS 패턴을 적용한 학습 진도 ViewSet"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        summary="학습 진도 조회",
        description="사용자의 학습 진도를 조회합니다.",
        parameters=[
            OpenApiParameter(
                name="subject_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="특정 과목의 진도 조회"
            )
        ]
    )
    def list(self, request):
        """학습 진도 조회"""
        try:
            subject_id = request.query_params.get('subject_id')
            query = GetStudyProgressQuery(
                user_id=request.user.id,
                subject_id=int(subject_id) if subject_id else None
            )
            
            result = self.dispatch_query(query)
            
            return Response({
                'result': result.data,
                'query_id': result.query_id,
                'cache_hit': result.cache_hit,
                'execution_time': result.execution_time
            })
            
        except Exception as e:
            logger.error(f"Error in study progress query: {e}")
            return Response(
                {'error': '학습 진도 조회 중 오류가 발생했습니다.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="학습 진도 업데이트",
        description="특정 과목의 학습 진도를 업데이트합니다.",
        request={
            "type": "object",
            "properties": {
                "subject_id": {"type": "integer", "description": "과목 ID"},
                "progress_percentage": {"type": "number", "description": "진도율 (0-100)"},
                "time_spent_minutes": {"type": "integer", "description": "학습 시간 (분)"},
                "completed_sections": {"type": "array", "items": {"type": "string"}, "description": "완료된 섹션"},
                "notes": {"type": "string", "description": "학습 노트"}
            },
            "required": ["subject_id", "progress_percentage", "time_spent_minutes"]
        }
    )
    @action(detail=False, methods=['post'])
    def update_progress(self, request):
        """학습 진도 업데이트"""
        try:
            command = UpdateStudyProgressCommand(
                user_id=request.user.id,
                subject_id=request.data.get('subject_id'),
                progress_percentage=float(request.data.get('progress_percentage')),
                time_spent_minutes=int(request.data.get('time_spent_minutes')),
                completed_sections=request.data.get('completed_sections', []),
                notes=request.data.get('notes')
            )
            
            result = self.dispatch_command(command)
            
            if result.status == CommandStatus.SUCCESS:
                # 학습 진도 업데이트 메트릭 추적
                track_user_event(EventType.STUDY_SESSION_END, request.user.id, {
                    'subject_id': command.subject_id,
                    'progress_percentage': command.progress_percentage,
                    'time_spent': command.time_spent_minutes
                })
                
                return Response({
                    'result': result.result,
                    'command_id': result.command_id,
                    'execution_time': result.execution_time,
                    'message': '학습 진도가 성공적으로 업데이트되었습니다.'
                })
            else:
                return Response({
                    'error': result.error_message,
                    'command_id': result.command_id
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Error in update progress command: {e}")
            return Response(
                {'error': '학습 진도 업데이트 중 오류가 발생했습니다.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CQRSStudyAnalyticsViewSet(viewsets.ViewSet, CQRSMixin):
    """CQRS 패턴을 적용한 학습 분석 ViewSet"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        summary="학습 분석 데이터 조회",
        description="사용자의 학습 분석 데이터를 조회합니다.",
        parameters=[
            OpenApiParameter(
                name="days",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="분석 기간 (일 수, 기본값: 30)"
            )
        ]
    )
    def list(self, request):
        """학습 분석 데이터 조회"""
        try:
            days = int(request.query_params.get('days', 30))
            query = GetStudyAnalyticsQuery(
                user_id=request.user.id,
                days=days
            )
            
            result = self.dispatch_query(query)
            
            return Response({
                'result': result.data,
                'query_id': result.query_id,
                'cache_hit': result.cache_hit,
                'execution_time': result.execution_time,
                'analysis_period_days': days
            })
            
        except Exception as e:
            logger.error(f"Error in study analytics query: {e}")
            return Response(
                {'error': '학습 분석 데이터 조회 중 오류가 발생했습니다.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )