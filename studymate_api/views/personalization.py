"""
개인화 API 뷰

사용자별 맞춤 학습 분석 및 추천 API를 제공합니다.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from typing import Dict, Any
import logging

from studymate_api.personalization import (
    get_user_personalization_profile,
    get_personalized_content_recommendations,
    update_learning_pattern,
    get_adaptive_difficulty,
    LearningStyle,
    DifficultyLevel
)

logger = logging.getLogger(__name__)


class PersonalizationViewSet(viewsets.ViewSet):
    """개인화 API ViewSet"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        summary="사용자 학습 프로필 조회",
        description="사용자의 학습 스타일, 선호도, 강점/약점 등 개인화 프로필을 조회합니다.",
        responses={
            200: {
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer"},
                    "learning_style": {"type": "string", "enum": [style.value for style in LearningStyle]},
                    "confidence_score": {"type": "number", "format": "float"},
                    "preferred_difficulty": {"type": "string", "enum": [level.value for level in DifficultyLevel]},
                    "strengths": {"type": "array", "items": {"type": "string"}},
                    "weaknesses": {"type": "array", "items": {"type": "string"}},
                    "recommendations": {"type": "array", "items": {"type": "object"}},
                    "last_updated": {"type": "string", "format": "date-time"}
                }
            },
            404: {"description": "사용자를 찾을 수 없음"}
        }
    )
    @action(detail=False, methods=['get'])
    def profile(self, request):
        """사용자 개인화 프로필 조회"""
        try:
            profile = get_user_personalization_profile(request.user.id)
            
            return Response({
                'user_id': profile.user_id,
                'learning_style': profile.learning_style.value,
                'confidence_score': profile.confidence_score,
                'preferred_difficulty': profile.preferred_difficulty.value,
                'learning_goals': profile.learning_goals,
                'strengths': profile.strengths,
                'weaknesses': profile.weaknesses,
                'recommendations': profile.recommendations,
                'last_updated': profile.last_updated.isoformat(),
                'analysis_quality': self._get_analysis_quality(profile.confidence_score)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"개인화 프로필 조회 실패 - 사용자 {request.user.id}: {e}")
            return Response({
                'error': '프로필 조회 중 오류가 발생했습니다.',
                'error_type': 'system_error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        summary="맞춤형 콘텐츠 추천",
        description="사용자의 학습 스타일과 선호도를 기반으로 맞춤형 콘텐츠를 추천합니다.",
        parameters=[
            OpenApiParameter(
                name="subject_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="특정 과목으로 필터링 (선택사항)"
            ),
            OpenApiParameter(
                name="limit",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="추천 개수 제한 (기본값: 10)"
            )
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "recommendations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "content_id": {"type": "string"},
                                "content_type": {"type": "string"},
                                "title": {"type": "string"},
                                "description": {"type": "string"},
                                "difficulty": {"type": "string"},
                                "estimated_time": {"type": "integer"},
                                "relevance_score": {"type": "number"},
                                "personalization_reason": {"type": "string"},
                                "tags": {"type": "array", "items": {"type": "string"}}
                            }
                        }
                    },
                    "total_count": {"type": "integer"},
                    "personalization_info": {"type": "object"}
                }
            }
        }
    )
    @action(detail=False, methods=['get'])
    def recommendations(self, request):
        """맞춤형 콘텐츠 추천"""
        try:
            subject_id = request.query_params.get('subject_id')
            limit = int(request.query_params.get('limit', 10))
            
            if subject_id:
                subject_id = int(subject_id)
            
            recommendations = get_personalized_content_recommendations(
                request.user.id, subject_id, limit
            )
            
            # 사용자 프로필 정보도 함께 제공
            profile = get_user_personalization_profile(request.user.id)
            
            recommendation_data = []
            for rec in recommendations:
                recommendation_data.append({
                    'content_id': rec.content_id,
                    'content_type': rec.content_type.value,
                    'title': rec.title,
                    'description': rec.description,
                    'difficulty': rec.difficulty.value,
                    'estimated_time': rec.estimated_time,
                    'relevance_score': rec.relevance_score,
                    'personalization_reason': rec.personalization_reason,
                    'tags': rec.tags
                })
            
            return Response({
                'recommendations': recommendation_data,
                'total_count': len(recommendation_data),
                'personalization_info': {
                    'learning_style': profile.learning_style.value,
                    'confidence_score': profile.confidence_score,
                    'preferred_difficulty': profile.preferred_difficulty.value
                },
                'generated_at': timezone.now().isoformat()
            }, status=status.HTTP_200_OK)
            
        except ValueError as e:
            return Response({
                'error': '잘못된 매개변수입니다.',
                'error_type': 'validation_error',
                'details': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f"콘텐츠 추천 실패 - 사용자 {request.user.id}: {e}")
            return Response({
                'error': '추천 생성 중 오류가 발생했습니다.',
                'error_type': 'system_error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        summary="학습 패턴 업데이트",
        description="사용자의 새로운 학습 활동 데이터를 기반으로 학습 패턴을 업데이트합니다.",
        request={
            "type": "object",
            "properties": {
                "activity_type": {"type": "string", "description": "활동 유형"},
                "duration": {"type": "integer", "description": "활동 시간 (분)"},
                "completion_rate": {"type": "number", "description": "완성도 (0-1)"},
                "performance_score": {"type": "number", "description": "성과 점수 (0-1)"},
                "content_type": {"type": "string", "description": "콘텐츠 유형"},
                "difficulty": {"type": "string", "description": "난이도"}
            },
            "required": ["activity_type"]
        },
        responses={
            200: {"description": "학습 패턴 업데이트 완료"},
            400: {"description": "잘못된 요청 데이터"}
        }
    )
    @action(detail=False, methods=['post'])
    def update_pattern(self, request):
        """학습 패턴 업데이트"""
        try:
            activity_data = request.data
            
            # 기본 검증
            required_fields = ['activity_type']
            for field in required_fields:
                if field not in activity_data:
                    return Response({
                        'error': f'필수 필드가 누락되었습니다: {field}',
                        'error_type': 'validation_error'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # 사용자 ID 추가
            activity_data['user_id'] = request.user.id
            activity_data['timestamp'] = timezone.now().isoformat()
            
            # 학습 패턴 업데이트
            update_learning_pattern(request.user.id, activity_data)
            
            return Response({
                'message': '학습 패턴이 업데이트되었습니다.',
                'updated_at': timezone.now().isoformat()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"학습 패턴 업데이트 실패 - 사용자 {request.user.id}: {e}")
            return Response({
                'error': '학습 패턴 업데이트 중 오류가 발생했습니다.',
                'error_type': 'system_error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        summary="적응형 난이도 조회",
        description="사용자의 현재 성과를 기반으로 적응형 난이도를 계산합니다.",
        parameters=[
            OpenApiParameter(
                name="subject_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="과목 ID",
                required=True
            ),
            OpenApiParameter(
                name="current_performance",
                type=OpenApiTypes.NUMBER,
                location=OpenApiParameter.QUERY,
                description="현재 성과 점수 (0-1)",
                required=True
            )
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "recommended_difficulty": {"type": "string"},
                    "current_performance": {"type": "number"},
                    "adjustment_reason": {"type": "string"},
                    "confidence": {"type": "number"}
                }
            }
        }
    )
    @action(detail=False, methods=['get'])
    def adaptive_difficulty(self, request):
        """적응형 난이도 조회"""
        try:
            subject_id = request.query_params.get('subject_id')
            current_performance = request.query_params.get('current_performance')
            
            if not subject_id or not current_performance:
                return Response({
                    'error': 'subject_id와 current_performance 매개변수가 필요합니다.',
                    'error_type': 'validation_error'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            subject_id = int(subject_id)
            current_performance = float(current_performance)
            
            if not 0 <= current_performance <= 1:
                return Response({
                    'error': 'current_performance는 0과 1 사이의 값이어야 합니다.',
                    'error_type': 'validation_error'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 적응형 난이도 계산
            recommended_difficulty = get_adaptive_difficulty(
                request.user.id, subject_id, current_performance
            )
            
            # 조정 이유 생성
            adjustment_reason = self._get_adjustment_reason(current_performance)
            
            return Response({
                'recommended_difficulty': recommended_difficulty.value,
                'current_performance': current_performance,
                'adjustment_reason': adjustment_reason,
                'confidence': self._calculate_adjustment_confidence(current_performance),
                'calculated_at': timezone.now().isoformat()
            }, status=status.HTTP_200_OK)
            
        except ValueError as e:
            return Response({
                'error': '잘못된 매개변수 형식입니다.',
                'error_type': 'validation_error',
                'details': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f"적응형 난이도 계산 실패 - 사용자 {request.user.id}: {e}")
            return Response({
                'error': '난이도 계산 중 오류가 발생했습니다.',
                'error_type': 'system_error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        summary="학습 스타일 분석 상세",
        description="사용자의 학습 스타일 분석 상세 정보를 제공합니다.",
        responses={
            200: {
                "type": "object",
                "properties": {
                    "analysis_details": {"type": "object"},
                    "style_breakdown": {"type": "object"},
                    "improvement_suggestions": {"type": "array"},
                    "data_quality": {"type": "object"}
                }
            }
        }
    )
    @action(detail=False, methods=['get'])
    def analysis_details(self, request):
        """학습 스타일 분석 상세"""
        try:
            profile = get_user_personalization_profile(request.user.id)
            
            # 스타일별 특성 설명
            style_descriptions = {
                'visual': {
                    'description': '시각적 자료를 통해 효과적으로 학습합니다.',
                    'characteristics': ['그래프와 다이어그램 선호', '색상과 이미지 활용', '공간적 사고']
                },
                'auditory': {
                    'description': '청각적 정보를 통해 효과적으로 학습합니다.',
                    'characteristics': ['음성 설명 선호', '토론과 대화', '리듬과 패턴 인식']
                },
                'kinesthetic': {
                    'description': '체험과 실습을 통해 효과적으로 학습합니다.',
                    'characteristics': ['손으로 만지고 조작', '움직임과 활동', '실제 경험 중시']
                },
                'reading': {
                    'description': '텍스트 읽기와 쓰기를 통해 효과적으로 학습합니다.',
                    'characteristics': ['텍스트 자료 선호', '노트 정리', '목록과 개요 작성']
                },
                'mixed': {
                    'description': '다양한 학습 방법을 조합하여 학습합니다.',
                    'characteristics': ['다양한 접근법', '상황별 방법 선택', '유연한 학습']
                }
            }
            
            style_info = style_descriptions.get(profile.learning_style.value, {})
            
            return Response({
                'analysis_details': {
                    'learning_style': profile.learning_style.value,
                    'confidence_score': profile.confidence_score,
                    'style_description': style_info.get('description', ''),
                    'characteristics': style_info.get('characteristics', [])
                },
                'style_breakdown': {
                    'primary_style': profile.learning_style.value,
                    'confidence_level': self._get_confidence_level(profile.confidence_score),
                    'reliability': self._get_analysis_quality(profile.confidence_score)
                },
                'improvement_suggestions': profile.recommendations,
                'data_quality': {
                    'analysis_date': profile.last_updated.isoformat(),
                    'data_sufficiency': self._assess_data_sufficiency(profile),
                    'recommendation': self._get_data_improvement_suggestion(profile)
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"학습 스타일 분석 상세 조회 실패 - 사용자 {request.user.id}: {e}")
            return Response({
                'error': '분석 상세 조회 중 오류가 발생했습니다.',
                'error_type': 'system_error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_analysis_quality(self, confidence_score: float) -> str:
        """분석 품질 평가"""
        if confidence_score >= 0.8:
            return "매우 높음"
        elif confidence_score >= 0.6:
            return "높음"
        elif confidence_score >= 0.4:
            return "보통"
        else:
            return "낮음"
    
    def _get_confidence_level(self, confidence_score: float) -> str:
        """신뢰도 수준"""
        if confidence_score >= 0.7:
            return "높은 신뢰도"
        elif confidence_score >= 0.5:
            return "보통 신뢰도"
        else:
            return "낮은 신뢰도"
    
    def _get_adjustment_reason(self, performance: float) -> str:
        """난이도 조정 이유"""
        if performance > 0.8:
            return "높은 성과로 인한 난이도 상승 권장"
        elif performance < 0.5:
            return "낮은 성과로 인한 난이도 하락 권장"
        else:
            return "현재 난이도 유지 권장"
    
    def _calculate_adjustment_confidence(self, performance: float) -> float:
        """조정 신뢰도 계산"""
        if performance > 0.8 or performance < 0.5:
            return 0.8  # 명확한 조정이 필요한 경우
        else:
            return 0.6  # 유지가 적절한 경우
    
    def _assess_data_sufficiency(self, profile) -> str:
        """데이터 충분성 평가"""
        if profile.confidence_score >= 0.7:
            return "충분"
        elif profile.confidence_score >= 0.5:
            return "보통"
        else:
            return "부족"
    
    def _get_data_improvement_suggestion(self, profile) -> str:
        """데이터 개선 제안"""
        if profile.confidence_score < 0.5:
            return "더 많은 학습 활동을 통해 정확한 분석이 가능합니다."
        elif profile.confidence_score < 0.7:
            return "다양한 유형의 학습 활동을 시도해보세요."
        else:
            return "충분한 데이터를 바탕으로 정확한 분석이 완료되었습니다."