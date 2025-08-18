"""
메트릭 관리 Django 명령어

사용법:
    python manage.py metrics_management --dashboard
    python manage.py metrics_management --export json
    python manage.py metrics_management --export csv
    python manage.py metrics_management --clear-old 30
    python manage.py metrics_management --realtime
"""

import json
import csv
import io
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from studymate_api.metrics import MetricsManager, metrics_collector


class Command(BaseCommand):
    help = '메트릭 수집 및 분석 시스템 관리'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dashboard',
            action='store_true',
            help='대시보드 메트릭 조회',
        )
        
        parser.add_argument(
            '--export',
            type=str,
            choices=['json', 'csv'],
            help='메트릭 데이터 내보내기 형식',
        )
        
        parser.add_argument(
            '--clear-old',
            type=int,
            metavar='DAYS',
            help='오래된 메트릭 데이터 정리 (일 수)',
        )
        
        parser.add_argument(
            '--realtime',
            action='store_true',
            help='실시간 메트릭 모니터링',
        )
        
        parser.add_argument(
            '--test-data',
            action='store_true',
            help='테스트 메트릭 데이터 생성',
        )

    def handle(self, *args, **options):
        manager = MetricsManager()

        if options['dashboard']:
            self.show_dashboard(manager)
            
        elif options['export']:
            self.export_metrics(manager, options['export'])
            
        elif options['clear_old']:
            self.clear_old_metrics(manager, options['clear_old'])
            
        elif options['realtime']:
            self.show_realtime_metrics()
            
        elif options['test_data']:
            self.generate_test_data()
            
        else:
            self.stdout.write(
                self.style.ERROR('사용 가능한 옵션을 선택해주세요. --help로 도움말을 확인하세요.')
            )

    def show_dashboard(self, manager):
        """대시보드 메트릭 표시"""
        self.stdout.write(self.style.SUCCESS('\n=== StudyMate 메트릭 대시보드 ===\n'))
        
        try:
            metrics = manager.get_dashboard_metrics()
            
            # 사용자 획득 메트릭
            user_metrics = metrics['user_acquisition']
            self.stdout.write(self.style.HTTP_INFO('📈 사용자 획득 메트릭 (30일)'))
            self.stdout.write(f"  • 총 신규 등록자: {user_metrics['total_registrations']}명")
            self.stdout.write(f"  • 평균 일일 등록자: {user_metrics['average_daily_registrations']:.1f}명")
            
            # 참여도 메트릭
            engagement_metrics = metrics['engagement']
            total_dau = sum(day['count'] for day in engagement_metrics['daily_active_users'][-7:])
            self.stdout.write(f"\n🎯 사용자 참여도 메트릭")
            self.stdout.write(f"  • 주간 활성 사용자 (7일): {total_dau}명")
            
            feature_usage = engagement_metrics['feature_usage']
            self.stdout.write(f"  • AI 요약 생성: {feature_usage.get('summary_generated', 0)}건")
            self.stdout.write(f"  • 퀴즈 시도: {feature_usage.get('quiz_attempted', 0)}건")
            self.stdout.write(f"  • AI 요청: {feature_usage.get('ai_request', 0)}건")
            
            # 수익 메트릭
            revenue_metrics = metrics['revenue']
            self.stdout.write(f"\n💰 수익 메트릭 (30일)")
            self.stdout.write(f"  • 총 수익: ₩{revenue_metrics['total_revenue']:,}")
            self.stdout.write(f"  • 신규 구독: {revenue_metrics['subscription_metrics']['new_subscriptions']}건")
            self.stdout.write(f"  • 구독 취소: {revenue_metrics['subscription_metrics']['cancelled_subscriptions']}건")
            self.stdout.write(f"  • 이탈률: {revenue_metrics['subscription_metrics']['churn_rate']:.1f}%")
            
            # API 성능 메트릭
            api_metrics = metrics['api_performance']
            self.stdout.write(f"\n⚡ API 성능 메트릭 (24시간)")
            self.stdout.write(f"  • 총 API 요청: {api_metrics['request_count']:,}건")
            self.stdout.write(f"  • 에러율: {api_metrics['error_rate']:.2f}%")
            self.stdout.write(f"  • 캐시 히트율: {api_metrics['cache_hit_rate']:.1f}%")
            
            # AI 사용량 메트릭
            ai_metrics = metrics['ai_usage']
            self.stdout.write(f"\n🤖 AI 사용량 메트릭 (7일)")
            self.stdout.write(f"  • 총 AI 요청: {ai_metrics['total_ai_requests']:,}건")
            self.stdout.write(f"  • AI 에러율: {ai_metrics['error_rate']:.2f}%")
            
            self.stdout.write(f"\n생성 시간: {metrics['generated_at']}")
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'대시보드 메트릭 조회 실패: {e}')
            )

    def export_metrics(self, manager, format_type):
        """메트릭 데이터 내보내기"""
        self.stdout.write(f'메트릭 데이터를 {format_type.upper()} 형식으로 내보내는 중...')
        
        try:
            metrics = manager.get_dashboard_metrics()
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            filename = f'studymate_metrics_{timestamp}.{format_type}'
            
            if format_type == 'json':
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(metrics, f, indent=2, ensure_ascii=False, default=str)
                    
            elif format_type == 'csv':
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    
                    # CSV 헤더
                    writer.writerow(['Metric Category', 'Metric Name', 'Value', 'Timestamp'])
                    
                    # 사용자 획득 메트릭
                    ua = metrics['user_acquisition']
                    writer.writerow(['User Acquisition', 'Total Registrations', ua['total_registrations'], metrics['generated_at']])
                    writer.writerow(['User Acquisition', 'Average Daily Registrations', ua['average_daily_registrations'], metrics['generated_at']])
                    
                    # 참여도 메트릭
                    eng = metrics['engagement']
                    for feature, count in eng['feature_usage'].items():
                        writer.writerow(['Engagement', f'Feature Usage - {feature}', count, metrics['generated_at']])
                    
                    # 수익 메트릭
                    rev = metrics['revenue']
                    writer.writerow(['Revenue', 'Total Revenue', rev['total_revenue'], metrics['generated_at']])
                    writer.writerow(['Revenue', 'New Subscriptions', rev['subscription_metrics']['new_subscriptions'], metrics['generated_at']])
                    writer.writerow(['Revenue', 'Churn Rate', rev['subscription_metrics']['churn_rate'], metrics['generated_at']])
                    
                    # API 성능 메트릭
                    api = metrics['api_performance']
                    writer.writerow(['API Performance', 'Request Count', api['request_count'], metrics['generated_at']])
                    writer.writerow(['API Performance', 'Error Rate', api['error_rate'], metrics['generated_at']])
                    writer.writerow(['API Performance', 'Cache Hit Rate', api['cache_hit_rate'], metrics['generated_at']])
            
            self.stdout.write(
                self.style.SUCCESS(f'메트릭 데이터가 {filename}에 저장되었습니다.')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'메트릭 내보내기 실패: {e}')
            )

    def clear_old_metrics(self, manager, days):
        """오래된 메트릭 데이터 정리"""
        self.stdout.write(f'{days}일 이전 메트릭 데이터를 정리하는 중...')
        
        try:
            manager.clear_old_metrics(days)
            self.stdout.write(
                self.style.SUCCESS(f'{days}일 이전 메트릭 데이터 정리가 완료되었습니다.')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'메트릭 정리 실패: {e}')
            )

    def show_realtime_metrics(self):
        """실시간 메트릭 모니터링"""
        import time
        from django.core.cache import cache
        
        self.stdout.write(self.style.SUCCESS('실시간 메트릭 모니터링 시작 (Ctrl+C로 종료)'))
        
        try:
            while True:
                current_hour = timezone.now().strftime('%Y-%m-%d-%H')
                
                # 실시간 카운터 조회
                api_requests = cache.get(f'metrics:counter:api_request:{current_hour}', 0)
                api_errors = cache.get(f'metrics:counter:api_error:{current_hour}', 0)
                cache_hits = cache.get(f'metrics:counter:cache_hit:{current_hour}', 0)
                cache_misses = cache.get(f'metrics:counter:cache_miss:{current_hour}', 0)
                ai_requests = cache.get(f'metrics:counter:ai_request:{current_hour}', 0)
                
                error_rate = (api_errors / api_requests * 100) if api_requests > 0 else 0
                cache_hit_rate = (cache_hits / (cache_hits + cache_misses) * 100) if (cache_hits + cache_misses) > 0 else 0
                
                # 화면 클리어 (Unix 시스템)
                print('\033[2J\033[H')
                
                self.stdout.write(self.style.SUCCESS(f'=== 실시간 메트릭 ({timezone.now().strftime("%Y-%m-%d %H:%M:%S")}) ==='))
                self.stdout.write(f'⚡ API 요청: {api_requests:,}건')
                self.stdout.write(f'❌ API 에러: {api_errors}건 ({error_rate:.2f}%)')
                self.stdout.write(f'💾 캐시 히트: {cache_hits}건 ({cache_hit_rate:.1f}%)')
                self.stdout.write(f'🤖 AI 요청: {ai_requests}건')
                self.stdout.write('\n업데이트 간격: 10초')
                
                time.sleep(10)
                
        except KeyboardInterrupt:
            self.stdout.write(self.style.SUCCESS('\n실시간 모니터링이 종료되었습니다.'))

    def generate_test_data(self):
        """테스트 메트릭 데이터 생성"""
        from studymate_api.metrics import (
            track_user_event, track_business_event, track_system_event, track_ai_event,
            EventType
        )
        import random
        
        self.stdout.write('테스트 메트릭 데이터를 생성하는 중...')
        
        try:
            # 사용자 이벤트 생성
            for i in range(100):
                track_user_event(EventType.USER_LOGIN, user_id=random.randint(1, 50))
                track_user_event(EventType.STUDY_SESSION_START, user_id=random.randint(1, 50))
                track_user_event(EventType.QUIZ_ATTEMPTED, user_id=random.randint(1, 50))
            
            # 비즈니스 이벤트 생성
            for i in range(20):
                track_business_event(EventType.USER_REGISTER)
                track_business_event(EventType.PAYMENT_SUCCESS, value=random.choice([9990, 29990, 49990]))
            
            # 시스템 이벤트 생성
            for i in range(500):
                track_system_event(EventType.API_REQUEST)
                if random.random() < 0.02:  # 2% 에러율
                    track_system_event(EventType.API_ERROR)
                
                if random.random() < 0.8:  # 80% 캐시 히트율
                    track_system_event(EventType.CACHE_HIT)
                else:
                    track_system_event(EventType.CACHE_MISS)
            
            # AI 이벤트 생성
            providers = ['openai', 'anthropic', 'together']
            for i in range(150):
                provider = random.choice(providers)
                track_ai_event(EventType.AI_REQUEST, provider)
                if random.random() < 0.01:  # 1% AI 에러율
                    track_ai_event(EventType.AI_ERROR, provider)
            
            self.stdout.write(
                self.style.SUCCESS('테스트 메트릭 데이터 생성이 완료되었습니다.')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'테스트 데이터 생성 실패: {e}')
            )