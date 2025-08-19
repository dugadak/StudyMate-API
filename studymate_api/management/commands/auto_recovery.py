"""
자동 복구 시스템 관리를 위한 Django 관리 명령어

사용법:
python manage.py auto_recovery --action start
python manage.py auto_recovery --action stop
python manage.py auto_recovery --action status
python manage.py auto_recovery --action test-alert --email admin@example.com
"""

import json
from django.core.management.base import BaseCommand, CommandError
from studymate_api.auto_recovery import (
    health_checker, auto_recovery_engine, get_system_health,
    start_monitoring, stop_monitoring
)
from studymate_api.auto_recovery_config import initialize_auto_recovery


class Command(BaseCommand):
    help = '자동 복구 시스템을 관리합니다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            type=str,
            choices=['start', 'stop', 'status', 'history', 'test-alert', 'init'],
            required=True,
            help='수행할 액션'
        )
        parser.add_argument(
            '--service',
            type=str,
            help='특정 서비스 이름 (status 액션용)'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=20,
            help='이력 조회 제한 (history 액션용)'
        )
        parser.add_argument(
            '--email',
            type=str,
            help='테스트 알림용 이메일 주소'
        )
        parser.add_argument(
            '--slack-webhook',
            type=str,
            help='테스트 알림용 Slack 웹훅 URL'
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['table', 'json'],
            default='table',
            help='출력 형식'
        )

    def handle(self, *args, **options):
        action = options['action']
        
        try:
            if action == 'init':
                self._initialize_system()
            elif action == 'start':
                self._start_monitoring()
            elif action == 'stop':
                self._stop_monitoring()
            elif action == 'status':
                self._show_status(options)
            elif action == 'history':
                self._show_history(options)
            elif action == 'test-alert':
                self._test_alert(options)
                
        except Exception as e:
            raise CommandError(f"작업 실패: {str(e)}")

    def _initialize_system(self):
        """시스템 초기화"""
        initialize_auto_recovery()
        self.stdout.write(
            self.style.SUCCESS("자동 복구 시스템이 초기화되었습니다.")
        )
        
        # 등록된 헬스 체크 및 복구 규칙 출력
        self.stdout.write("\n등록된 헬스 체크:")
        for name, check in health_checker.checks.items():
            self.stdout.write(f"  - {name} ({check.check_type})")
        
        self.stdout.write("\n등록된 복구 규칙:")
        for service_name, rules in auto_recovery_engine.recovery_rules.items():
            self.stdout.write(f"  - {service_name}: {len(rules)}개 규칙")

    def _start_monitoring(self):
        """모니터링 시작"""
        if health_checker.running:
            self.stdout.write(
                self.style.WARNING("모니터링이 이미 실행 중입니다.")
            )
            return
        
        start_monitoring()
        self.stdout.write(
            self.style.SUCCESS("자동 복구 모니터링이 시작되었습니다.")
        )

    def _stop_monitoring(self):
        """모니터링 중지"""
        if not health_checker.running:
            self.stdout.write(
                self.style.WARNING("모니터링이 실행되고 있지 않습니다.")
            )
            return
        
        stop_monitoring()
        self.stdout.write(
            self.style.SUCCESS("자동 복구 모니터링이 중지되었습니다.")
        )

    def _show_status(self, options):
        """상태 조회"""
        service_name = options.get('service')
        format_type = options['format']
        
        if service_name:
            # 특정 서비스 상태
            health = health_checker.get_health_status(service_name)
            if not health:
                raise CommandError(f"서비스 '{service_name}'을 찾을 수 없습니다.")
            
            if format_type == 'json':
                self.stdout.write(json.dumps(health.to_dict(), indent=2, ensure_ascii=False))
            else:
                self._print_service_status(health)
        else:
            # 전체 시스템 상태
            health_data = get_system_health()
            
            if format_type == 'json':
                self.stdout.write(json.dumps(health_data, indent=2, ensure_ascii=False))
            else:
                self._print_system_status(health_data)

    def _print_system_status(self, health_data):
        """시스템 상태를 테이블 형식으로 출력"""
        self.stdout.write(self.style.SUCCESS("\n시스템 헬스 상태"))
        self.stdout.write("=" * 60)
        
        # 전체 상태
        overall_status = health_data['overall_status']
        status_color = self.style.SUCCESS if overall_status == 'healthy' else \
                      self.style.WARNING if overall_status == 'warning' else \
                      self.style.ERROR
        
        self.stdout.write(f"전체 상태: {status_color(overall_status.upper())}")
        self.stdout.write(f"총 서비스: {health_data['total_services']}")
        self.stdout.write(f"정상 서비스: {health_data['healthy_services']}")
        self.stdout.write(f"모니터링 활성: {health_checker.running}")
        self.stdout.write(f"자동 복구 활성: {auto_recovery_engine.running}")
        
        # 서비스별 상태
        self.stdout.write("\n서비스별 상태:")
        self.stdout.write("-" * 80)
        self.stdout.write(f"{'서비스':<15} {'상태':<10} {'응답시간':<12} {'연속실패':<8} {'마지막체크':<20}")
        self.stdout.write("-" * 80)
        
        for service_name, service_data in health_data['services'].items():
            status_text = service_data['status']
            status_color = self.style.SUCCESS if status_text == 'healthy' else \
                          self.style.WARNING if status_text == 'warning' else \
                          self.style.ERROR
            
            response_time = f"{service_data['response_time']:.1f}ms"
            failures = str(service_data['consecutive_failures'])
            last_check = service_data['last_check'][:19] if service_data['last_check'] else 'N/A'
            
            self.stdout.write(
                f"{service_name:<15} {status_color(status_text):<10} "
                f"{response_time:<12} {failures:<8} {last_check:<20}"
            )

    def _print_service_status(self, health):
        """개별 서비스 상태 출력"""
        self.stdout.write(self.style.SUCCESS(f"\n서비스 상태: {health.service_name}"))
        self.stdout.write("-" * 40)
        
        status_color = self.style.SUCCESS if health.status.value == 'healthy' else \
                      self.style.WARNING if health.status.value == 'warning' else \
                      self.style.ERROR
        
        self.stdout.write(f"상태: {status_color(health.status.value.upper())}")
        self.stdout.write(f"응답시간: {health.response_time:.2f}ms")
        self.stdout.write(f"연속 실패: {health.consecutive_failures}회")
        self.stdout.write(f"마지막 체크: {health.last_check}")
        
        if health.error_message:
            self.stdout.write(f"오류 메시지: {self.style.ERROR(health.error_message)}")
        
        if health.metrics:
            self.stdout.write("\n메트릭:")
            for key, value in health.metrics.items():
                self.stdout.write(f"  {key}: {value}")

    def _show_history(self, options):
        """복구 이력 조회"""
        limit = options['limit']
        format_type = options['format']
        
        history = auto_recovery_engine.get_recovery_history(limit)
        
        if not history:
            self.stdout.write("복구 이력이 없습니다.")
            return
        
        if format_type == 'json':
            # JSON 시리얼라이제이션을 위해 datetime 객체를 문자열로 변환
            serializable_history = []
            for record in history:
                serializable_record = record.copy()
                serializable_record['timestamp'] = record['timestamp'].isoformat()
                serializable_history.append(serializable_record)
            
            self.stdout.write(json.dumps(serializable_history, indent=2, ensure_ascii=False))
        else:
            self._print_recovery_history(history)

    def _print_recovery_history(self, history):
        """복구 이력을 테이블 형식으로 출력"""
        self.stdout.write(self.style.SUCCESS(f"\n복구 이력 (최근 {len(history)}개)"))
        self.stdout.write("=" * 100)
        self.stdout.write(f"{'시간':<20} {'서비스':<15} {'액션':<20} {'성공':<6} {'상태':<10}")
        self.stdout.write("-" * 100)
        
        for record in reversed(history):  # 최신 순으로 정렬
            timestamp = record['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
            service = record['service_name']
            action = record['action']
            success = '성공' if record['success'] else '실패'
            success_color = self.style.SUCCESS if record['success'] else self.style.ERROR
            
            health_status = record['health_status']['status']
            
            self.stdout.write(
                f"{timestamp:<20} {service:<15} {action:<20} "
                f"{success_color(success):<6} {health_status:<10}"
            )

    def _test_alert(self, options):
        """알림 테스트"""
        email = options.get('email')
        slack_webhook = options.get('slack_webhook')
        
        if not email and not slack_webhook:
            raise CommandError("테스트할 알림 방법을 지정해주세요. (--email 또는 --slack-webhook)")
        
        # 테스트용 더미 데이터
        from studymate_api.auto_recovery import ServiceHealth, HealthStatus
        from django.utils import timezone
        
        test_health = ServiceHealth(
            service_name="test_service",
            status=HealthStatus.CRITICAL,
            response_time=5000.0,
            error_message="자동 복구 시스템 알림 테스트",
            last_check=timezone.now(),
            consecutive_failures=5
        )
        
        try:
            if email:
                alert_config = {'email': [email]}
                auto_recovery_engine._send_email_alert(test_health, alert_config)
                self.stdout.write(
                    self.style.SUCCESS(f"테스트 이메일이 {email}로 발송되었습니다.")
                )
            
            if slack_webhook:
                alert_config = {'slack_webhook': slack_webhook}
                auto_recovery_engine._send_slack_alert(test_health, alert_config)
                self.stdout.write(
                    self.style.SUCCESS("테스트 Slack 메시지가 발송되었습니다.")
                )
                
        except Exception as e:
            raise CommandError(f"알림 테스트 실패: {str(e)}")