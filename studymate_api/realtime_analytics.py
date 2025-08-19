"""
실시간 학습 분석 시스템

사용자의 학습 패턴을 실시간으로 분석하고 즉시 피드백을 제공하는 고도화된 분석 엔진
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict, deque
import statistics

from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .metrics import track_user_event, EventType, MetricEvent, MetricType
from .personalization import PersonalizationEngine

logger = logging.getLogger(__name__)
User = get_user_model()


class LearningSessionState(Enum):
    """학습 세션 상태"""
    ACTIVE = "active"
    PAUSED = "paused"
    FOCUSED = "focused"
    DISTRACTED = "distracted"
    COMPLETED = "completed"


class AnalysisLevel(Enum):
    """분석 수준"""
    BASIC = "basic"          # 기본 분석
    ADVANCED = "advanced"    # 고급 분석
    REAL_TIME = "real_time"  # 실시간 분석
    PREDICTIVE = "predictive" # 예측 분석


@dataclass
class LearningEvent:
    """학습 이벤트 데이터"""
    user_id: int
    session_id: str
    event_type: str
    subject_id: Optional[int] = None
    content_id: Optional[str] = None
    timestamp: datetime = None
    duration: float = 0.0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = timezone.now()
        if self.metadata is None:
            self.metadata = {}


@dataclass
class LearningSession:
    """학습 세션 데이터"""
    session_id: str
    user_id: int
    subject_id: Optional[int]
    start_time: datetime
    last_activity: datetime
    state: LearningSessionState = LearningSessionState.ACTIVE
    focus_score: float = 100.0
    events: List[LearningEvent] = None
    total_time: float = 0.0
    break_time: float = 0.0
    productivity_score: float = 0.0
    
    def __post_init__(self):
        if self.events is None:
            self.events = []


@dataclass
class RealTimeAnalysis:
    """실시간 분석 결과"""
    user_id: int
    session_id: str
    current_focus_level: float
    learning_velocity: float
    efficiency_score: float
    recommendations: List[str]
    alerts: List[Dict[str, Any]]
    predictions: Dict[str, Any]
    generated_at: datetime = None
    
    def __post_init__(self):
        if self.generated_at is None:
            self.generated_at = timezone.now()


class RealTimeLearningAnalyzer:
    """실시간 학습 분석 엔진"""
    
    def __init__(self):
        self.channel_layer = get_channel_layer()
        self.personalization_engine = PersonalizationEngine()
        
        # 분석 설정
        self.analysis_interval = 30  # 30초마다 분석
        self.focus_window = 300     # 5분 집중도 윈도우
        self.prediction_horizon = 3600  # 1시간 예측 범위
        
        # 임계값 설정
        self.low_focus_threshold = 70
        self.high_efficiency_threshold = 85
        self.break_recommendation_threshold = 45  # 45분 후 휴식 권장
        
        # 세션 저장소
        self.active_sessions: Dict[str, LearningSession] = {}
        self.session_events: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
    
    async def start_learning_session(self, user_id: int, subject_id: Optional[int] = None, 
                                   session_id: Optional[str] = None) -> str:
        """학습 세션 시작"""
        if not session_id:
            session_id = f"session_{user_id}_{int(timezone.now().timestamp())}"
        
        session = LearningSession(
            session_id=session_id,
            user_id=user_id,
            subject_id=subject_id,
            start_time=timezone.now(),
            last_activity=timezone.now()
        )
        
        self.active_sessions[session_id] = session
        
        # 세션 시작 이벤트 추적
        await self._track_session_event(session_id, "session_start", {
            'subject_id': subject_id,
            'start_time': session.start_time.isoformat()
        })
        
        # 실시간 분석 시작
        asyncio.create_task(self._start_session_monitoring(session_id))
        
        logger.info(f"학습 세션 시작: {session_id} (사용자: {user_id})")
        return session_id
    
    async def end_learning_session(self, session_id: str) -> Dict[str, Any]:
        """학습 세션 종료"""
        if session_id not in self.active_sessions:
            raise ValueError(f"활성 세션을 찾을 수 없습니다: {session_id}")
        
        session = self.active_sessions[session_id]
        session.state = LearningSessionState.COMPLETED
        
        # 최종 분석 수행
        final_analysis = await self._generate_session_summary(session)
        
        # 세션 종료 이벤트 추적
        await self._track_session_event(session_id, "session_end", {
            'duration': session.total_time,
            'focus_score': session.focus_score,
            'productivity_score': session.productivity_score
        })
        
        # 세션 정리
        del self.active_sessions[session_id]
        
        logger.info(f"학습 세션 종료: {session_id}")
        return final_analysis
    
    async def track_learning_event(self, session_id: str, event_type: str, 
                                 metadata: Dict[str, Any] = None) -> None:
        """학습 이벤트 추적"""
        if session_id not in self.active_sessions:
            logger.warning(f"비활성 세션에 이벤트 추적 시도: {session_id}")
            return
        
        session = self.active_sessions[session_id]
        session.last_activity = timezone.now()
        
        event = LearningEvent(
            user_id=session.user_id,
            session_id=session_id,
            event_type=event_type,
            subject_id=session.subject_id,
            metadata=metadata or {}
        )
        
        session.events.append(event)
        self.session_events[session_id].append(event)
        
        # 즉시 분석 수행
        await self._analyze_event(session, event)
    
    async def _start_session_monitoring(self, session_id: str):
        """세션 모니터링 시작"""
        while session_id in self.active_sessions:
            try:
                session = self.active_sessions[session_id]
                
                # 세션 상태 업데이트
                await self._update_session_state(session)
                
                # 실시간 분석 수행
                analysis = await self._perform_realtime_analysis(session)
                
                # 클라이언트에 분석 결과 전송
                await self._broadcast_analysis(session_id, analysis)
                
                # 알림 및 권장사항 처리
                await self._process_recommendations(session, analysis)
                
                await asyncio.sleep(self.analysis_interval)
                
            except Exception as e:
                logger.error(f"세션 모니터링 오류 {session_id}: {e}")
                await asyncio.sleep(self.analysis_interval)
    
    async def _update_session_state(self, session: LearningSession):
        """세션 상태 업데이트"""
        now = timezone.now()
        time_since_activity = (now - session.last_activity).total_seconds()
        
        # 비활성 시간 기반 상태 업데이트
        if time_since_activity > 300:  # 5분 이상 비활성
            session.state = LearningSessionState.PAUSED
        elif time_since_activity < 30:  # 30초 이내 활동
            session.state = LearningSessionState.ACTIVE
        
        # 총 학습 시간 업데이트
        session.total_time = (now - session.start_time).total_seconds()
    
    async def _perform_realtime_analysis(self, session: LearningSession) -> RealTimeAnalysis:
        """실시간 분석 수행"""
        # 집중도 분석
        focus_level = await self._analyze_focus_level(session)
        
        # 학습 속도 분석
        learning_velocity = await self._calculate_learning_velocity(session)
        
        # 효율성 점수 계산
        efficiency_score = await self._calculate_efficiency_score(session)
        
        # 권장사항 생성
        recommendations = await self._generate_recommendations(session, focus_level, efficiency_score)
        
        # 알림 생성
        alerts = await self._generate_alerts(session, focus_level, efficiency_score)
        
        # 예측 수행
        predictions = await self._make_predictions(session)
        
        analysis = RealTimeAnalysis(
            user_id=session.user_id,
            session_id=session.session_id,
            current_focus_level=focus_level,
            learning_velocity=learning_velocity,
            efficiency_score=efficiency_score,
            recommendations=recommendations,
            alerts=alerts,
            predictions=predictions
        )
        
        return analysis
    
    async def _analyze_focus_level(self, session: LearningSession) -> float:
        """집중도 레벨 분석"""
        if not session.events:
            return 100.0
        
        # 최근 이벤트들을 기반으로 집중도 계산
        recent_events = [e for e in session.events 
                        if (timezone.now() - e.timestamp).total_seconds() < self.focus_window]
        
        if not recent_events:
            return session.focus_score
        
        # 이벤트 패턴 분석
        productive_events = 0
        total_events = len(recent_events)
        
        for event in recent_events:
            if event.event_type in ['content_read', 'problem_solved', 'note_taken']:
                productive_events += 1
            elif event.event_type in ['tab_switch', 'idle', 'scroll_fast']:
                productive_events -= 0.5
        
        # 집중도 점수 계산 (0-100)
        focus_ratio = max(0, productive_events / total_events) if total_events > 0 else 1
        focus_score = min(100, focus_ratio * 100)
        
        # 스무딩 적용
        session.focus_score = (session.focus_score * 0.7) + (focus_score * 0.3)
        
        return session.focus_score
    
    async def _calculate_learning_velocity(self, session: LearningSession) -> float:
        """학습 속도 계산"""
        if session.total_time < 300:  # 5분 미만
            return 0.0
        
        # 학습 진도 기반 속도 계산
        learning_events = [e for e in session.events 
                          if e.event_type in ['content_completed', 'quiz_answered', 'concept_mastered']]
        
        if not learning_events:
            return 0.0
        
        # 시간당 학습 단위 계산
        hours = session.total_time / 3600
        velocity = len(learning_events) / hours if hours > 0 else 0
        
        return velocity
    
    async def _calculate_efficiency_score(self, session: LearningSession) -> float:
        """효율성 점수 계산"""
        if session.total_time < 300:
            return 0.0
        
        # 생산적 시간 vs 총 시간 비율
        productive_time = 0
        idle_time = 0
        
        for event in session.events:
            if event.event_type in ['content_read', 'problem_solved', 'note_taken']:
                productive_time += event.duration
            elif event.event_type in ['idle', 'break']:
                idle_time += event.duration
        
        total_tracked_time = productive_time + idle_time
        if total_tracked_time == 0:
            return session.focus_score  # 기본값으로 집중도 사용
        
        efficiency = (productive_time / total_tracked_time) * 100
        
        # 집중도 가중치 적용
        weighted_efficiency = (efficiency * 0.6) + (session.focus_score * 0.4)
        
        session.productivity_score = weighted_efficiency
        return weighted_efficiency
    
    async def _generate_recommendations(self, session: LearningSession, 
                                      focus_level: float, efficiency_score: float) -> List[str]:
        """권장사항 생성"""
        recommendations = []
        
        # 집중도 기반 권장사항
        if focus_level < self.low_focus_threshold:
            recommendations.append("집중도가 낮습니다. 5분 휴식을 권장합니다.")
            recommendations.append("학습 환경을 점검해보세요.")
        
        # 학습 시간 기반 권장사항
        study_minutes = session.total_time / 60
        if study_minutes > self.break_recommendation_threshold:
            recommendations.append("장시간 학습 중입니다. 15분 휴식을 권장합니다.")
        
        # 효율성 기반 권장사항
        if efficiency_score < 60:
            recommendations.append("학습 방법을 변경해보세요.")
            recommendations.append("더 상호작용적인 학습 자료를 시도해보세요.")
        elif efficiency_score > self.high_efficiency_threshold:
            recommendations.append("훌륭한 집중력입니다! 이 상태를 유지하세요.")
        
        # 개인화된 권장사항
        if session.user_id:
            profile = await self._get_user_profile(session.user_id)
            if profile:
                personalized_recommendations = await self._generate_personalized_recommendations(
                    profile, session, focus_level, efficiency_score
                )
                recommendations.extend(personalized_recommendations)
        
        return recommendations
    
    async def _generate_alerts(self, session: LearningSession, 
                             focus_level: float, efficiency_score: float) -> List[Dict[str, Any]]:
        """알림 생성"""
        alerts = []
        
        # 집중도 저하 알림
        if focus_level < 50:
            alerts.append({
                'type': 'warning',
                'title': '집중도 저하 감지',
                'message': '집중도가 크게 떨어졌습니다. 잠깐 휴식을 취하는 것이 좋겠습니다.',
                'severity': 'high',
                'action': 'suggest_break'
            })
        
        # 장시간 학습 알림
        if session.total_time > 3600:  # 1시간 이상
            alerts.append({
                'type': 'info',
                'title': '장시간 학습 감지',
                'message': '1시간 이상 학습하고 계십니다. 건강한 학습을 위해 휴식을 권장합니다.',
                'severity': 'medium',
                'action': 'suggest_break'
            })
        
        # 목표 달성 알림
        if efficiency_score > 90:
            alerts.append({
                'type': 'success',
                'title': '높은 학습 효율성',
                'message': '매우 효율적으로 학습하고 계십니다! 계속 좋은 페이스를 유지하세요.',
                'severity': 'low',
                'action': 'positive_reinforcement'
            })
        
        return alerts
    
    async def _make_predictions(self, session: LearningSession) -> Dict[str, Any]:
        """예측 수행"""
        predictions = {}
        
        if session.total_time < 600:  # 10분 미만은 예측 불가
            return predictions
        
        # 현재 페이스 기반 예측
        current_velocity = await self._calculate_learning_velocity(session)
        
        # 1시간 후 예상 진도
        if current_velocity > 0:
            predicted_progress = current_velocity * 1  # 1시간 후
            predictions['progress_1h'] = {
                'estimated_units': predicted_progress,
                'confidence': min(0.8, session.total_time / 3600)
            }
        
        # 집중도 지속 예측
        focus_trend = await self._calculate_focus_trend(session)
        predictions['focus_sustainability'] = {
            'trend': focus_trend,
            'recommended_break_time': max(0, 45 - (session.total_time / 60))
        }
        
        # 목표 달성 예측
        if session.subject_id:
            goal_prediction = await self._predict_goal_achievement(session)
            predictions['goal_achievement'] = goal_prediction
        
        return predictions
    
    async def _calculate_focus_trend(self, session: LearningSession) -> str:
        """집중도 트렌드 계산"""
        if len(session.events) < 10:
            return "insufficient_data"
        
        # 최근 이벤트들의 집중도 변화 분석
        recent_focus_scores = []
        window_size = 5
        
        for i in range(len(session.events) - window_size + 1):
            window_events = session.events[i:i + window_size]
            productive = sum(1 for e in window_events 
                           if e.event_type in ['content_read', 'problem_solved', 'note_taken'])
            focus_score = (productive / window_size) * 100
            recent_focus_scores.append(focus_score)
        
        if len(recent_focus_scores) < 3:
            return "stable"
        
        # 트렌드 분석
        if recent_focus_scores[-1] > recent_focus_scores[-3] + 10:
            return "improving"
        elif recent_focus_scores[-1] < recent_focus_scores[-3] - 10:
            return "declining"
        else:
            return "stable"
    
    async def _predict_goal_achievement(self, session: LearningSession) -> Dict[str, Any]:
        """목표 달성 예측"""
        # 기본 예측 (실제 구현에서는 더 정교한 모델 사용)
        current_efficiency = session.productivity_score
        
        if current_efficiency > 80:
            achievement_probability = 0.9
            estimated_time = "목표 시간 내"
        elif current_efficiency > 60:
            achievement_probability = 0.7
            estimated_time = "목표 시간보다 약간 늦음"
        else:
            achievement_probability = 0.4
            estimated_time = "목표 시간보다 상당히 늦음"
        
        return {
            'probability': achievement_probability,
            'estimated_completion': estimated_time,
            'recommended_adjustments': []
        }
    
    async def _get_user_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        """사용자 프로필 조회"""
        try:
            profile_data = await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: self.personalization_engine.get_user_profile(user_id)
            )
            return profile_data
        except Exception as e:
            logger.error(f"사용자 프로필 조회 실패 {user_id}: {e}")
            return None
    
    async def _generate_personalized_recommendations(self, profile: Dict[str, Any], 
                                                   session: LearningSession,
                                                   focus_level: float, 
                                                   efficiency_score: float) -> List[str]:
        """개인화된 권장사항 생성"""
        recommendations = []
        
        learning_style = profile.get('learning_style', 'mixed')
        
        if focus_level < 70:
            if learning_style == 'visual':
                recommendations.append("시각적 자료(도표, 그래프)를 활용해보세요.")
            elif learning_style == 'auditory':
                recommendations.append("소리 내어 읽거나 음성 자료를 활용해보세요.")
            elif learning_style == 'kinesthetic':
                recommendations.append("손으로 직접 써보거나 실습을 해보세요.")
        
        # 선호 학습 시간대 기반
        preferred_time = profile.get('preferred_study_time', 'any')
        current_hour = timezone.now().hour
        
        if preferred_time == 'morning' and current_hour > 14:
            recommendations.append("오후 시간입니다. 가벼운 복습 위주로 학습하세요.")
        elif preferred_time == 'evening' and current_hour < 10:
            recommendations.append("아침 시간의 집중력을 최대한 활용하세요.")
        
        return recommendations
    
    async def _broadcast_analysis(self, session_id: str, analysis: RealTimeAnalysis):
        """분석 결과 브로드캐스트"""
        if self.channel_layer:
            try:
                await self.channel_layer.group_send(
                    f"user_{analysis.user_id}",
                    {
                        'type': 'learning_analysis',
                        'data': asdict(analysis)
                    }
                )
            except Exception as e:
                logger.error(f"분석 결과 브로드캐스트 실패: {e}")
    
    async def _process_recommendations(self, session: LearningSession, analysis: RealTimeAnalysis):
        """권장사항 처리"""
        for alert in analysis.alerts:
            if alert['severity'] == 'high':
                # 높은 우선순위 알림은 즉시 전송
                await self._send_urgent_notification(session.user_id, alert)
    
    async def _send_urgent_notification(self, user_id: int, alert: Dict[str, Any]):
        """긴급 알림 전송"""
        if self.channel_layer:
            try:
                await self.channel_layer.group_send(
                    f"user_{user_id}",
                    {
                        'type': 'urgent_alert',
                        'alert': alert
                    }
                )
            except Exception as e:
                logger.error(f"긴급 알림 전송 실패: {e}")
    
    async def _track_session_event(self, session_id: str, event_type: str, metadata: Dict[str, Any]):
        """세션 이벤트 추적"""
        try:
            # 메트릭 시스템에 이벤트 기록
            if session_id in self.active_sessions:
                session = self.active_sessions[session_id]
                
                # 동기 함수를 비동기로 실행
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: track_user_event(
                        EventType.STUDY_SESSION_START if event_type == "session_start" 
                        else EventType.STUDY_SESSION_END,
                        session.user_id,
                        metadata
                    )
                )
        except Exception as e:
            logger.error(f"세션 이벤트 추적 실패: {e}")
    
    async def _analyze_event(self, session: LearningSession, event: LearningEvent):
        """개별 이벤트 분석"""
        # 이벤트 기반 즉시 피드백
        if event.event_type == 'idle' and event.duration > 180:  # 3분 이상 유휴
            await self._send_focus_reminder(session.user_id)
        elif event.event_type == 'problem_solved':
            await self._send_positive_reinforcement(session.user_id)
    
    async def _send_focus_reminder(self, user_id: int):
        """집중 알림 전송"""
        if self.channel_layer:
            await self.channel_layer.group_send(
                f"user_{user_id}",
                {
                    'type': 'focus_reminder',
                    'message': '잠시 휴식 중이신가요? 학습으로 돌아와보세요!'
                }
            )
    
    async def _send_positive_reinforcement(self, user_id: int):
        """긍정적 강화 전송"""
        if self.channel_layer:
            await self.channel_layer.group_send(
                f"user_{user_id}",
                {
                    'type': 'positive_feedback',
                    'message': '잘하고 있습니다! 계속 이런 페이스를 유지하세요.'
                }
            )
    
    async def _generate_session_summary(self, session: LearningSession) -> Dict[str, Any]:
        """세션 요약 생성"""
        summary = {
            'session_id': session.session_id,
            'user_id': session.user_id,
            'duration': session.total_time,
            'focus_score': session.focus_score,
            'productivity_score': session.productivity_score,
            'total_events': len(session.events),
            'insights': [],
            'achievements': [],
            'improvement_areas': []
        }
        
        # 인사이트 생성
        if session.focus_score > 80:
            summary['insights'].append("높은 집중도를 유지했습니다.")
        if session.productivity_score > 85:
            summary['insights'].append("매우 효율적인 학습 세션이었습니다.")
        
        # 개선 영역
        if session.focus_score < 60:
            summary['improvement_areas'].append("집중도 향상이 필요합니다.")
        
        return summary
    
    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """세션 상태 조회"""
        if session_id not in self.active_sessions:
            return None
        
        session = self.active_sessions[session_id]
        return {
            'session_id': session_id,
            'state': session.state.value,
            'duration': session.total_time,
            'focus_score': session.focus_score,
            'last_activity': session.last_activity.isoformat()
        }
    
    def get_active_sessions_count(self) -> int:
        """활성 세션 수 조회"""
        return len(self.active_sessions)


# 전역 분석기 인스턴스
realtime_analyzer = RealTimeLearningAnalyzer()


# 편의 함수들
async def start_learning_session(user_id: int, subject_id: Optional[int] = None) -> str:
    """학습 세션 시작"""
    return await realtime_analyzer.start_learning_session(user_id, subject_id)


async def end_learning_session(session_id: str) -> Dict[str, Any]:
    """학습 세션 종료"""
    return await realtime_analyzer.end_learning_session(session_id)


async def track_learning_event(session_id: str, event_type: str, 
                             metadata: Dict[str, Any] = None) -> None:
    """학습 이벤트 추적"""
    await realtime_analyzer.track_learning_event(session_id, event_type, metadata)


def get_session_status(session_id: str) -> Optional[Dict[str, Any]]:
    """세션 상태 조회"""
    return realtime_analyzer.get_session_status(session_id)