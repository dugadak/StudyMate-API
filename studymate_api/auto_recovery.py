"""
자동화된 장애 복구 시스템

서비스 장애를 감지하고 자동으로 복구 작업을 수행하는 시스템입니다.
"""

import logging
import time
import threading
import subprocess
import psutil
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
import requests
import redis
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.core.mail import send_mail
from django.db import connections
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """서비스 상태"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    DOWN = "down"


class RecoveryAction(Enum):
    """복구 액션"""
    RESTART_SERVICE = "restart_service"
    CLEAR_CACHE = "clear_cache"
    RESET_DATABASE_CONNECTIONS = "reset_db_connections"
    SCALE_UP = "scale_up"
    CIRCUIT_BREAKER_RESET = "circuit_breaker_reset"
    MANUAL_INTERVENTION = "manual_intervention"


@dataclass
class HealthCheck:
    """헬스 체크 설정"""
    name: str
    check_type: str  # http, database, redis, memory, disk
    endpoint: Optional[str] = None
    timeout: int = 30
    retry_count: int = 3
    threshold: Dict[str, float] = None
    check_interval: int = 60  # seconds
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ServiceHealth:
    """서비스 헬스 상태"""
    service_name: str
    status: HealthStatus
    response_time: float
    error_message: Optional[str] = None
    metrics: Dict[str, Any] = None
    last_check: datetime = None
    consecutive_failures: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['last_check'] = self.last_check.isoformat() if self.last_check else None
        data['status'] = self.status.value
        return data


@dataclass
class RecoveryRule:
    """복구 규칙"""
    service_name: str
    condition: str  # status condition
    action: RecoveryAction
    parameters: Dict[str, Any] = None
    max_attempts: int = 3
    cooldown_period: int = 300  # 5분
    escalation_rules: List[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['action'] = self.action.value
        return data


class HealthChecker:
    """헬스 체크 실행기"""
    
    def __init__(self):
        self.checks = {}
        self.results = {}
        self.running = False
        self.check_thread = None
        
    def register_check(self, health_check: HealthCheck):
        """헬스 체크 등록"""
        self.checks[health_check.name] = health_check
        logger.info(f"Health check registered: {health_check.name}")
    
    def start_monitoring(self):
        """모니터링 시작"""
        if self.running:
            return
        
        self.running = True
        self.check_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.check_thread.start()
        logger.info("Health monitoring started")
    
    def stop_monitoring(self):
        """모니터링 중지"""
        self.running = False
        if self.check_thread:
            self.check_thread.join()
        logger.info("Health monitoring stopped")
    
    def _monitoring_loop(self):
        """모니터링 루프"""
        while self.running:
            try:
                for check_name, health_check in self.checks.items():
                    result = self._execute_check(health_check)
                    self.results[check_name] = result
                    
                    # 결과를 캐시에 저장
                    cache_key = f"health_check:{check_name}"
                    cache.set(cache_key, result.to_dict(), timeout=300)
                
                # 체크 간격만큼 대기
                time.sleep(min(check.check_interval for check in self.checks.values()))
                
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                time.sleep(30)
    
    def _execute_check(self, health_check: HealthCheck) -> ServiceHealth:
        """개별 헬스 체크 실행"""
        start_time = time.time()
        
        try:
            if health_check.check_type == "http":
                return self._check_http_endpoint(health_check, start_time)
            elif health_check.check_type == "database":
                return self._check_database(health_check, start_time)
            elif health_check.check_type == "redis":
                return self._check_redis(health_check, start_time)
            elif health_check.check_type == "memory":
                return self._check_memory(health_check, start_time)
            elif health_check.check_type == "disk":
                return self._check_disk(health_check, start_time)
            else:
                raise ValueError(f"Unknown check type: {health_check.check_type}")
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ServiceHealth(
                service_name=health_check.name,
                status=HealthStatus.CRITICAL,
                response_time=response_time,
                error_message=str(e),
                last_check=timezone.now(),
                consecutive_failures=self.results.get(health_check.name, ServiceHealth(
                    service_name=health_check.name, status=HealthStatus.HEALTHY, response_time=0
                )).consecutive_failures + 1
            )
    
    def _check_http_endpoint(self, health_check: HealthCheck, start_time: float) -> ServiceHealth:
        """HTTP 엔드포인트 체크"""
        response = requests.get(
            health_check.endpoint,
            timeout=health_check.timeout
        )
        response_time = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            status = HealthStatus.HEALTHY
            error_message = None
        elif response.status_code < 500:
            status = HealthStatus.WARNING
            error_message = f"HTTP {response.status_code}"
        else:
            status = HealthStatus.CRITICAL
            error_message = f"HTTP {response.status_code}"
        
        return ServiceHealth(
            service_name=health_check.name,
            status=status,
            response_time=response_time,
            error_message=error_message,
            metrics={'status_code': response.status_code},
            last_check=timezone.now(),
            consecutive_failures=0 if status == HealthStatus.HEALTHY else 
                self.results.get(health_check.name, ServiceHealth(
                    service_name=health_check.name, status=HealthStatus.HEALTHY, response_time=0
                )).consecutive_failures + 1
        )
    
    def _check_database(self, health_check: HealthCheck, start_time: float) -> ServiceHealth:
        """데이터베이스 연결 체크"""
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            response_time = (time.time() - start_time) * 1000
            
            return ServiceHealth(
                service_name=health_check.name,
                status=HealthStatus.HEALTHY,
                response_time=response_time,
                last_check=timezone.now(),
                consecutive_failures=0
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ServiceHealth(
                service_name=health_check.name,
                status=HealthStatus.CRITICAL,
                response_time=response_time,
                error_message=str(e),
                last_check=timezone.now(),
                consecutive_failures=self.results.get(health_check.name, ServiceHealth(
                    service_name=health_check.name, status=HealthStatus.HEALTHY, response_time=0
                )).consecutive_failures + 1
            )
    
    def _check_redis(self, health_check: HealthCheck, start_time: float) -> ServiceHealth:
        """Redis 연결 체크"""
        try:
            redis_client = redis.Redis.from_url(settings.CACHES['default']['LOCATION'])
            redis_client.ping()
            
            response_time = (time.time() - start_time) * 1000
            
            return ServiceHealth(
                service_name=health_check.name,
                status=HealthStatus.HEALTHY,
                response_time=response_time,
                last_check=timezone.now(),
                consecutive_failures=0
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ServiceHealth(
                service_name=health_check.name,
                status=HealthStatus.CRITICAL,
                response_time=response_time,
                error_message=str(e),
                last_check=timezone.now(),
                consecutive_failures=self.results.get(health_check.name, ServiceHealth(
                    service_name=health_check.name, status=HealthStatus.HEALTHY, response_time=0
                )).consecutive_failures + 1
            )
    
    def _check_memory(self, health_check: HealthCheck, start_time: float) -> ServiceHealth:
        """메모리 사용량 체크"""
        memory = psutil.virtual_memory()
        response_time = (time.time() - start_time) * 1000
        
        threshold = health_check.threshold or {'warning': 80.0, 'critical': 90.0}
        
        if memory.percent < threshold.get('warning', 80.0):
            status = HealthStatus.HEALTHY
        elif memory.percent < threshold.get('critical', 90.0):
            status = HealthStatus.WARNING
        else:
            status = HealthStatus.CRITICAL
        
        return ServiceHealth(
            service_name=health_check.name,
            status=status,
            response_time=response_time,
            metrics={
                'memory_percent': memory.percent,
                'memory_used_mb': memory.used / 1024 / 1024,
                'memory_total_mb': memory.total / 1024 / 1024
            },
            last_check=timezone.now(),
            consecutive_failures=0 if status == HealthStatus.HEALTHY else 
                self.results.get(health_check.name, ServiceHealth(
                    service_name=health_check.name, status=HealthStatus.HEALTHY, response_time=0
                )).consecutive_failures + 1
        )
    
    def _check_disk(self, health_check: HealthCheck, start_time: float) -> ServiceHealth:
        """디스크 사용량 체크"""
        disk = psutil.disk_usage('/')
        response_time = (time.time() - start_time) * 1000
        
        threshold = health_check.threshold or {'warning': 80.0, 'critical': 90.0}
        
        if disk.percent < threshold.get('warning', 80.0):
            status = HealthStatus.HEALTHY
        elif disk.percent < threshold.get('critical', 90.0):
            status = HealthStatus.WARNING
        else:
            status = HealthStatus.CRITICAL
        
        return ServiceHealth(
            service_name=health_check.name,
            status=status,
            response_time=response_time,
            metrics={
                'disk_percent': disk.percent,
                'disk_used_gb': disk.used / 1024 / 1024 / 1024,
                'disk_total_gb': disk.total / 1024 / 1024 / 1024
            },
            last_check=timezone.now(),
            consecutive_failures=0 if status == HealthStatus.HEALTHY else 
                self.results.get(health_check.name, ServiceHealth(
                    service_name=health_check.name, status=HealthStatus.HEALTHY, response_time=0
                )).consecutive_failures + 1
        )
    
    def get_health_status(self, service_name: str) -> Optional[ServiceHealth]:
        """서비스 헬스 상태 조회"""
        return self.results.get(service_name)
    
    def get_all_health_status(self) -> Dict[str, ServiceHealth]:
        """모든 서비스 헬스 상태 조회"""
        return self.results.copy()


class AutoRecoveryEngine:
    """자동 복구 엔진"""
    
    def __init__(self, health_checker: HealthChecker):
        self.health_checker = health_checker
        self.recovery_rules = {}
        self.recovery_history = []
        self.running = False
        self.recovery_thread = None
        self.last_recovery_attempts = {}
        
    def register_recovery_rule(self, rule: RecoveryRule):
        """복구 규칙 등록"""
        if rule.service_name not in self.recovery_rules:
            self.recovery_rules[rule.service_name] = []
        self.recovery_rules[rule.service_name].append(rule)
        logger.info(f"Recovery rule registered for {rule.service_name}: {rule.action.value}")
    
    def start_recovery_monitoring(self):
        """복구 모니터링 시작"""
        if self.running:
            return
        
        self.running = True
        self.recovery_thread = threading.Thread(target=self._recovery_loop, daemon=True)
        self.recovery_thread.start()
        logger.info("Auto recovery monitoring started")
    
    def stop_recovery_monitoring(self):
        """복구 모니터링 중지"""
        self.running = False
        if self.recovery_thread:
            self.recovery_thread.join()
        logger.info("Auto recovery monitoring stopped")
    
    def _recovery_loop(self):
        """복구 모니터링 루프"""
        while self.running:
            try:
                health_results = self.health_checker.get_all_health_status()
                
                for service_name, health in health_results.items():
                    if self._should_attempt_recovery(service_name, health):
                        self._attempt_recovery(service_name, health)
                
                time.sleep(30)  # 30초마다 체크
                
            except Exception as e:
                logger.error(f"Recovery monitoring error: {e}")
                time.sleep(60)
    
    def _should_attempt_recovery(self, service_name: str, health: ServiceHealth) -> bool:
        """복구 시도 여부 판단"""
        # 상태가 정상이면 복구 불필요
        if health.status == HealthStatus.HEALTHY:
            return False
        
        # 복구 규칙이 없으면 복구 불가
        if service_name not in self.recovery_rules:
            return False
        
        # 쿨다운 기간 확인
        last_attempt = self.last_recovery_attempts.get(service_name)
        if last_attempt:
            cooldown = min(rule.cooldown_period for rule in self.recovery_rules[service_name])
            if timezone.now() - last_attempt < timedelta(seconds=cooldown):
                return False
        
        return True
    
    def _attempt_recovery(self, service_name: str, health: ServiceHealth):
        """복구 시도"""
        rules = self.recovery_rules.get(service_name, [])
        
        for rule in rules:
            if self._rule_matches_condition(rule, health):
                success = self._execute_recovery_action(rule, health)
                
                # 복구 이력 기록
                recovery_record = {
                    'service_name': service_name,
                    'action': rule.action.value,
                    'timestamp': timezone.now(),
                    'success': success,
                    'health_status': health.to_dict(),
                    'rule': rule.to_dict()
                }
                self.recovery_history.append(recovery_record)
                
                # 최근 시도 시간 기록
                self.last_recovery_attempts[service_name] = timezone.now()
                
                if success:
                    logger.info(f"Recovery successful for {service_name}: {rule.action.value}")
                    break
                else:
                    logger.warning(f"Recovery failed for {service_name}: {rule.action.value}")
    
    def _rule_matches_condition(self, rule: RecoveryRule, health: ServiceHealth) -> bool:
        """복구 규칙 조건 매칭"""
        condition = rule.condition.lower()
        
        if condition == "critical":
            return health.status == HealthStatus.CRITICAL
        elif condition == "warning_or_critical":
            return health.status in [HealthStatus.WARNING, HealthStatus.CRITICAL]
        elif condition == "consecutive_failures":
            threshold = rule.parameters.get('failure_threshold', 3)
            return health.consecutive_failures >= threshold
        
        return False
    
    def _execute_recovery_action(self, rule: RecoveryRule, health: ServiceHealth) -> bool:
        """복구 액션 실행"""
        try:
            if rule.action == RecoveryAction.RESTART_SERVICE:
                return self._restart_service(rule, health)
            elif rule.action == RecoveryAction.CLEAR_CACHE:
                return self._clear_cache(rule, health)
            elif rule.action == RecoveryAction.RESET_DATABASE_CONNECTIONS:
                return self._reset_database_connections(rule, health)
            elif rule.action == RecoveryAction.SCALE_UP:
                return self._scale_up(rule, health)
            elif rule.action == RecoveryAction.CIRCUIT_BREAKER_RESET:
                return self._reset_circuit_breaker(rule, health)
            elif rule.action == RecoveryAction.MANUAL_INTERVENTION:
                return self._request_manual_intervention(rule, health)
            else:
                logger.error(f"Unknown recovery action: {rule.action}")
                return False
                
        except Exception as e:
            logger.error(f"Recovery action execution failed: {e}")
            return False
    
    def _restart_service(self, rule: RecoveryRule, health: ServiceHealth) -> bool:
        """서비스 재시작"""
        service_command = rule.parameters.get('service_command')
        if not service_command:
            logger.error("No service command specified for restart")
            return False
        
        try:
            # systemctl이나 다른 서비스 관리자를 통한 재시작
            subprocess.run(['sudo', 'systemctl', 'restart', service_command], 
                         check=True, timeout=60)
            
            # 재시작 후 잠시 대기
            time.sleep(10)
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Service restart failed: {e}")
            return False
    
    def _clear_cache(self, rule: RecoveryRule, health: ServiceHealth) -> bool:
        """캐시 초기화"""
        try:
            cache.clear()
            logger.info("Cache cleared successfully")
            return True
        except Exception as e:
            logger.error(f"Cache clear failed: {e}")
            return False
    
    def _reset_database_connections(self, rule: RecoveryRule, health: ServiceHealth) -> bool:
        """데이터베이스 연결 리셋"""
        try:
            for alias in connections:
                connections[alias].close()
            logger.info("Database connections reset successfully")
            return True
        except Exception as e:
            logger.error(f"Database connection reset failed: {e}")
            return False
    
    def _scale_up(self, rule: RecoveryRule, health: ServiceHealth) -> bool:
        """스케일 업 (Kubernetes 등 오케스트레이션 환경)"""
        try:
            # Kubernetes 환경에서의 스케일링 예시
            namespace = rule.parameters.get('namespace', 'default')
            deployment = rule.parameters.get('deployment')
            replicas = rule.parameters.get('target_replicas', 3)
            
            if deployment:
                subprocess.run([
                    'kubectl', 'scale', f'deployment/{deployment}',
                    f'--replicas={replicas}', f'--namespace={namespace}'
                ], check=True, timeout=60)
                
                logger.info(f"Scaled up {deployment} to {replicas} replicas")
                return True
            
            return False
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Scale up failed: {e}")
            return False
    
    def _reset_circuit_breaker(self, rule: RecoveryRule, health: ServiceHealth) -> bool:
        """서킷 브레이커 리셋"""
        try:
            # 서킷 브레이커 상태를 캐시에서 제거
            circuit_breaker_key = rule.parameters.get('circuit_breaker_key')
            if circuit_breaker_key:
                cache.delete(circuit_breaker_key)
                logger.info(f"Circuit breaker reset: {circuit_breaker_key}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Circuit breaker reset failed: {e}")
            return False
    
    def _request_manual_intervention(self, rule: RecoveryRule, health: ServiceHealth) -> bool:
        """수동 개입 요청 (알림 발송)"""
        try:
            alert_config = rule.parameters.get('alert_config', {})
            
            # 이메일 알림
            if alert_config.get('email'):
                self._send_email_alert(health, alert_config)
            
            # Slack 알림
            if alert_config.get('slack_webhook'):
                self._send_slack_alert(health, alert_config)
            
            logger.info(f"Manual intervention requested for {health.service_name}")
            return True
            
        except Exception as e:
            logger.error(f"Manual intervention request failed: {e}")
            return False
    
    def _send_email_alert(self, health: ServiceHealth, alert_config: Dict[str, Any]):
        """이메일 알림 발송"""
        try:
            subject = f"[StudyMate] Service Health Alert: {health.service_name}"
            body = f"""
