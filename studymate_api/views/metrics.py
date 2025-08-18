"""
메트릭 API 뷰

관리자 및 대시보드용 메트릭 데이터 API를 제공합니다.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.http import HttpResponse
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from typing import Dict, Any
import json
import csv
import io
import logging

from studymate_api.metrics import (
    MetricsManager, 
    track_user_event, 
    track_business_event,
    track_system_event,
    EventType
)

logger = logging.getLogger(__name__)


class MetricsViewSet(viewsets.ViewSet):
    """메트릭 API ViewSet"""
    
    permission_classes = [permissions.IsAdminUser]  # 관리자만 접근 가능
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.manager = MetricsManager()
    
    @extend_schema(
        summary="종합 대시보드 메트릭 조회",
        description="사용자 획득, 참여도, 수익, API 성능, AI 사용량 등 종합 메트릭을 제공합니다.",
        responses={
            200: {
                "type": "object",
                "properties": {
                    "user_acquisition": {"type": "object"},
                    "engagement": {"type": "object"},
                    "revenue": {"type": "object"},
                    "api_performance": {"type": "object"},
                    "ai_usage": {"type": "object"},
                    "generated_at": {"type": "string", "format": "date-time"}
                }
            }
        }
    )
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """종합 대시보드 메트릭"""
        try:
            metrics = self.manager.get_dashboard_metrics()
            
            return Response(metrics, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"대시보드 메트릭 조회 실패: {e}")
            return Response({
                'error': '메트릭 조회 중 오류가 발생했습니다.',
                'error_type': 'system_error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        summary="사용자 획득 메트릭",
        description="신규 사용자 등록, 일별 통계, 변환율 등의 사용자 획득 메트릭을 제공합니다.",
        parameters=[
            OpenApiParameter(
                name="days",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="분석 기간 (일 수, 기본값: 30)"
            )
        ]
    )
    @action(detail=False, methods=['get'])
    def user_acquisition(self, request):
        """사용자 획득 메트릭"""
        try:
            days = int(request.query_params.get('days', 30))
            if days > 365:  # 최대 1년
                days = 365
            
            metrics = self.manager.business_analyzer.get_user_acquisition_metrics(days)
            
            return Response({
                'metrics': metrics,
                'period': f'{days}일',
                'generated_at': timezone.now().isoformat()
            }, status=status.HTTP_200_OK)
            
        except ValueError:
            return Response({
                'error': '유효하지 않은 days 매개변수입니다.',
                'error_type': 'validation_error'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f"사용자 획득 메트릭 조회 실패: {e}")
            return Response({
                'error': '메트릭 조회 중 오류가 발생했습니다.',
                'error_type': 'system_error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        summary="사용자 참여도 메트릭",
        description="일일 활성 사용자, 세션 시간, 기능 사용률 등의 참여도 메트릭을 제공합니다.",
        parameters=[
            OpenApiParameter(
                name="days",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="분석 기간 (일 수, 기본값: 30)"
            )
        ]
    )
    @action(detail=False, methods=['get'])
    def engagement(self, request):
        """사용자 참여도 메트릭"""
        try:
            days = int(request.query_params.get('days', 30))
            if days > 365:
                days = 365
            
            metrics = self.manager.business_analyzer.get_engagement_metrics(days)
            
            return Response({
                'metrics': metrics,
                'period': f'{days}일',
                'generated_at': timezone.now().isoformat()
            }, status=status.HTTP_200_OK)
            
        except ValueError:
            return Response({
                'error': '유효하지 않은 days 매개변수입니다.',
                'error_type': 'validation_error'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f"참여도 메트릭 조회 실패: {e}")
            return Response({
                'error': '메트릭 조회 중 오류가 발생했습니다.',
                'error_type': 'system_error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        summary="수익 메트릭",
        description="총 수익, 일별 수익, ARPU, 구독 관련 메트릭을 제공합니다.",
        parameters=[
            OpenApiParameter(
                name="days",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="분석 기간 (일 수, 기본값: 30)"
            )
        ]
    )
    @action(detail=False, methods=['get'])
    def revenue(self, request):
        """수익 메트릭"""
        try:
            days = int(request.query_params.get('days', 30))
            if days > 365:
                days = 365
            
            metrics = self.manager.business_analyzer.get_revenue_metrics(days)
            
            return Response({
                'metrics': metrics,
                'period': f'{days}일',
                'generated_at': timezone.now().isoformat()
            }, status=status.HTTP_200_OK)
            
        except ValueError:
            return Response({
                'error': '유효하지 않은 days 매개변수입니다.',
                'error_type': 'validation_error'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f"수익 메트릭 조회 실패: {e}")
            return Response({
                'error': '메트릭 조회 중 오류가 발생했습니다.',
                'error_type': 'system_error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        summary="API 성능 메트릭",
        description="API 요청 수, 에러율, 응답 시간, 캐시 성능 등의 시스템 성능 메트릭을 제공합니다.",
        parameters=[
            OpenApiParameter(
                name="hours",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="분석 기간 (시간 수, 기본값: 24)"
            )
        ]
    )
    @action(detail=False, methods=['get'])
    def api_performance(self, request):
        """API 성능 메트릭"""
        try:
            hours = int(request.query_params.get('hours', 24))
            if hours > 168:  # 최대 7일
                hours = 168
            
            metrics = self.manager.performance_analyzer.get_api_performance_metrics(hours)
            
            return Response({
                'metrics': metrics,
                'period': f'{hours}시간',
                'generated_at': timezone.now().isoformat()
            }, status=status.HTTP_200_OK)
            
        except ValueError:
            return Response({
                'error': '유효하지 않은 hours 매개변수입니다.',
                'error_type': 'validation_error'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f"API 성능 메트릭 조회 실패: {e}")
            return Response({
                'error': '메트릭 조회 중 오류가 발생했습니다.',
                'error_type': 'system_error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        summary="AI 사용량 메트릭",
        description="AI 요청 수, 제공자별 통계, 에러율, 응답 시간 등의 AI 사용량 메트릭을 제공합니다.",
        parameters=[
            OpenApiParameter(
                name="days",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="분석 기간 (일 수, 기본값: 7)"
            )
        ]
    )
    @action(detail=False, methods=['get'])
    def ai_usage(self, request):
        """AI 사용량 메트릭"""
        try:
            days = int(request.query_params.get('days', 7))
            if days > 90:  # 최대 3개월
                days = 90
            
            metrics = self.manager.performance_analyzer.get_ai_usage_metrics(days)
            
            return Response({
                'metrics': metrics,
                'period': f'{days}일',
                'generated_at': timezone.now().isoformat()
            }, status=status.HTTP_200_OK)
            
        except ValueError:
            return Response({
                'error': '유효하지 않은 days 매개변수입니다.',
                'error_type': 'validation_error'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f"AI 사용량 메트릭 조회 실패: {e}")
            return Response({
                'error': '메트릭 조회 중 오류가 발생했습니다.',
                'error_type': 'system_error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        summary="메트릭 데이터 내보내기",
        description="메트릭 데이터를 JSON 또는 CSV 형식으로 내보냅니다.",
        parameters=[
            OpenApiParameter(
                name="format",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="내보내기 형식 (json 또는 csv, 기본값: json)"
            )
        ]
    )
    @action(detail=False, methods=['get'])
    def export(self, request):
        """메트릭 데이터 내보내기"""
        try:
            format_type = request.query_params.get('format', 'json').lower()
            
            if format_type not in ['json', 'csv']:
                return Response({
                    'error': '지원하지 않는 형식입니다. json 또는 csv를 사용하세요.',
                    'error_type': 'validation_error'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            metrics = self.manager.get_dashboard_metrics()
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            
            if format_type == 'json':
                response = HttpResponse(
                    json.dumps(metrics, indent=2, ensure_ascii=False, default=str),
                    content_type='application/json; charset=utf-8'
                )
                response['Content-Disposition'] = f'attachment; filename="studymate_metrics_{timestamp}.json"'
                
            elif format_type == 'csv':
                output = io.StringIO()
                writer = csv.writer(output)
                
                # CSV 헤더
                writer.writerow(['Category', 'Metric', 'Value', 'Timestamp'])
                
                # 메트릭 데이터를 CSV 행으로 변환
                self._write_metrics_to_csv(writer, metrics)
                
                response = HttpResponse(
                    output.getvalue(),
                    content_type='text/csv; charset=utf-8'
                )
                response['Content-Disposition'] = f'attachment; filename="studymate_metrics_{timestamp}.csv"'
            
            return response
            
        except Exception as e:
            logger.error(f"메트릭 내보내기 실패: {e}")
            return Response({
                'error': '메트릭 내보내기 중 오류가 발생했습니다.',
                'error_type': 'system_error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _write_metrics_to_csv(self, writer, metrics):
        """메트릭 데이터를 CSV로 변환"""
        timestamp = metrics['generated_at']
        
        # 사용자 획득 메트릭
        ua = metrics['user_acquisition']
        writer.writerow(['User Acquisition', 'Total Registrations', ua['total_registrations'], timestamp])
        writer.writerow(['User Acquisition', 'Average Daily Registrations', ua['average_daily_registrations'], timestamp])
        
        # 참여도 메트릭
        eng = metrics['engagement']
        for feature, count in eng['feature_usage'].items():
            writer.writerow(['Engagement', f'Feature Usage - {feature}', count, timestamp])
        
        # 수익 메트릭
        rev = metrics['revenue']
        writer.writerow(['Revenue', 'Total Revenue', rev['total_revenue'], timestamp])
        sub_metrics = rev['subscription_metrics']
        writer.writerow(['Revenue', 'New Subscriptions', sub_metrics['new_subscriptions'], timestamp])
        writer.writerow(['Revenue', 'Cancelled Subscriptions', sub_metrics['cancelled_subscriptions'], timestamp])
        writer.writerow(['Revenue', 'Churn Rate (%)', sub_metrics['churn_rate'], timestamp])
        
        # API 성능 메트릭
        api = metrics['api_performance']
        writer.writerow(['API Performance', 'Total Requests', api['request_count'], timestamp])
        writer.writerow(['API Performance', 'Error Rate (%)', api['error_rate'], timestamp])
        writer.writerow(['API Performance', 'Cache Hit Rate (%)', api['cache_hit_rate'], timestamp])
        
        # AI 사용량 메트릭
        ai = metrics['ai_usage']
        writer.writerow(['AI Usage', 'Total AI Requests', ai['total_ai_requests'], timestamp])
        writer.writerow(['AI Usage', 'Error Rate (%)', ai['error_rate'], timestamp])
    
    @extend_schema(
        summary="테스트 메트릭 이벤트 생성",
        description="개발 및 테스트 목적으로 샘플 메트릭 이벤트를 생성합니다. (개발 환경에서만 사용)",
        request={
            "type": "object",
            "properties": {
                "event_count": {
                    "type": "integer", 
                    "description": "생성할 이벤트 수 (기본값: 100)"
                }
            }
        }
    )
    @action(detail=False, methods=['post'])
    def generate_test_events(self, request):
        """테스트 메트릭 이벤트 생성"""
        from django.conf import settings
        import random
        
        # 프로덕션 환경에서는 비활성화
        if not settings.DEBUG:
            return Response({
                'error': '이 기능은 개발 환경에서만 사용할 수 있습니다.',
                'error_type': 'permission_denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            event_count = request.data.get('event_count', 100)
            
            # 다양한 테스트 이벤트 생성
            for i in range(event_count):
                # 사용자 이벤트
                if random.random() < 0.3:
                    track_user_event(EventType.USER_LOGIN, user_id=random.randint(1, 50))
                
                if random.random() < 0.2:
                    track_user_event(EventType.STUDY_SESSION_START, user_id=random.randint(1, 50))
                
                # 비즈니스 이벤트
                if random.random() < 0.1:
                    track_business_event(EventType.USER_REGISTER)
                
                if random.random() < 0.05:
                    track_business_event(EventType.PAYMENT_SUCCESS, 
                                       value=random.choice([9990, 29990, 49990]))
                
                # 시스템 이벤트
                track_system_event(EventType.API_REQUEST)
                
                if random.random() < 0.02:  # 2% 에러율
                    track_system_event(EventType.API_ERROR)
            
            return Response({
                'message': f'{event_count}개의 테스트 메트릭 이벤트가 생성되었습니다.',
                'generated_at': timezone.now().isoformat()
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"테스트 이벤트 생성 실패: {e}")
            return Response({
                'error': '테스트 이벤트 생성 중 오류가 발생했습니다.',
                'error_type': 'system_error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)