"""
Study 앱의 A/B 테스트 통합

AI 요약 생성 및 퀴즈 생성에서 A/B 테스트를 적용합니다.
"""

import logging
import time
from typing import Dict, Any, Optional, Tuple
from django.conf import settings
from django.contrib.auth import get_user_model

from studymate_api.ab_testing import (
    ab_test_manager, get_user_ai_model_variant, record_ai_model_result,
    AIModelConfig, TestResult
)
from .tracing_decorators import trace_ai_generation

logger = logging.getLogger(__name__)
User = get_user_model()


class AIModelABTestMixin:
    """AI 모델 A/B 테스트 믹스인"""
    
    def __init__(self):
        self.ab_testing_enabled = getattr(settings, 'AB_TESTING_ENABLED', True)
        
        # 기본 테스트 설정
        self.default_tests = {
            'ai_summary_generation': 'ai_summary_test_v1',
            'ai_quiz_generation': 'ai_quiz_test_v1',
            'ai_explanation_generation': 'ai_explanation_test_v1'
        }
    
    def get_ai_model_for_user(self, user_id: int, operation: str) -> Optional[AIModelConfig]:
        """사용자를 위한 AI 모델 선택"""
        if not self.ab_testing_enabled:
            return self._get_default_model_config(operation)
        
        test_id = self.default_tests.get(operation)
        if not test_id:
            return self._get_default_model_config(operation)
        
        # A/B 테스트에서 변형 조회
        variant_config = get_user_ai_model_variant(test_id, user_id)
        if variant_config:
            logger.info(f"Using A/B test variant for user {user_id}, operation {operation}")
            return variant_config
        
        # 폴백: 기본 모델
        return self._get_default_model_config(operation)
    
    def record_ai_operation_result(self, user_id: int, operation: str, 
                                 variant_id: str, metrics: Dict[str, float],
                                 metadata: Dict[str, Any] = None):
        """AI 작업 결과 기록"""
        if not self.ab_testing_enabled:
            return
        
        test_id = self.default_tests.get(operation)
        if not test_id:
            return
        
        # 세션 ID 생성 (실제로는 요청에서 가져옴)
        session_id = f"session_{int(time.time())}"
        
        record_ai_model_result(
            test_id=test_id,
            user_id=user_id,
            session_id=session_id,
            variant_id=variant_id,
            metrics=metrics,
            metadata=metadata or {}
        )
        
        logger.info(f"Recorded A/B test result for user {user_id}, operation {operation}")
    
    def _get_default_model_config(self, operation: str) -> AIModelConfig:
        """기본 모델 설정 반환"""
        # AI 설정에서 기본 모델 조회
        ai_config = getattr(settings, 'AI_MODELS', {})
        openai_config = ai_config.get('openai', {})
        
        default_model = openai_config.get('default_model', 'gpt-3.5-turbo')
        model_config = openai_config.get('models', {}).get(default_model, {})
        
        return AIModelConfig(
            name=f"default_{operation}",
            provider="openai",
            model_id=default_model,
            parameters={
                "temperature": model_config.get('temperature', 0.7),
                "max_tokens": model_config.get('max_tokens', 2000)
            },
            cost_per_token=model_config.get('cost_per_1k_tokens', 0.002) / 1000,
            max_tokens=model_config.get('max_tokens', 2000),
            temperature=model_config.get('temperature', 0.7)
        )


