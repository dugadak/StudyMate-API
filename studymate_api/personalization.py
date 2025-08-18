"""
StudyMate API 개인화 엔진

이 모듈은 다음 기능을 제공합니다:
- 학습 스타일 분석 및 분류
- 맞춤형 콘텐츠 추천
- 개인화된 학습 경로 생성
- 적응형 난이도 조절
- 학습 패턴 기반 최적화
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import numpy as np
from collections import defaultdict, Counter
import statistics

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum, F
from django.core.cache import cache

from studymate_api.advanced_cache import cache_user_profile, smart_cache

User = get_user_model()
logger = logging.getLogger(__name__)


class LearningStyle(Enum):
    """학습 스타일 유형"""
    VISUAL = "visual"           # 시각적 학습자
    AUDITORY = "auditory"       # 청각적 학습자
    KINESTHETIC = "kinesthetic" # 체험적 학습자
    READING = "reading"         # 읽기/쓰기 학습자
    MIXED = "mixed"            # 혼합형 학습자


class ContentType(Enum):
    """콘텐츠 유형"""
    TEXT = "text"
    VIDEO = "video"
    AUDIO = "audio"
    INTERACTIVE = "interactive"
    QUIZ = "quiz"
    EXERCISE = "exercise"


class DifficultyLevel(Enum):
    """난이도 수준"""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


@dataclass
class LearningPattern:
    """학습 패턴 데이터"""
    user_id: int
    session_duration_avg: float
    completion_rate: float
    preferred_time_slots: List[int]  # 시간대 (0-23)
    preferred_content_types: Dict[str, float]
    difficulty_progression: Dict[str, float]
    interaction_frequency: Dict[str, int]
    learning_speed: float  # 평균 학습 속도
    retention_rate: float  # 지식 보존율
    preferred_session_length: int  # 선호 세션 길이 (분)


@dataclass
class PersonalizationProfile:
    """개인화 프로필"""
    user_id: int
    learning_style: LearningStyle
    confidence_score: float
    preferred_difficulty: DifficultyLevel
    learning_goals: List[str]
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[Dict[str, Any]]
    last_updated: datetime


@dataclass
class ContentRecommendation:
    """콘텐츠 추천"""
    content_id: str
    content_type: ContentType
    title: str
    description: str
    difficulty: DifficultyLevel
    estimated_time: int  # 분
    relevance_score: float
    personalization_reason: str
    tags: List[str]


class LearningStyleAnalyzer:
    """학습 스타일 분석기"""
    
    def __init__(self):
        # 학습 스타일별 행동 패턴 가중치
        self.style_weights = {
            LearningStyle.VISUAL: {
                'image_interactions': 3.0,
                'video_completion': 2.5,
                'diagram_views': 2.0,
                'visual_quiz_preference': 2.0,
                'text_highlighting': 1.5
            },
            LearningStyle.AUDITORY: {
                'audio_content_preference': 3.0,
                'voice_note_usage': 2.5,
                'discussion_participation': 2.0,
                'audio_quiz_preference': 2.0,
                'lecture_completion': 1.5
            },
            LearningStyle.KINESTHETIC: {
                'interactive_content_preference': 3.0,
                'hands_on_exercises': 2.5,
                'frequent_breaks': 2.0,
                'movement_based_learning': 2.0,
                'practical_examples': 1.5
            },
            LearningStyle.READING: {
                'text_content_preference': 3.0,
                'note_taking_frequency': 2.5,
                'reading_completion': 2.0,
                'written_quiz_preference': 2.0,
                'summary_creation': 1.5
            }
        }
    
    def analyze_user_learning_style(self, user_id: int) -> PersonalizationProfile:
        """사용자 학습 스타일 분석"""
        def analysis_func():
            try:
                # 사용자 학습 데이터 수집
                learning_data = self._collect_learning_data(user_id)
                
                # 학습 패턴 분석
                pattern = self._analyze_learning_pattern(learning_data)
                
                # 학습 스타일 분류
                style, confidence = self._classify_learning_style(pattern)
                
                # 개인화 프로필 생성
                profile = self._create_personalization_profile(
                    user_id, style, confidence, pattern
                )
                
                logger.info(f"사용자 {user_id} 학습 스타일 분석 완료: {style.value} (신뢰도: {confidence:.2f})")
                return profile
                
            except Exception as e:
                logger.error(f"학습 스타일 분석 실패 - 사용자 {user_id}: {e}")
                return self._create_default_profile(user_id)
        
        # 캐시를 사용하여 분석 결과 저장
        return cache_user_profile(user_id, analysis_func)
    
    def _collect_learning_data(self, user_id: int) -> Dict[str, Any]:
        """사용자 학습 데이터 수집"""
        from study.models import StudySummary, StudyProgress
        from quiz.models import Quiz, UserAnswer
        
        # 학습 세션 데이터
        study_sessions = StudyProgress.objects.filter(
            user_id=user_id,
            created_at__gte=timezone.now() - timedelta(days=90)
        ).values(
            'session_duration', 'completion_percentage', 'created_at',
            'interaction_count', 'content_type'
        )
        
        # 퀴즈 데이터
        quiz_data = UserAnswer.objects.filter(
            user_id=user_id,
            created_at__gte=timezone.now() - timedelta(days=90)
        ).select_related('question__quiz').values(
            'is_correct', 'time_taken', 'question__question_type',
            'created_at'
        )
        
        # 학습 요약 데이터
        summary_data = StudySummary.objects.filter(
            user_id=user_id,
            generated_at__gte=timezone.now() - timedelta(days=90)
        ).values(
            'difficulty_level', 'user_rating', 'reading_time',
            'generated_at', 'topics_covered'
        )
        
        return {
            'study_sessions': list(study_sessions),
            'quiz_data': list(quiz_data),
            'summary_data': list(summary_data),
            'total_sessions': len(study_sessions),
            'total_quizzes': len(quiz_data),
            'total_summaries': len(summary_data)
        }
    
    def _analyze_learning_pattern(self, learning_data: Dict[str, Any]) -> LearningPattern:
        """학습 패턴 분석"""
        sessions = learning_data['study_sessions']
        quiz_data = learning_data['quiz_data']
        
        if not sessions:
            return self._create_default_pattern(learning_data.get('user_id', 0))
        
        # 세션 지속 시간 분석
        session_durations = [s['session_duration'] for s in sessions if s['session_duration']]
        avg_duration = statistics.mean(session_durations) if session_durations else 30.0
        
        # 완성률 분석
        completion_rates = [s['completion_percentage'] for s in sessions if s['completion_percentage'] is not None]
        avg_completion = statistics.mean(completion_rates) if completion_rates else 50.0
        
        # 선호 시간대 분석
        session_hours = [s['created_at'].hour for s in sessions]
        preferred_hours = [hour for hour, count in Counter(session_hours).most_common(3)]
        
        # 콘텐츠 유형 선호도 분석
        content_preferences = defaultdict(int)
        for session in sessions:
            if session['content_type']:
                content_preferences[session['content_type']] += 1
        
        total_content = sum(content_preferences.values()) or 1
        content_prefs_normalized = {
            k: v / total_content for k, v in content_preferences.items()
        }
        
        # 난이도 진행 분석
        difficulty_data = learning_data['summary_data']
        difficulty_progression = defaultdict(list)
        for summary in difficulty_data:
            if summary['difficulty_level'] and summary['user_rating']:
                difficulty_progression[summary['difficulty_level']].append(summary['user_rating'])
        
        difficulty_scores = {}
        for level, ratings in difficulty_progression.items():
            difficulty_scores[level] = statistics.mean(ratings) if ratings else 0.0
        
        # 학습 속도 계산 (퀴즈 응답 시간 기반)
        quiz_times = [q['time_taken'] for q in quiz_data if q['time_taken']]
        learning_speed = statistics.mean(quiz_times) if quiz_times else 60.0
        
        # 지식 보존율 (정답률)
        correct_answers = sum(1 for q in quiz_data if q['is_correct'])
        total_answers = len(quiz_data)
        retention_rate = (correct_answers / total_answers * 100) if total_answers > 0 else 50.0
        
        return LearningPattern(
            user_id=learning_data.get('user_id', 0),
            session_duration_avg=avg_duration,
            completion_rate=avg_completion,
            preferred_time_slots=preferred_hours,
            preferred_content_types=content_prefs_normalized,
            difficulty_progression=difficulty_scores,
            interaction_frequency=content_preferences,
            learning_speed=learning_speed,
            retention_rate=retention_rate,
            preferred_session_length=int(avg_duration)
        )
    
    def _classify_learning_style(self, pattern: LearningPattern) -> Tuple[LearningStyle, float]:
        """학습 스타일 분류"""
        style_scores = {style: 0.0 for style in LearningStyle}
        
        # 콘텐츠 선호도 기반 점수 계산
        for content_type, preference in pattern.preferred_content_types.items():
            if content_type in ['video', 'image', 'diagram']:
                style_scores[LearningStyle.VISUAL] += preference * 2.0
            elif content_type in ['audio', 'podcast', 'lecture']:
                style_scores[LearningStyle.AUDITORY] += preference * 2.0
            elif content_type in ['interactive', 'exercise', 'simulation']:
                style_scores[LearningStyle.KINESTHETIC] += preference * 2.0
            elif content_type in ['text', 'article', 'document']:
                style_scores[LearningStyle.READING] += preference * 2.0
        
        # 세션 길이 기반 분석
        if pattern.preferred_session_length < 15:
            style_scores[LearningStyle.KINESTHETIC] += 1.0
        elif pattern.preferred_session_length > 45:
            style_scores[LearningStyle.READING] += 1.0
        
        # 완성률 기반 분석
        if pattern.completion_rate > 80:
            style_scores[LearningStyle.READING] += 0.5
            style_scores[LearningStyle.VISUAL] += 0.5
        elif pattern.completion_rate < 60:
            style_scores[LearningStyle.KINESTHETIC] += 0.5
        
        # 학습 속도 기반 분석
        if pattern.learning_speed < 30:  # 빠른 학습
            style_scores[LearningStyle.VISUAL] += 0.5
        elif pattern.learning_speed > 90:  # 신중한 학습
            style_scores[LearningStyle.READING] += 0.5
        
        # 가장 높은 점수의 스타일 선택
        if not any(style_scores.values()):
            return LearningStyle.MIXED, 0.5
        
        max_style = max(style_scores, key=style_scores.get)
        max_score = style_scores[max_style]
        total_score = sum(style_scores.values())
        
        confidence = max_score / total_score if total_score > 0 else 0.5
        
        # 혼합형 판단 (최고점과 다른 점수들의 차이가 작은 경우)
        if confidence < 0.4:
            return LearningStyle.MIXED, confidence
        
        return max_style, confidence
    
    def _create_personalization_profile(self, user_id: int, style: LearningStyle, 
                                       confidence: float, pattern: LearningPattern) -> PersonalizationProfile:
        """개인화 프로필 생성"""
        # 강점과 약점 분석
        strengths = self._analyze_strengths(pattern, style)
        weaknesses = self._analyze_weaknesses(pattern, style)
        
        # 추천 사항 생성
        recommendations = self._generate_recommendations(pattern, style)
        
        # 선호 난이도 결정
        preferred_difficulty = self._determine_preferred_difficulty(pattern)
        
        return PersonalizationProfile(
            user_id=user_id,
            learning_style=style,
            confidence_score=confidence,
            preferred_difficulty=preferred_difficulty,
            learning_goals=self._extract_learning_goals(pattern),
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations,
            last_updated=timezone.now()
        )
    
    def _analyze_strengths(self, pattern: LearningPattern, style: LearningStyle) -> List[str]:
        """강점 분석"""
        strengths = []
        
        if pattern.completion_rate > 80:
            strengths.append("높은 학습 완성도")
        
        if pattern.retention_rate > 75:
            strengths.append("우수한 지식 보존 능력")
        
        if pattern.session_duration_avg > 30:
            strengths.append("집중력이 뛰어남")
        
        if style == LearningStyle.VISUAL:
            strengths.append("시각적 정보 처리 능력")
        elif style == LearningStyle.AUDITORY:
            strengths.append("청각적 학습 능력")
        elif style == LearningStyle.KINESTHETIC:
            strengths.append("체험적 학습 능력")
        elif style == LearningStyle.READING:
            strengths.append("텍스트 기반 학습 능력")
        
        return strengths or ["꾸준한 학습 의지"]
    
    def _analyze_weaknesses(self, pattern: LearningPattern, style: LearningStyle) -> List[str]:
        """약점 분석"""
        weaknesses = []
        
        if pattern.completion_rate < 50:
            weaknesses.append("학습 완성도 개선 필요")
        
        if pattern.retention_rate < 60:
            weaknesses.append("복습 강화 필요")
        
        if pattern.session_duration_avg < 15:
            weaknesses.append("집중 시간 연장 필요")
        
        if pattern.learning_speed > 120:
            weaknesses.append("학습 속도 개선 필요")
        
        return weaknesses or ["지속적인 발전 가능성"]
    
    def _generate_recommendations(self, pattern: LearningPattern, style: LearningStyle) -> List[Dict[str, Any]]:
        """추천 사항 생성"""
        recommendations = []
        
        # 학습 스타일별 추천
        style_recommendations = {
            LearningStyle.VISUAL: [
                {"type": "content", "suggestion": "인포그래픽과 다이어그램 활용"},
                {"type": "method", "suggestion": "마인드맵 작성하기"},
                {"type": "tool", "suggestion": "시각적 학습 도구 사용"}
            ],
            LearningStyle.AUDITORY: [
                {"type": "content", "suggestion": "팟캐스트와 오디오 강의 활용"},
                {"type": "method", "suggestion": "소리내어 읽기"},
                {"type": "tool", "suggestion": "음성 메모 활용"}
            ],
            LearningStyle.KINESTHETIC: [
                {"type": "content", "suggestion": "실습과 체험 활동 중심"},
                {"type": "method", "suggestion": "짧은 세션으로 나누어 학습"},
                {"type": "tool", "suggestion": "인터랙티브 콘텐츠 활용"}
            ],
            LearningStyle.READING: [
                {"type": "content", "suggestion": "텍스트 기반 자료 활용"},
                {"type": "method", "suggestion": "노트 정리 및 요약"},
                {"type": "tool", "suggestion": "하이라이팅 기능 활용"}
            ]
        }
        
        recommendations.extend(style_recommendations.get(style, []))
        
        # 패턴 기반 추천
        if pattern.completion_rate < 70:
            recommendations.append({
                "type": "improvement",
                "suggestion": "짧은 목표 설정으로 완성도 향상"
            })
        
        if pattern.preferred_session_length < 20:
            recommendations.append({
                "type": "duration",
                "suggestion": "점진적으로 학습 시간 늘리기"
            })
        
        return recommendations
    
    def _determine_preferred_difficulty(self, pattern: LearningPattern) -> DifficultyLevel:
        """선호 난이도 결정"""
        if not pattern.difficulty_progression:
            return DifficultyLevel.INTERMEDIATE
        
        # 난이도별 만족도 기준으로 선호도 결정
        max_satisfaction = max(pattern.difficulty_progression.values())
        
        for level, satisfaction in pattern.difficulty_progression.items():
            if satisfaction == max_satisfaction:
                try:
                    return DifficultyLevel(level)
                except ValueError:
                    continue
        
        return DifficultyLevel.INTERMEDIATE
    
    def _extract_learning_goals(self, pattern: LearningPattern) -> List[str]:
        """학습 목표 추출"""
        goals = []
        
        if pattern.completion_rate < 80:
            goals.append("학습 완성도 향상")
        
        if pattern.retention_rate < 70:
            goals.append("지식 보존력 강화")
        
        if pattern.session_duration_avg < 30:
            goals.append("집중 시간 연장")
        
        goals.append("개인화된 학습 경로 완성")
        
        return goals or ["효과적인 학습 습관 형성"]
    
    def _create_default_profile(self, user_id: int) -> PersonalizationProfile:
        """기본 프로필 생성"""
        return PersonalizationProfile(
            user_id=user_id,
            learning_style=LearningStyle.MIXED,
            confidence_score=0.5,
            preferred_difficulty=DifficultyLevel.INTERMEDIATE,
            learning_goals=["효과적인 학습 습관 형성"],
            strengths=["학습 의지"],
            weaknesses=["충분한 데이터 수집 필요"],
            recommendations=[
                {"type": "general", "suggestion": "다양한 학습 방법 시도해보기"},
                {"type": "data", "suggestion": "더 많은 학습 활동으로 정확한 분석 가능"}
            ],
            last_updated=timezone.now()
        )
    
    def _create_default_pattern(self, user_id: int) -> LearningPattern:
        """기본 학습 패턴 생성"""
        return LearningPattern(
            user_id=user_id,
            session_duration_avg=30.0,
            completion_rate=50.0,
            preferred_time_slots=[19, 20, 21],  # 저녁 시간대
            preferred_content_types={'text': 0.5, 'video': 0.3, 'interactive': 0.2},
            difficulty_progression={'intermediate': 3.0},
            interaction_frequency={'text': 1},
            learning_speed=60.0,
            retention_rate=50.0,
            preferred_session_length=30
        )


class ContentRecommendationEngine:
    """콘텐츠 추천 엔진"""
    
    def __init__(self):
        self.analyzer = LearningStyleAnalyzer()
    
    def get_personalized_recommendations(self, user_id: int, subject_id: Optional[int] = None, 
                                       limit: int = 10) -> List[ContentRecommendation]:
        """개인화된 콘텐츠 추천"""
        try:
            # 사용자 프로필 가져오기
            profile = self.analyzer.analyze_user_learning_style(user_id)
            
            # 추천 콘텐츠 생성
            recommendations = self._generate_content_recommendations(
                profile, subject_id, limit
            )
            
            logger.info(f"사용자 {user_id}에게 {len(recommendations)}개 콘텐츠 추천")
            return recommendations
            
        except Exception as e:
            logger.error(f"콘텐츠 추천 실패 - 사용자 {user_id}: {e}")
            return []
    
    def _generate_content_recommendations(self, profile: PersonalizationProfile, 
                                        subject_id: Optional[int], limit: int) -> List[ContentRecommendation]:
        """콘텐츠 추천 생성"""
        from study.models import Subject, StudySummary
        
        recommendations = []
        
        # 과목별 추천
        subjects = Subject.objects.filter(is_active=True)
        if subject_id:
            subjects = subjects.filter(id=subject_id)
        
        for subject in subjects[:limit]:
            recommendation = self._create_subject_recommendation(subject, profile)
            if recommendation:
                recommendations.append(recommendation)
        
        # 추천 점수로 정렬
        recommendations.sort(key=lambda x: x.relevance_score, reverse=True)
        
        return recommendations[:limit]
    
    def _create_subject_recommendation(self, subject, profile: PersonalizationProfile) -> Optional[ContentRecommendation]:
        """과목별 추천 생성"""
        try:
            # 학습 스타일에 따른 콘텐츠 유형 결정
            content_type = self._get_preferred_content_type(profile.learning_style)
            
            # 관련성 점수 계산
            relevance_score = self._calculate_relevance_score(subject, profile)
            
            # 개인화 이유 생성
            reason = self._generate_personalization_reason(profile, subject)
            
            return ContentRecommendation(
                content_id=f"subject_{subject.id}",
                content_type=content_type,
                title=subject.name,
                description=getattr(subject, 'description', ''),
                difficulty=profile.preferred_difficulty,
                estimated_time=30,  # 기본 30분
                relevance_score=relevance_score,
                personalization_reason=reason,
                tags=getattr(subject, 'tags', '').split(',') if hasattr(subject, 'tags') else []
            )
            
        except Exception as e:
            logger.error(f"과목 추천 생성 실패 - {subject.id}: {e}")
            return None
    
    def _get_preferred_content_type(self, learning_style: LearningStyle) -> ContentType:
        """학습 스타일별 선호 콘텐츠 유형"""
        style_content_map = {
            LearningStyle.VISUAL: ContentType.VIDEO,
            LearningStyle.AUDITORY: ContentType.AUDIO,
            LearningStyle.KINESTHETIC: ContentType.INTERACTIVE,
            LearningStyle.READING: ContentType.TEXT,
            LearningStyle.MIXED: ContentType.QUIZ
        }
        return style_content_map.get(learning_style, ContentType.TEXT)
    
    def _calculate_relevance_score(self, subject, profile: PersonalizationProfile) -> float:
        """관련성 점수 계산"""
        score = 0.5  # 기본 점수
        
        # 신뢰도 반영
        score += profile.confidence_score * 0.3
        
        # 학습 스타일 적합성
        if hasattr(subject, 'suitable_learning_styles'):
            if profile.learning_style.value in subject.suitable_learning_styles:
                score += 0.2
        
        # 난이도 적합성
        if hasattr(subject, 'default_difficulty'):
            if subject.default_difficulty == profile.preferred_difficulty.value:
                score += 0.2
        
        return min(score, 1.0)
    
    def _generate_personalization_reason(self, profile: PersonalizationProfile, subject) -> str:
        """개인화 이유 생성"""
        reasons = []
        
        if profile.learning_style != LearningStyle.MIXED:
            reasons.append(f"{profile.learning_style.value} 학습 스타일에 적합")
        
        if profile.confidence_score > 0.7:
            reasons.append("개인화 분석 결과 매우 적합")
        
        if hasattr(subject, 'category') and subject.category:
            reasons.append(f"{subject.category} 분야 추천")
        
        return " · ".join(reasons) or "개인화된 추천"


# 전역 인스턴스
personalization_engine = ContentRecommendationEngine()


def get_user_personalization_profile(user_id: int) -> PersonalizationProfile:
    """사용자 개인화 프로필 조회"""
    analyzer = LearningStyleAnalyzer()
    return analyzer.analyze_user_learning_style(user_id)


def get_personalized_content_recommendations(user_id: int, subject_id: Optional[int] = None, 
                                           limit: int = 10) -> List[ContentRecommendation]:
    """개인화된 콘텐츠 추천 조회"""
    return personalization_engine.get_personalized_recommendations(user_id, subject_id, limit)


def update_learning_pattern(user_id: int, activity_data: Dict[str, Any]):
    """학습 패턴 업데이트"""
    try:
        # 캐시된 프로필 무효화하여 다음 분석에서 새로운 데이터 반영
        smart_cache.invalidate_user_cache(user_id)
        logger.info(f"사용자 {user_id} 학습 패턴 업데이트 완료")
        
    except Exception as e:
        logger.error(f"학습 패턴 업데이트 실패 - 사용자 {user_id}: {e}")


def get_adaptive_difficulty(user_id: int, subject_id: int, current_performance: float) -> DifficultyLevel:
    """적응형 난이도 조절"""
    try:
        profile = get_user_personalization_profile(user_id)
        
        # 현재 성과에 따른 난이도 조절
        if current_performance > 0.8:  # 80% 이상 성과
            # 난이도 상승
            difficulty_order = [DifficultyLevel.BEGINNER, DifficultyLevel.INTERMEDIATE, 
                              DifficultyLevel.ADVANCED, DifficultyLevel.EXPERT]
            current_index = difficulty_order.index(profile.preferred_difficulty)
            if current_index < len(difficulty_order) - 1:
                return difficulty_order[current_index + 1]
        
        elif current_performance < 0.5:  # 50% 미만 성과
            # 난이도 하락
            difficulty_order = [DifficultyLevel.BEGINNER, DifficultyLevel.INTERMEDIATE, 
                              DifficultyLevel.ADVANCED, DifficultyLevel.EXPERT]
            current_index = difficulty_order.index(profile.preferred_difficulty)
            if current_index > 0:
                return difficulty_order[current_index - 1]
        
        return profile.preferred_difficulty
        
    except Exception as e:
        logger.error(f"적응형 난이도 조절 실패 - 사용자 {user_id}: {e}")
        return DifficultyLevel.INTERMEDIATE