"""
A/B 테스트 관리를 위한 Django 관리 명령어

사용법:
python manage.py manage_ab_test --test-id ai_summary_v2 --action start
python manage.py manage_ab_test --test-id ai_summary_v2 --action pause
python manage.py manage_ab_test --test-id ai_summary_v2 --action results
"""

import json
from django.core.management.base import BaseCommand, CommandError
from studymate_api.ab_testing import ab_test_manager


class Command(BaseCommand):
    help = 'A/B 테스트를 관리합니다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-id',
            type=str,
            help='A/B 테스트 ID'
        )
        parser.add_argument(
            '--action',
            type=str,
            choices=['list', 'start', 'pause', 'resume', 'end', 'results', 'delete'],
            required=True,
            help='수행할 액션'
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
            if action == 'list':
                self._list_tests(options['format'])
            else:
                test_id = options.get('test_id')
                if not test_id:
                    raise CommandError("--test-id가 필요합니다")
                
                if action == 'start':
                    self._start_test(test_id)
                elif action == 'pause':
                    self._pause_test(test_id)
                elif action == 'resume':
                    self._resume_test(test_id)
                elif action == 'end':
                    self._end_test(test_id)
                elif action == 'results':
                    self._show_results(test_id, options['format'])
                elif action == 'delete':
                    self._delete_test(test_id)
                    
        except Exception as e:
            raise CommandError(f"작업 실패: {str(e)}")

    def _list_tests(self, format_type):
        """모든 테스트 목록 출력"""
        tests = ab_test_manager.list_tests()
        
        if not tests:
            self.stdout.write("등록된 A/B 테스트가 없습니다.")
            return
        
        if format_type == 'json':
            test_data = []
            for test in tests:
                test_data.append({
                    'test_id': test.test_id,
                    'name': test.name,
                    'status': test.status.value,
                    'variants': len(test.variants),
                    'metrics': len(test.metrics),
                    'created_at': test.created_at.isoformat(),
                    'started_at': test.started_at.isoformat() if test.started_at else None
                })
            self.stdout.write(json.dumps(test_data, indent=2, ensure_ascii=False))
        else:
            self.stdout.write(self.style.SUCCESS("\nA/B 테스트 목록:"))
            self.stdout.write("-" * 80)
            self.stdout.write(f"{'테스트 ID':<20} {'이름':<25} {'상태':<10} {'변형':<6} {'메트릭':<6}")
            self.stdout.write("-" * 80)
            
            for test in tests:
                self.stdout.write(
                    f"{test.test_id:<20} {test.name[:24]:<25} "
                    f"{test.status.value:<10} {len(test.variants):<6} {len(test.metrics):<6}"
                )

    def _start_test(self, test_id):
        """테스트 시작"""
        test = ab_test_manager.get_test(test_id)
        if not test:
            raise CommandError(f"테스트 '{test_id}'를 찾을 수 없습니다")
        
        test.start_test()
        self.stdout.write(
            self.style.SUCCESS(f"A/B 테스트 '{test_id}'가 시작되었습니다.")
        )

    def _pause_test(self, test_id):
        """테스트 일시정지"""
        test = ab_test_manager.get_test(test_id)
        if not test:
            raise CommandError(f"테스트 '{test_id}'를 찾을 수 없습니다")
        
        test.pause_test()
        self.stdout.write(
            self.style.WARNING(f"A/B 테스트 '{test_id}'가 일시정지되었습니다.")
        )

    def _resume_test(self, test_id):
        """테스트 재개"""
        test = ab_test_manager.get_test(test_id)
        if not test:
            raise CommandError(f"테스트 '{test_id}'를 찾을 수 없습니다")
        
        test.resume_test()
        self.stdout.write(
            self.style.SUCCESS(f"A/B 테스트 '{test_id}'가 재개되었습니다.")
        )

    def _end_test(self, test_id):
        """테스트 종료"""
        test = ab_test_manager.get_test(test_id)
        if not test:
            raise CommandError(f"테스트 '{test_id}'를 찾을 수 없습니다")
        
        # 사용자 확인
        confirmation = input(f"테스트 '{test_id}'를 종료하시겠습니까? (y/N): ")
        if confirmation.lower() != 'y':
            self.stdout.write("테스트 종료가 취소되었습니다.")
            return
        
        final_results = test.end_test()
        self.stdout.write(
            self.style.SUCCESS(f"A/B 테스트 '{test_id}'가 종료되었습니다.")
        )
        
        # 최종 결과 출력
        self.stdout.write("\n최종 결과:")
        self.stdout.write(json.dumps(final_results, indent=2, ensure_ascii=False))

    def _show_results(self, test_id, format_type):
        """테스트 결과 출력"""
        test = ab_test_manager.get_test(test_id)
        if not test:
            raise CommandError(f"테스트 '{test_id}'를 찾을 수 없습니다")
        
        results = test.generate_results_report()
        
        if format_type == 'json':
            self.stdout.write(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            self._print_results_table(results)

    def _print_results_table(self, results):
        """결과를 테이블 형식으로 출력"""
        self.stdout.write(self.style.SUCCESS(f"\nA/B 테스트 결과: {results['test_name']}"))
        self.stdout.write(f"테스트 ID: {results['test_id']}")
        self.stdout.write(f"상태: {results['status']}")
        self.stdout.write(f"기간: {results.get('duration_days', 0):.1f}일")
        self.stdout.write(f"총 사용자: {results.get('total_users', 0)}")
        self.stdout.write(f"총 세션: {results.get('total_sessions', 0)}")
        
        variant_stats = results.get('variant_statistics', {})
        if variant_stats:
            self.stdout.write("\n변형별 통계:")
            self.stdout.write("-" * 60)
            
            for variant_id, stats in variant_stats.items():
                self.stdout.write(f"\n변형 ID: {variant_id}")
                self.stdout.write(f"  샘플 크기: {stats.get('sample_size', 0)}")
                
                metrics = stats.get('metrics', {})
                for metric_name, metric_stats in metrics.items():
                    self.stdout.write(f"  {metric_name}:")
                    self.stdout.write(f"    평균: {metric_stats.get('mean', 0):.3f}")
                    self.stdout.write(f"    중앙값: {metric_stats.get('median', 0):.3f}")
                    self.stdout.write(f"    표준편차: {metric_stats.get('std_dev', 0):.3f}")
        
        # 권장사항
        recommendations = results.get('recommendations', [])
        if recommendations:
            self.stdout.write("\n권장사항:")
            for i, recommendation in enumerate(recommendations, 1):
                self.stdout.write(f"  {i}. {recommendation}")

    def _delete_test(self, test_id):
        """테스트 삭제"""
        test = ab_test_manager.get_test(test_id)
        if not test:
            raise CommandError(f"테스트 '{test_id}'를 찾을 수 없습니다")
        
        # 사용자 확인
        confirmation = input(f"테스트 '{test_id}'를 삭제하시겠습니까? (y/N): ")
        if confirmation.lower() != 'y':
            self.stdout.write("테스트 삭제가 취소되었습니다.")
            return
        
        # 실제로는 AB 테스트 매니저에 delete 메소드 구현 필요
        if test_id in ab_test_manager.active_tests:
            del ab_test_manager.active_tests[test_id]
        
        self.stdout.write(
            self.style.SUCCESS(f"A/B 테스트 '{test_id}'가 삭제되었습니다.")
        )