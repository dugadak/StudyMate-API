"""
CQRS 패턴 관리 Django 명령어

사용법:
    python manage.py cqrs_management --stats
    python manage.py cqrs_management --register-handlers
    python manage.py cqrs_management --test-commands
    python manage.py cqrs_management --test-queries
    python manage.py cqrs_management --clear-cache
"""

import json
import time
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.core.cache import cache
from studymate_api.cqrs import (
    command_bus, query_bus, CQRSMetrics,
    dispatch_command, dispatch_query
)


class Command(BaseCommand):
    help = 'CQRS 패턴 시스템 관리'

    def add_arguments(self, parser):
        parser.add_argument(
            '--stats',
            action='store_true',
            help='CQRS 통계 조회',
        )
        
        parser.add_argument(
            '--register-handlers',
            action='store_true',
            help='핸들러 등록 상태 확인',
        )
        
        parser.add_argument(
            '--test-commands',
            action='store_true',
            help='명령 테스트 실행',
        )
        
        parser.add_argument(
            '--test-queries',
            action='store_true',
            help='조회 테스트 실행',
        )
        
        parser.add_argument(
            '--clear-cache',
            action='store_true',
            help='CQRS 관련 캐시 정리',
        )
        
        parser.add_argument(
            '--benchmark',
            type=int,
            metavar='COUNT',
            help='성능 벤치마크 실행 (실행 횟수)',
        )

    def handle(self, *args, **options):
        if options['stats']:
            self.show_stats()
            
        elif options['register_handlers']:
            self.show_handlers()
            
        elif options['test_commands']:
            self.test_commands()
            
        elif options['test_queries']:
            self.test_queries()
            
        elif options['clear_cache']:
            self.clear_cache()
            
        elif options['benchmark']:
            self.run_benchmark(options['benchmark'])
            
        else:
            self.stdout.write(
                self.style.ERROR('사용 가능한 옵션을 선택해주세요. --help로 도움말을 확인하세요.')
            )

    def show_stats(self):
        """CQRS 통계 표시"""
        self.stdout.write(self.style.SUCCESS('\n=== CQRS 시스템 통계 ===\n'))
        
        try:
            stats = CQRSMetrics.get_overall_stats()
            
            # 핸들러 등록 현황
            self.stdout.write(self.style.HTTP_INFO('📋 핸들러 등록 현황'))
            self.stdout.write(f"  • 등록된 명령 핸들러: {stats['registered_handlers']['commands']}개")
            self.stdout.write(f"  • 등록된 조회 핸들러: {stats['registered_handlers']['queries']}개")
            
            # 명령 통계
            self.stdout.write(f"\n⚡ 명령 실행 통계")
            if stats['commands']:
                for command_name, command_stats in stats['commands'].items():
                    total = command_stats['total_count']
                    success = command_stats['success_count']
                    failure = command_stats['failure_count']
                    avg_time = command_stats['avg_execution_time']
                    success_rate = (success / total * 100) if total > 0 else 0
                    
                    self.stdout.write(f"  📌 {command_name}")
                    self.stdout.write(f"     총 실행: {total}회, 성공: {success}회, 실패: {failure}회")
                    self.stdout.write(f"     성공률: {success_rate:.1f}%, 평균 실행시간: {avg_time:.3f}초")
            else:
                self.stdout.write("  아직 실행된 명령이 없습니다.")
            
            # 조회 통계
            self.stdout.write(f"\n🔍 조회 실행 통계")
            if stats['queries']:
                for query_name, query_stats in stats['queries'].items():
                    total = query_stats['total_count']
                    cache_hit = query_stats['cache_hit_count']
                    cache_miss = query_stats['cache_miss_count']
                    avg_time = query_stats['avg_execution_time']
                    hit_rate = (cache_hit / total * 100) if total > 0 else 0
                    
                    self.stdout.write(f"  📌 {query_name}")
                    self.stdout.write(f"     총 조회: {total}회, 캐시 히트: {cache_hit}회, 미스: {cache_miss}회")
                    self.stdout.write(f"     캐시 히트율: {hit_rate:.1f}%, 평균 실행시간: {avg_time:.3f}초")
            else:
                self.stdout.write("  아직 실행된 조회가 없습니다.")
            
            self.stdout.write(f"\n생성 시간: {timezone.now()}")
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'통계 조회 실패: {e}')
            )

    def show_handlers(self):
        """등록된 핸들러 표시"""
        self.stdout.write(self.style.SUCCESS('\n=== 등록된 CQRS 핸들러 ===\n'))
        
        # 명령 핸들러
        self.stdout.write(self.style.HTTP_INFO('⚡ 명령 핸들러'))
        if command_bus._handlers:
            for command_type, handler in command_bus._handlers.items():
                self.stdout.write(f"  📌 {command_type.__name__} -> {handler.__class__.__name__}")
        else:
            self.stdout.write("  등록된 명령 핸들러가 없습니다.")
        
        # 조회 핸들러
        self.stdout.write(f"\n🔍 조회 핸들러")
        if query_bus._handlers:
            for query_type, handler in query_bus._handlers.items():
                self.stdout.write(f"  📌 {query_type.__name__} -> {handler.__class__.__name__}")
        else:
            self.stdout.write("  등록된 조회 핸들러가 없습니다.")
        
        # 미들웨어
        self.stdout.write(f"\n🔧 미들웨어")
        self.stdout.write(f"  명령 미들웨어: {len(command_bus._middleware)}개")
        self.stdout.write(f"  조회 미들웨어: {len(query_bus._middleware)}개")

    def test_commands(self):
        """명령 테스트 실행"""
        self.stdout.write(self.style.SUCCESS('CQRS 명령 테스트를 실행합니다...'))
        
        try:
            # Study 관련 명령 테스트
            self.stdout.write("\n📚 Study 명령 테스트")
            
            # 필요한 모듈 import
            from study.cqrs import CreateSubjectCommand, UpdateSubjectCommand
            from django.contrib.auth import get_user_model
            
            User = get_user_model()
            
            # 테스트 사용자 생성 또는 조회
            test_user, created = User.objects.get_or_create(
                username='cqrs_test_user',
                defaults={
                    'email': 'cqrs_test@example.com',
                    'first_name': 'CQRS',
                    'last_name': 'Test'
                }
            )
            
            # 과목 생성 명령 테스트
            create_command = CreateSubjectCommand(
                user_id=test_user.id,
                name="CQRS 테스트 과목",
                description="CQRS 패턴 테스트를 위한 과목입니다.",
                category="computer_science",
                difficulty_level="intermediate",
                tags=["cqrs", "test"],
                keywords=["pattern", "architecture"]
            )
            
            result = dispatch_command(create_command)
            
            if result.status.value == "success":
                self.stdout.write(
                    self.style.SUCCESS(f"  ✅ 과목 생성 성공: {result.execution_time:.3f}초")
                )
                
                # 생성된 과목 ID 추출
                subject_id = result.result['id']
                
                # 과목 수정 명령 테스트
                update_command = UpdateSubjectCommand(
                    user_id=test_user.id,
                    subject_id=subject_id,
                    description="CQRS 패턴 테스트를 위해 수정된 과목입니다."
                )
                
                update_result = dispatch_command(update_command)
                
                if update_result.status.value == "success":
                    self.stdout.write(
                        self.style.SUCCESS(f"  ✅ 과목 수정 성공: {update_result.execution_time:.3f}초")
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f"  ❌ 과목 수정 실패: {update_result.error_message}")
                    )
            else:
                self.stdout.write(
                    self.style.ERROR(f"  ❌ 과목 생성 실패: {result.error_message}")
                )
            
            self.stdout.write(
                self.style.SUCCESS('명령 테스트가 완료되었습니다.')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'명령 테스트 실패: {e}')
            )

    def test_queries(self):
        """조회 테스트 실행"""
        self.stdout.write(self.style.SUCCESS('CQRS 조회 테스트를 실행합니다...'))
        
        try:
            # Study 관련 조회 테스트
            self.stdout.write("\n📚 Study 조회 테스트")
            
            from study.cqrs import GetSubjectsQuery
            from django.contrib.auth import get_user_model
            
            User = get_user_model()
            
            # 테스트 사용자 조회
            test_user = User.objects.filter(username='cqrs_test_user').first()
            
            if test_user:
                # 과목 목록 조회 (캐시 미스)
                subjects_query = GetSubjectsQuery(
                    user_id=test_user.id,
                    limit=5
                )
                
                result = dispatch_query(subjects_query)
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✅ 과목 목록 조회 성공: {len(result.data)}개 결과, "
                        f"캐시: {'HIT' if result.cache_hit else 'MISS'}, "
                        f"시간: {result.execution_time:.3f}초"
                    )
                )
                
                # 같은 조회 다시 실행 (캐시 히트 예상)
                result2 = dispatch_query(subjects_query)
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✅ 과목 목록 조회 재실행: {len(result2.data)}개 결과, "
                        f"캐시: {'HIT' if result2.cache_hit else 'MISS'}, "
                        f"시간: {result2.execution_time:.3f}초"
                    )
                )
            else:
                self.stdout.write("  테스트 사용자가 없습니다. 먼저 --test-commands를 실행하세요.")
            
            self.stdout.write(
                self.style.SUCCESS('조회 테스트가 완료되었습니다.')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'조회 테스트 실패: {e}')
            )

    def clear_cache(self):
        """CQRS 관련 캐시 정리"""
        self.stdout.write('CQRS 관련 캐시를 정리하는 중...')
        
        try:
            # CQRS 관련 캐시 키 패턴들
            cache_patterns = [
                'cqrs:*',
                'metrics:*',
                'advanced_cache:*'
            ]
            
            cleared_count = 0
            
            # Redis 캐시인 경우 패턴 매칭으로 삭제
            try:
                from django.core.cache.backends.redis import RedisCache
                if isinstance(cache, RedisCache):
                    import redis
                    redis_client = cache._cache.get_client(write=True)
                    
                    for pattern in cache_patterns:
                        keys = redis_client.keys(pattern)
                        if keys:
                            deleted = redis_client.delete(*keys)
                            cleared_count += deleted
                            self.stdout.write(f"  패턴 '{pattern}': {deleted}개 키 삭제")
                else:
                    # 다른 캐시 백엔드의 경우 전체 삭제
                    cache.clear()
                    cleared_count = "전체"
                    
            except ImportError:
                # Redis가 없는 경우 전체 캐시 삭제
                cache.clear()
                cleared_count = "전체"
            
            self.stdout.write(
                self.style.SUCCESS(f'캐시 정리가 완료되었습니다. ({cleared_count}개 항목)')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'캐시 정리 실패: {e}')
            )

    def run_benchmark(self, count: int):
        """성능 벤치마크 실행"""
        self.stdout.write(self.style.SUCCESS(f'CQRS 성능 벤치마크를 실행합니다 ({count}회)...'))
        
        try:
            from study.cqrs import GetSubjectsQuery
            from django.contrib.auth import get_user_model
            
            User = get_user_model()
            test_user = User.objects.filter(username='cqrs_test_user').first()
            
            if not test_user:
                self.stdout.write("  테스트 사용자가 없습니다. 먼저 --test-commands를 실행하세요.")
                return
            
            # 벤치마크 실행
            total_time = 0
            cache_hits = 0
            cache_misses = 0
            
            self.stdout.write(f"벤치마크 진행 중...")
            
            for i in range(count):
                # 진행률 표시
                if (i + 1) % (count // 10) == 0:
                    progress = (i + 1) / count * 100
                    self.stdout.write(f"  진행률: {progress:.0f}%", ending='\r')
                
                query = GetSubjectsQuery(
                    user_id=test_user.id,
                    limit=10,
                    offset=i % 20  # 다양한 쿼리 생성
                )
                
                start_time = time.time()
                result = dispatch_query(query)
                execution_time = time.time() - start_time
                
                total_time += execution_time
                
                if result.cache_hit:
                    cache_hits += 1
                else:
                    cache_misses += 1
            
            # 결과 출력
            avg_time = total_time / count
            cache_hit_rate = (cache_hits / count) * 100
            
            self.stdout.write(f"\n")
            self.stdout.write(self.style.SUCCESS("=== 벤치마크 결과 ==="))
            self.stdout.write(f"총 실행 횟수: {count:,}회")
            self.stdout.write(f"총 실행 시간: {total_time:.3f}초")
            self.stdout.write(f"평균 실행 시간: {avg_time*1000:.2f}ms")
            self.stdout.write(f"초당 처리량: {count/total_time:.1f} ops/sec")
            self.stdout.write(f"캐시 히트율: {cache_hit_rate:.1f}% ({cache_hits}/{count})")
            self.stdout.write(f"캐시 미스율: {100-cache_hit_rate:.1f}% ({cache_misses}/{count})")
            
            # 성능 등급
            if avg_time < 0.01:
                grade = "🚀 매우 빠름"
            elif avg_time < 0.05:
                grade = "⚡ 빠름"
            elif avg_time < 0.1:
                grade = "✅ 보통"
            else:
                grade = "🐌 느림"
            
            self.stdout.write(f"성능 등급: {grade}")
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'벤치마크 실행 실패: {e}')
            )