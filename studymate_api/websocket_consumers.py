"""
WebSocket 컨슈머 - 실시간 학습 분석 데이터 전송

실시간으로 학습 분석 결과를 클라이언트에 전송하고 사용자 상호작용을 처리합니다.
"""

import json
import logging
from typing import Dict, Any, Optional
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model

from .realtime_analytics import realtime_analyzer, track_learning_event

logger = logging.getLogger(__name__)
User = get_user_model()


class LearningAnalyticsConsumer(AsyncWebsocketConsumer):
    """실시간 학습 분석 WebSocket 컨슈머"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_id = None
        self.session_id = None
        self.group_name = None
    
    async def connect(self):
        """WebSocket 연결"""
        # 사용자 인증 확인
        user = await self._get_user()
        if isinstance(user, AnonymousUser):
            logger.warning("비인증 사용자의 WebSocket 연결 시도")
            await self.close()
            return
        
        self.user_id = user.id
        self.group_name = f"user_{self.user_id}"
        
        # 그룹에 추가
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # 연결 확인 메시지 전송
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'user_id': self.user_id,
            'message': '실시간 학습 분석 연결이 완료되었습니다.'
        }))
        
        logger.info(f"사용자 {self.user_id}의 WebSocket 연결 완료")
    
    async def disconnect(self, close_code):
        """WebSocket 연결 해제"""
        if self.group_name:
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
        
        # 활성 세션이 있으면 종료
        if self.session_id:
            try:
                await realtime_analyzer.end_learning_session(self.session_id)
                logger.info(f"세션 {self.session_id} 자동 종료")
            except Exception as e:
                logger.error(f"세션 자동 종료 실패: {e}")
        
        logger.info(f"사용자 {self.user_id}의 WebSocket 연결 해제")
    
    async def receive(self, text_data):
        """클라이언트로부터 메시지 수신"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'start_session':
                await self._handle_start_session(data)
            elif message_type == 'end_session':
                await self._handle_end_session(data)
            elif message_type == 'track_event':
                await self._handle_track_event(data)
            elif message_type == 'get_status':
                await self._handle_get_status(data)
            elif message_type == 'ping':
                await self._handle_ping()
            else:
                await self._send_error(f"알 수 없는 메시지 타입: {message_type}")
                
        except json.JSONDecodeError:
            await self._send_error("잘못된 JSON 형식")
        except Exception as e:
            logger.error(f"메시지 처리 오류: {e}")
            await self._send_error("메시지 처리 중 오류가 발생했습니다.")
    
    async def _handle_start_session(self, data: Dict[str, Any]):
        """학습 세션 시작 처리"""
        try:
            subject_id = data.get('subject_id')
            
            # 기존 세션 종료
            if self.session_id:
                await realtime_analyzer.end_learning_session(self.session_id)
            
            # 새 세션 시작
            self.session_id = await realtime_analyzer.start_learning_session(
                self.user_id, subject_id
            )
            
            await self.send(text_data=json.dumps({
                'type': 'session_started',
                'session_id': self.session_id,
                'subject_id': subject_id,
                'message': '학습 세션이 시작되었습니다.'
            }))
            
            logger.info(f"사용자 {self.user_id} 학습 세션 시작: {self.session_id}")
            
        except Exception as e:
            logger.error(f"세션 시작 오류: {e}")
            await self._send_error("세션 시작 중 오류가 발생했습니다.")
    
    async def _handle_end_session(self, data: Dict[str, Any]):
        """학습 세션 종료 처리"""
        try:
            if not self.session_id:
                await self._send_error("종료할 활성 세션이 없습니다.")
                return
            
            summary = await realtime_analyzer.end_learning_session(self.session_id)
            
            await self.send(text_data=json.dumps({
                'type': 'session_ended',
                'session_id': self.session_id,
                'summary': summary,
                'message': '학습 세션이 종료되었습니다.'
            }))
            
            logger.info(f"사용자 {self.user_id} 학습 세션 종료: {self.session_id}")
            self.session_id = None
            
        except Exception as e:
            logger.error(f"세션 종료 오류: {e}")
            await self._send_error("세션 종료 중 오류가 발생했습니다.")
    
    async def _handle_track_event(self, data: Dict[str, Any]):
        """학습 이벤트 추적 처리"""
        try:
            if not self.session_id:
                await self._send_error("활성 세션이 없습니다.")
                return
            
            event_type = data.get('event_type')
            metadata = data.get('metadata', {})
            
            if not event_type:
                await self._send_error("이벤트 타입이 필요합니다.")
                return
            
            await track_learning_event(self.session_id, event_type, metadata)
            
            # 확인 메시지는 전송하지 않음 (너무 많은 메시지 방지)
            
        except Exception as e:
            logger.error(f"이벤트 추적 오류: {e}")
            await self._send_error("이벤트 추적 중 오류가 발생했습니다.")
    
    async def _handle_get_status(self, data: Dict[str, Any]):
        """세션 상태 조회 처리"""
        try:
            if not self.session_id:
                await self.send(text_data=json.dumps({
                    'type': 'status_response',
                    'status': None,
                    'message': '활성 세션이 없습니다.'
                }))
                return
            
            status = realtime_analyzer.get_session_status(self.session_id)
            
            await self.send(text_data=json.dumps({
                'type': 'status_response',
                'status': status
            }))
            
        except Exception as e:
            logger.error(f"상태 조회 오류: {e}")
            await self._send_error("상태 조회 중 오류가 발생했습니다.")
    
    async def _handle_ping(self):
        """핑 처리"""
        await self.send(text_data=json.dumps({
            'type': 'pong',
            'timestamp': str(timezone.now())
        }))
    
    # 채널 레이어 메시지 핸들러들
    async def learning_analysis(self, event):
        """실시간 분석 결과 전송"""
        await self.send(text_data=json.dumps({
            'type': 'learning_analysis',
            'analysis': event['data']
        }))
    
    async def urgent_alert(self, event):
        """긴급 알림 전송"""
        await self.send(text_data=json.dumps({
            'type': 'urgent_alert',
            'alert': event['alert']
        }))
    
    async def focus_reminder(self, event):
        """집중 알림 전송"""
        await self.send(text_data=json.dumps({
            'type': 'focus_reminder',
            'message': event['message']
        }))
    
    async def positive_feedback(self, event):
        """긍정적 피드백 전송"""
        await self.send(text_data=json.dumps({
            'type': 'positive_feedback',
            'message': event['message']
        }))
    
    async def _send_error(self, message: str):
        """에러 메시지 전송"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message
        }))
    
    @database_sync_to_async
    def _get_user(self):
        """현재 사용자 조회"""
        return self.scope["user"]


class StudyRoomConsumer(AsyncWebsocketConsumer):
    """학습방 WebSocket 컨슈머 (그룹 학습용)"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.room_id = None
        self.user_id = None
        self.room_group_name = None
    
    async def connect(self):
        """학습방 연결"""
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f"study_room_{self.room_id}"
        
        # 사용자 인증 확인
        user = await self._get_user()
        if isinstance(user, AnonymousUser):
            await self.close()
            return
        
        self.user_id = user.id
        
        # 그룹에 추가
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # 사용자 입장 알림
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_joined',
                'user_id': self.user_id,
                'username': user.username
            }
        )
        
        logger.info(f"사용자 {self.user_id}가 학습방 {self.room_id}에 입장")
    
    async def disconnect(self, close_code):
        """학습방 연결 해제"""
        if self.room_group_name:
            # 사용자 퇴장 알림
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_left',
                    'user_id': self.user_id
                }
            )
            
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
        
        logger.info(f"사용자 {self.user_id}가 학습방 {self.room_id}에서 퇴장")
    
    async def receive(self, text_data):
        """학습방 메시지 수신"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'study_status':
                await self._handle_study_status(data)
            elif message_type == 'focus_check':
                await self._handle_focus_check(data)
            elif message_type == 'break_request':
                await self._handle_break_request(data)
            elif message_type == 'goal_share':
                await self._handle_goal_share(data)
            else:
                await self._send_error(f"알 수 없는 메시지 타입: {message_type}")
                
        except json.JSONDecodeError:
            await self._send_error("잘못된 JSON 형식")
        except Exception as e:
            logger.error(f"학습방 메시지 처리 오류: {e}")
            await self._send_error("메시지 처리 중 오류가 발생했습니다.")
    
    async def _handle_study_status(self, data: Dict[str, Any]):
        """학습 상태 공유"""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'study_status_update',
                'user_id': self.user_id,
                'status': data.get('status'),
                'subject': data.get('subject'),
                'progress': data.get('progress')
            }
        )
    
    async def _handle_focus_check(self, data: Dict[str, Any]):
        """집중도 체크 요청"""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'focus_check_request',
                'requesting_user': self.user_id,
                'message': '모두 집중하고 계신가요? 집중도를 체크해주세요!'
            }
        )
    
    async def _handle_break_request(self, data: Dict[str, Any]):
        """휴식 제안"""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'break_suggestion',
                'suggesting_user': self.user_id,
                'break_duration': data.get('duration', 15),
                'message': f'{data.get("duration", 15)}분 휴식을 제안합니다.'
            }
        )
    
    async def _handle_goal_share(self, data: Dict[str, Any]):
        """목표 공유"""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'goal_shared',
                'user_id': self.user_id,
                'goal': data.get('goal'),
                'target_time': data.get('target_time')
            }
        )
    
    # 채널 레이어 메시지 핸들러들
    async def user_joined(self, event):
        """사용자 입장 알림"""
        await self.send(text_data=json.dumps({
            'type': 'user_joined',
            'user_id': event['user_id'],
            'username': event['username'],
            'message': f"{event['username']}님이 학습방에 입장했습니다."
        }))
    
    async def user_left(self, event):
        """사용자 퇴장 알림"""
        await self.send(text_data=json.dumps({
            'type': 'user_left',
            'user_id': event['user_id'],
            'message': "사용자가 학습방에서 나갔습니다."
        }))
    
    async def study_status_update(self, event):
        """학습 상태 업데이트"""
        await self.send(text_data=json.dumps({
            'type': 'study_status_update',
            'user_id': event['user_id'],
            'status': event['status'],
            'subject': event['subject'],
            'progress': event['progress']
        }))
    
    async def focus_check_request(self, event):
        """집중도 체크 요청"""
        await self.send(text_data=json.dumps({
            'type': 'focus_check_request',
            'requesting_user': event['requesting_user'],
            'message': event['message']
        }))
    
    async def break_suggestion(self, event):
        """휴식 제안"""
        await self.send(text_data=json.dumps({
            'type': 'break_suggestion',
            'suggesting_user': event['suggesting_user'],
            'break_duration': event['break_duration'],
            'message': event['message']
        }))
    
    async def goal_shared(self, event):
        """목표 공유"""
        await self.send(text_data=json.dumps({
            'type': 'goal_shared',
            'user_id': event['user_id'],
            'goal': event['goal'],
            'target_time': event['target_time']
        }))
    
    async def _send_error(self, message: str):
        """에러 메시지 전송"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message
        }))
    
    @database_sync_to_async
    def _get_user(self):
        """현재 사용자 조회"""
        return self.scope["user"]


