"""
AI 모델 A/B 테스트 시스템

다양한 AI 모델의 성능을 비교하고 최적의 모델을 선택하는 시스템입니다.
"""

import logging
import random
import hashlib
import json
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
import statistics

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import models

logger = logging.getLogger(__name__)
User = get_user_model()


class TestStatus(Enum):
    """테스트 상태"""
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AllocationMethod(Enum):
    """할당 방법"""
    RANDOM = "random"
    USER_HASH = "user_hash"
    WEIGHTED = "weighted"
    FEATURE_BASED = "feature_based"


class MetricType(Enum):
    """메트릭 타입"""
    RESPONSE_TIME = "response_time"
    ACCURACY = "accuracy"
    USER_SATISFACTION = "user_satisfaction"
    TOKEN_USAGE = "token_usage"
    COST = "cost"
    ERROR_RATE = "error_rate"
    CONVERSION_RATE = "conversion_rate"


@dataclass
class AIModelConfig:
    """AI 모델 설정"""
    name: str
    provider: str  # openai, anthropic, together
    model_id: str  # gpt-3.5-turbo, claude-3, etc.
    parameters: Dict[str, Any]
    cost_per_token: float
    max_tokens: int
    temperature: float = 0.7
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TestVariant:
    """테스트 변형"""
    id: str
    name: str
    description: str
    model_config: AIModelConfig
    allocation_percentage: float
    is_control: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'model_config': self.model_config.to_dict(),
            'allocation_percentage': self.allocation_percentage,
            'is_control': self.is_control
        }


@dataclass
class TestMetric:
    """테스트 메트릭"""
    type: MetricType
    name: str
    description: str
    target_value: Optional[float] = None
    higher_is_better: bool = True
    weight: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.type.value,
            'name': self.name,
            'description': self.description,
            'target_value': self.target_value,
            'higher_is_better': self.higher_is_better,
            'weight': self.weight
        }


@dataclass
class TestResult:
    """테스트 결과"""
    variant_id: str
    user_id: int
    session_id: str
    metrics: Dict[str, float]
    metadata: Dict[str, Any]
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'variant_id': self.variant_id,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'metrics': self.metrics,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat()
        }


