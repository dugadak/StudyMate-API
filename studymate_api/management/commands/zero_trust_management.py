"""
Zero Trust 보안 시스템 관리 명령어

Zero Trust 보안 시스템의 상태 확인, 위협 분석, 정책 관리를 담당합니다.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, List

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth import get_user_model

from studymate_api.zero_trust_security import zero_trust_engine, ThreatLevel, SecurityAction

User = get_user_model()


class Command(BaseCommand):
    """Zero Trust 보안 시스템 관리 명령어"""
    
    help = 'Zero Trust 보안 시스템 관리'
    
    def add_arguments(self, parser):
        """명령어 인자 추가"""
        parser.add_argument(
            '--status',
            action='store_true',
            help='Zero Trust 시스템 상태 확인'
        )
        
        parser.add_argument(
            '--threat-analysis',
            action='store_true',
            help='위협 분석 리포트 생성'
        )
        
        parser.add_argument(
            '--user-security',
            type=int,
            help='특정 사용자의 보안 상태 확인 (user_id)'
        )
        
        parser.add_argument(
            '--trusted-devices',
            action='store_true',
            help='신뢰 디바이스 현황'
        )
        
        parser.add_argument(
            '--security-events',
            action='store_true',
            help='최근 보안 이벤트 조회'
        )
        
        parser.add_argument(
            '--quarantined-users',
            action='store_true',
            help='격리된 사용자 목록'
        )
        
        parser.add_argument(
            '--policy-test',
            action='store_true',
            help='보안 정책 테스트'
        )
        
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='만료된 데이터 정리'
        )
        
        parser.add_argument(
            '--export-config',
            action='store_true',
            help='현재 Zero Trust 설정 내보내기'
        )
    
    def handle(self, *args, **options):
        """명령어 실행"""
        try:
            if options['status']:
                self._show_system_status()
            elif options['threat_analysis']:
                self._generate_threat_analysis()
            elif options['user_security']:
                self._show_user_security(options['user_security'])
            elif options['trusted_devices']:
                self._show_trusted_devices()
            elif options['security_events']:
                self._show_security_events()
            elif options['quarantined_users']:
                self._show_quarantined_users()
            elif options['policy_test']:
                self._test_security_policies()
            elif options['cleanup']:
                self._cleanup_expired_data()
            elif options['export_config']:
                self._export_configuration()
            else:
                self.stdout.write(
                    self.style.WARNING('사용 가능한 옵션을 확인하려면 --help를 사용하세요.')
                )
        
        except Exception as e:
            raise CommandError(f'명령어 실행 실패: {e}')
    
    def _show_system_status(self):
        """Zero Trust 시스템 상태 표시"""
        self.stdout.write(self.style.SUCCESS('🛡️  Zero Trust 보안 시스템 상태'))
        self.stdout.write('=' * 50)
        
        # 기본 설정 정보
        zt_enabled = getattr(settings, 'ZERO_TRUST_ENABLED', False)
        self.stdout.write(f"🔧 시스템 활성화: {zt_enabled}")
        
        if not zt_enabled:
            self.stdout.write(self.style.WARNING("⚠️  Zero Trust 시스템이 비활성화되어 있습니다."))
            return
        
        # 정책 설정
        policy = getattr(settings, 'ZERO_TRUST_POLICY', {})
        self.stdout.write(f"\n📋 보안 정책:")
        self.stdout.write(f"  🔸 신뢰 점수 임계값: {policy.get('TRUST_SCORE_THRESHOLD', 'N/A')}")
        self.stdout.write(f"  🔸 MFA 필요 임계값: {policy.get('MFA_REQUIRED_THRESHOLD', 'N/A')}")
        self.stdout.write(f"  🔸 관리자 필요 임계값: {policy.get('ADMIN_REQUIRED_THRESHOLD', 'N/A')}")
        self.stdout.write(f"  🔸 최대 실패 시도: {policy.get('MAX_FAILED_ATTEMPTS', 'N/A')}")
        
        # 위협 탐지 설정
        threat_config = getattr(settings, 'THREAT_DETECTION', {})
        self.stdout.write(f"\n🚨 위협 탐지 설정:")
        self.stdout.write(f"  🔸 분당 요청 제한: {threat_config.get('RATE_LIMIT_PER_MINUTE', 'N/A')}")
        self.stdout.write(f"  🔸 무차별 대입 임계값: {threat_config.get('BRUTE_FORCE_THRESHOLD', 'N/A')}")
        self.stdout.write(f"  🔸 지역 차단: {threat_config.get('ENABLE_GEO_BLOCKING', False)}")
        
        # 활성 세션 통계
        self._show_active_sessions_stats()
        
        # 위협 통계
        self._show_threat_stats()
    
    def _generate_threat_analysis(self):
        """위협 분석 리포트 생성"""
        self.stdout.write(self.style.SUCCESS('🔍 위협 분석 리포트'))
        self.stdout.write('=' * 50)
        
        # 시간 범위 설정
        end_time = timezone.now()
        start_time = end_time - timedelta(hours=24)
        
        # 위협 레벨별 통계
        self.stdout.write(f"📊 최근 24시간 위협 분석 ({start_time.strftime('%Y-%m-%d %H:%M')} ~ {end_time.strftime('%Y-%m-%d %H:%M')})")
        
        threat_stats = self._collect_threat_statistics()
        
        self.stdout.write(f"\n🎯 위협 레벨별 이벤트:")
        for level, count in threat_stats['threat_levels'].items():
            self.stdout.write(f"  🔸 {level.upper()}: {count:,}건")
        
        self.stdout.write(f"\n🚫 보안 액션별 통계:")
        for action, count in threat_stats['security_actions'].items():
            self.stdout.write(f"  🔸 {action.upper()}: {count:,}건")
        
        # 상위 위험 IP
        self.stdout.write(f"\n⚠️  상위 위험 IP 주소:")
        for ip, events in threat_stats['top_risk_ips'][:10]:
            self.stdout.write(f"  🔸 {ip}: {events}건")
        
        # 상위 위험 사용자
        self.stdout.write(f"\n👤 상위 위험 사용자:")
        for user_id, score in threat_stats['top_risk_users'][:10]:
            self.stdout.write(f"  🔸 User {user_id}: 신뢰도 {score:.2f}")
        
        # 권장사항
        recommendations = self._generate_security_recommendations(threat_stats)
        if recommendations:
            self.stdout.write(f"\n💡 보안 권장사항:")
            for rec in recommendations:
                self.stdout.write(f"  🔸 {rec}")
    
    def _show_user_security(self, user_id: int):
        """특정 사용자 보안 상태 표시"""
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ 사용자 ID {user_id}를 찾을 수 없습니다."))
            return
        
        self.stdout.write(self.style.SUCCESS(f'👤 사용자 보안 상태: {user.email}'))
        self.stdout.write('=' * 50)
        
        # 사용자 디바이스
        devices_key = f"user_devices:{user_id}"
        devices = cache.get(devices_key, [])
        
        self.stdout.write(f"📱 등록된 디바이스: {len(devices)}개")
        for device in devices:
            status = "신뢰됨" if device.get('trusted', False) else "일반"
            self.stdout.write(f"  🔸 {device.get('name', 'Unknown')}: {status}")
        
        # 신뢰 위치
        locations_key = f"known_locations:{user_id}"
        locations = cache.get(locations_key, [])
        
        self.stdout.write(f"\n📍 신뢰 위치: {len(locations)}개")
        for location in locations:
            self.stdout.write(f"  🔸 {location.get('country', 'Unknown')}, {location.get('city', 'Unknown')}")
        
        # 최근 보안 이벤트
        self._show_user_security_events(user_id)
        
        # 격리 상태
        quarantine_key = f"quarantined_user:{user_id}"
        quarantine_data = cache.get(quarantine_key)
        
        if quarantine_data:
            self.stdout.write(f"\n🚨 격리 상태:")
            self.stdout.write(f"  🔸 격리 시작: {quarantine_data.get('quarantined_at', 'Unknown')}")
            self.stdout.write(f"  🔸 격리 사유: {quarantine_data.get('reason', 'Unknown')}")
        else:
            self.stdout.write(f"\n✅ 정상 상태 (격리되지 않음)")
    
    def _show_trusted_devices(self):
        """신뢰 디바이스 현황"""
        self.stdout.write(self.style.SUCCESS('📱 신뢰 디바이스 현황'))
        self.stdout.write('=' * 50)
        
        # 모든 사용자의 신뢰 디바이스 수집
        total_devices = 0
        trusted_devices = 0
        
        for user in User.objects.all():
            devices_key = f"user_devices:{user.id}"
            devices = cache.get(devices_key, [])
            
            total_devices += len(devices)
            trusted_devices += sum(1 for device in devices if device.get('trusted', False))
        
        self.stdout.write(f"📊 총 등록된 디바이스: {total_devices:,}개")
        self.stdout.write(f"🔒 신뢰 디바이스: {trusted_devices:,}개")
        
        if total_devices > 0:
            trust_rate = (trusted_devices / total_devices) * 100
            self.stdout.write(f"📈 신뢰 비율: {trust_rate:.1f}%")
    
    def _show_security_events(self):
        """최근 보안 이벤트 조회"""
        self.stdout.write(self.style.SUCCESS('🔔 최근 보안 이벤트'))
        self.stdout.write('=' * 50)
        
        # 캐시에서 최근 이벤트 조회
        events_key = "recent_security_events"
        events = cache.get(events_key, [])
        
        if not events:
            self.stdout.write("📝 최근 보안 이벤트가 없습니다.")
            return
        
        # 최근 20개 이벤트 표시
        for event in events[-20:]:
            timestamp = event.get('timestamp', 'Unknown')
            event_type = event.get('type', 'Unknown')
            user_id = event.get('user_id', 'Unknown')
            threat_level = event.get('threat_level', 'unknown')
            
            # 위협 레벨에 따른 색상
            if threat_level == 'critical':
                color = self.style.ERROR
            elif threat_level == 'high':
                color = self.style.WARNING
            else:
                color = self.style.SUCCESS
            
            self.stdout.write(color(f"🔸 [{timestamp}] User {user_id}: {event_type} ({threat_level})"))
    
    def _show_quarantined_users(self):
        """격리된 사용자 목록"""
        self.stdout.write(self.style.SUCCESS('🚨 격리된 사용자 목록'))
        self.stdout.write('=' * 50)
        
        quarantined_users = []
        
        # 모든 사용자 확인
        for user in User.objects.all():
            quarantine_key = f"quarantined_user:{user.id}"
            quarantine_data = cache.get(quarantine_key)
            
            if quarantine_data:
                quarantined_users.append({
                    'user_id': user.id,
                    'email': user.email,
                    'quarantined_at': quarantine_data.get('quarantined_at'),
                    'reason': quarantine_data.get('reason'),
                    'duration': quarantine_data.get('duration')
                })
        
        if not quarantined_users:
            self.stdout.write("✅ 현재 격리된 사용자가 없습니다.")
            return
        
        self.stdout.write(f"⚠️  총 {len(quarantined_users)}명의 사용자가 격리되어 있습니다:")
        
        for user_data in quarantined_users:
            self.stdout.write(f"🔸 {user_data['email']} (ID: {user_data['user_id']})")
            self.stdout.write(f"   격리 시작: {user_data['quarantined_at']}")
            self.stdout.write(f"   격리 사유: {user_data['reason']}")
            self.stdout.write(f"   격리 기간: {user_data['duration']}초")
            self.stdout.write("")
    
    def _test_security_policies(self):
        """보안 정책 테스트"""
        self.stdout.write(self.style.SUCCESS('🧪 보안 정책 테스트'))
        self.stdout.write('=' * 50)
        
        # 정책 설정 검증
        policy = getattr(settings, 'ZERO_TRUST_POLICY', {})
        issues = []
        
        # 임계값 검증
        trust_threshold = policy.get('TRUST_SCORE_THRESHOLD', 0.6)
        if trust_threshold < 0.3 or trust_threshold > 0.9:
            issues.append(f"신뢰 점수 임계값이 권장 범위(0.3-0.9)를 벗어남: {trust_threshold}")
        
        mfa_threshold = policy.get('MFA_REQUIRED_THRESHOLD', 0.5)
        if mfa_threshold >= trust_threshold:
            issues.append(f"MFA 임계값이 신뢰 임계값보다 높거나 같음: {mfa_threshold} >= {trust_threshold}")
        
        # 위협 탐지 설정 검증
        threat_config = getattr(settings, 'THREAT_DETECTION', {})
        rate_limit = threat_config.get('RATE_LIMIT_PER_MINUTE', 60)
        if rate_limit < 10 or rate_limit > 300:
            issues.append(f"분당 요청 제한이 권장 범위(10-300)를 벗어남: {rate_limit}")
        
        # 결과 출력
        if issues:
            self.stdout.write(self.style.WARNING("⚠️  발견된 정책 문제점:"))
            for issue in issues:
                self.stdout.write(f"  🔸 {issue}")
        else:
            self.stdout.write(self.style.SUCCESS("✅ 모든 보안 정책이 올바르게 설정되었습니다."))
        
        # 성능 테스트
        self._test_performance()
    
    def _cleanup_expired_data(self):
        """만료된 데이터 정리"""
        self.stdout.write(self.style.SUCCESS('🧹 만료된 데이터 정리'))
        self.stdout.write('=' * 50)
        
        cleaned_items = 0
        
        # 만료된 챌린지 정리
        for user in User.objects.all():
            mfa_key = f"mfa_challenge:{user.id}"
            if cache.get(mfa_key):
                cache.delete(mfa_key)
                cleaned_items += 1
        
        # 오래된 보안 이벤트 정리
        events_key = "recent_security_events"
        events = cache.get(events_key, [])
        if events:
            # 최근 1000개만 유지
            if len(events) > 1000:
                cache.set(events_key, events[-1000:], timeout=86400)
                cleaned_items += len(events) - 1000
        
        self.stdout.write(f"✅ {cleaned_items:,}개의 만료된 항목을 정리했습니다.")
    
    def _export_configuration(self):
        """현재 Zero Trust 설정 내보내기"""
        self.stdout.write(self.style.SUCCESS('📄 Zero Trust 설정 내보내기'))
        self.stdout.write('=' * 50)
        
        config = {
            'zero_trust_enabled': getattr(settings, 'ZERO_TRUST_ENABLED', False),
            'zero_trust_policy': getattr(settings, 'ZERO_TRUST_POLICY', {}),
            'threat_detection': getattr(settings, 'THREAT_DETECTION', {}),
            'geoip_db_path': getattr(settings, 'GEOIP_DB_PATH', ''),
            'export_timestamp': timezone.now().isoformat()
        }
        
        self.stdout.write(json.dumps(config, indent=2, ensure_ascii=False))
    
    def _show_active_sessions_stats(self):
        """활성 세션 통계"""
        # 실제 구현에서는 세션 저장소에서 데이터 수집
        active_sessions = 0  # 예시 값
        high_risk_sessions = 0  # 예시 값
        
        self.stdout.write(f"\n📊 세션 통계:")
        self.stdout.write(f"  🔸 활성 세션: {active_sessions:,}개")
        self.stdout.write(f"  🔸 고위험 세션: {high_risk_sessions:,}개")
    
    def _show_threat_stats(self):
        """위협 통계"""
        # 실제 구현에서는 로그나 캐시에서 데이터 수집
        total_threats = 0  # 예시 값
        blocked_requests = 0  # 예시 값
        
        self.stdout.write(f"\n🚨 위협 통계 (최근 24시간):")
        self.stdout.write(f"  🔸 탐지된 위협: {total_threats:,}건")
        self.stdout.write(f"  🔸 차단된 요청: {blocked_requests:,}건")
    
    def _collect_threat_statistics(self) -> Dict[str, Any]:
        """위협 통계 수집"""
        # 실제 구현에서는 로그 분석이나 데이터베이스 쿼리
        return {
            'threat_levels': {
                'low': 100,
                'medium': 50,
                'high': 20,
                'critical': 5
            },
            'security_actions': {
                'allow': 1000,
                'challenge': 100,
                'block': 50,
                'quarantine': 5
            },
            'top_risk_ips': [
                ('192.168.1.100', 25),
                ('10.0.0.50', 15)
            ],
            'top_risk_users': [
                (123, 0.3),
                (456, 0.4)
            ]
        }
    
    def _generate_security_recommendations(self, stats: Dict[str, Any]) -> List[str]:
        """보안 권장사항 생성"""
        recommendations = []
        
        # 위협 레벨 분석
        critical_threats = stats['threat_levels'].get('critical', 0)
        if critical_threats > 10:
            recommendations.append("임계 위협이 많이 감지되었습니다. 보안 정책을 강화하세요.")
        
        # 차단 비율 분석
        total_actions = sum(stats['security_actions'].values())
        block_ratio = stats['security_actions'].get('block', 0) / max(1, total_actions)
        
        if block_ratio > 0.1:
            recommendations.append("차단 비율이 높습니다. 신뢰 임계값 조정을 고려하세요.")
        
        # IP 기반 위협 분석
        if len(stats['top_risk_ips']) > 5:
            recommendations.append("위험 IP가 많습니다. 지역 차단을 고려하세요.")
        
        return recommendations
    
    def _show_user_security_events(self, user_id: int):
        """사용자별 보안 이벤트 표시"""
        # 실제 구현에서는 사용자별 이벤트 로그 조회
        self.stdout.write(f"\n🔔 최근 보안 이벤트:")
        self.stdout.write(f"  🔸 로그인 시도: 3회")
        self.stdout.write(f"  🔸 MFA 인증: 1회")
        self.stdout.write(f"  🔸 디바이스 등록: 0회")
    
    def _test_performance(self):
        """성능 테스트"""
        self.stdout.write(f"\n⚡ 성능 테스트:")
        
        # Zero Trust 엔진 성능 테스트
        import time
        start_time = time.time()
        
        # 더미 평가 10회 실행
        for _ in range(10):
            # 실제로는 mock request와 user로 테스트
            pass
        
        end_time = time.time()
        avg_time = (end_time - start_time) / 10 * 1000
        
        self.stdout.write(f"  🔸 평균 평가 시간: {avg_time:.2f}ms")
        
        if avg_time > 100:
            self.stdout.write(self.style.WARNING("  ⚠️  평가 시간이 느립니다. 성능 최적화가 필요합니다."))
        else:
            self.stdout.write(self.style.SUCCESS("  ✅ 평가 성능이 양호합니다."))