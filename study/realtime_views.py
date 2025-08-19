"""
실시간 학습 분석 API Views

실시간 학습 분석 데이터를 제공하는 REST API 엔드포인트
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.core.cache import cache
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from typing import Dict, Any
import logging
import asyncio

from studymate_api.realtime_analytics import (
    realtime_analyzer, 
    start_learning_session, 
    end_learning_session,
    track_learning_event,
    get_session_status
)
from studymate_api.streaming import (
    stream_processor,
    learning_event_stream,
    get_streaming_status
)
from studymate_api.metrics import track_user_event, EventType

logger = logging.getLogger(__name__)


class RealTimeLearningViewSet(viewsets.ViewSet):
    """실시간 학습 분석 ViewSet"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        summary="학습 세션 시작",
        description="새로운 실시간 학습 세션을 시작합니다.",
        request={
            "type": "object",
            "properties": {
                "subject_id": {"type": "integer", "description": "학습할 과목 ID"}
            }
        }
    )
    @action(detail=False, methods=['post'])
    def start_session(self, request):
        """학습 세션 시작"""
        try:
            subject_id = request.data.get('subject_id')
            
            # 비동기 함수를 동기적으로 실행
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                session_id = loop.run_until_complete(
                    start_learning_session(request.user.id, subject_id)
                )
            finally:
                loop.close()
            
            # 메트릭 추적
            track_user_event(EventType.STUDY_SESSION_START, request.user.id, {
                'session_id': session_id,
                'subject_id': subject_id
            })
            
            return Response({
                'session_id': session_id,
                'user_id': request.user.id,
                'subject_id': subject_id,
                'start_time': timezone.now().isoformat(),
                'message': '학습 세션이 시작되었습니다.',
                'websocket_url': f'/ws/learning/analytics/'
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"학습 세션 시작 오류: {e}")
            return Response({
                'error': '학습 세션 시작 중 오류가 발생했습니다.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        summary="학습 세션 종료",
        description="현재 진행 중인 학습 세션을 종료하고 요약을 제공합니다.",
        request={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "종료할 세션 ID"}
            },
            "required": ["session_id"]
        }
    )
    @action(detail=False, methods=['post'])
    def end_session(self, request):
        """학습 세션 종료"""
        try:
            session_id = request.data.get('session_id')
            
            if not session_id:
                return Response({
                    'error': '세션 ID가 필요합니다.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 비동기 함수를 동기적으로 실행
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                summary = loop.run_until_complete(
                    end_learning_session(session_id)
                )
            finally:
                loop.close()
            
            # 메트릭 추적
            track_user_event(EventType.STUDY_SESSION_END, request.user.id, {
                'session_id': session_id,
                'duration': summary.get('duration', 0),
                'focus_score': summary.get('focus_score', 0)
            })
            
            return Response({
                'session_id': session_id,
                'summary': summary,
                'message': '학습 세션이 종료되었습니다.'
            })
            
        except ValueError as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"학습 세션 종료 오류: {e}")
            return Response({
                'error': '학습 세션 종료 중 오류가 발생했습니다.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        summary="세션 상태 조회",
        description="특정 학습 세션의 현재 상태를 조회합니다.",
        parameters=[
            OpenApiParameter(
                name="session_id",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="조회할 세션 ID"
            )
        ]
    )
    @action(detail=False, methods=['get'])
    def session_status(self, request):
        """세션 상태 조회"""
        try:
            session_id = request.query_params.get('session_id')
            
            if not session_id:
                return Response({
                    'error': '세션 ID가 필요합니다.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            status_data = get_session_status(session_id)
            
            if not status_data:
                return Response({
                    'error': '세션을 찾을 수 없습니다.'
                }, status=status.HTTP_404_NOT_FOUND)
            
            return Response({
                'status': status_data
            })
            
        except Exception as e:
            logger.error(f"세션 상태 조회 오류: {e}")
            return Response({
                'error': '세션 상태 조회 중 오류가 발생했습니다.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        summary="사용자 활성 세션 조회",
        description="현재 사용자의 모든 활성 세션을 조회합니다."
    )
    @action(detail=False, methods=['get'])
    def active_sessions(self, request):
        """사용자 활성 세션 조회"""
        try:
            user_sessions = []
            
            # 현재 사용자의 활성 세션 찾기
            for session_id, session in realtime_analyzer.active_sessions.items():
                if session.user_id == request.user.id:
                    user_sessions.append({
                        'session_id': session_id,
                        'subject_id': session.subject_id,
                        'start_time': session.start_time.isoformat(),
                        'duration': session.total_time,
                        'state': session.state.value,
                        'focus_score': session.focus_score
                    })
            
            return Response({
                'active_sessions': user_sessions,
                'count': len(user_sessions)
            })
            
        except Exception as e:
            logger.error(f"활성 세션 조회 오류: {e}")
            return Response({
                'error': '활성 세션 조회 중 오류가 발생했습니다.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        summary="실시간 대시보드 데이터",
        description="실시간 학습 분석 대시보드를 위한 데이터를 제공합니다.",
        parameters=[
            OpenApiParameter(
                name="session_id",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="특정 세션의 대시보드 데이터"
            )
        ]
    )
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """실시간 대시보드 데이터"""
        try:
            session_id = request.query_params.get('session_id')
            
            if session_id:
                # 특정 세션 대시보드
                session_status = get_session_status(session_id)
                if not session_status:
                    return Response({
                        'error': '세션을 찾을 수 없습니다.'
                    }, status=status.HTTP_404_NOT_FOUND)
                
                dashboard_data = {
                    'session': session_status,
                    'real_time_metrics': self._get_session_metrics(session_id),
                    'recommendations': self._get_session_recommendations(session_id)
                }
            else:
                # 전체 사용자 대시보드
                dashboard_data = {
                    'user_overview': self._get_user_overview(request.user.id),
                    'recent_activity': self._get_recent_activity(request.user.id),
                    'learning_trends': self._get_learning_trends(request.user.id)
                }
            
            return Response({
                'dashboard': dashboard_data,
                'generated_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"대시보드 데이터 조회 오류: {e}")
            return Response({
                'error': '대시보드 데이터 조회 중 오류가 발생했습니다.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_session_metrics(self, session_id: str) -> Dict[str, Any]:
        """세션 메트릭 조회"""
        cache_key = f"session_metrics:{session_id}"
        cached_metrics = cache.get(cache_key)
        
        if cached_metrics:
            return cached_metrics
        
        # 기본 메트릭
        metrics = {
            'focus_trend': [],
            'productivity_score': 0,
            'learning_velocity': 0,
            'break_recommendations': 0
        }
        
        cache.set(cache_key, metrics, timeout=300)
        return metrics
    
    def _get_session_recommendations(self, session_id: str) -> Dict[str, Any]:
        """세션 권장사항 조회"""
        cache_key = f"session_recommendations:{session_id}"
        cached_recommendations = cache.get(cache_key)
        
        if cached_recommendations:
            return cached_recommendations
        
        # 기본 권장사항
        recommendations = {
            'immediate': [],
            'upcoming': [],
            'learning_style': []
        }
        
        cache.set(cache_key, recommendations, timeout=300)
        return recommendations
    
    def _get_user_overview(self, user_id: int) -> Dict[str, Any]:
        """사용자 개요 조회"""
        cache_key = f"user_overview:{user_id}"
        cached_overview = cache.get(cache_key)
        
        if cached_overview:
            return cached_overview
        
        # 기본 개요
        overview = {
            'total_study_time_today': 0,
            'focus_score_average': 0,
            'completed_goals': 0,
            'active_subjects': 0,
            'streak_days': 0
        }
        
        cache.set(cache_key, overview, timeout=1800)  # 30분
        return overview
    
    def _get_recent_activity(self, user_id: int) -> Dict[str, Any]:
        """최근 활동 조회"""
        cache_key = f"recent_activity:{user_id}"
        cached_activity = cache.get(cache_key)
        
        if cached_activity:
            return cached_activity
        
        # 기본 활동
        activity = {
            'recent_sessions': [],
            'achievements': [],
            'study_patterns': {}
        }
        
        cache.set(cache_key, activity, timeout=900)  # 15분
        return activity
    
    def _get_learning_trends(self, user_id: int) -> Dict[str, Any]:
        """학습 트렌드 조회"""
        cache_key = f"learning_trends:{user_id}"
        cached_trends = cache.get(cache_key)
        
        if cached_trends:
            return cached_trends
        
        # 기본 트렌드
        trends = {
            'daily_progress': [],
            'subject_distribution': {},
            'efficiency_trend': [],
            'goal_progress': {}
        }
        
        cache.set(cache_key, trends, timeout=3600)  # 1시간
        return trends


class StreamingStatusViewSet(viewsets.ViewSet):
    """스트리밍 상태 조회 ViewSet (관리자용)"""
    
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        summary="스트리밍 상태 조회",
        description="실시간 스트리밍 처리 상태를 조회합니다."
    )
    @action(detail=False, methods=['get'])
    def status(self, request):
        """스트리밍 상태 조회"""
        try:
            # 비동기 함수를 동기적으로 실행
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                streaming_status = loop.run_until_complete(get_streaming_status())
            finally:
                loop.close()
            
            return Response({
                'streaming': streaming_status,
                'query_time': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"스트리밍 상태 조회 오류: {e}")
            return Response({
                'error': '스트리밍 상태 조회 중 오류가 발생했습니다.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        summary="스트림 메트릭 조회",
        description="개별 스트림의 상세 메트릭을 조회합니다.",
        parameters=[
            OpenApiParameter(
                name="stream_name",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="조회할 스트림명"
            )
        ]
    )
    @action(detail=False, methods=['get'])
    def metrics(self, request):
        """스트림 메트릭 조회"""
        try:
            stream_name = request.query_params.get('stream_name')
            
            # 비동기 함수를 동기적으로 실행
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                metrics = loop.run_until_complete(
                    stream_processor.get_stream_metrics(stream_name)
                )
            finally:
                loop.close()
            
            return Response({
                'metrics': metrics,
                'query_time': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"스트림 메트릭 조회 오류: {e}")
            return Response({
                'error': '스트림 메트릭 조회 중 오류가 발생했습니다.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        summary="시스템 성능 조회",
        description="실시간 분석 시스템의 전체 성능 지표를 조회합니다."
    )
    @action(detail=False, methods=['get'])
    def performance(self, request):
        """시스템 성능 조회"""
        try:
            performance_data = {
                'active_sessions': realtime_analyzer.get_active_sessions_count(),
                'stream_status': cache.get('stream_metrics', {}),
                'system_load': {
                    'cpu_usage': 0,  # 실제 구현에서는 psutil 사용
                    'memory_usage': 0,
                    'connection_count': 0
                },
                'processing_stats': {
                    'events_per_second': 0,
                    'average_latency_ms': 0,
                    'error_rate': 0
                }
            }
            
            return Response({
                'performance': performance_data,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"시스템 성능 조회 오류: {e}")
            return Response({
                'error': '시스템 성능 조회 중 오류가 발생했습니다.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)