class StudyABTestService(AIModelABTestMixin):
    """학습 관련 A/B 테스트 서비스"""
    
    @trace_ai_generation("ab_test", "various")
    def generate_summary_with_ab_test(self, user_id: int, text: str, 
                                    subject_id: int) -> Tuple[str, Dict[str, Any]]:
        """A/B 테스트를 적용한 요약 생성"""
        start_time = time.time()
        
        # 사용자를 위한 AI 모델 선택
        model_config = self.get_ai_model_for_user(user_id, 'ai_summary_generation')
        
        if not model_config:
            raise ValueError("No AI model configuration available")
        
        try:
            # AI 모델로 요약 생성
            summary_content = self._call_ai_model_for_summary(
                model_config, text, subject_id
            )
            
            # 성능 메트릭 계산
            response_time = (time.time() - start_time) * 1000  # ms
            
            # 품질 메트릭 (실제로는 더 정교한 계산)
            quality_score = self._calculate_summary_quality(summary_content, text)
            
            # A/B 테스트 결과 기록
            metrics = {
                'response_time': response_time,
                'quality_score': quality_score,
                'summary_length': len(summary_content),
                'compression_ratio': len(summary_content) / len(text),
                'user_satisfaction': 0.8  # 실제로는 사용자 피드백에서
            }
            
            metadata = {
                'model_provider': model_config.provider,
                'model_id': model_config.model_id,
                'subject_id': subject_id,
                'original_text_length': len(text),
                'temperature': model_config.temperature
            }
            
            self.record_ai_operation_result(
                user_id=user_id,
                operation='ai_summary_generation',
                variant_id=model_config.name,
                metrics=metrics,
                metadata=metadata
            )
            
            return summary_content, {
                'model_used': model_config.name,
                'response_time_ms': response_time,
                'quality_score': quality_score
            }
            
        except Exception as e:
            # 오류 메트릭 기록
            error_metrics = {
                'response_time': (time.time() - start_time) * 1000,
                'error_rate': 1.0,
                'success_rate': 0.0
            }
            
            self.record_ai_operation_result(
                user_id=user_id,
                operation='ai_summary_generation',
                variant_id=model_config.name,
                metrics=error_metrics,
                metadata={'error': str(e)}
            )
            
            raise
    
    @trace_ai_generation("ab_test", "various")
    def generate_quiz_with_ab_test(self, user_id: int, content: str, 
                                 difficulty: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """A/B 테스트를 적용한 퀴즈 생성"""
        start_time = time.time()
        
        # 사용자를 위한 AI 모델 선택
        model_config = self.get_ai_model_for_user(user_id, 'ai_quiz_generation')
        
        if not model_config:
            raise ValueError("No AI model configuration available")
        
        try:
            # AI 모델로 퀴즈 생성
            quiz_data = self._call_ai_model_for_quiz(
                model_config, content, difficulty
            )
            
            # 성능 메트릭 계산
            response_time = (time.time() - start_time) * 1000  # ms
            
            # 품질 메트릭
            question_count = len(quiz_data.get('questions', []))
            diversity_score = self._calculate_quiz_diversity(quiz_data)
            
            # A/B 테스트 결과 기록
            metrics = {
                'response_time': response_time,
                'question_count': question_count,
                'diversity_score': diversity_score,
                'difficulty_accuracy': self._calculate_difficulty_accuracy(quiz_data, difficulty),
                'format_compliance': 1.0  # JSON 형식 준수 여부
            }
            
            metadata = {
                'model_provider': model_config.provider,
                'model_id': model_config.model_id,
                'target_difficulty': difficulty,
                'content_length': len(content),
                'temperature': model_config.temperature
            }
            
            self.record_ai_operation_result(
                user_id=user_id,
                operation='ai_quiz_generation',
                variant_id=model_config.name,
                metrics=metrics,
                metadata=metadata
            )
            
            return quiz_data, {
                'model_used': model_config.name,
                'response_time_ms': response_time,
                'question_count': question_count,
                'diversity_score': diversity_score
            }
            
        except Exception as e:
            # 오류 메트릭 기록
            error_metrics = {
                'response_time': (time.time() - start_time) * 1000,
                'error_rate': 1.0,
                'success_rate': 0.0,
                'question_count': 0
            }
            
            self.record_ai_operation_result(
                user_id=user_id,
                operation='ai_quiz_generation',
                variant_id=model_config.name,
                metrics=error_metrics,
                metadata={'error': str(e)}
            )
            
            raise
    
    def _call_ai_model_for_summary(self, model_config: AIModelConfig, 
                                 text: str, subject_id: int) -> str:
        """AI 모델로 요약 생성"""
        # 실제 구현에서는 model_config에 따라 적절한 AI 클라이언트 사용
        
        if model_config.provider == "openai":
            return self._call_openai_for_summary(model_config, text)
        elif model_config.provider == "anthropic":
            return self._call_anthropic_for_summary(model_config, text)
        elif model_config.provider == "together":
            return self._call_together_for_summary(model_config, text)
        else:
            raise ValueError(f"Unsupported AI provider: {model_config.provider}")
    
    def _call_ai_model_for_quiz(self, model_config: AIModelConfig, 
                              content: str, difficulty: str) -> Dict[str, Any]:
        """AI 모델로 퀴즈 생성"""
        # 실제 구현에서는 model_config에 따라 적절한 AI 클라이언트 사용
        
        if model_config.provider == "openai":
            return self._call_openai_for_quiz(model_config, content, difficulty)
        elif model_config.provider == "anthropic":
            return self._call_anthropic_for_quiz(model_config, content, difficulty)
        elif model_config.provider == "together":
            return self._call_together_for_quiz(model_config, content, difficulty)
        else:
            raise ValueError(f"Unsupported AI provider: {model_config.provider}")
    
    def _call_openai_for_summary(self, model_config: AIModelConfig, text: str) -> str:
        """OpenAI로 요약 생성"""
        # 기존 OpenAI 호출 로직 사용
        # 실제로는 study/services.py의 _generate_with_openai 참조
        return f"OpenAI 요약: {text[:100]}..."
    
    def _call_anthropic_for_summary(self, model_config: AIModelConfig, text: str) -> str:
        """Anthropic으로 요약 생성"""
        # Anthropic Claude 호출 로직
        return f"Claude 요약: {text[:100]}..."
    
    def _call_together_for_summary(self, model_config: AIModelConfig, text: str) -> str:
        """Together AI로 요약 생성"""
        # Together AI 호출 로직
        return f"Together 요약: {text[:100]}..."
    
    def _call_openai_for_quiz(self, model_config: AIModelConfig, 
                            content: str, difficulty: str) -> Dict[str, Any]:
        """OpenAI로 퀴즈 생성"""
        return {
            "questions": [
                {
                    "question": "OpenAI 생성 문제 1",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": "A",
                    "difficulty": difficulty
                }
            ]
        }
    
    def _call_anthropic_for_quiz(self, model_config: AIModelConfig, 
                               content: str, difficulty: str) -> Dict[str, Any]:
        """Anthropic으로 퀴즈 생성"""
        return {
            "questions": [
                {
                    "question": "Claude 생성 문제 1",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": "B",
                    "difficulty": difficulty
                }
            ]
        }
    
    def _call_together_for_quiz(self, model_config: AIModelConfig, 
                              content: str, difficulty: str) -> Dict[str, Any]:
        """Together AI로 퀴즈 생성"""
        return {
            "questions": [
                {
                    "question": "Together 생성 문제 1",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": "C",
                    "difficulty": difficulty
                }
            ]
        }
    
    def _calculate_summary_quality(self, summary: str, original_text: str) -> float:
        """요약 품질 점수 계산"""
        # 실제 구현에서는 더 정교한 품질 측정
        # - 내용 보존도
        # - 간결성
        # - 가독성
        # - 핵심 정보 포함 여부
        
        compression_ratio = len(summary) / len(original_text)
        
        # 적절한 압축 비율 (10-30%)에 따른 품질 점수
        if 0.1 <= compression_ratio <= 0.3:
            quality_score = 0.9
        elif 0.05 <= compression_ratio <= 0.5:
            quality_score = 0.7
        else:
            quality_score = 0.5
        
        return quality_score
    
    def _calculate_quiz_diversity(self, quiz_data: Dict[str, Any]) -> float:
        """퀴즈 다양성 점수 계산"""
        questions = quiz_data.get('questions', [])
        if not questions:
            return 0.0
        
        # 문제 유형 다양성, 답안 분포 등 고려
        # 실제로는 더 정교한 다양성 측정
        
        # 간단한 다양성 계산: 정답 분포
        correct_answers = [q.get('correct_answer', '') for q in questions]
        unique_answers = set(correct_answers)
        
        if len(questions) == 0:
            return 0.0
        
        diversity_score = len(unique_answers) / min(len(questions), 4)  # 최대 4개 선택지
        return min(diversity_score, 1.0)
    
    def _calculate_difficulty_accuracy(self, quiz_data: Dict[str, Any], 
                                     target_difficulty: str) -> float:
        """난이도 정확도 계산"""
        questions = quiz_data.get('questions', [])
        if not questions:
            return 0.0
        
        # 실제로는 문제 복잡도, 어휘 수준 등을 분석
        # 여기서는 간단히 난이도 일치 여부만 확인
        
        matching_count = sum(
            1 for q in questions 
            if q.get('difficulty', '').lower() == target_difficulty.lower()
        )
        
        return matching_count / len(questions)


# 전역 서비스 인스턴스
study_ab_test_service = StudyABTestService()


# 편의 함수들
def generate_summary_with_ab_test(user_id: int, text: str, subject_id: int) -> Tuple[str, Dict[str, Any]]:
    """A/B 테스트를 적용한 요약 생성"""
    return study_ab_test_service.generate_summary_with_ab_test(user_id, text, subject_id)


def generate_quiz_with_ab_test(user_id: int, content: str, difficulty: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """A/B 테스트를 적용한 퀴즈 생성"""
    return study_ab_test_service.generate_quiz_with_ab_test(user_id, content, difficulty)


def record_user_feedback_for_ab_test(user_id: int, operation: str, 
                                    rating: float, feedback: str = ""):
    """사용자 피드백을 A/B 테스트 결과에 반영"""
    # 사용자 피드백을 별도 메트릭으로 기록
    test_service = StudyABTestService()
    
    # 현재 사용자의 변형 조회
    model_config = test_service.get_ai_model_for_user(user_id, operation)
    if not model_config:
        return
    
    # 피드백 메트릭 기록
    feedback_metrics = {
        'user_rating': rating,  # 1-5 점수
        'user_satisfaction': rating / 5.0,  # 0-1 정규화
        'feedback_provided': 1.0 if feedback else 0.0
    }
    
    feedback_metadata = {
        'feedback_text': feedback,
        'rating_scale': '1-5',
        'feedback_timestamp': time.time()
    }
    
    test_service.record_ai_operation_result(
        user_id=user_id,
        operation=f"{operation}_feedback",
        variant_id=model_config.name,
        metrics=feedback_metrics,
        metadata=feedback_metadata
    )