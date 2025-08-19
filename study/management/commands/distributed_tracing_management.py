"""
분산 추적 시스템 관리 명령어

OpenTelemetry 분산 추적 시스템의 상태 확인, 메트릭 조회, 설정 관리를 담당합니다.
"""

import json
import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache

from studymate_api.distributed_tracing import studymate_tracer, get_current_trace_id


class Command(BaseCommand):
    """분산 추적 시스템 관리 명령어"""
    
    help = 'OpenTelemetry 분산 추적 시스템 관리'
    
    def add_arguments(self, parser):
        """명령어 인자 추가"""
        parser.add_argument(
            '--status',
            action='store_true',
            help='분산 추적 시스템 상태 확인'
        )
        
        parser.add_argument(
            '--metrics',
            action='store_true',
            help='추적 메트릭 조회'
        )
        
        parser.add_argument(
            '--test-trace',
            action='store_true',
            help='테스트 트레이스 생성'
        )
        
        parser.add_argument(
            '--reset-metrics',
            action='store_true',
            help='메트릭 초기화'
        )
        
        parser.add_argument(
            '--export-config',
            action='store_true',
            help='현재 설정 내보내기'
        )
        
        parser.add_argument(
            '--validate-setup',
            action='store_true',
            help='분산 추적 설정 검증'
        )
        
        parser.add_argument(
            '--span-analysis',
            type=str,
            help='특정 스팬 패턴 분석 (예: study.*)'
        )
        
        parser.add_argument(
            '--performance-report',
            action='store_true',
            help='성능 분석 리포트 생성'
        )
    
    def handle(self, *args, **options):
        """명령어 실행"""
        try:
            if options['status']:
                self._show_status()
            elif options['metrics']:
                self._show_metrics()
            elif options['test_trace']:
                self._create_test_trace()
            elif options['reset_metrics']:
                self._reset_metrics()
            elif options['export_config']:
                self._export_config()
            elif options['validate_setup']:
                self._validate_setup()
            elif options['span_analysis']:
                self._analyze_spans(options['span_analysis'])
            elif options['performance_report']:
                self._generate_performance_report()
            else:
                self.stdout.write(
                    self.style.WARNING('사용 가능한 옵션을 확인하려면 --help를 사용하세요.')
                )
        
        except Exception as e:
            raise CommandError(f'명령어 실행 실패: {e}')
    
    def _show_status(self):
        """분산 추적 시스템 상태 표시"""
        self.stdout.write(self.style.SUCCESS('📊 분산 추적 시스템 상태'))
        self.stdout.write('=' * 50)
        
        # 기본 설정 정보
        tracing_config = getattr(settings, 'DISTRIBUTED_TRACING', {})
        
        self.stdout.write(f"🔧 활성화 상태: {tracing_config.get('ENABLED', False)}")
        self.stdout.write(f"🏷️  서비스명: {tracing_config.get('SERVICE_NAME', 'N/A')}")
        self.stdout.write(f"📋 버전: {tracing_config.get('SERVICE_VERSION', 'N/A')}")
        self.stdout.write(f"🔍 샘플링 비율: {tracing_config.get('TRACE_SAMPLE_RATE', 'N/A')}")
        
        # Tracer 상태
        self.stdout.write(f"\n🏃 Tracer 초기화: {studymate_tracer.is_initialized}")
        
        if studymate_tracer.is_initialized:
            self.stdout.write(f"📈 현재 트레이스 ID: {get_current_trace_id() or 'N/A'}")
        
        # Exporter 설정
        self.stdout.write(f"\n📤 Exporter 설정:")
        if tracing_config.get('JAEGER_ENDPOINT'):
            self.stdout.write(f"  🔸 Jaeger: {tracing_config['JAEGER_ENDPOINT']}")
        if tracing_config.get('OTLP_ENDPOINT'):
            self.stdout.write(f"  🔸 OTLP: {tracing_config['OTLP_ENDPOINT']}")
        if tracing_config.get('CONSOLE_EXPORTER'):
            self.stdout.write(f"  🔸 Console: 활성화됨")
        
        # 자동 계측 상태
        self.stdout.write(f"\n🤖 자동 계측: {tracing_config.get('AUTO_INSTRUMENT', False)}")
    
    def _show_metrics(self):
        """추적 메트릭 표시"""
        self.stdout.write(self.style.SUCCESS('📈 분산 추적 메트릭'))
        self.stdout.write('=' * 50)
        
        if not studymate_tracer.is_initialized:
            self.stdout.write(self.style.WARNING('⚠️  분산 추적 시스템이 초기화되지 않았습니다.'))
            return
        
        metrics = studymate_tracer.get_trace_metrics()
        
        self.stdout.write(f"📊 총 스팬 수: {metrics['total_spans']:,}")
        self.stdout.write(f"❌ 오류 스팬: {metrics['error_spans']:,}")
        self.stdout.write(f"🐌 느린 스팬: {metrics['slow_spans']:,}")
        self.stdout.write(f"📉 오류율: {metrics['error_rate']:.2f}%")
        self.stdout.write(f"📉 느림율: {metrics['slow_rate']:.2f}%")
        self.stdout.write(f"⚡ 초당 스팬: {metrics['spans_per_second']:.2f}")
        self.stdout.write(f"🕐 마지막 초기화: {metrics['last_reset']}")
        
        # 캐시된 스팬 메트릭
        span_metrics = cache.get('span_metrics_summary', {})
        if span_metrics:
            self.stdout.write(f"\n📋 스팬별 메트릭:")
            for span_name, data in span_metrics.items():
                self.stdout.write(f"  🔸 {span_name}: {data.get('count', 0)}회, "
                                f"평균 {data.get('avg_duration', 0):.2f}ms")
    
    def _create_test_trace(self):
        """테스트 트레이스 생성"""
        self.stdout.write(self.style.SUCCESS('🧪 테스트 트레이스 생성 중...'))
        
        if not studymate_tracer.is_initialized:
            studymate_tracer.initialize()
        
        # 테스트 트레이스 생성
        with studymate_tracer.create_span("test.command_execution") as span:
            span.set_attribute("test.type", "management_command")
            span.set_attribute("test.timestamp", timezone.now().isoformat())
            
            # 중첩 스팬 생성
            with studymate_tracer.create_span("test.database_operation") as db_span:
                db_span.set_attribute("db.operation", "test_query")
                time.sleep(0.1)  # 시뮬레이션
            
            with studymate_tracer.create_span("test.ai_operation") as ai_span:
                ai_span.set_attribute("ai.provider", "test")
                ai_span.set_attribute("ai.model", "test-model")
                time.sleep(0.2)  # 시뮬레이션
            
            time.sleep(0.05)  # 메인 스팬 시뮬레이션
        
        trace_id = get_current_trace_id()
        self.stdout.write(f"✅ 테스트 트레이스 생성 완료!")
        if trace_id:
            self.stdout.write(f"🆔 트레이스 ID: {trace_id}")
    
    def _reset_metrics(self):
        """메트릭 초기화"""
        self.stdout.write(self.style.WARNING('🔄 메트릭 초기화 중...'))
        
        if studymate_tracer.is_initialized:
            studymate_tracer.reset_metrics()
        
        # 캐시된 메트릭도 초기화
        cache.delete_pattern('span_metrics:*')
        cache.delete('span_metrics_summary')
        
        self.stdout.write(self.style.SUCCESS('✅ 메트릭 초기화 완료'))
    
    def _export_config(self):
        """현재 설정 내보내기"""
        self.stdout.write(self.style.SUCCESS('📄 분산 추적 설정 내보내기'))
        self.stdout.write('=' * 50)
        
        config = {
            'distributed_tracing': getattr(settings, 'DISTRIBUTED_TRACING', {}),
            'otel_settings': {
                'enabled': getattr(settings, 'OTEL_ENABLED', False),
                'service_name': getattr(settings, 'OTEL_SERVICE_NAME', ''),
                'service_version': getattr(settings, 'OTEL_SERVICE_VERSION', ''),
                'jaeger_endpoint': getattr(settings, 'JAEGER_ENDPOINT', ''),
                'otlp_endpoint': getattr(settings, 'OTEL_EXPORTER_OTLP_ENDPOINT', ''),
            },
            'export_timestamp': timezone.now().isoformat()
        }
        
        self.stdout.write(json.dumps(config, indent=2, ensure_ascii=False))
    
    def _validate_setup(self):
        """분산 추적 설정 검증"""
        self.stdout.write(self.style.SUCCESS('🔍 분산 추적 설정 검증'))
        self.stdout.write('=' * 50)
        
        issues = []
        
        # 기본 설정 확인
        tracing_config = getattr(settings, 'DISTRIBUTED_TRACING', {})
        if not tracing_config.get('ENABLED'):
            issues.append("⚠️  분산 추적이 비활성화되어 있습니다.")
        
        # 서비스명 확인
        if not tracing_config.get('SERVICE_NAME'):
            issues.append("❌ 서비스명이 설정되지 않았습니다.")
        
        # Exporter 설정 확인
        has_exporter = False
        if tracing_config.get('JAEGER_ENDPOINT'):
            has_exporter = True
            self.stdout.write("✅ Jaeger Exporter 설정됨")
        
        if tracing_config.get('OTLP_ENDPOINT'):
            has_exporter = True
            self.stdout.write("✅ OTLP Exporter 설정됨")
        
        if tracing_config.get('CONSOLE_EXPORTER'):
            has_exporter = True
            self.stdout.write("✅ Console Exporter 설정됨")
        
        if not has_exporter:
            issues.append("❌ Exporter가 설정되지 않았습니다.")
        
        # 샘플링 비율 확인
        sample_rate = tracing_config.get('TRACE_SAMPLE_RATE', 0)
        if sample_rate <= 0 or sample_rate > 1:
            issues.append(f"⚠️  샘플링 비율이 잘못되었습니다: {sample_rate}")
        
        # 결과 출력
        if issues:
            self.stdout.write(f"\n❌ 발견된 문제점:")
            for issue in issues:
                self.stdout.write(f"  {issue}")
        else:
            self.stdout.write(f"\n✅ 모든 설정이 올바릅니다!")
    
    def _analyze_spans(self, pattern: str):
        """스팬 패턴 분석"""
        self.stdout.write(self.style.SUCCESS(f'🔍 스팬 패턴 분석: {pattern}'))
        self.stdout.write('=' * 50)
        
        # 캐시에서 스팬 메트릭 조회
        all_span_metrics = {}
        
        # 패턴 매칭으로 스팬 찾기
        cache_keys = cache.keys(f'span_metrics:{pattern}')
        
        for key in cache_keys:
            span_name = key.replace('span_metrics:', '')
            metrics = cache.get(key, {})
            if metrics:
                all_span_metrics[span_name] = metrics
        
        if not all_span_metrics:
            self.stdout.write(f"⚠️  패턴 '{pattern}'에 해당하는 스팬을 찾을 수 없습니다.")
            return
        
        # 분석 결과 출력
        total_calls = sum(m.get('count', 0) for m in all_span_metrics.values())
        total_duration = sum(m.get('total_duration', 0) for m in all_span_metrics.values())
        
        self.stdout.write(f"📊 총 호출 수: {total_calls:,}")
        self.stdout.write(f"🕐 총 실행 시간: {total_duration:,.2f}ms")
        self.stdout.write(f"⚡ 평균 실행 시간: {total_duration/max(1, total_calls):.2f}ms")
        
        # 개별 스팬 상세 정보
        self.stdout.write(f"\n📋 개별 스팬 정보:")
        for span_name, metrics in sorted(all_span_metrics.items()):
            count = metrics.get('count', 0)
            avg_duration = metrics.get('avg_duration', 0)
            self.stdout.write(f"  🔸 {span_name}: {count:,}회, 평균 {avg_duration:.2f}ms")
    
    def _generate_performance_report(self):
        """성능 분석 리포트 생성"""
        self.stdout.write(self.style.SUCCESS('📊 성능 분석 리포트 생성'))
        self.stdout.write('=' * 50)
        
        if not studymate_tracer.is_initialized:
            self.stdout.write(self.style.WARNING('⚠️  분산 추적 시스템이 초기화되지 않았습니다.'))
            return
        
        # 전체 메트릭
        metrics = studymate_tracer.get_trace_metrics()
        
        # 성능 요약
        self.stdout.write(f"📈 성능 요약 (마지막 초기화부터):")
        self.stdout.write(f"  🔸 총 요청: {metrics['total_spans']:,}")
        self.stdout.write(f"  🔸 평균 처리율: {metrics['spans_per_second']:.2f} spans/sec")
        self.stdout.write(f"  🔸 오류율: {metrics['error_rate']:.2f}%")
        self.stdout.write(f"  🔸 느린 요청 비율: {metrics['slow_rate']:.2f}%")
        
        # 성능 등급 평가
        performance_grade = self._calculate_performance_grade(metrics)
        self.stdout.write(f"\n🏆 성능 등급: {performance_grade}")
        
        # 개선 권장사항
        recommendations = self._generate_recommendations(metrics)
        if recommendations:
            self.stdout.write(f"\n💡 개선 권장사항:")
            for rec in recommendations:
                self.stdout.write(f"  🔸 {rec}")
    
    def _calculate_performance_grade(self, metrics: Dict[str, Any]) -> str:
        """성능 등급 계산"""
        error_rate = metrics['error_rate']
        slow_rate = metrics['slow_rate']
        
        if error_rate < 1 and slow_rate < 5:
            return "🟢 우수 (A)"
        elif error_rate < 3 and slow_rate < 10:
            return "🟡 양호 (B)"
        elif error_rate < 5 and slow_rate < 20:
            return "🟠 보통 (C)"
        else:
            return "🔴 개선 필요 (D)"
    
    def _generate_recommendations(self, metrics: Dict[str, Any]) -> List[str]:
        """개선 권장사항 생성"""
        recommendations = []
        
        if metrics['error_rate'] > 3:
            recommendations.append("오류율이 높습니다. 에러 로그를 확인하고 안정성을 개선하세요.")
        
        if metrics['slow_rate'] > 10:
            recommendations.append("느린 요청이 많습니다. 병목 지점을 식별하고 성능을 최적화하세요.")
        
        if metrics['spans_per_second'] > 100:
            recommendations.append("높은 트래픽이 감지됩니다. 샘플링 비율 조정을 고려하세요.")
        
        if metrics['total_spans'] < 100:
            recommendations.append("충분한 데이터가 수집되지 않았습니다. 더 많은 데이터 수집 후 재분석하세요.")
        
        return recommendations