"""
Zero Trust 보안 모델 구현

"Never trust, always verify" 원칙에 따른 포괄적인 보안 시스템입니다.
"""

import logging
import hashlib
import hmac
import secrets
import time
from typing import Dict, Any, Optional, List, Tuple, Set
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
import ipaddress
import jwt
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from django.utils import timezone
from django.db import models
import geoip2.database
import geoip2.errors

logger = logging.getLogger(__name__)
User = get_user_model()


class ThreatLevel(Enum):
    """위협 수준"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityAction(Enum):
    """보안 액션"""
    ALLOW = "allow"
    CHALLENGE = "challenge"
    BLOCK = "block"
    QUARANTINE = "quarantine"


class ContextType(Enum):
    """컨텍스트 타입"""
    DEVICE = "device"
    LOCATION = "location"
    BEHAVIOR = "behavior"
    NETWORK = "network"
    TIME = "time"


@dataclass
class DeviceFingerprint:
    """디바이스 지문"""
    user_agent: str
    screen_resolution: str
    timezone: str
    language: str
    platform: str
    browser_hash: str
    
    def generate_fingerprint(self) -> str:
        """고유 디바이스 지문 생성"""
        data = f"{self.user_agent}:{self.screen_resolution}:{self.timezone}:{self.language}:{self.platform}"
        return hashlib.sha256(data.encode()).hexdigest()


@dataclass
class LocationContext:
    """위치 컨텍스트"""
    ip_address: str
    country: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_vpn: bool = False
    is_tor: bool = False
    
    def is_suspicious_location(self, known_locations: List[Dict]) -> bool:
        """의심스러운 위치인지 확인"""
        if self.is_vpn or self.is_tor:
            return True
        
        # 알려진 위치와 비교
        for known_loc in known_locations:
            if (self.country == known_loc.get('country') and 
                self.city == known_loc.get('city')):
                return False
        
        return len(known_locations) > 0  # 새로운 위치는 의심스러움


@dataclass
class BehaviorPattern:
    """행동 패턴"""
    login_frequency: float  # 시간당 로그인 횟수
    api_call_pattern: Dict[str, int]  # API 호출 패턴
    active_hours: List[int]  # 활성 시간대
    session_duration: float  # 평균 세션 시간
    failed_attempts: int  # 실패 시도 횟수
    
    def calculate_anomaly_score(self, current_behavior: Dict[str, Any]) -> float:
        """행동 이상 점수 계산"""
        score = 0.0
        
        # 로그인 빈도 이상
        current_frequency = current_behavior.get('login_frequency', 0)
        if current_frequency > self.login_frequency * 3:
            score += 0.3
        
        # 비정상적인 시간대 접근
        current_hour = datetime.now().hour
        if current_hour not in self.active_hours:
            score += 0.2
        
        # 과도한 실패 시도
        current_failures = current_behavior.get('failed_attempts', 0)
        if current_failures > 5:
            score += 0.4
        
        # API 호출 패턴 이상
        current_api_calls = current_behavior.get('api_calls', {})
        for endpoint, count in current_api_calls.items():
            normal_count = self.api_call_pattern.get(endpoint, 0)
            if count > normal_count * 5:
                score += 0.1
        
        return min(score, 1.0)


@dataclass
class SecurityContext:
    """보안 컨텍스트"""
    user_id: int
    session_id: str
    device_fingerprint: DeviceFingerprint
    location_context: LocationContext
    behavior_pattern: BehaviorPattern
    request_metadata: Dict[str, Any]
    timestamp: datetime
    
    def calculate_trust_score(self) -> float:
        """신뢰 점수 계산 (0.0 ~ 1.0)"""
        score = 1.0
        
        # 디바이스 신뢰도
        if not self._is_known_device():
            score -= 0.3
        
        # 위치 신뢰도
        if self.location_context.is_suspicious_location(self._get_known_locations()):
            score -= 0.4
        
        # 행동 패턴 신뢰도
        behavior_score = self.behavior_pattern.calculate_anomaly_score(
            self.request_metadata.get('current_behavior', {})
        )
        score -= behavior_score * 0.5
        
        return max(score, 0.0)
    
    def _is_known_device(self) -> bool:
        """알려진 디바이스인지 확인"""
        fingerprint = self.device_fingerprint.generate_fingerprint()
        cache_key = f"known_device:{self.user_id}:{fingerprint}"
        return cache.get(cache_key, False)
    
    def _get_known_locations(self) -> List[Dict]:
        """사용자의 알려진 위치 목록"""
        cache_key = f"known_locations:{self.user_id}"
        return cache.get(cache_key, [])


class ZeroTrustEngine:
    """Zero Trust 보안 엔진"""
    
    def __init__(self):
        self.geoip_db_path = getattr(settings, 'GEOIP_DB_PATH', None)
        self.trust_thresholds = {
            ThreatLevel.LOW: 0.8,
            ThreatLevel.MEDIUM: 0.6,
            ThreatLevel.HIGH: 0.4,
            ThreatLevel.CRITICAL: 0.2
        }
        
        # 보안 정책
        self.security_policies = {
            'max_failed_attempts': 5,
            'session_timeout': 3600,  # 1시간
            'device_trust_duration': 86400 * 30,  # 30일
            'location_trust_duration': 86400 * 7,  # 7일
            'mfa_required_threshold': 0.5,
            'admin_required_threshold': 0.3
        }
    
    def evaluate_request(self, request: HttpRequest, user: User) -> Tuple[SecurityAction, Dict[str, Any]]:
        """요청 평가 및 보안 액션 결정"""
        try:
            # 보안 컨텍스트 생성
            context = self._build_security_context(request, user)
            
            # 신뢰 점수 계산
            trust_score = context.calculate_trust_score()
            
            # 위협 수준 결정
            threat_level = self._determine_threat_level(trust_score)
            
            # 보안 액션 결정
            action = self._determine_security_action(threat_level, context)
            
            # 결과 로깅
            self._log_security_decision(context, trust_score, threat_level, action)
            
            # 추가 보안 조치
            additional_measures = self._get_additional_measures(action, context)
            
            return action, {
                'trust_score': trust_score,
                'threat_level': threat_level.value,
                'context': asdict(context),
                'additional_measures': additional_measures,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Zero Trust 평가 중 오류: {e}")
            # 오류 시 보수적으로 CHALLENGE 반환
            return SecurityAction.CHALLENGE, {
                'error': str(e),
                'fallback_action': True
            }
    
    def _build_security_context(self, request: HttpRequest, user: User) -> SecurityContext:
        """보안 컨텍스트 구축"""
        # 디바이스 지문 생성
        device_fingerprint = self._extract_device_fingerprint(request)
        
        # 위치 컨텍스트 생성
        location_context = self._extract_location_context(request)
        
        # 행동 패턴 분석
        behavior_pattern = self._analyze_behavior_pattern(user)
        
        # 요청 메타데이터
        request_metadata = self._extract_request_metadata(request)
        
        return SecurityContext(
            user_id=user.id,
            session_id=request.session.session_key or '',
            device_fingerprint=device_fingerprint,
            location_context=location_context,
            behavior_pattern=behavior_pattern,
            request_metadata=request_metadata,
            timestamp=timezone.now()
        )
    
    def _extract_device_fingerprint(self, request: HttpRequest) -> DeviceFingerprint:
        """디바이스 지문 추출"""
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # 클라이언트 힌트에서 추가 정보 추출
        platform = request.META.get('HTTP_SEC_CH_UA_PLATFORM', 'unknown')
        
        return DeviceFingerprint(
            user_agent=user_agent,
            screen_resolution=request.META.get('HTTP_SCREEN_RESOLUTION', 'unknown'),
            timezone=request.META.get('HTTP_TIMEZONE', 'unknown'),
            language=request.META.get('HTTP_ACCEPT_LANGUAGE', 'unknown'),
            platform=platform,
            browser_hash=hashlib.md5(user_agent.encode()).hexdigest()
        )
    
    def _extract_location_context(self, request: HttpRequest) -> LocationContext:
        """위치 컨텍스트 추출"""
        ip_address = self._get_client_ip(request)
        
        location_data = self._get_location_from_ip(ip_address)
        
        return LocationContext(
            ip_address=ip_address,
            country=location_data.get('country'),
            city=location_data.get('city'),
            latitude=location_data.get('latitude'),
            longitude=location_data.get('longitude'),
            is_vpn=self._is_vpn_ip(ip_address),
            is_tor=self._is_tor_ip(ip_address)
        )
    
    def _analyze_behavior_pattern(self, user: User) -> BehaviorPattern:
        """사용자 행동 패턴 분석"""
        cache_key = f"behavior_pattern:{user.id}"
        cached_pattern = cache.get(cache_key)
        
        if cached_pattern:
            return BehaviorPattern(**cached_pattern)
        
        # 기본 패턴 (실제로는 데이터베이스에서 분석)
        pattern = BehaviorPattern(
            login_frequency=2.0,  # 시간당 2회
            api_call_pattern={
                'study': 10,
                'quiz': 5,
                'auth': 1
            },
            active_hours=list(range(9, 22)),  # 9시-22시
            session_duration=1800.0,  # 30분
            failed_attempts=0
        )
        
        # 캐시에 저장
        cache.set(cache_key, asdict(pattern), timeout=3600)
        
        return pattern
    
    def _extract_request_metadata(self, request: HttpRequest) -> Dict[str, Any]:
        """요청 메타데이터 추출"""
        return {
            'method': request.method,
            'path': request.path,
            'is_ajax': request.headers.get('X-Requested-With') == 'XMLHttpRequest',
            'content_type': request.content_type,
            'secure': request.is_secure(),
            'timestamp': timezone.now().isoformat(),
            'referer': request.META.get('HTTP_REFERER', ''),
            'current_behavior': self._get_current_behavior(request)
        }
    
    def _get_current_behavior(self, request: HttpRequest) -> Dict[str, Any]:
        """현재 행동 분석"""
        session = request.session
        
        # 세션에서 현재 행동 데이터 수집
        current_hour = datetime.now().hour
        session_start = session.get('session_start', timezone.now().timestamp())
        session_duration = time.time() - session_start
        
        return {
            'login_frequency': session.get('login_count', 0),
            'failed_attempts': session.get('failed_attempts', 0),
            'session_duration': session_duration,
            'current_hour': current_hour,
            'api_calls': session.get('api_calls', {})
        }
    
    def _determine_threat_level(self, trust_score: float) -> ThreatLevel:
        """위협 수준 결정"""
        if trust_score >= self.trust_thresholds[ThreatLevel.LOW]:
            return ThreatLevel.LOW
        elif trust_score >= self.trust_thresholds[ThreatLevel.MEDIUM]:
            return ThreatLevel.MEDIUM
        elif trust_score >= self.trust_thresholds[ThreatLevel.HIGH]:
            return ThreatLevel.HIGH
        else:
            return ThreatLevel.CRITICAL
    
    def _determine_security_action(self, threat_level: ThreatLevel, context: SecurityContext) -> SecurityAction:
        """보안 액션 결정"""
        # 관리자 계정은 더 엄격한 기준 적용
        user = User.objects.get(id=context.user_id)
        is_admin = user.is_staff or user.is_superuser
        
        if threat_level == ThreatLevel.LOW:
            return SecurityAction.ALLOW
        
        elif threat_level == ThreatLevel.MEDIUM:
            # MFA 필요한 경우
            if context.calculate_trust_score() < self.security_policies['mfa_required_threshold']:
                return SecurityAction.CHALLENGE
            return SecurityAction.ALLOW
        
        elif threat_level == ThreatLevel.HIGH:
            if is_admin:
                return SecurityAction.BLOCK
            return SecurityAction.CHALLENGE
        
        else:  # CRITICAL
            return SecurityAction.BLOCK
    
    def _get_additional_measures(self, action: SecurityAction, context: SecurityContext) -> Dict[str, Any]:
        """추가 보안 조치"""
        measures = {}
        
        if action == SecurityAction.CHALLENGE:
            measures['mfa_required'] = True
            measures['challenge_type'] = 'email_verification'
            
        elif action == SecurityAction.BLOCK:
            measures['block_duration'] = 3600  # 1시간
            measures['notification_required'] = True
            
        elif action == SecurityAction.QUARANTINE:
            measures['quarantine_duration'] = 86400  # 24시간
            measures['admin_notification'] = True
        
        # 디바이스 등록
        if not context._is_known_device():
            measures['device_registration'] = True
        
        return measures
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """클라이언트 IP 추출"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        
        return ip
    
    def _get_location_from_ip(self, ip_address: str) -> Dict[str, Any]:
        """IP에서 위치 정보 추출"""
        if not self.geoip_db_path:
            return {}
        
        try:
            with geoip2.database.Reader(self.geoip_db_path) as reader:
                response = reader.city(ip_address)
                return {
                    'country': response.country.name,
                    'city': response.city.name,
                    'latitude': float(response.location.latitude) if response.location.latitude else None,
                    'longitude': float(response.location.longitude) if response.location.longitude else None
                }
        except (geoip2.errors.AddressNotFoundError, Exception) as e:
            logger.warning(f"GeoIP 조회 실패: {e}")
            return {}
    
    def _is_vpn_ip(self, ip_address: str) -> bool:
        """VPN IP 확인"""
        # 실제 구현에서는 VPN 탐지 서비스 연동
        vpn_ranges = [
            '10.0.0.0/8',
            '172.16.0.0/12',
            '192.168.0.0/16'
        ]
        
        try:
            ip = ipaddress.ip_address(ip_address)
            for range_str in vpn_ranges:
                if ip in ipaddress.ip_network(range_str):
                    return True
        except Exception:
            pass
        
        return False
    
    def _is_tor_ip(self, ip_address: str) -> bool:
        """Tor IP 확인"""
        # 실제 구현에서는 Tor 노드 리스트와 비교
        cache_key = f"tor_check:{ip_address}"
        cached_result = cache.get(cache_key)
        
        if cached_result is not None:
            return cached_result
        
        # 간단한 Tor 탐지 (실제로는 더 정교한 방법 사용)
        is_tor = False  # 실제 Tor 탐지 로직 구현 필요
        
        cache.set(cache_key, is_tor, timeout=3600)
        return is_tor
    
    def _log_security_decision(self, context: SecurityContext, trust_score: float, 
                             threat_level: ThreatLevel, action: SecurityAction):
        """보안 결정 로깅"""
        log_data = {
            'user_id': context.user_id,
            'trust_score': trust_score,
            'threat_level': threat_level.value,
            'action': action.value,
            'ip_address': context.location_context.ip_address,
            'timestamp': context.timestamp.isoformat()
        }
        
        logger.info(f"Zero Trust Decision: {log_data}")
        
        # 고위험 상황은 별도 로깅
        if threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
            logger.warning(f"High Risk Security Event: {log_data}")
    
    def register_trusted_device(self, user_id: int, device_fingerprint: str):
        """신뢰 디바이스 등록"""
        cache_key = f"known_device:{user_id}:{device_fingerprint}"
        cache.set(cache_key, True, timeout=self.security_policies['device_trust_duration'])
        
        logger.info(f"Trusted device registered for user {user_id}")
    
    def register_trusted_location(self, user_id: int, location_data: Dict[str, Any]):
        """신뢰 위치 등록"""
        cache_key = f"known_locations:{user_id}"
        known_locations = cache.get(cache_key, [])
        
        # 중복 제거
        for loc in known_locations:
            if (loc.get('country') == location_data.get('country') and 
                loc.get('city') == location_data.get('city')):
                return
        
        known_locations.append(location_data)
        cache.set(cache_key, known_locations, timeout=self.security_policies['location_trust_duration'])
        
        logger.info(f"Trusted location registered for user {user_id}: {location_data}")


# 전역 Zero Trust 엔진 인스턴스
zero_trust_engine = ZeroTrustEngine()


# 편의 함수들
def evaluate_request_security(request: HttpRequest, user: User) -> Tuple[SecurityAction, Dict[str, Any]]:
    """요청 보안 평가"""
    return zero_trust_engine.evaluate_request(request, user)


def register_trusted_device(user_id: int, device_fingerprint: str):
    """신뢰 디바이스 등록"""
    zero_trust_engine.register_trusted_device(user_id, device_fingerprint)


def register_trusted_location(user_id: int, location_data: Dict[str, Any]):
    """신뢰 위치 등록"""
    zero_trust_engine.register_trusted_location(user_id, location_data)