class SystemMonitoringConsumer(AsyncWebsocketConsumer):
    """시스템 모니터링 WebSocket 컨슈머 (관리자용)"""
    
    async def connect(self):
        """시스템 모니터링 연결"""
        user = await self._get_user()
        
        # 관리자 권한 확인
        if isinstance(user, AnonymousUser) or not user.is_staff:
            await self.close()
            return
        
        await self.channel_layer.group_add("system_monitoring", self.channel_name)
        await self.accept()
        
        # 현재 시스템 상태 전송
        await self._send_system_status()
        
        logger.info(f"관리자 {user.id}의 시스템 모니터링 연결")
    
    async def disconnect(self, close_code):
        """시스템 모니터링 연결 해제"""
        await self.channel_layer.group_discard("system_monitoring", self.channel_name)
    
    async def receive(self, text_data):
        """시스템 모니터링 명령 수신"""
        try:
            data = json.loads(text_data)
            command = data.get('command')
            
            if command == 'get_active_sessions':
                await self._send_active_sessions()
            elif command == 'get_system_metrics':
                await self._send_system_metrics()
            elif command == 'force_session_end':
                await self._force_session_end(data.get('session_id'))
            
        except Exception as e:
            logger.error(f"시스템 모니터링 명령 오류: {e}")
    
    async def _send_system_status(self):
        """시스템 상태 전송"""
        active_sessions = realtime_analyzer.get_active_sessions_count()
        
        await self.send(text_data=json.dumps({
            'type': 'system_status',
            'active_sessions': active_sessions,
            'timestamp': str(timezone.now())
        }))
    
    async def _send_active_sessions(self):
        """활성 세션 목록 전송"""
        sessions = []
        for session_id, session in realtime_analyzer.active_sessions.items():
            sessions.append({
                'session_id': session_id,
                'user_id': session.user_id,
                'duration': session.total_time,
                'focus_score': session.focus_score,
                'state': session.state.value
            })
        
        await self.send(text_data=json.dumps({
            'type': 'active_sessions',
            'sessions': sessions
        }))
    
    async def _send_system_metrics(self):
        """시스템 메트릭 전송"""
        # 실제 구현에서는 더 상세한 메트릭 수집
        await self.send(text_data=json.dumps({
            'type': 'system_metrics',
            'cpu_usage': 0,  # psutil 등을 사용하여 실제 값 수집
            'memory_usage': 0,
            'active_connections': len(realtime_analyzer.active_sessions)
        }))
    
    async def _force_session_end(self, session_id: str):
        """강제 세션 종료"""
        try:
            if session_id in realtime_analyzer.active_sessions:
                await realtime_analyzer.end_learning_session(session_id)
                await self.send(text_data=json.dumps({
                    'type': 'session_ended',
                    'session_id': session_id,
                    'message': '세션이 강제 종료되었습니다.'
                }))
        except Exception as e:
            logger.error(f"강제 세션 종료 오류: {e}")
    
    @database_sync_to_async
    def _get_user(self):
        """현재 사용자 조회"""
        return self.scope["user"]