"""
A/B 테스트 관리 API 뷰

A/B 테스트 생성, 관리, 결과 조회 등의 API를 제공합니다.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from studymate_api.ab_testing import (
    ab_test_manager, ABTest, TestVariant, TestMetric, AIModelConfig,
    TestStatus, AllocationMethod, MetricType
)

logger = logging.getLogger(__name__)
User = get_user_model()


class AIModelConfigSerializer(serializers.Serializer):
    """AI 모델 설정 시리얼라이저"""
    name = serializers.CharField(max_length=100)
    provider = serializers.ChoiceField(choices=['openai', 'anthropic', 'together'])
    model_id = serializers.CharField(max_length=100)
    parameters = serializers.DictField()
    cost_per_token = serializers.FloatField()
    max_tokens = serializers.IntegerField()
    temperature = serializers.FloatField(default=0.7)


class TestVariantSerializer(serializers.Serializer):
    """테스트 변형 시리얼라이저"""
    id = serializers.CharField(max_length=50)
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(max_length=500)
    model_config = AIModelConfigSerializer()
    allocation_percentage = serializers.FloatField(min_value=0, max_value=100)
    is_control = serializers.BooleanField(default=False)


class TestMetricSerializer(serializers.Serializer):
    """테스트 메트릭 시리얼라이저"""
    type = serializers.ChoiceField(choices=[m.value for m in MetricType])
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(max_length=500)
    target_value = serializers.FloatField(required=False)
    higher_is_better = serializers.BooleanField(default=True)
    weight = serializers.FloatField(default=1.0)


class CreateABTestSerializer(serializers.Serializer):
    """A/B 테스트 생성 시리얼라이저"""
    test_id = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(max_length=1000)
    variants = TestVariantSerializer(many=True)
    metrics = TestMetricSerializer(many=True)
    allocation_method = serializers.ChoiceField(
        choices=[m.value for m in AllocationMethod],
        default=AllocationMethod.USER_HASH.value
    )
    traffic_percentage = serializers.FloatField(min_value=0, max_value=100, default=100)
    minimum_sample_size = serializers.IntegerField(default=100)
    confidence_level = serializers.FloatField(default=0.95)


class ABTestManagementView(APIView):
    """A/B 테스트 관리 API"""
    
    permission_classes = [IsAdminUser]
    
    def post(self, request):
        """새 A/B 테스트 생성"""
        serializer = CreateABTestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            data = serializer.validated_data
            
            # A/B 테스트 생성
            test = ab_test_manager.create_test(
                test_id=data['test_id'],
                name=data['name'],
                description=data['description']
            )
            
            # 변형 추가
            for variant_data in data['variants']:
                model_config = AIModelConfig(**variant_data['model_config'])
                variant = TestVariant(
                    id=variant_data['id'],
                    name=variant_data['name'],
                    description=variant_data['description'],
                    model_config=model_config,
                    allocation_percentage=variant_data['allocation_percentage'],
                    is_control=variant_data['is_control']
                )
                test.add_variant(variant)
            
            # 메트릭 추가
            for metric_data in data['metrics']:
                metric = TestMetric(
                    type=MetricType(metric_data['type']),
                    name=metric_data['name'],
                    description=metric_data['description'],
                    target_value=metric_data.get('target_value'),
                    higher_is_better=metric_data['higher_is_better'],
                    weight=metric_data['weight']
                )
                test.add_metric(metric)
            
            # 테스트 설정
            test.allocation_method = AllocationMethod(data['allocation_method'])
            test.traffic_percentage = data['traffic_percentage']
            test.minimum_sample_size = data['minimum_sample_size']
            test.confidence_level = data['confidence_level']
            
            logger.info(f"A/B test created: {test.test_id}")
            
            return Response({
                'message': 'A/B 테스트가 성공적으로 생성되었습니다.',
                'test_id': test.test_id,
                'status': test.status.value,
                'variants_count': len(test.variants),
                'metrics_count': len(test.metrics)
            }, status=status.HTTP_201_CREATED)
            
        except ValueError as e:
            return Response({
                'error': 'validation_error',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"A/B test creation error: {e}")
            return Response({
                'error': 'creation_failed',
                'message': 'A/B 테스트 생성 중 오류가 발생했습니다.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get(self, request):
        """A/B 테스트 목록 조회"""
        try:
            tests = ab_test_manager.list_tests()
            
            test_list = []
            for test in tests:
                test_info = {
                    'test_id': test.test_id,
                    'name': test.name,
                    'description': test.description,
                    'status': test.status.value,
                    'variants_count': len(test.variants),
                    'metrics_count': len(test.metrics),
                    'traffic_percentage': test.traffic_percentage,
                    'created_at': test.created_at.isoformat(),
                    'started_at': test.started_at.isoformat() if test.started_at else None,
                    'ended_at': test.ended_at.isoformat() if test.ended_at else None
                }
                
                # 실행 중인 테스트의 기본 통계
                if test.status == TestStatus.RUNNING:
                    test_info['duration_days'] = test._get_test_duration_days()
                
                test_list.append(test_info)
            
            return Response({
                'tests': test_list,
                'total_count': len(test_list)
            })
            
        except Exception as e:
            logger.error(f"A/B test list error: {e}")
            return Response({
                'error': 'list_failed',
                'message': 'A/B 테스트 목록 조회 중 오류가 발생했습니다.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ABTestDetailView(APIView):
    """A/B 테스트 상세 정보 API"""
    
    permission_classes = [IsAdminUser]
    
    def get(self, request, test_id):
        """A/B 테스트 상세 정보 조회"""
        try:
            test = ab_test_manager.get_test(test_id)
            if not test:
                return Response({
                    'error': 'test_not_found',
                    'message': '테스트를 찾을 수 없습니다.'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # 상세 정보 구성
            test_detail = test.to_dict()
            
            # 실시간 통계 추가
            if test.status == TestStatus.RUNNING:
                results_report = test.generate_results_report()
                test_detail['current_statistics'] = results_report
            
            return Response(test_detail)
            
        except Exception as e:
            logger.error(f"A/B test detail error: {e}")
            return Response({
                'error': 'detail_failed',
                'message': 'A/B 테스트 상세 정보 조회 중 오류가 발생했습니다.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def patch(self, request, test_id):
        """A/B 테스트 상태 변경"""
        try:
            test = ab_test_manager.get_test(test_id)
            if not test:
                return Response({
                    'error': 'test_not_found',
                    'message': '테스트를 찾을 수 없습니다.'
                }, status=status.HTTP_404_NOT_FOUND)
            
            action = request.data.get('action')
            
            if action == 'start':
                test.start_test()
                message = '테스트가 시작되었습니다.'
            elif action == 'pause':
                test.pause_test()
                message = '테스트가 일시정지되었습니다.'
            elif action == 'resume':
                test.resume_test()
                message = '테스트가 재개되었습니다.'
            elif action == 'end':
                final_results = test.end_test()
                return Response({
                    'message': '테스트가 종료되었습니다.',
                    'final_results': final_results
                })
            else:
                return Response({
                    'error': 'invalid_action',
                    'message': '유효하지 않은 액션입니다.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                'message': message,
                'test_id': test.test_id,
                'new_status': test.status.value
            })
            
        except ValueError as e:
            return Response({
                'error': 'action_failed',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"A/B test action error: {e}")
            return Response({
                'error': 'action_failed',
                'message': 'A/B 테스트 상태 변경 중 오류가 발생했습니다.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ABTestResultsView(APIView):
    """A/B 테스트 결과 API"""
    
    permission_classes = [IsAdminUser]
    
    def get(self, request, test_id):
        """A/B 테스트 결과 조회"""
        try:
            test = ab_test_manager.get_test(test_id)
            if not test:
                return Response({
                    'error': 'test_not_found',
                    'message': '테스트를 찾을 수 없습니다.'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # 결과 리포트 생성
            results_report = test.generate_results_report()
            
            return Response(results_report)
            
        except Exception as e:
            logger.error(f"A/B test results error: {e}")
            return Response({
                'error': 'results_failed',
                'message': 'A/B 테스트 결과 조회 중 오류가 발생했습니다.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserABTestView(APIView):
    """사용자 A/B 테스트 API"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """사용자의 A/B 테스트 할당 정보"""
        try:
            user_id = request.user.id
            user_tests = {}
            
            # 모든 활성 테스트에서 사용자 할당 확인
            for test in ab_test_manager.list_tests():
                if test.status == TestStatus.RUNNING:
                    variant = test.get_user_variant(user_id)
                    if variant:
                        user_tests[test.test_id] = {
                            'test_name': test.name,
                            'variant_id': variant.id,
                            'variant_name': variant.name,
                            'is_control': variant.is_control,
                            'model_provider': variant.model_config.provider,
                            'model_id': variant.model_config.model_id
                        }
            
            return Response({
                'user_id': user_id,
                'active_tests': user_tests,
                'total_tests': len(user_tests)
            })
            
        except Exception as e:
            logger.error(f"User A/B test info error: {e}")
            return Response({
                'error': 'user_info_failed',
                'message': '사용자 A/B 테스트 정보 조회 중 오류가 발생했습니다.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ABTestFeedbackView(APIView):
    """A/B 테스트 사용자 피드백 API"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """사용자 피드백 제출"""
        try:
            test_id = request.data.get('test_id')
            variant_id = request.data.get('variant_id')
            rating = request.data.get('rating')  # 1-5
            feedback_text = request.data.get('feedback', '')
            
            if not all([test_id, variant_id, rating]):
                return Response({
                    'error': 'missing_fields',
                    'message': '필수 필드가 누락되었습니다.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 테스트 존재 확인
            test = ab_test_manager.get_test(test_id)
            if not test:
                return Response({
                    'error': 'test_not_found',
                    'message': '테스트를 찾을 수 없습니다.'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # 사용자 할당 확인
            user_variant = test.get_user_variant(request.user.id)
            if not user_variant or user_variant.id != variant_id:
                return Response({
                    'error': 'variant_mismatch',
                    'message': '사용자에게 할당된 변형과 일치하지 않습니다.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 피드백을 A/B 테스트 시스템에 기록
            from study.ab_testing_integration import record_user_feedback_for_ab_test
            
            # 테스트 타입에 따른 operation 결정
            operation = 'ai_summary_generation'  # 기본값
            if 'quiz' in test.name.lower():
                operation = 'ai_quiz_generation'
            elif 'explanation' in test.name.lower():
                operation = 'ai_explanation_generation'
            
            record_user_feedback_for_ab_test(
                user_id=request.user.id,
                operation=operation,
                rating=float(rating),
                feedback=feedback_text
            )
            
            logger.info(f"User feedback recorded for test {test_id}, user {request.user.id}")
            
            return Response({
                'message': '피드백이 성공적으로 제출되었습니다.',
                'test_id': test_id,
                'variant_id': variant_id,
                'rating': rating
            })
            
        except Exception as e:
            logger.error(f"A/B test feedback error: {e}")
            return Response({
                'error': 'feedback_failed',
                'message': '피드백 제출 중 오류가 발생했습니다.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ABTestAnalyticsView(APIView):
    """A/B 테스트 분석 API"""
    
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        """전체 A/B 테스트 분석"""
        try:
            # 전체 테스트 통계
            all_tests = ab_test_manager.list_tests()
            
            total_tests = len(all_tests)
            running_tests = len([t for t in all_tests if t.status == TestStatus.RUNNING])
            completed_tests = len([t for t in all_tests if t.status == TestStatus.COMPLETED])
            
            # 최근 30일 테스트 활동
            recent_date = timezone.now() - timedelta(days=30)
            recent_tests = [t for t in all_tests if t.created_at >= recent_date]
            
            # 성과 요약
            performance_summary = self._calculate_performance_summary(all_tests)
            
            # 인기 있는 AI 모델
            popular_models = self._get_popular_models(all_tests)
            
            return Response({
                'summary': {
                    'total_tests': total_tests,
                    'running_tests': running_tests,
                    'completed_tests': completed_tests,
                    'recent_tests_30d': len(recent_tests)
                },
                'performance_summary': performance_summary,
                'popular_models': popular_models,
                'generated_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"A/B test analytics error: {e}")
            return Response({
                'error': 'analytics_failed',
                'message': 'A/B 테스트 분석 중 오류가 발생했습니다.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _calculate_performance_summary(self, tests: List[ABTest]) -> Dict[str, Any]:
        """성과 요약 계산"""
        completed_tests = [t for t in tests if t.status == TestStatus.COMPLETED]
        
        if not completed_tests:
            return {
                'total_completed': 0,
                'avg_duration_days': 0,
                'success_rate': 0
            }
        
        total_duration = sum(t._get_test_duration_days() for t in completed_tests)
        avg_duration = total_duration / len(completed_tests)
        
        # 성공률 (임의로 계산)
        successful_tests = len([t for t in completed_tests if len(t.variants) > 1])
        success_rate = successful_tests / len(completed_tests) if completed_tests else 0
        
        return {
            'total_completed': len(completed_tests),
            'avg_duration_days': round(avg_duration, 1),
            'success_rate': round(success_rate * 100, 1)
        }
    
    def _get_popular_models(self, tests: List[ABTest]) -> List[Dict[str, Any]]:
        """인기 있는 AI 모델 조회"""
        model_counts = {}
        
        for test in tests:
            for variant in test.variants:
                model_key = f"{variant.model_config.provider}:{variant.model_config.model_id}"
                model_counts[model_key] = model_counts.get(model_key, 0) + 1
        
        # 상위 5개 모델
        popular = sorted(model_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return [
            {
                'model': model_key,
                'usage_count': count,
                'provider': model_key.split(':')[0],
                'model_id': model_key.split(':')[1]
            }
            for model_key, count in popular
        ]