class ABTest:
    """A/B 테스트 클래스"""
    
    def __init__(self, test_id: str, name: str, description: str):
        self.test_id = test_id
        self.name = name
        self.description = description
        self.status = TestStatus.DRAFT
        self.variants: List[TestVariant] = []
        self.metrics: List[TestMetric] = []
        self.allocation_method = AllocationMethod.USER_HASH
        self.traffic_percentage = 100.0
        self.created_at = timezone.now()
        self.started_at: Optional[datetime] = None
        self.ended_at: Optional[datetime] = None
        self.target_users = None
        self.exclusion_criteria = []
        
        # 통계적 유의성 설정
        self.confidence_level = 0.95
        self.minimum_sample_size = 100
        self.minimum_effect_size = 0.05
        
        # 안전 장치
        self.auto_pause_on_error_rate = 0.1
        self.max_duration_days = 30
    
    def add_variant(self, variant: TestVariant):
        """변형 추가"""
        self.variants.append(variant)
        logger.info(f"Added variant {variant.id} to test {self.test_id}")
    
    def add_metric(self, metric: TestMetric):
        """메트릭 추가"""
        self.metrics.append(metric)
        logger.info(f"Added metric {metric.name} to test {self.test_id}")
    
    def start_test(self):
        """테스트 시작"""
        if self.status != TestStatus.DRAFT:
            raise ValueError(f"Cannot start test in {self.status.value} status")
        
        # 유효성 검사
        self._validate_test_configuration()
        
        self.status = TestStatus.RUNNING
        self.started_at = timezone.now()
        
        # 테스트 설정 저장
        self._save_test_configuration()
        
        logger.info(f"Started A/B test {self.test_id}")
    
    def pause_test(self):
        """테스트 일시정지"""
        if self.status != TestStatus.RUNNING:
            raise ValueError(f"Cannot pause test in {self.status.value} status")
        
        self.status = TestStatus.PAUSED
        logger.info(f"Paused A/B test {self.test_id}")
    
    def resume_test(self):
        """테스트 재개"""
        if self.status != TestStatus.PAUSED:
            raise ValueError(f"Cannot resume test in {self.status.value} status")
        
        self.status = TestStatus.RUNNING
        logger.info(f"Resumed A/B test {self.test_id}")
    
    def end_test(self):
        """테스트 종료"""
        if self.status not in [TestStatus.RUNNING, TestStatus.PAUSED]:
            raise ValueError(f"Cannot end test in {self.status.value} status")
        
        self.status = TestStatus.COMPLETED
        self.ended_at = timezone.now()
        
        # 최종 결과 생성
        final_results = self.generate_final_results()
        
        logger.info(f"Ended A/B test {self.test_id}")
        return final_results
    
    def allocate_user_to_variant(self, user_id: int) -> Optional[TestVariant]:
        """사용자를 변형에 할당"""
        if self.status != TestStatus.RUNNING:
            return None
        
        # 트래픽 비율 확인
        if not self._should_include_user_in_test(user_id):
            return None
        
        # 제외 기준 확인
        if self._is_user_excluded(user_id):
            return None
        
        # 기존 할당 확인
        existing_variant = self._get_user_existing_allocation(user_id)
        if existing_variant:
            return existing_variant
        
        # 새로운 할당
        variant = self._allocate_user_to_new_variant(user_id)
        if variant:
            self._save_user_allocation(user_id, variant)
        
        return variant
    
    def record_result(self, result: TestResult):
        """테스트 결과 기록"""
        if self.status != TestStatus.RUNNING:
            logger.warning(f"Recording result for non-running test {self.test_id}")
            return
        
        # 결과 유효성 검사
        if not self._validate_result(result):
            logger.error(f"Invalid result for test {self.test_id}")
            return
        
        # 결과 저장
        self._save_test_result(result)
        
        # 실시간 모니터링
        self._monitor_test_health(result)
        
        logger.info(f"Recorded result for test {self.test_id}, variant {result.variant_id}")
    
    def get_user_variant(self, user_id: int) -> Optional[TestVariant]:
        """사용자의 할당된 변형 조회"""
        cache_key = f"ab_test_allocation:{self.test_id}:{user_id}"
        variant_id = cache.get(cache_key)
        
        if variant_id:
            return self._get_variant_by_id(variant_id)
        
        return None
    
    def generate_results_report(self) -> Dict[str, Any]:
        """결과 리포트 생성"""
        results = self._collect_test_results()
        
        if not results:
            return {
                'test_id': self.test_id,
                'status': 'no_data',
                'message': '충분한 데이터가 없습니다.'
            }
        
        # 변형별 통계 계산
        variant_stats = {}
        for variant in self.variants:
            variant_results = [r for r in results if r.variant_id == variant.id]
            variant_stats[variant.id] = self._calculate_variant_statistics(variant_results)
        
        # 통계적 유의성 테스트
        significance_tests = self._perform_significance_tests(variant_stats)
        
        # 권장사항 생성
        recommendations = self._generate_recommendations(variant_stats, significance_tests)
        
        return {
            'test_id': self.test_id,
            'test_name': self.name,
            'status': self.status.value,
            'duration_days': self._get_test_duration_days(),
            'total_users': len(set(r.user_id for r in results)),
            'total_sessions': len(results),
            'variant_statistics': variant_stats,
            'significance_tests': significance_tests,
            'recommendations': recommendations,
            'generated_at': timezone.now().isoformat()
        }
    
    def generate_final_results(self) -> Dict[str, Any]:
        """최종 결과 생성"""
        report = self.generate_results_report()
        
        # 승자 결정
        winner = self._determine_winner(report.get('variant_statistics', {}))
        
        # 비즈니스 임팩트 계산
        business_impact = self._calculate_business_impact(report.get('variant_statistics', {}))
        
        report.update({
            'winner': winner,
            'business_impact': business_impact,
            'final_recommendation': self._generate_final_recommendation(winner, business_impact)
        })
        
        # 최종 결과 저장
        self._save_final_results(report)
        
        return report
    
    def _validate_test_configuration(self):
        """테스트 설정 유효성 검사"""
        if not self.variants:
            raise ValueError("At least one variant is required")
        
        if not self.metrics:
            raise ValueError("At least one metric is required")
        
        # 할당 비율 합계 확인
        total_allocation = sum(v.allocation_percentage for v in self.variants)
        if abs(total_allocation - 100.0) > 0.01:
            raise ValueError(f"Total allocation percentage must be 100%, got {total_allocation}%")
        
        # 컨트롤 그룹 확인
        control_variants = [v for v in self.variants if v.is_control]
        if len(control_variants) != 1:
            raise ValueError("Exactly one control variant is required")
    
    def _should_include_user_in_test(self, user_id: int) -> bool:
        """사용자를 테스트에 포함할지 결정"""
        if self.traffic_percentage >= 100.0:
            return True
        
        # 사용자 ID 기반 해시로 일관된 결과 보장
        user_hash = hashlib.md5(f"{self.test_id}:{user_id}".encode()).hexdigest()
        hash_value = int(user_hash[:8], 16) % 100
        
        return hash_value < self.traffic_percentage
    
    def _is_user_excluded(self, user_id: int) -> bool:
        """사용자 제외 여부 확인"""
        # 실제 구현에서는 제외 기준 로직 추가
        return False
    
    def _get_user_existing_allocation(self, user_id: int) -> Optional[TestVariant]:
        """사용자의 기존 할당 조회"""
        cache_key = f"ab_test_allocation:{self.test_id}:{user_id}"
        variant_id = cache.get(cache_key)
        
        if variant_id:
            return self._get_variant_by_id(variant_id)
        
        return None
    
    def _allocate_user_to_new_variant(self, user_id: int) -> Optional[TestVariant]:
        """사용자를 새로운 변형에 할당"""
        if self.allocation_method == AllocationMethod.USER_HASH:
            return self._allocate_by_user_hash(user_id)
        elif self.allocation_method == AllocationMethod.RANDOM:
            return self._allocate_randomly()
        elif self.allocation_method == AllocationMethod.WEIGHTED:
            return self._allocate_by_weight()
        else:
            return self._allocate_randomly()
    
    def _allocate_by_user_hash(self, user_id: int) -> TestVariant:
        """사용자 해시 기반 할당"""
        user_hash = hashlib.md5(f"{self.test_id}:{user_id}".encode()).hexdigest()
        hash_value = int(user_hash[:8], 16) % 100
        
        cumulative_percentage = 0.0
        for variant in self.variants:
            cumulative_percentage += variant.allocation_percentage
            if hash_value < cumulative_percentage:
                return variant
        
        return self.variants[-1]  # 마지막 변형으로 폴백
    
    def _allocate_randomly(self) -> TestVariant:
        """랜덤 할당"""
        rand_value = random.random() * 100
        
        cumulative_percentage = 0.0
        for variant in self.variants:
            cumulative_percentage += variant.allocation_percentage
            if rand_value < cumulative_percentage:
                return variant
        
        return self.variants[-1]
    
    def _allocate_by_weight(self) -> TestVariant:
        """가중치 기반 할당"""
        # 실제 구현에서는 동적 가중치 로직 추가
        return self._allocate_randomly()
    
    def _save_user_allocation(self, user_id: int, variant: TestVariant):
        """사용자 할당 저장"""
        cache_key = f"ab_test_allocation:{self.test_id}:{user_id}"
        cache.set(cache_key, variant.id, timeout=86400 * 30)  # 30일
        
        # 할당 로그 저장
        allocation_log = {
            'test_id': self.test_id,
            'user_id': user_id,
            'variant_id': variant.id,
            'allocated_at': timezone.now().isoformat()
        }
        
        allocations_key = f"ab_test_allocations:{self.test_id}"
        allocations = cache.get(allocations_key, [])
        allocations.append(allocation_log)
        cache.set(allocations_key, allocations[-10000:], timeout=86400 * 30)  # 최대 10000개
    
    def _get_variant_by_id(self, variant_id: str) -> Optional[TestVariant]:
        """ID로 변형 조회"""
        for variant in self.variants:
            if variant.id == variant_id:
                return variant
        return None
    
    def _validate_result(self, result: TestResult) -> bool:
        """결과 유효성 검사"""
        # 변형 ID 확인
        if not self._get_variant_by_id(result.variant_id):
            return False
        
        # 메트릭 확인
        expected_metrics = {metric.name for metric in self.metrics}
        result_metrics = set(result.metrics.keys())
        
        if not expected_metrics.issubset(result_metrics):
            return False
        
        return True
    
    def _save_test_result(self, result: TestResult):
        """테스트 결과 저장"""
        results_key = f"ab_test_results:{self.test_id}"
        results = cache.get(results_key, [])
        results.append(result.to_dict())
        cache.set(results_key, results[-100000:], timeout=86400 * 30)  # 최대 100000개
    
    def _monitor_test_health(self, result: TestResult):
        """테스트 상태 모니터링"""
        # 오류율 모니터링
        error_rate = self._calculate_current_error_rate(result.variant_id)
        if error_rate > self.auto_pause_on_error_rate:
            logger.warning(f"High error rate detected for variant {result.variant_id}: {error_rate}")
            self.pause_test()
        
        # 최대 기간 확인
        if self.started_at and (timezone.now() - self.started_at).days > self.max_duration_days:
            logger.info(f"Test {self.test_id} reached maximum duration")
            self.end_test()
    
    def _calculate_current_error_rate(self, variant_id: str) -> float:
        """현재 오류율 계산"""
        # 실제 구현에서는 최근 결과 기반으로 계산
        return 0.0
    
    def _collect_test_results(self) -> List[TestResult]:
        """테스트 결과 수집"""
        results_key = f"ab_test_results:{self.test_id}"
        results_data = cache.get(results_key, [])
        
        results = []
        for data in results_data:
            result = TestResult(
                variant_id=data['variant_id'],
                user_id=data['user_id'],
                session_id=data['session_id'],
                metrics=data['metrics'],
                metadata=data['metadata'],
                timestamp=datetime.fromisoformat(data['timestamp'])
            )
            results.append(result)
        
        return results
    
    def _calculate_variant_statistics(self, results: List[TestResult]) -> Dict[str, Any]:
        """변형별 통계 계산"""
        if not results:
            return {'sample_size': 0}
        
        stats = {
            'sample_size': len(results),
            'metrics': {}
        }
        
        # 메트릭별 통계
        for metric in self.metrics:
            metric_values = [r.metrics.get(metric.name, 0) for r in results if metric.name in r.metrics]
            
            if metric_values:
                stats['metrics'][metric.name] = {
                    'mean': statistics.mean(metric_values),
                    'median': statistics.median(metric_values),
                    'std_dev': statistics.stdev(metric_values) if len(metric_values) > 1 else 0,
                    'min': min(metric_values),
                    'max': max(metric_values),
                    'count': len(metric_values)
                }
        
        return stats
    
    def _perform_significance_tests(self, variant_stats: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """통계적 유의성 테스트"""
        # 실제 구현에서는 t-test, chi-square test 등 수행
        significance_tests = {}
        
        control_variant = next((v for v in self.variants if v.is_control), None)
        if not control_variant:
            return significance_tests
        
        control_stats = variant_stats.get(control_variant.id, {})
        
        for variant in self.variants:
            if variant.is_control:
                continue
            
            variant_stat = variant_stats.get(variant.id, {})
            
            # 간단한 유의성 테스트 시뮬레이션
            significance_tests[variant.id] = {
                'p_value': 0.05,  # 실제로는 계산
                'is_significant': True,  # 실제로는 p_value < 0.05
                'confidence_interval': [0.95, 1.05],  # 실제로는 계산
                'effect_size': 0.1  # 실제로는 계산
            }
        
        return significance_tests
    
    def _generate_recommendations(self, variant_stats: Dict[str, Dict[str, Any]], 
                                significance_tests: Dict[str, Any]) -> List[str]:
        """권장사항 생성"""
        recommendations = []
        
        # 샘플 크기 확인
        total_samples = sum(stats.get('sample_size', 0) for stats in variant_stats.values())
        if total_samples < self.minimum_sample_size:
            recommendations.append(f"더 많은 데이터가 필요합니다. (현재: {total_samples}, 최소: {self.minimum_sample_size})")
        
        # 유의성 확인
        significant_variants = [vid for vid, test in significance_tests.items() if test.get('is_significant', False)]
        if not significant_variants:
            recommendations.append("통계적으로 유의한 차이가 발견되지 않았습니다.")
        
        # 성능 개선 확인
        control_variant = next((v for v in self.variants if v.is_control), None)
        if control_variant:
            for variant in self.variants:
                if variant.is_control:
                    continue
                
                # 주요 메트릭 비교
                if self._is_variant_better(variant.id, control_variant.id, variant_stats):
                    recommendations.append(f"변형 {variant.name}이 컨트롤보다 우수한 성능을 보입니다.")
        
        return recommendations
    
    def _determine_winner(self, variant_stats: Dict[str, Dict[str, Any]]) -> Optional[str]:
        """승자 결정"""
        if not variant_stats:
            return None
        
        # 가중치 기반 점수 계산
        variant_scores = {}
        
        for variant in self.variants:
            stats = variant_stats.get(variant.id, {})
            if stats.get('sample_size', 0) < self.minimum_sample_size:
                continue
            
            score = 0.0
            for metric in self.metrics:
                metric_stats = stats.get('metrics', {}).get(metric.name, {})
                metric_value = metric_stats.get('mean', 0)
                
                # 정규화 및 가중치 적용
                normalized_value = self._normalize_metric_value(metric, metric_value)
                weighted_value = normalized_value * metric.weight
                
                if metric.higher_is_better:
                    score += weighted_value
                else:
                    score -= weighted_value
            
            variant_scores[variant.id] = score
        
        if not variant_scores:
            return None
        
        return max(variant_scores, key=variant_scores.get)
    
    def _normalize_metric_value(self, metric: TestMetric, value: float) -> float:
        """메트릭 값 정규화"""
        # 실제 구현에서는 더 정교한 정규화 로직
        return value
    
    def _is_variant_better(self, variant_id: str, control_id: str, 
                          variant_stats: Dict[str, Dict[str, Any]]) -> bool:
        """변형이 컨트롤보다 나은지 확인"""
        variant_stats_data = variant_stats.get(variant_id, {})
        control_stats_data = variant_stats.get(control_id, {})
        
        for metric in self.metrics:
            variant_metric = variant_stats_data.get('metrics', {}).get(metric.name, {})
            control_metric = control_stats_data.get('metrics', {}).get(metric.name, {})
            
            variant_value = variant_metric.get('mean', 0)
            control_value = control_metric.get('mean', 0)
            
            if metric.higher_is_better:
                if variant_value > control_value * (1 + self.minimum_effect_size):
                    return True
            else:
                if variant_value < control_value * (1 - self.minimum_effect_size):
                    return True
        
        return False
    
    def _calculate_business_impact(self, variant_stats: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """비즈니스 임팩트 계산"""
        # 실제 구현에서는 비즈니스 메트릭 기반 계산
        return {
            'estimated_revenue_impact': 0.0,
            'cost_savings': 0.0,
            'user_experience_improvement': 0.0
        }
    
    def _generate_final_recommendation(self, winner: Optional[str], 
                                     business_impact: Dict[str, Any]) -> str:
        """최종 권장사항 생성"""
        if not winner:
            return "충분한 데이터가 없어 권장사항을 제공할 수 없습니다."
        
        winner_variant = self._get_variant_by_id(winner)
        if not winner_variant:
            return "승자 변형을 찾을 수 없습니다."
        
        if winner_variant.is_control:
            return "현재 모델을 계속 사용하는 것을 권장합니다."
        else:
            return f"변형 '{winner_variant.name}'으로 전환하는 것을 권장합니다."
    
    def _get_test_duration_days(self) -> float:
        """테스트 기간 (일) 계산"""
        if not self.started_at:
            return 0.0
        
        end_time = self.ended_at or timezone.now()
        duration = end_time - self.started_at
        return duration.total_seconds() / 86400
    
    def _save_test_configuration(self):
        """테스트 설정 저장"""
        config = {
            'test_id': self.test_id,
            'name': self.name,
            'description': self.description,
            'status': self.status.value,
            'variants': [v.to_dict() for v in self.variants],
            'metrics': [m.to_dict() for m in self.metrics],
            'allocation_method': self.allocation_method.value,
            'traffic_percentage': self.traffic_percentage,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None
        }
        
        cache_key = f"ab_test_config:{self.test_id}"
        cache.set(cache_key, config, timeout=86400 * 30)
    
    def _save_final_results(self, results: Dict[str, Any]):
        """최종 결과 저장"""
        cache_key = f"ab_test_final_results:{self.test_id}"
        cache.set(cache_key, results, timeout=86400 * 365)  # 1년
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'test_id': self.test_id,
            'name': self.name,
            'description': self.description,
            'status': self.status.value,
            'variants': [v.to_dict() for v in self.variants],
            'metrics': [m.to_dict() for m in self.metrics],
            'allocation_method': self.allocation_method.value,
            'traffic_percentage': self.traffic_percentage,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'ended_at': self.ended_at.isoformat() if self.ended_at else None
        }


class ABTestManager:
    """A/B 테스트 관리자"""
    
    def __init__(self):
        self.active_tests: Dict[str, ABTest] = {}
        self._load_active_tests()
    
    def create_test(self, test_id: str, name: str, description: str) -> ABTest:
        """새 테스트 생성"""
        if test_id in self.active_tests:
            raise ValueError(f"Test {test_id} already exists")
        
        test = ABTest(test_id, name, description)
        self.active_tests[test_id] = test
        
        logger.info(f"Created A/B test {test_id}")
        return test
    
    def get_test(self, test_id: str) -> Optional[ABTest]:
        """테스트 조회"""
        return self.active_tests.get(test_id)
    
    def list_tests(self) -> List[ABTest]:
        """테스트 목록"""
        return list(self.active_tests.values())
    
    def get_user_variant_for_test(self, test_id: str, user_id: int) -> Optional[TestVariant]:
        """사용자의 테스트 변형 조회"""
        test = self.get_test(test_id)
        if not test:
            return None
        
        return test.allocate_user_to_variant(user_id)
    
    def record_test_result(self, test_id: str, result: TestResult):
        """테스트 결과 기록"""
        test = self.get_test(test_id)
        if test:
            test.record_result(result)
    
    def _load_active_tests(self):
        """활성 테스트 로드"""
        # 실제 구현에서는 데이터베이스나 캐시에서 로드
        pass


# 전역 A/B 테스트 관리자
ab_test_manager = ABTestManager()


# 편의 함수들
def create_ab_test(test_id: str, name: str, description: str) -> ABTest:
    """A/B 테스트 생성"""
    return ab_test_manager.create_test(test_id, name, description)


def get_user_ai_model_variant(test_id: str, user_id: int) -> Optional[AIModelConfig]:
    """사용자의 AI 모델 변형 조회"""
    variant = ab_test_manager.get_user_variant_for_test(test_id, user_id)
    if variant:
        return variant.model_config
    return None


def record_ai_model_result(test_id: str, user_id: int, session_id: str, 
                          variant_id: str, metrics: Dict[str, float], 
                          metadata: Dict[str, Any] = None):
    """AI 모델 결과 기록"""
    result = TestResult(
        variant_id=variant_id,
        user_id=user_id,
        session_id=session_id,
        metrics=metrics,
        metadata=metadata or {},
        timestamp=timezone.now()
    )
    
    ab_test_manager.record_test_result(test_id, result)