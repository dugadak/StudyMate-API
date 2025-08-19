"""
자동 복구 시스템 설정

기본 헬스 체크 및 복구 규칙을 정의합니다.
"""

from .auto_recovery import (
    HealthCheck, RecoveryRule, RecoveryAction, 
    health_checker, auto_recovery_engine
)


def setup_default_health_checks():
    """기본 헬스 체크 설정"""
    
    # HTTP 서비스 체크
    health_checker.register_check(HealthCheck(
        name="web_server",
        check_type="http",
        endpoint="http://localhost:8000/health/",
        timeout=10,
        retry_count=3,
        check_interval=30
    ))
    
    # 데이터베이스 체크
    health_checker.register_check(HealthCheck(
        name="database",
        check_type="database",
        timeout=15,
        retry_count=3,
        check_interval=60
    ))
    
    # Redis 캐시 체크
    health_checker.register_check(HealthCheck(
        name="redis",
        check_type="redis",
        timeout=10,
        retry_count=3,
        check_interval=60
    ))
    
    # 메모리 사용량 체크
    health_checker.register_check(HealthCheck(
        name="memory",
        check_type="memory",
        threshold={
            'warning': 80.0,
            'critical': 90.0
        },
        check_interval=120
    ))
    
    # 디스크 사용량 체크
    health_checker.register_check(HealthCheck(
        name="disk",
        check_type="disk",
        threshold={
            'warning': 85.0,
            'critical': 95.0
        },
        check_interval=300
    ))


def setup_default_recovery_rules():
    """기본 복구 규칙 설정"""
    
    # 웹 서버 복구 규칙
    auto_recovery_engine.register_recovery_rule(RecoveryRule(
        service_name="web_server",
        condition="consecutive_failures",
        action=RecoveryAction.RESTART_SERVICE,
        parameters={
            'service_command': 'gunicorn',
            'failure_threshold': 3
        },
        max_attempts=3,
        cooldown_period=300
    ))
    
    # 데이터베이스 연결 복구
    auto_recovery_engine.register_recovery_rule(RecoveryRule(
        service_name="database",
        condition="critical",
        action=RecoveryAction.RESET_DATABASE_CONNECTIONS,
        max_attempts=5,
        cooldown_period=120
    ))
    
    # Redis 캐시 복구
    auto_recovery_engine.register_recovery_rule(RecoveryRule(
        service_name="redis",
        condition="critical",
        action=RecoveryAction.CLEAR_CACHE,
        max_attempts=3,
        cooldown_period=180
    ))
    
    # 메모리 부족 시 캐시 정리
    auto_recovery_engine.register_recovery_rule(RecoveryRule(
        service_name="memory",
        condition="critical",
        action=RecoveryAction.CLEAR_CACHE,
        max_attempts=2,
        cooldown_period=300
    ))
    
    # 심각한 상황에서 수동 개입 요청
    auto_recovery_engine.register_recovery_rule(RecoveryRule(
        service_name="web_server",
        condition="critical",
        action=RecoveryAction.MANUAL_INTERVENTION,
        parameters={
            'alert_config': {
                'email': ['admin@studymate.com'],
                'slack_webhook': 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
            }
        },
        max_attempts=1,
        cooldown_period=600
    ))
    
    # 디스크 공간 부족 알림
    auto_recovery_engine.register_recovery_rule(RecoveryRule(
        service_name="disk",
        condition="critical",
        action=RecoveryAction.MANUAL_INTERVENTION,
        parameters={
            'alert_config': {
                'email': ['admin@studymate.com', 'devops@studymate.com']
            }
        },
        max_attempts=1,
        cooldown_period=1800  # 30분
    ))


def setup_kubernetes_recovery_rules():
    """Kubernetes 환경용 복구 규칙"""
    
    # Pod 스케일링
    auto_recovery_engine.register_recovery_rule(RecoveryRule(
        service_name="web_server",
        condition="warning_or_critical",
        action=RecoveryAction.SCALE_UP,
        parameters={
            'namespace': 'studymate',
            'deployment': 'studymate-api',
            'target_replicas': 5
        },
        max_attempts=2,
        cooldown_period=600
    ))


def initialize_auto_recovery():
    """자동 복구 시스템 초기화"""
    setup_default_health_checks()
    setup_default_recovery_rules()
    
    # Kubernetes 환경이면 추가 규칙 설정
    try:
        import kubernetes
        setup_kubernetes_recovery_rules()
    except ImportError:
        pass