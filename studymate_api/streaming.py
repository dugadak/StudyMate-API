"""
실시간 스트리밍 처리 모듈

대용량 실시간 데이터 처리와 스트리밍 분석을 담당합니다.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, AsyncGenerator, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import defaultdict, deque
import json

from django.core.cache import cache
from django.utils import timezone
from channels.layers import get_channel_layer

from .realtime_analytics import LearningEvent, LearningSession

logger = logging.getLogger(__name__)


@dataclass
class StreamProcessor:
    """스트림 처리기 설정"""
    name: str
    buffer_size: int = 1000
    batch_size: int = 100
    flush_interval: float = 30.0  # 초
    processor_func: Optional[Callable] = None


@dataclass
class StreamMetrics:
    """스트림 메트릭"""
    processed_events: int = 0
    processing_rate: float = 0.0  # events/second
    buffer_usage: float = 0.0  # percentage
    latency_ms: float = 0.0
    errors: int = 0
    last_update: datetime = None
    
    def __post_init__(self):
        if self.last_update is None:
            self.last_update = timezone.now()


class RealTimeStreamProcessor:
    """실시간 스트림 처리 엔진"""
    
    def __init__(self):
        self.channel_layer = get_channel_layer()
        
        # 스트림 버퍼들
        self.event_buffers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self.processing_queues: Dict[str, asyncio.Queue] = defaultdict(lambda: asyncio.Queue(maxsize=1000))
        
        # 처리기 등록소
        self.processors: Dict[str, StreamProcessor] = {}
        self.active_tasks: Dict[str, asyncio.Task] = {}
        
        # 메트릭
        self.stream_metrics: Dict[str, StreamMetrics] = defaultdict(StreamMetrics)
        
        # 처리 상태
        self.is_running = False
        self.shutdown_event = asyncio.Event()
    
    def register_processor(self, processor: StreamProcessor):
        """스트림 처리기 등록"""
        self.processors[processor.name] = processor
        self.stream_metrics[processor.name] = StreamMetrics()
        logger.info(f"스트림 처리기 등록: {processor.name}")
    
    async def start_processing(self):
        """스트림 처리 시작"""
        if self.is_running:
            logger.warning("스트림 처리가 이미 실행 중입니다.")
            return
        
        self.is_running = True
        self.shutdown_event.clear()
        
        # 각 처리기에 대한 태스크 시작
        for processor_name, processor in self.processors.items():
            task = asyncio.create_task(
                self._process_stream(processor_name, processor)
            )
            self.active_tasks[processor_name] = task
        
        # 메트릭 업데이트 태스크
        self.active_tasks['metrics'] = asyncio.create_task(self._update_metrics())
        
        logger.info("실시간 스트림 처리 시작")
    
    async def stop_processing(self):
        """스트림 처리 중지"""
        if not self.is_running:
            return
        
        self.is_running = False
        self.shutdown_event.set()
        
        # 모든 태스크 종료 대기
        if self.active_tasks:
            await asyncio.gather(*self.active_tasks.values(), return_exceptions=True)
            self.active_tasks.clear()
        
        logger.info("실시간 스트림 처리 중지")
    
    async def push_event(self, stream_name: str, event: LearningEvent):
        """이벤트를 스트림에 추가"""
        try:
            # 버퍼에 추가
            self.event_buffers[stream_name].append(event)
            
            # 처리 큐에 추가 (논블로킹)
            if stream_name in self.processing_queues:
                try:
                    self.processing_queues[stream_name].put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning(f"스트림 {stream_name}의 처리 큐가 가득참")
            
            # 메트릭 업데이트
            self.stream_metrics[stream_name].processed_events += 1
            
        except Exception as e:
            logger.error(f"이벤트 스트림 추가 실패 {stream_name}: {e}")
            self.stream_metrics[stream_name].errors += 1
    
    async def _process_stream(self, stream_name: str, processor: StreamProcessor):
        """개별 스트림 처리"""
        batch = []
        last_flush = timezone.now()
        
        while not self.shutdown_event.is_set():
            try:
                # 이벤트 대기 (타임아웃 포함)
                try:
                    event = await asyncio.wait_for(
                        self.processing_queues[stream_name].get(),
                        timeout=1.0
                    )
                    batch.append(event)
                except asyncio.TimeoutError:
                    pass
                
                current_time = timezone.now()
                time_since_flush = (current_time - last_flush).total_seconds()
                
                # 배치 처리 조건 확인
                should_flush = (
                    len(batch) >= processor.batch_size or
                    time_since_flush >= processor.flush_interval
                )
                
                if should_flush and batch:
                    await self._process_batch(stream_name, processor, batch)
                    batch.clear()
                    last_flush = current_time
                
            except Exception as e:
                logger.error(f"스트림 {stream_name} 처리 오류: {e}")
                self.stream_metrics[stream_name].errors += 1
                await asyncio.sleep(1)
        
        # 종료 시 남은 배치 처리
        if batch:
            await self._process_batch(stream_name, processor, batch)
    
    async def _process_batch(self, stream_name: str, processor: StreamProcessor, 
                           batch: List[LearningEvent]):
        """배치 처리"""
        start_time = timezone.now()
        
        try:
            if processor.processor_func:
                # 사용자 정의 처리 함수 실행
                await processor.processor_func(batch)
            else:
                # 기본 처리
                await self._default_batch_processing(stream_name, batch)
            
            # 레이턴시 계산
            latency = (timezone.now() - start_time).total_seconds() * 1000
            self.stream_metrics[stream_name].latency_ms = (
                self.stream_metrics[stream_name].latency_ms * 0.9 + latency * 0.1
            )
            
            logger.debug(f"스트림 {stream_name} 배치 처리 완료: {len(batch)}개 이벤트")
            
        except Exception as e:
            logger.error(f"배치 처리 실패 {stream_name}: {e}")
            self.stream_metrics[stream_name].errors += 1
    
    async def _default_batch_processing(self, stream_name: str, batch: List[LearningEvent]):
        """기본 배치 처리"""
        # 이벤트 집계
        event_counts = defaultdict(int)
        user_activities = defaultdict(list)
        
        for event in batch:
            event_counts[event.event_type] += 1
            user_activities[event.user_id].append(event)
        
        # 집계 결과 캐싱
        cache_key = f"stream_aggregated:{stream_name}:{timezone.now().strftime('%Y-%m-%d-%H-%M')}"
        aggregate_data = {
            'event_counts': dict(event_counts),
            'user_count': len(user_activities),
            'batch_size': len(batch),
            'timestamp': timezone.now().isoformat()
        }
        
        cache.set(cache_key, aggregate_data, timeout=3600)
        
        # 실시간 대시보드에 브로드캐스트
        if self.channel_layer:
            await self.channel_layer.group_send(
                "realtime_dashboard",
                {
                    'type': 'stream_update',
                    'stream_name': stream_name,
                    'data': aggregate_data
                }
            )
    
    async def _update_metrics(self):
        """메트릭 업데이트"""
        while not self.shutdown_event.is_set():
            try:
                current_time = timezone.now()
                
                for stream_name, metrics in self.stream_metrics.items():
                    # 처리율 계산
                    if metrics.last_update:
                        time_diff = (current_time - metrics.last_update).total_seconds()
                        if time_diff > 0:
                            # 최근 처리된 이벤트 수 기반으로 rate 계산
                            buffer_size = len(self.event_buffers[stream_name])
                            processing_queue_size = self.processing_queues[stream_name].qsize()
                            
                            metrics.processing_rate = buffer_size / time_diff if time_diff > 0 else 0
                            metrics.buffer_usage = (processing_queue_size / 1000) * 100  # 큐 최대 크기 기준
                    
                    metrics.last_update = current_time
                
                # 메트릭을 캐시에 저장
                cache.set('stream_metrics', 
                         {name: asdict(metrics) for name, metrics in self.stream_metrics.items()},
                         timeout=300)
                
                await asyncio.sleep(10)  # 10초마다 업데이트
                
            except Exception as e:
                logger.error(f"메트릭 업데이트 오류: {e}")
                await asyncio.sleep(10)
    
    async def get_stream_metrics(self, stream_name: Optional[str] = None) -> Dict[str, Any]:
        """스트림 메트릭 조회"""
        if stream_name:
            if stream_name in self.stream_metrics:
                return asdict(self.stream_metrics[stream_name])
            return {}
        
        return {name: asdict(metrics) for name, metrics in self.stream_metrics.items()}
    
    async def get_stream_status(self) -> Dict[str, Any]:
        """스트림 상태 조회"""
        return {
            'is_running': self.is_running,
            'active_processors': list(self.processors.keys()),
            'total_buffered_events': sum(len(buffer) for buffer in self.event_buffers.values()),
            'queue_sizes': {name: queue.qsize() for name, queue in self.processing_queues.items()},
            'metrics': await self.get_stream_metrics()
        }


class LearningEventStream:
    """학습 이벤트 스트림 관리"""
    
    def __init__(self, stream_processor: RealTimeStreamProcessor):
        self.stream_processor = stream_processor
        self.setup_processors()
    
    def setup_processors(self):
        """기본 처리기 설정"""
        # 사용자 활동 스트림
        user_activity_processor = StreamProcessor(
            name="user_activity",
            batch_size=50,
            flush_interval=20.0,
            processor_func=self._process_user_activity
        )
        self.stream_processor.register_processor(user_activity_processor)
        
        # 학습 진도 스트림
        progress_processor = StreamProcessor(
            name="learning_progress",
            batch_size=30,
            flush_interval=30.0,
            processor_func=self._process_learning_progress
        )
        self.stream_processor.register_processor(progress_processor)
        
        # 집중도 분석 스트림
        focus_processor = StreamProcessor(
            name="focus_analysis",
            batch_size=20,
            flush_interval=15.0,
            processor_func=self._process_focus_events
        )
        self.stream_processor.register_processor(focus_processor)
        
        # 실시간 알림 스트림
        alert_processor = StreamProcessor(
            name="real_time_alerts",
            batch_size=10,
            flush_interval=5.0,
            processor_func=self._process_alert_events
        )
        self.stream_processor.register_processor(alert_processor)
    
    async def _process_user_activity(self, events: List[LearningEvent]):
        """사용자 활동 처리"""
        user_sessions = defaultdict(list)
        
        for event in events:
            user_sessions[event.user_id].append(event)
        
        # 사용자별 활동 패턴 분석
        for user_id, user_events in user_sessions.items():
            activity_pattern = await self._analyze_activity_pattern(user_events)
            
            # 패턴을 캐시에 저장
            cache_key = f"user_activity_pattern:{user_id}"
            cache.set(cache_key, activity_pattern, timeout=1800)  # 30분
            
            # 실시간 업데이트 전송
            if self.stream_processor.channel_layer:
                await self.stream_processor.channel_layer.group_send(
                    f"user_{user_id}",
                    {
                        'type': 'activity_update',
                        'pattern': activity_pattern
                    }
                )
    
    async def _process_learning_progress(self, events: List[LearningEvent]):
        """학습 진도 처리"""
        progress_events = [e for e in events if e.event_type in 
                          ['content_completed', 'quiz_answered', 'concept_mastered']]
        
        user_progress = defaultdict(list)
        for event in progress_events:
            user_progress[event.user_id].append(event)
        
        # 진도 업데이트
        for user_id, progress_list in user_progress.items():
            progress_data = await self._calculate_real_time_progress(user_id, progress_list)
            
            # 진도 캐시 업데이트
            cache_key = f"realtime_progress:{user_id}"
            cache.set(cache_key, progress_data, timeout=3600)
            
            # 진도 업데이트 브로드캐스트
            if self.stream_processor.channel_layer:
                await self.stream_processor.channel_layer.group_send(
                    f"user_{user_id}",
                    {
                        'type': 'progress_update',
                        'progress': progress_data
                    }
                )
    
    async def _process_focus_events(self, events: List[LearningEvent]):
        """집중도 이벤트 처리"""
        focus_events = [e for e in events if e.event_type in 
                       ['idle', 'tab_switch', 'content_read', 'scroll_behavior']]
        
        user_focus = defaultdict(list)
        for event in focus_events:
            user_focus[event.user_id].append(event)
        
        # 실시간 집중도 분석
        for user_id, focus_list in user_focus.items():
            focus_score = await self._calculate_real_time_focus(focus_list)
            
            # 집중도가 낮으면 즉시 알림
            if focus_score < 60:
                await self._send_focus_alert(user_id, focus_score)
    
    async def _process_alert_events(self, events: List[LearningEvent]):
        """알림 이벤트 처리"""
        alert_events = [e for e in events if e.event_type in 
                       ['error_occurred', 'goal_achieved', 'milestone_reached']]
        
        for event in alert_events:
            await self._handle_immediate_alert(event)
    
    async def _analyze_activity_pattern(self, events: List[LearningEvent]) -> Dict[str, Any]:
        """활동 패턴 분석"""
        if not events:
            return {'pattern': 'inactive', 'score': 0}
        
        # 이벤트 타입별 분류
        productive_events = [e for e in events if e.event_type in 
                           ['content_read', 'problem_solved', 'note_taken']]
        idle_events = [e for e in events if e.event_type in ['idle', 'break']]
        
        productivity_ratio = len(productive_events) / len(events) if events else 0
        
        if productivity_ratio > 0.8:
            pattern = 'highly_productive'
        elif productivity_ratio > 0.6:
            pattern = 'productive'
        elif productivity_ratio > 0.4:
            pattern = 'moderately_active'
        else:
            pattern = 'low_activity'
        
        return {
            'pattern': pattern,
            'score': productivity_ratio * 100,
            'total_events': len(events),
            'productive_events': len(productive_events),
            'idle_events': len(idle_events),
            'timestamp': timezone.now().isoformat()
        }
    
    async def _calculate_real_time_progress(self, user_id: int, 
                                          events: List[LearningEvent]) -> Dict[str, Any]:
        """실시간 진도 계산"""
        if not events:
            return {'progress': 0, 'velocity': 0}
        
        # 시간당 진도 계산
        time_span = (events[-1].timestamp - events[0].timestamp).total_seconds() / 3600
        progress_velocity = len(events) / time_span if time_span > 0 else 0
        
        return {
            'recent_completions': len(events),
            'velocity_per_hour': progress_velocity,
            'trend': 'increasing' if progress_velocity > 2 else 'stable',
            'timestamp': timezone.now().isoformat()
        }
    
    async def _calculate_real_time_focus(self, events: List[LearningEvent]) -> float:
        """실시간 집중도 계산"""
        if not events:
            return 100.0
        
        productive_count = sum(1 for e in events 
                             if e.event_type in ['content_read', 'problem_solved'])
        distraction_count = sum(1 for e in events 
                              if e.event_type in ['idle', 'tab_switch'])
        
        focus_score = max(0, (productive_count - distraction_count * 0.5) / len(events) * 100)
        return min(100, focus_score)
    
    async def _send_focus_alert(self, user_id: int, focus_score: float):
        """집중도 알림 전송"""
        if self.stream_processor.channel_layer:
            await self.stream_processor.channel_layer.group_send(
                f"user_{user_id}",
                {
                    'type': 'focus_alert',
                    'score': focus_score,
                    'message': f'집중도가 {focus_score:.1f}%로 낮습니다. 잠시 휴식을 권장합니다.'
                }
            )
    
    async def _handle_immediate_alert(self, event: LearningEvent):
        """즉시 처리 알림"""
        if event.event_type == 'goal_achieved':
            await self._send_achievement_notification(event)
        elif event.event_type == 'error_occurred':
            await self._send_error_notification(event)
    
    async def _send_achievement_notification(self, event: LearningEvent):
        """달성 알림 전송"""
        if self.stream_processor.channel_layer:
            await self.stream_processor.channel_layer.group_send(
                f"user_{event.user_id}",
                {
                    'type': 'achievement_notification',
                    'achievement': event.metadata.get('achievement', '목표 달성'),
                    'message': '축하합니다! 목표를 달성하셨습니다.'
                }
            )
    
    async def _send_error_notification(self, event: LearningEvent):
        """오류 알림 전송"""
        if self.stream_processor.channel_layer:
            await self.stream_processor.channel_layer.group_send(
                f"user_{event.user_id}",
                {
                    'type': 'error_notification',
                    'error': event.metadata.get('error', '알 수 없는 오류'),
                    'message': '학습 중 오류가 발생했습니다.'
                }
            )


# 전역 스트림 처리기 인스턴스
stream_processor = RealTimeStreamProcessor()
learning_event_stream = LearningEventStream(stream_processor)


# 편의 함수들
async def start_streaming():
    """스트리밍 처리 시작"""
    await stream_processor.start_processing()


async def stop_streaming():
    """스트리밍 처리 중지"""
    await stream_processor.stop_processing()


async def push_learning_event(stream_name: str, event: LearningEvent):
    """학습 이벤트를 스트림에 추가"""
    await stream_processor.push_event(stream_name, event)


async def get_streaming_status() -> Dict[str, Any]:
    """스트리밍 상태 조회"""
    return await stream_processor.get_stream_status()