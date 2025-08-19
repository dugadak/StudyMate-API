"""
A/B 테스트 생성을 위한 Django 관리 명령어

사용법:
python manage.py create_ab_test --test-id ai_summary_v2 --name "AI 요약 성능 테스트" --control-model gpt-3.5-turbo --test-model gpt-4
"""

import json
from django.core.management.base import BaseCommand, CommandError
from studymate_api.ab_testing import (
    ab_test_manager, ABTest, TestVariant, TestMetric, AIModelConfig,
    AllocationMethod, MetricType
)


class Command(BaseCommand):
    help = 'A/B 테스트를 생성합니다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-id',
            type=str,
            required=True,
            help='A/B 테스트 ID'
        )
        parser.add_argument(
            '--name',
            type=str,
            required=True,
            help='A/B 테스트 이름'
        )
        parser.add_argument(
            '--description',
            type=str,
            default='',
            help='A/B 테스트 설명'
        )
        parser.add_argument(
            '--control-model',
            type=str,
            default='gpt-3.5-turbo',
            help='컨트롤 그룹 AI 모델'
        )
        parser.add_argument(
            '--test-model',
            type=str,
            default='gpt-4',
            help='테스트 그룹 AI 모델'
        )
        parser.add_argument(
            '--allocation',
            type=str,
            default='50:50',
            help='할당 비율 (예: 50:50, 70:30)'
        )
        parser.add_argument(
            '--traffic-percentage',
            type=float,
            default=100.0,
            help='테스트에 포함할 트래픽 비율 (0-100)'
        )
        parser.add_argument(
            '--start-immediately',
            action='store_true',
            help='테스트를 즉시 시작'
        )

    def handle(self, *args, **options):
        try:
            # A/B 테스트 생성
            test = ab_test_manager.create_test(
                test_id=options['test_id'],
                name=options['name'],
                description=options['description']
            )

            # 할당 비율 파싱
            allocation_parts = options['allocation'].split(':')
            if len(allocation_parts) != 2:
                raise CommandError("할당 비율은 '50:50' 형식이어야 합니다")
            
            control_percentage = float(allocation_parts[0])
            test_percentage = float(allocation_parts[1])
            
            if control_percentage + test_percentage != 100:
                raise CommandError("할당 비율의 합은 100이어야 합니다")

            # 컨트롤 변형 추가
            control_config = self._create_model_config(
                f"control_{options['control_model']}", 
                options['control_model']
            )
            control_variant = TestVariant(
                id='control',
                name='컨트롤 그룹',
                description=f"{options['control_model']} 기반 컨트롤 그룹",
                model_config=control_config,
                allocation_percentage=control_percentage,
                is_control=True
            )
            test.add_variant(control_variant)

            # 테스트 변형 추가
            test_config = self._create_model_config(
                f"test_{options['test_model']}", 
                options['test_model']
            )
            test_variant = TestVariant(
                id='test',
                name='테스트 그룹',
                description=f"{options['test_model']} 기반 테스트 그룹",
                model_config=test_config,
                allocation_percentage=test_percentage,
                is_control=False
            )
            test.add_variant(test_variant)

            # 기본 메트릭 추가
            metrics = [
                TestMetric(
                    type=MetricType.RESPONSE_TIME,
                    name='response_time',
                    description='응답 시간 (밀리초)',
                    target_value=2000.0,
                    higher_is_better=False,
                    weight=0.3
                ),
                TestMetric(
                    type=MetricType.USER_SATISFACTION,
                    name='user_satisfaction',
                    description='사용자 만족도 (0-1)',
                    target_value=0.8,
                    higher_is_better=True,
                    weight=0.4
                ),
                TestMetric(
                    type=MetricType.ACCURACY,
                    name='quality_score',
                    description='콘텐츠 품질 점수 (0-1)',
                    target_value=0.7,
                    higher_is_better=True,
                    weight=0.3
                )
            ]

            for metric in metrics:
                test.add_metric(metric)

            # 테스트 설정
            test.traffic_percentage = options['traffic_percentage']
            test.allocation_method = AllocationMethod.USER_HASH

            # 즉시 시작 옵션
            if options['start_immediately']:
                test.start_test()
                self.stdout.write(
                    self.style.SUCCESS(f"A/B 테스트 '{options['test_id']}'가 생성되고 시작되었습니다.")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"A/B 테스트 '{options['test_id']}'가 생성되었습니다.")
                )

            # 테스트 정보 출력
            self.stdout.write(f"테스트 ID: {test.test_id}")
            self.stdout.write(f"테스트 이름: {test.name}")
            self.stdout.write(f"변형 수: {len(test.variants)}")
            self.stdout.write(f"메트릭 수: {len(test.metrics)}")
            self.stdout.write(f"할당 비율: {options['allocation']}")
            self.stdout.write(f"트래픽 비율: {options['traffic_percentage']}%")

        except Exception as e:
            raise CommandError(f"A/B 테스트 생성 실패: {str(e)}")

    def _create_model_config(self, name: str, model_id: str) -> AIModelConfig:
        """AI 모델 설정 생성"""
        # 모델별 기본 설정
        model_configs = {
            'gpt-3.5-turbo': {
                'provider': 'openai',
                'cost_per_token': 0.000002,
                'max_tokens': 2000,
                'temperature': 0.7
            },
            'gpt-4': {
                'provider': 'openai',
                'cost_per_token': 0.00003,
                'max_tokens': 2000,
                'temperature': 0.7
            },
            'claude-3': {
                'provider': 'anthropic',
                'cost_per_token': 0.000015,
                'max_tokens': 2000,
                'temperature': 0.7
            },
            'claude-3.5-sonnet': {
                'provider': 'anthropic',
                'cost_per_token': 0.000015,
                'max_tokens': 4000,
                'temperature': 0.7
            }
        }

        config = model_configs.get(model_id, model_configs['gpt-3.5-turbo'])
        
        return AIModelConfig(
            name=name,
            provider=config['provider'],
            model_id=model_id,
            parameters={
                'temperature': config['temperature'],
                'max_tokens': config['max_tokens']
            },
            cost_per_token=config['cost_per_token'],
            max_tokens=config['max_tokens'],
            temperature=config['temperature']
        )