서비스 장애가 감지되었습니다.

서비스: {health.service_name}
상태: {health.status.value}
응답시간: {health.response_time:.2f}ms
연속 실패: {health.consecutive_failures}회
오류 메시지: {health.error_message or 'N/A'}
확인 시간: {health.last_check}

즉시 확인이 필요합니다.
            """
            
            send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=alert_config['email'],
                fail_silently=False
            )
            
        except Exception as e:
            logger.error(f"Email alert failed: {e}")
    
    def _send_slack_alert(self, health: ServiceHealth, alert_config: Dict[str, Any]):
        """Slack 알림 발송"""
        try:
            webhook_url = alert_config['slack_webhook']
            
            payload = {
                "text": f"🚨 Service Health Alert: {health.service_name}",
                "attachments": [
                    {
                        "color": "danger" if health.status == HealthStatus.CRITICAL else "warning",
                        "fields": [
                            {"title": "Service", "value": health.service_name, "short": True},
                            {"title": "Status", "value": health.status.value, "short": True},
                            {"title": "Response Time", "value": f"{health.response_time:.2f}ms", "short": True},
                            {"title": "Consecutive Failures", "value": str(health.consecutive_failures), "short": True},
                            {"title": "Error", "value": health.error_message or "N/A", "short": False},
                            {"title": "Check Time", "value": str(health.last_check), "short": False}
                        ]
                    }
                ]
            }
            
            requests.post(webhook_url, json=payload, timeout=10)
            
        except Exception as e:
            logger.error(f"Slack alert failed: {e}")
    
    def get_recovery_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """복구 이력 조회"""
        return self.recovery_history[-limit:]


# 전역 인스턴스
health_checker = HealthChecker()
auto_recovery_engine = AutoRecoveryEngine(health_checker)


# 편의 함수들
def start_monitoring():
    """모니터링 시작"""
    health_checker.start_monitoring()
    auto_recovery_engine.start_recovery_monitoring()


def stop_monitoring():
    """모니터링 중지"""
    health_checker.stop_monitoring()
    auto_recovery_engine.stop_recovery_monitoring()


def get_system_health() -> Dict[str, Any]:
    """시스템 전체 헬스 상태"""
    health_results = health_checker.get_all_health_status()
    
    overall_status = HealthStatus.HEALTHY
    for health in health_results.values():
        if health.status == HealthStatus.CRITICAL:
            overall_status = HealthStatus.CRITICAL
            break
        elif health.status == HealthStatus.WARNING and overall_status != HealthStatus.CRITICAL:
            overall_status = HealthStatus.WARNING
    
    return {
        'overall_status': overall_status.value,
        'services': {name: health.to_dict() for name, health in health_results.items()},
        'total_services': len(health_results),
        'healthy_services': len([h for h in health_results.values() if h.status == HealthStatus.HEALTHY]),
        'timestamp': timezone.now().isoformat()
    }