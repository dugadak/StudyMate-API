"""
API Versioning system for StudyMate API

This module provides a flexible API versioning system.
"""

from django.urls import path, include
from rest_framework.versioning import URLPathVersioning
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from typing import Dict, List
import re


class StudyMateAPIVersioning(URLPathVersioning):
    """커스텀 API 버저닝 클래스"""
    
    default_version = 'v1'
    allowed_versions = ['v1', 'v2']
    version_param = 'version'
    
    def determine_version(self, request, *args, **kwargs):
        """API 버전 결정"""
        version = super().determine_version(request, *args, **kwargs)
        
        # 버전 헤더 확인 (URL 버전보다 우선)
        header_version = request.META.get('HTTP_API_VERSION')
        if header_version and header_version in self.allowed_versions:
            version = header_version
        
        return version


class APIVersionInfo:
    """API 버전 정보 관리 클래스"""
    
    VERSIONS = {
        'v1': {
            'status': 'stable',
            'deprecated': False,
            'sunset_date': None,
            'description': 'Initial stable API version',
            'changes': [],
        },
        'v2': {
            'status': 'beta',
            'deprecated': False,
            'sunset_date': None,
            'description': 'Enhanced API with improved performance and new features',
            'changes': [
                'Improved caching strategy',
                'Enhanced response format',
                'New bulk operations',
                'WebSocket support for real-time updates'
            ],
        }
    }
    
    @classmethod
    def get_version_info(cls, version: str) -> Dict:
        """특정 버전 정보 반환"""
        return cls.VERSIONS.get(version, {})
    
    @classmethod
    def get_all_versions(cls) -> Dict:
        """모든 버전 정보 반환"""
        return cls.VERSIONS
    
    @classmethod
    def is_deprecated(cls, version: str) -> bool:
        """버전 deprecation 확인"""
        version_info = cls.get_version_info(version)
        return version_info.get('deprecated', False)
    
    @classmethod
    def get_latest_stable(cls) -> str:
        """최신 안정 버전 반환"""
        for version, info in cls.VERSIONS.items():
            if info['status'] == 'stable' and not info['deprecated']:
                return version
        return 'v1'


class VersionAwareRouter:
    """버전별 URL 라우팅 관리"""
    
    def __init__(self):
        self.version_patterns = {}
    
    def register(self, version: str, patterns: List):
        """버전별 URL 패턴 등록"""
        if version not in StudyMateAPIVersioning.allowed_versions:
            raise ValueError(f"Invalid version: {version}")
        self.version_patterns[version] = patterns
    
    def get_urlpatterns(self) -> List:
        """모든 버전의 URL 패턴 반환"""
        urlpatterns = []
        
        for version, patterns in self.version_patterns.items():
            # 버전별 URL 패턴 추가
            urlpatterns.append(
                path(f'api/{version}/', include(patterns))
            )
        
        return urlpatterns


