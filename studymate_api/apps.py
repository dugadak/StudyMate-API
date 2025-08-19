"""
StudyMate API Django 앱 설정

분산 추적 및 기타 시스템 초기화를 담당합니다.
"""

from django.apps import AppConfig
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class StudymateApiConfig(AppConfig):
    """StudyMate API 앱 설정"""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'studymate_api'
    verbose_name = 'StudyMate API'
    
    def ready(self):
        """앱이 로드될 때 실행되는 초기화 코드"""
        try:
            # OpenTelemetry 분산 추적 초기화
            if getattr(settings, 'DISTRIBUTED_TRACING', {}).get('ENABLED', False):
                self._initialize_distributed_tracing()
            
            # 실시간 분석 시스템 초기화
            if getattr(settings, 'REALTIME_ANALYTICS', {}).get('ENABLE_NOTIFICATIONS', True):
                self._initialize_realtime_analytics()
            
            # 성능 모니터링 초기화
            self._initialize_performance_monitoring()
            
            logger.info("StudyMate API 앱 초기화 완료")
            
        except Exception as e:
            logger.error(f"StudyMate API 앱 초기화 실패: {e}")
            # 초기화 실패가 전체 서버 시작을 막지 않도록 함
    
    def _initialize_distributed_tracing(self):
        """분산 추적 시스템 초기화"""
        try:
            from .distributed_tracing import initialize_tracing
            initialize_tracing()
            logger.info("OpenTelemetry 분산 추적 시스템 초기화 완료")
        except Exception as e:
            logger.warning(f"분산 추적 시스템 초기화 실패: {e}")
    
    def _initialize_realtime_analytics(self):
        """실시간 분석 시스템 초기화"""
        try:
            # 실시간 분석 관련 초기화는 필요시 추가
            pass
        except Exception as e:
            logger.warning(f"실시간 분석 시스템 초기화 실패: {e}")
    
    def _initialize_performance_monitoring(self):
        """성능 모니터링 초기화"""
        try:
            # 성능 모니터링 관련 초기화는 필요시 추가
            pass
        except Exception as e:
            logger.warning(f"성능 모니터링 초기화 실패: {e}")