"""
캐시 관리 Django 명령어

사용법:
    python manage.py cache_management --warm-all           # 모든 캐시 예열
    python manage.py cache_management --warm-popular       # 인기 콘텐츠 캐시 예열
    python manage.py cache_management --invalidate-user 123 # 특정 사용자 캐시 무효화
    python manage.py cache_management --health             # 캐시 상태 확인
    python manage.py cache_management --stats              # 캐시 통계 출력
    python manage.py cache_management --cleanup            # 만료된 캐시 정리
"""

import json
from typing import Any, Dict, List
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from studymate_api.advanced_cache import smart_cache
from accounts.models import User
from study.models import Subject, StudySummary
from quiz.models import Quiz


User = get_user_model()


class Command(BaseCommand):
    help = '고급 캐시 시스템 관리'

    def add_arguments(self, parser):
        parser.add_argument(
            '--warm-all',
            action='store_true',
            help='모든 캐시 예열',
        )
        
        parser.add_argument(
            '--warm-popular',
            action='store_true',
            help='인기 콘텐츠 캐시 예열',
        )
        
        parser.add_argument(
            '--warm-user',
            type=int,
            help='특정 사용자 캐시 예열',
        )
        
        parser.add_argument(
            '--invalidate-user',
            type=int,
            help='특정 사용자 캐시 무효화',
        )
        
        parser.add_argument(
            '--invalidate-content',
            nargs=2,
            metavar=('TYPE', 'ID'),
            help='특정 콘텐츠 캐시 무효화 (예: study 123)',
        )
        
        parser.add_argument(
            '--health',
            action='store_true',
            help='캐시 시스템 상태 확인',
        )
        
        parser.add_argument(
            '--stats',
            action='store_true',
            help='캐시 통계 출력',
        )
        
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='만료된 캐시 정리',
        )
        
        parser.add_argument(
            '--benchmark',
            action='store_true',
            help='캐시 성능 벤치마크',
        )

    def handle(self, *args, **options):
        """명령어 처리"""
        
        if options['warm_all']:
            self.warm_all_caches()
        
        elif options['warm_popular']:
            self.warm_popular_caches()
        
        elif options['warm_user']:
            self.warm_user_cache(options['warm_user'])
        
        elif options['invalidate_user']:
            self.invalidate_user_cache(options['invalidate_user'])
        
        elif options['invalidate_content']:
            content_type, content_id = options['invalidate_content']
            self.invalidate_content_cache(content_type, int(content_id))
        
        elif options['health']:
            self.show_cache_health()
        
        elif options['stats']:
            self.show_cache_stats()
        
        elif options['cleanup']:
            self.cleanup_expired_caches()
        
        elif options['benchmark']:
            self.run_cache_benchmark()
        
        else:
            self.stdout.write(
                self.style.ERROR('사용할 옵션을 지정해주세요. --help로 도움말을 확인하세요.')
            )

    def warm_all_caches(self):
        """모든 캐시 예열"""
        self.stdout.write("모든 캐시 예열을 시작합니다...")
        
        # 사용자 프로필 캐시 예열
        self.stdout.write("사용자 프로필 캐시 예열 중...")
        active_users = User.objects.filter(
            is_active=True,
            last_login__gte=timezone.now() - timedelta(days=30)
        )[:100]  # 최근 30일 내 활동한 상위 100명
        
        user_warm_data = []
        for user in active_users:
            user_warm_data.append({
                'key_data': {'user_id': user.id},
                'value_func': lambda u=user: self._get_user_profile_data(u),
            })
        
        smart_cache.warm_cache('user_profile', user_warm_data)
        self.stdout.write(f"✓ {len(user_warm_data)}개 사용자 프로필 캐시 예열 완료")
        
        # 학습 콘텐츠 캐시 예열
        self.stdout.write("학습 콘텐츠 캐시 예열 중...")
        popular_subjects = Subject.objects.all()[:50]  # 상위 50개 과목
        
        content_warm_data = []
        for subject in popular_subjects:
            for difficulty in ['beginner', 'intermediate', 'advanced']:
                content_warm_data.append({
                    'key_data': {'subject_id': subject.id, 'difficulty': difficulty},
                    'value_func': lambda s=subject, d=difficulty: self._get_study_content_data(s, d),
                })
        
        smart_cache.warm_cache('study_content', content_warm_data)
        self.stdout.write(f"✓ {len(content_warm_data)}개 학습 콘텐츠 캐시 예열 완료")
        
        # 분석 데이터 캐시 예열
        self.stdout.write("분석 데이터 캐시 예열 중...")
        analytics_warm_data = [
            {
                'key_data': {'metric_type': 'daily_users', 'date_range': 'last_7_days'},
                'value_func': lambda: self._get_analytics_data('daily_users', 'last_7_days'),
            },
            {
                'key_data': {'metric_type': 'popular_subjects', 'date_range': 'last_30_days'},
                'value_func': lambda: self._get_analytics_data('popular_subjects', 'last_30_days'),
            },
        ]
        
        smart_cache.warm_cache('analytics', analytics_warm_data)
        self.stdout.write(f"✓ {len(analytics_warm_data)}개 분석 데이터 캐시 예열 완료")
        
        self.stdout.write(
            self.style.SUCCESS("모든 캐시 예열이 완료되었습니다!")
        )

    def warm_popular_caches(self):
        """인기 콘텐츠 캐시 예열"""
        self.stdout.write("인기 콘텐츠 캐시 예열을 시작합니다...")
        
        try:
            smart_cache.auto_warm_popular_content()
            self.stdout.write(
                self.style.SUCCESS("인기 콘텐츠 캐시 예열이 완료되었습니다!")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"인기 콘텐츠 캐시 예열 실패: {e}")
            )

    def warm_user_cache(self, user_id: int):
        """특정 사용자 캐시 예열"""
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise CommandError(f'사용자 ID {user_id}를 찾을 수 없습니다.')
        
        self.stdout.write(f"사용자 {user.email} 캐시 예열 중...")
        
        # 사용자 프로필 캐시
        user_warm_data = [{
            'key_data': {'user_id': user.id},
            'value_func': lambda: self._get_user_profile_data(user),
        }]
        smart_cache.warm_cache('user_profile', user_warm_data)
        
        # 사용자의 최근 퀴즈 결과 캐시
        recent_quizzes = Quiz.objects.filter(
            useranswer__user=user
        ).distinct()[:10]
        
        quiz_warm_data = []
        for quiz in recent_quizzes:
            quiz_warm_data.append({
                'key_data': {'user_id': user.id, 'quiz_id': quiz.id},
                'value_func': lambda q=quiz: self._get_quiz_results_data(user, q),
            })
        
        if quiz_warm_data:
            smart_cache.warm_cache('quiz_results', quiz_warm_data)
        
        self.stdout.write(
            self.style.SUCCESS(f"사용자 {user.email} 캐시 예열 완료!")
        )

    def invalidate_user_cache(self, user_id: int):
        """특정 사용자 캐시 무효화"""
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise CommandError(f'사용자 ID {user_id}를 찾을 수 없습니다.')
        
        deleted_count = smart_cache.invalidate_user_cache(user_id)
        
        self.stdout.write(
            self.style.SUCCESS(
                f"사용자 {user.email}의 캐시 {deleted_count}개를 무효화했습니다."
            )
        )

    def invalidate_content_cache(self, content_type: str, content_id: int):
        """특정 콘텐츠 캐시 무효화"""
        deleted_count = smart_cache.invalidate_content_cache(content_type, content_id)
        
        self.stdout.write(
            self.style.SUCCESS(
                f"{content_type} {content_id}의 캐시 {deleted_count}개를 무효화했습니다."
            )
        )

    def show_cache_health(self):
        """캐시 시스템 상태 표시"""
        health = smart_cache.get_cache_health()
        
        self.stdout.write("=" * 50)
        self.stdout.write("캐시 시스템 상태")
        self.stdout.write("=" * 50)
        
        status_color = self.style.SUCCESS if health['status'] == 'healthy' else self.style.ERROR
        self.stdout.write(f"상태: {status_color(health['status'])}")
        
        self.stdout.write("\n통계:")
        stats = health['statistics']
        self.stdout.write(f"  히트율: {stats['hit_rate']:.2%}")
        self.stdout.write(f"  평균 접근 시간: {stats['avg_access_time']:.3f}초")
        self.stdout.write(f"  총 태그 수: {stats['total_tags']}")
        self.stdout.write(f"  총 키 수: {stats['total_keys']}")
        
        self.stdout.write(f"\n활성 전략: {', '.join(health['strategies'])}")
        
        if health['warnings']:
            self.stdout.write(f"\n{self.style.WARNING('경고:')}")
            for warning in health['warnings']:
                self.stdout.write(f"  - {warning}")
        
        self.stdout.write("\n접근 패턴:")
        for strategy, count in health['access_patterns'].items():
            self.stdout.write(f"  {strategy}: {count}개 기록")

    def show_cache_stats(self):
        """캐시 통계 표시"""
        stats = smart_cache.tagged_cache.get_stats()
        
        self.stdout.write("=" * 50)
        self.stdout.write("캐시 통계")
        self.stdout.write("=" * 50)
        
        self.stdout.write(f"캐시 히트: {stats['hits']:,}")
        self.stdout.write(f"캐시 미스: {stats['misses']:,}")
        self.stdout.write(f"캐시 설정: {stats['sets']:,}")
        self.stdout.write(f"캐시 삭제: {stats['deletes']:,}")
        
        total_reads = stats['hits'] + stats['misses']
        if total_reads > 0:
            hit_rate = stats['hits'] / total_reads
            self.stdout.write(f"히트율: {hit_rate:.2%}")
        
        self.stdout.write(f"평균 접근 시간: {stats['avg_access_time']:.3f}초")
        self.stdout.write(f"총 태그 수: {stats['total_tags']}")
        self.stdout.write(f"총 키 수: {stats['total_keys']}")

    def cleanup_expired_caches(self):
        """만료된 캐시 정리"""
        self.stdout.write("만료된 캐시 정리 중...")
        
        # Django의 기본 캐시 정리 기능 사용
        try:
            from django.core.cache import cache
            if hasattr(cache, 'clear'):
                # 주의: 이 방법은 모든 캐시를 삭제합니다
                # 실제 환경에서는 더 정교한 만료 캐시 감지 로직이 필요합니다
                self.stdout.write("현재 캐시 백엔드는 선택적 정리를 지원하지 않습니다.")
                self.stdout.write("전체 캐시를 삭제하려면 --clear-all 옵션을 추가하세요.")
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"캐시 정리 실패: {e}")
            )

    def run_cache_benchmark(self):
        """캐시 성능 벤치마크"""
        import time
        import random
        
        self.stdout.write("캐시 성능 벤치마크를 실행합니다...")
        
        # 벤치마크 데이터
        test_keys = [f"benchmark_key_{i}" for i in range(1000)]
        test_values = [f"benchmark_value_{i}" * 100 for i in range(1000)]
        
        # 쓰기 성능 테스트
        start_time = time.time()
        for i, (key, value) in enumerate(zip(test_keys, test_values)):
            smart_cache.tagged_cache.set(key, value, tags=['benchmark'], timeout=3600)
            
        write_time = time.time() - start_time
        self.stdout.write(f"쓰기 성능: {len(test_keys)}개 항목을 {write_time:.2f}초에 처리")
        self.stdout.write(f"초당 쓰기: {len(test_keys) / write_time:.0f} ops/sec")
        
        # 읽기 성능 테스트
        start_time = time.time()
        hit_count = 0
        for _ in range(2000):  # 읽기를 더 많이 테스트
            key = random.choice(test_keys)
            value = smart_cache.tagged_cache.get(key)
            if value is not None:
                hit_count += 1
                
        read_time = time.time() - start_time
        self.stdout.write(f"읽기 성능: 2000번 조회를 {read_time:.2f}초에 처리")
        self.stdout.write(f"초당 읽기: {2000 / read_time:.0f} ops/sec")
        self.stdout.write(f"히트율: {hit_count / 2000:.2%}")
        
        # 태그 무효화 성능 테스트
        start_time = time.time()
        deleted_count = smart_cache.tagged_cache.invalidate_tag('benchmark')
        invalidate_time = time.time() - start_time
        
        self.stdout.write(f"무효화 성능: {deleted_count}개 항목을 {invalidate_time:.2f}초에 처리")
        
        self.stdout.write(
            self.style.SUCCESS("벤치마크 완료!")
        )

    def _get_user_profile_data(self, user: User) -> Dict[str, Any]:
        """사용자 프로필 데이터 조회"""
        return {
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'learning_language': getattr(user, 'learning_language', 'ko'),
            'difficulty_preference': getattr(user, 'difficulty_preference', 'intermediate'),
            'last_login': user.last_login.isoformat() if user.last_login else None,
        }

    def _get_study_content_data(self, subject: Subject, difficulty: str) -> Dict[str, Any]:
        """학습 콘텐츠 데이터 조회"""
        return {
            'subject_id': subject.id,
            'subject_name': subject.name,
            'difficulty': difficulty,
            'description': getattr(subject, 'description', ''),
            'content_count': StudySummary.objects.filter(
                subject=subject,
                difficulty_level=difficulty
            ).count(),
        }

    def _get_quiz_results_data(self, user: User, quiz: Quiz) -> Dict[str, Any]:
        """퀴즈 결과 데이터 조회"""
        return {
            'user_id': user.id,
            'quiz_id': quiz.id,
            'quiz_title': quiz.title,
            'total_questions': quiz.question_set.count(),
            'user_score': 0,  # 실제 점수 계산 로직 필요
        }

    def _get_analytics_data(self, metric_type: str, date_range: str) -> Dict[str, Any]:
        """분석 데이터 조회"""
        # 실제 분석 로직 구현 필요
        return {
            'metric_type': metric_type,
            'date_range': date_range,
            'data': {},
            'generated_at': timezone.now().isoformat(),
        }