"""
실시간 학습 분석 시스템 관리 Django 명령어

사용법:
    python manage.py realtime_analytics_management --start-streaming
    python manage.py realtime_analytics_management --stop-streaming
    python manage.py realtime_analytics_management --status
    python manage.py realtime_analytics_management --active-sessions
    python manage.py realtime_analytics_management --cleanup-sessions
    python manage.py realtime_analytics_management --performance-report
"""

import asyncio
import json
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.contrib.auth import get_user_model

from studymate_api.realtime_analytics import realtime_analyzer
from studymate_api.streaming import (
    stream_processor, 
    learning_event_stream,
    start_streaming,
    stop_streaming,
    get_streaming_status
)

User = get_user_model()


class Command(BaseCommand):
    help = '실시간 학습 분석 시스템 관리'

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-streaming',
            action='store_true',
            help='스트리밍 처리 시작',
        )
        
        parser.add_argument(
            '--stop-streaming',
            action='store_true',
            help='스트리밍 처리 중지',
        )
        
        parser.add_argument(
            '--status',
            action='store_true',
            help='실시간 분석 시스템 상태 조회',
        )
        
        parser.add_argument(
            '--active-sessions',
            action='store_true',
            help='활성 학습 세션 조회',
        )
        
        parser.add_argument(
            '--cleanup-sessions',
            action='store_true',
            help='비활성 세션 정리',
        )
        
        parser.add_argument(
            '--performance-report',
            action='store_true',
            help='성능 리포트 생성',
        )
        
        parser.add_argument(
            '--test-session',
            type=int,
            metavar='USER_ID',
            help='테스트 세션 생성 (사용자 ID)',
        )
        
        parser.add_argument(
            '--benchmark',
            type=int,
            metavar='COUNT',
            help='성능 벤치마크 실행 (이벤트 수)',
        )

    def handle(self, *args, **options):
        if options['start_streaming']:
            self.start_streaming()
            
        elif options['stop_streaming']:
            self.stop_streaming()
            
        elif options['status']:
            self.show_status()
            
        elif options['active_sessions']:
            self.show_active_sessions()
            
        elif options['cleanup_sessions']:
            self.cleanup_sessions()
            
        elif options['performance_report']:
            self.generate_performance_report()
            
        elif options['test_session']:
            self.create_test_session(options['test_session'])
            
        elif options['benchmark']:
            self.run_benchmark(options['benchmark'])
            
        else:
            self.stdout.write(
                self.style.ERROR('사용 가능한 옵션을 선택해주세요. --help로 도움말을 확인하세요.')
            )

    def start_streaming(self):
        """스트리밍 처리 시작"""
        self.stdout.write(self.style.SUCCESS('실시간 스트리밍 처리를 시작합니다...'))
        
        try:
            # 비동기 함수를 동기적으로 실행
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(start_streaming())
                self.stdout.write(
                    self.style.SUCCESS('✅ 스트리밍 처리가 성공적으로 시작되었습니다.')
                )
            finally:
                # 백그라운드에서 계속 실행되도록 루프를 닫지 않음
                pass
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ 스트리밍 시작 실패: {e}')
            )

    def stop_streaming(self):
        """스트리밍 처리 중지"""
        self.stdout.write('실시간 스트리밍 처리를 중지합니다...')
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(stop_streaming())
                self.stdout.write(
                    self.style.SUCCESS('✅ 스트리밍 처리가 중지되었습니다.')
                )
            finally:
                loop.close()
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ 스트리밍 중지 실패: {e}')
            )

    def show_status(self):
        """시스템 상태 표시"""
        self.stdout.write(self.style.SUCCESS('\\n=== 실시간 학습 분석 시스템 상태 ===\\n'))
        
        try:
            # 스트리밍 상태
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                streaming_status = loop.run_until_complete(get_streaming_status())
            finally:
                loop.close()
            
            self.stdout.write(self.style.HTTP_INFO('📊 스트리밍 처리 상태'))
            self.stdout.write(f"  • 실행 상태: {'🟢 실행 중' if streaming_status['is_running'] else '🔴 중지됨'}")
            self.stdout.write(f"  • 활성 처리기: {len(streaming_status['active_processors'])}개")
            self.stdout.write(f"  • 버퍼된 이벤트: {streaming_status['total_buffered_events']:,}개")
            
            # 활성 세션 상태
            self.stdout.write(f"\\n⚡ 학습 세션 상태")
            active_count = realtime_analyzer.get_active_sessions_count()
            self.stdout.write(f"  • 활성 세션 수: {active_count}개")
            
            if active_count > 0:
                self.stdout.write("  • 최근 세션 활동:")
                count = 0
                for session_id, session in realtime_analyzer.active_sessions.items():
                    if count >= 5:  # 최대 5개만 표시
                        break
                    user_id = session.user_id
                    duration_minutes = int(session.total_time / 60)
                    focus_score = session.focus_score
                    
                    self.stdout.write(
                        f"    - 세션 {session_id[:8]}... (사용자: {user_id}, "
                        f"시간: {duration_minutes}분, 집중도: {focus_score:.1f}%)"
                    )
                    count += 1
            
            # 큐 상태
            if streaming_status['queue_sizes']:
                self.stdout.write(f"\\n📋 처리 큐 상태")
                for queue_name, size in streaming_status['queue_sizes'].items():
                    self.stdout.write(f"  • {queue_name}: {size}개 대기 중")
            
            # 메트릭 상태
            if streaming_status.get('metrics'):
                self.stdout.write(f"\\n📈 성능 메트릭")
                for stream_name, metrics in streaming_status['metrics'].items():
                    processing_rate = metrics.get('processing_rate', 0)
                    buffer_usage = metrics.get('buffer_usage', 0)
                    latency = metrics.get('latency_ms', 0)
                    
                    self.stdout.write(f"  • {stream_name}:")
                    self.stdout.write(f"    처리율: {processing_rate:.1f} 이벤트/초")
                    self.stdout.write(f"    버퍼 사용률: {buffer_usage:.1f}%")
                    self.stdout.write(f"    레이턴시: {latency:.1f}ms")
            
            self.stdout.write(f"\\n🕐 상태 조회 시간: {timezone.now()}")
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'상태 조회 실패: {e}')
            )

    def show_active_sessions(self):
        """활성 세션 표시"""
        self.stdout.write(self.style.SUCCESS('\\n=== 활성 학습 세션 목록 ===\\n'))
        
        try:
            active_sessions = realtime_analyzer.active_sessions
            
            if not active_sessions:
                self.stdout.write("현재 활성 세션이 없습니다.")
                return
            
            self.stdout.write(f"총 {len(active_sessions)}개의 활성 세션")
            self.stdout.write("-" * 80)
            
            for session_id, session in active_sessions.items():
                user = None
                try:
                    user = User.objects.get(id=session.user_id)
                    username = user.username
                except User.DoesNotExist:
                    username = f"사용자_{session.user_id}"
                
                duration_minutes = int(session.total_time / 60)
                duration_seconds = int(session.total_time % 60)
                
                self.stdout.write(f"📚 세션 ID: {session_id}")
                self.stdout.write(f"   👤 사용자: {username} (ID: {session.user_id})")
                self.stdout.write(f"   📖 과목 ID: {session.subject_id or '없음'}")
                self.stdout.write(f"   ⏰ 지속시간: {duration_minutes}분 {duration_seconds}초")
                self.stdout.write(f"   🎯 집중도: {session.focus_score:.1f}%")
                self.stdout.write(f"   📊 생산성: {session.productivity_score:.1f}%")
                self.stdout.write(f"   🔄 상태: {session.state.value}")
                self.stdout.write(f"   📅 시작 시간: {session.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
                self.stdout.write(f"   📝 이벤트 수: {len(session.events)}개")
                self.stdout.write("-" * 40)
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'활성 세션 조회 실패: {e}')
            )

    def cleanup_sessions(self):
        """비활성 세션 정리"""
        self.stdout.write('비활성 세션을 정리합니다...')
        
        try:
            current_time = timezone.now()
            cleanup_count = 0
            
            # 2시간 이상 비활성 세션 정리
            sessions_to_remove = []
            
            for session_id, session in realtime_analyzer.active_sessions.items():
                inactive_duration = (current_time - session.last_activity).total_seconds()
                
                if inactive_duration > 7200:  # 2시간
                    sessions_to_remove.append(session_id)
            
            # 세션 제거
            for session_id in sessions_to_remove:
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    try:
                        loop.run_until_complete(
                            realtime_analyzer.end_learning_session(session_id)
                        )
                        cleanup_count += 1
                        self.stdout.write(f"정리된 세션: {session_id}")
                    finally:
                        loop.close()
                        
                except Exception as e:
                    self.stdout.write(f"세션 정리 실패 {session_id}: {e}")
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ {cleanup_count}개의 비활성 세션이 정리되었습니다.')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'세션 정리 실패: {e}')
            )

    def generate_performance_report(self):
        """성능 리포트 생성"""
        self.stdout.write(self.style.SUCCESS('\\n=== 실시간 분석 시스템 성능 리포트 ===\\n'))
        
        try:
            # 스트리밍 메트릭
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                streaming_status = loop.run_until_complete(get_streaming_status())
                stream_metrics = loop.run_until_complete(
                    stream_processor.get_stream_metrics()
                )
            finally:
                loop.close()
            
            # 전체 시스템 상태
            active_sessions = realtime_analyzer.get_active_sessions_count()
            total_buffered = streaming_status.get('total_buffered_events', 0)
            
            self.stdout.write("📊 **시스템 개요**")
            self.stdout.write(f"  • 활성 세션: {active_sessions}개")
            self.stdout.write(f"  • 버퍼된 이벤트: {total_buffered:,}개")
            self.stdout.write(f"  • 스트리밍 상태: {'🟢 실행 중' if streaming_status['is_running'] else '🔴 중지됨'}")
            
            # 스트림별 성능
            if stream_metrics:
                self.stdout.write("\\n⚡ **스트림별 성능**")
                
                for stream_name, metrics in stream_metrics.items():
                    self.stdout.write(f"\\n  📈 {stream_name}")
                    self.stdout.write(f"    • 처리된 이벤트: {metrics.get('processed_events', 0):,}개")
                    self.stdout.write(f"    • 처리율: {metrics.get('processing_rate', 0):.1f} 이벤트/초")
                    self.stdout.write(f"    • 평균 레이턴시: {metrics.get('latency_ms', 0):.1f}ms")
                    self.stdout.write(f"    • 버퍼 사용률: {metrics.get('buffer_usage', 0):.1f}%")
                    self.stdout.write(f"    • 에러 수: {metrics.get('errors', 0)}개")
            
            # 세션 통계
            if active_sessions > 0:
                self.stdout.write("\\n👥 **세션 통계**")
                
                total_duration = 0
                total_focus = 0
                total_productivity = 0
                
                for session in realtime_analyzer.active_sessions.values():
                    total_duration += session.total_time
                    total_focus += session.focus_score
                    total_productivity += session.productivity_score
                
                avg_duration = total_duration / active_sessions / 60  # 분
                avg_focus = total_focus / active_sessions
                avg_productivity = total_productivity / active_sessions
                
                self.stdout.write(f"  • 평균 세션 시간: {avg_duration:.1f}분")
                self.stdout.write(f"  • 평균 집중도: {avg_focus:.1f}%")
                self.stdout.write(f"  • 평균 생산성: {avg_productivity:.1f}%")
            
            # 권장사항
            self.stdout.write("\\n💡 **시스템 권장사항**")
            
            if total_buffered > 5000:
                self.stdout.write("  ⚠️  버퍼된 이벤트가 많습니다. 처리 성능을 확인하세요.")
            
            if active_sessions > 500:
                self.stdout.write("  ⚠️  활성 세션이 많습니다. 리소스 사용량을 모니터링하세요.")
            
            if not streaming_status['is_running']:
                self.stdout.write("  ❌ 스트리밍이 중지되어 있습니다. --start-streaming으로 시작하세요.")
            
            if stream_metrics:
                for stream_name, metrics in stream_metrics.items():
                    if metrics.get('errors', 0) > 10:
                        self.stdout.write(f"  ❌ {stream_name} 스트림에서 많은 에러가 발생했습니다.")
                    
                    if metrics.get('latency_ms', 0) > 1000:
                        self.stdout.write(f"  ⚠️  {stream_name} 스트림의 레이턴시가 높습니다.")
            
            self.stdout.write(f"\\n🕐 리포트 생성 시간: {timezone.now()}")
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'성능 리포트 생성 실패: {e}')
            )

    def create_test_session(self, user_id: int):
        """테스트 세션 생성"""
        self.stdout.write(f'사용자 {user_id}의 테스트 세션을 생성합니다...')
        
        try:
            # 사용자 확인
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'사용자 ID {user_id}를 찾을 수 없습니다.')
                )
                return
            
            # 테스트 세션 시작
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                session_id = loop.run_until_complete(
                    realtime_analyzer.start_learning_session(user_id, subject_id=1)
                )
                
                self.stdout.write(
                    self.style.SUCCESS(f'✅ 테스트 세션이 생성되었습니다.')
                )
                self.stdout.write(f"세션 ID: {session_id}")
                self.stdout.write(f"사용자: {user.username} (ID: {user_id})")
                self.stdout.write("WebSocket 연결 테스트 URL: ws://localhost:8000/ws/learning/analytics/")
                
            finally:
                loop.close()
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'테스트 세션 생성 실패: {e}')
            )

    def run_benchmark(self, event_count: int):
        """성능 벤치마크 실행"""
        self.stdout.write(self.style.SUCCESS(f'성능 벤치마크를 실행합니다 ({event_count:,}개 이벤트)...'))
        
        try:
            import time
            from studymate_api.realtime_analytics import LearningEvent
            
            # 테스트 사용자 생성 또는 조회
            test_user, created = User.objects.get_or_create(
                username='benchmark_test_user',
                defaults={
                    'email': 'benchmark@test.com',
                    'first_name': 'Benchmark',
                    'last_name': 'User'
                }
            )
            
            # 테스트 세션 시작
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                session_id = loop.run_until_complete(
                    realtime_analyzer.start_learning_session(test_user.id)
                )
                
                self.stdout.write(f"벤치마크 세션 시작: {session_id}")
                
                # 이벤트 생성 및 처리 시간 측정
                start_time = time.time()
                
                for i in range(event_count):
                    if i % (event_count // 10) == 0:
                        progress = (i / event_count) * 100
                        self.stdout.write(f"진행률: {progress:.0f}%", ending='\\r')
                    
                    # 다양한 이벤트 타입 시뮬레이션
                    event_types = ['content_read', 'problem_solved', 'note_taken', 'idle', 'tab_switch']
                    event_type = event_types[i % len(event_types)]
                    
                    event = LearningEvent(
                        user_id=test_user.id,
                        session_id=session_id,
                        event_type=event_type,
                        duration=1.0,
                        metadata={'benchmark': True, 'sequence': i}
                    )
                    
                    # 스트림에 이벤트 추가
                    loop.run_until_complete(
                        stream_processor.push_event('benchmark_stream', event)
                    )
                
                end_time = time.time()
                total_time = end_time - start_time
                
                # 세션 종료
                loop.run_until_complete(
                    realtime_analyzer.end_learning_session(session_id)
                )
                
                # 결과 출력
                self.stdout.write("\\n")
                self.stdout.write(self.style.SUCCESS("=== 벤치마크 결과 ==="))
                self.stdout.write(f"총 이벤트 수: {event_count:,}개")
                self.stdout.write(f"총 실행 시간: {total_time:.3f}초")
                self.stdout.write(f"이벤트 처리율: {event_count/total_time:.1f} 이벤트/초")
                self.stdout.write(f"평균 이벤트 처리 시간: {(total_time/event_count)*1000:.2f}ms")
                
                # 성능 등급
                events_per_second = event_count / total_time
                if events_per_second > 1000:
                    grade = "🚀 매우 빠름"
                elif events_per_second > 500:
                    grade = "⚡ 빠름"
                elif events_per_second > 100:
                    grade = "✅ 보통"
                else:
                    grade = "🐌 느림"
                
                self.stdout.write(f"성능 등급: {grade}")
                
            finally:
                loop.close()
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'벤치마크 실행 실패: {e}')
            )