class APIVersionView(APIView):
    """API 버전 정보 제공 뷰"""
    
    authentication_classes = []
    permission_classes = []
    
    def get(self, request):
        """사용 가능한 API 버전 정보 반환"""
        versions = APIVersionInfo.get_all_versions()
        current_version = request.version or StudyMateAPIVersioning.default_version
        
        response_data = {
            'current_version': current_version,
            'latest_stable': APIVersionInfo.get_latest_stable(),
            'available_versions': versions,
            'deprecation_notices': self._get_deprecation_notices(),
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    def _get_deprecation_notices(self) -> List[Dict]:
        """Deprecation 공지 반환"""
        notices = []
        for version, info in APIVersionInfo.VERSIONS.items():
            if info['deprecated']:
                notices.append({
                    'version': version,
                    'sunset_date': info.get('sunset_date'),
                    'migration_guide': f'/api/docs/migration/{version}/'
                })
        return notices


def version_specific(versions: List[str]):
    """특정 버전에서만 동작하는 뷰 데코레이터"""
    def decorator(view_func):
        def wrapped_view(request, *args, **kwargs):
            current_version = getattr(request, 'version', 'v1')
            if current_version not in versions:
                return Response(
                    {
                        'error': f'This endpoint is not available in API version {current_version}',
                        'available_versions': versions
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator


def deprecated_in(version: str, sunset_date: str = None):
    """API deprecation 표시 데코레이터"""
    def decorator(view_func):
        def wrapped_view(request, *args, **kwargs):
            response = view_func(request, *args, **kwargs)
            
            # Deprecation 헤더 추가
            current_version = getattr(request, 'version', 'v1')
            if current_version == version:
                response['Deprecation'] = 'true'
                if sunset_date:
                    response['Sunset'] = sunset_date
                response['Link'] = f'</api/docs/migration/{version}/>; rel="deprecation"'
            
            return response
        return wrapped_view
    return decorator


class VersionedSerializer:
    """버전별 시리얼라이저 관리"""
    
    def __init__(self, version_map: Dict):
        """
        Args:
            version_map: 버전별 시리얼라이저 맵핑
                예: {'v1': SerializerV1, 'v2': SerializerV2}
        """
        self.version_map = version_map
    
    def get_serializer_class(self, version: str):
        """버전에 맞는 시리얼라이저 클래스 반환"""
        serializer_class = self.version_map.get(version)
        if not serializer_class:
            # 기본값으로 최신 버전 사용
            latest = APIVersionInfo.get_latest_stable()
            serializer_class = self.version_map.get(latest)
        return serializer_class


class VersionedViewMixin:
    """버전별 뷰 처리를 위한 믹스인"""
    
    versioned_serializers = None  # VersionedSerializer 인스턴스
    
    def get_serializer_class(self):
        """요청 버전에 맞는 시리얼라이저 반환"""
        if self.versioned_serializers:
            version = getattr(self.request, 'version', 'v1')
            return self.versioned_serializers.get_serializer_class(version)
        return super().get_serializer_class()
    
    def get_queryset(self):
        """버전별 쿼리셋 처리"""
        queryset = super().get_queryset()
        version = getattr(self.request, 'version', 'v1')
        
        # 버전별 필터링 로직
        if hasattr(self, f'filter_queryset_{version}'):
            filter_method = getattr(self, f'filter_queryset_{version}')
            queryset = filter_method(queryset)
        
        return queryset


# URL 패턴 생성 헬퍼
def create_versioned_urlpatterns():
    """버전별 URL 패턴 생성"""
    from accounts import urls as accounts_urls
    from study import urls as study_urls
    from quiz import urls as quiz_urls
    from subscription import urls as subscription_urls
    from notifications import urls as notifications_urls
    
    router = VersionAwareRouter()
    
    # v1 URL 패턴
    v1_patterns = [
        path('versions/', APIVersionView.as_view(), name='api-versions'),
        path('auth/', include(accounts_urls)),
        path('study/', include(study_urls)),
        path('quiz/', include(quiz_urls)),
        path('subscription/', include(subscription_urls)),
        path('notifications/', include(notifications_urls)),
    ]
    router.register('v1', v1_patterns)
    
    # v2 URL 패턴 (v1 + 추가 기능)
    v2_patterns = v1_patterns + [
        # v2 전용 엔드포인트
        path('bulk/', include('studymate_api.bulk_urls')),
        path('realtime/', include('studymate_api.realtime_urls')),
        path('analytics/', include('studymate_api.analytics_urls')),
    ]
    router.register('v2', v2_patterns)
    
    return router.get_urlpatterns()


# 버전 마이그레이션 가이드
class VersionMigrationGuide:
    """버전 마이그레이션 가이드 제공"""
    
    MIGRATION_GUIDES = {
        'v1_to_v2': {
            'breaking_changes': [
                {
                    'endpoint': '/api/study/summaries/',
                    'change': 'Response format changed to include metadata',
                    'migration': 'Update response parsing to handle new format'
                },
                {
                    'endpoint': '/api/auth/login/',
                    'change': 'Now returns refresh token separately',
                    'migration': 'Store refresh token in secure storage'
                }
            ],
            'new_features': [
                'Bulk operations for summaries and quizzes',
                'WebSocket support for real-time updates',
                'Enhanced caching with ETags'
            ],
            'deprecated': [
                {
                    'endpoint': '/api/study/old-summary/',
                    'replacement': '/api/study/summaries/',
                    'sunset': '2025-06-01'
                }
            ]
        }
    }
    
    @classmethod
    def get_migration_guide(cls, from_version: str, to_version: str) -> Dict:
        """특정 버전 간 마이그레이션 가이드 반환"""
        guide_key = f"{from_version}_to_{to_version}"
        return cls.MIGRATION_GUIDES.get(guide_key, {})