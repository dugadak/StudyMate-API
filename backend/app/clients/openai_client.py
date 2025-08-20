import json
import hashlib
from typing import Dict, Any, Optional
import openai
import asyncio
import structlog
from datetime import datetime

from app.core.config import settings
from app.core.exceptions import ExternalServiceError, ValidationError
from app.core.cache import CacheManager

logger = structlog.get_logger(__name__)

class OpenAIClient:
    """OpenAI ChatGPT API 클라이언트"""
    
    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.cache = CacheManager()
        self.model = "gpt-4o"  # 최신 GPT-4o 모델 사용
        self.max_tokens = 2000
        self.temperature = 0.3  # 일관된 결과를 위해 낮은 온도 설정
        
    async def parse_text_to_event(
        self, 
        text: str, 
        user_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        자연어 텍스트를 TimeTree 이벤트 형식으로 파싱합니다.
        """
        try:
            # 캐시 키 생성
            cache_key = self._generate_cache_key(text, user_context or {})
            
            # 캐시에서 결과 확인
            cached_result = await self.cache.get(cache_key)
            if cached_result:
                logger.info("캐시된 파싱 결과 사용", text_length=len(text))
                return cached_result
            
            logger.info("OpenAI ChatGPT API 파싱 시작", text=text[:50] + "...")
            
            # 시스템 프롬프트 로드
            system_prompt = await self._load_system_prompt()
            
            # 사용자 컨텍스트 정보 추가
            context_info = self._format_user_context(user_context or {})
            user_prompt = f"{context_info}\n\n파싱할 텍스트: {text}"
            
            # ChatGPT API 호출
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                response_format={"type": "json_object"}  # JSON 형식 강제
            )
            
            # 응답 파싱
            result_text = response.choices[0].message.content
            parsed_result = json.loads(result_text)
            
            # 결과 검증
            validated_result = await self._validate_parsing_result(parsed_result, text)
            
            # 캐시에 저장 (24시간)
            await self.cache.set(cache_key, validated_result, expire=86400)
            
            logger.info("OpenAI 파싱 완료", 
                       confidence=validated_result.get('confidence', 0),
                       title=validated_result.get('title', 'Unknown'))
            
            return validated_result
            
        except json.JSONDecodeError as e:
            logger.error("OpenAI 응답 JSON 파싱 실패", error=str(e))
            raise ValidationError("AI 응답 형식이 올바르지 않습니다")
            
        except openai.RateLimitError as e:
            logger.error("OpenAI API 요청 한도 초과", error=str(e))
            raise ExternalServiceError("AI 서비스 요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요")
            
        except openai.APIError as e:
            logger.error("OpenAI API 오류", error=str(e))
            raise ExternalServiceError(f"AI 서비스 오류: {str(e)}")
            
        except Exception as e:
            logger.error("OpenAI 클라이언트 예상치 못한 오류", error=str(e))
            raise ExternalServiceError("AI 파싱 중 오류가 발생했습니다")
    
    async def _load_system_prompt(self) -> str:
        """시스템 프롬프트를 로드합니다."""
        try:
            with open("backend/prompts/chatgpt_event_parser.md", "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            # 기본 프롬프트 사용
            return self._get_default_system_prompt()
    
    def _get_default_system_prompt(self) -> str:
        """기본 시스템 프롬프트"""
        return """당신은 한국어 자연어를 TimeTree 캘린더 이벤트로 변환하는 전문 AI입니다.

다음 JSON 형식으로만 응답하세요:
{
  "title": "이벤트 제목",
  "description": "상세 설명 (선택사항)",
  "start_at": "YYYY-MM-DDTHH:MM:SS+09:00",
  "end_at": "YYYY-MM-DDTHH:MM:SS+09:00",
  "start_timezone": "Asia/Seoul",
  "end_timezone": "Asia/Seoul",
  "all_day": false,
  "location": "장소 (있는 경우)",
  "recurrence_rule": "반복 규칙 (있는 경우)",
  "category": "일정 카테고리 (work/personal/health/family/social/travel/education/other)",
  "confidence": 0.95,
  "suggestions": ["추천사항1", "추천사항2"],
  "extracted_entities": {
    "datetime": "추출된 날짜/시간 정보",
    "location": "추출된 장소 정보",
    "duration": "추출된 기간 정보",
    "participants": "추출된 참석자 정보"
  }
}

규칙:
1. 현재 시간: {current_time}
2. 상대적 표현("내일", "다음주" 등)을 절대 날짜로 변환
3. 시간이 없으면 오전 9시(09:00) 기본값 사용
4. 종료시간이 없으면 시작시간 + 1시간
5. confidence는 0.0~1.0 범위
6. 반드시 JSON 형식으로만 응답"""
    
    def _format_user_context(self, context: Dict[str, Any]) -> str:
        """사용자 컨텍스트 정보를 포맷팅합니다."""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        timezone = context.get('timezone', 'Asia/Seoul')
        
        context_str = f"현재 시간: {current_time} ({timezone})"
        
        if context.get('default_calendar_id'):
            context_str += f"\n기본 캘린더: {context['default_calendar_id']}"
            
        if context.get('user_preferences'):
            prefs = context['user_preferences']
            if prefs.get('default_event_duration'):
                context_str += f"\n기본 이벤트 길이: {prefs['default_event_duration']}분"
                
        return context_str
    
    async def _validate_parsing_result(self, result: Dict[str, Any], original_text: str) -> Dict[str, Any]:
        """파싱 결과를 검증하고 필요한 필드를 보완합니다."""
        # 필수 필드 확인
        required_fields = ['title', 'start_at']
        for field in required_fields:
            if not result.get(field):
                raise ValidationError(f"필수 필드 '{field}'가 누락되었습니다")
        
        # 신뢰도 검증
        confidence = result.get('confidence', 0.0)
        if confidence < 0.3:
            raise ValidationError("파싱 신뢰도가 너무 낮습니다. 더 구체적인 정보를 제공해주세요")
        
        # 기본값 설정
        result.setdefault('description', None)
        result.setdefault('all_day', False)
        result.setdefault('location', None)
        result.setdefault('recurrence_rule', None)
        result.setdefault('category', 'other')
        result.setdefault('suggestions', [])
        result.setdefault('start_timezone', 'Asia/Seoul')
        result.setdefault('end_timezone', 'Asia/Seoul')
        
        # 종료시간이 없으면 시작시간 + 1시간으로 설정
        if not result.get('end_at') and result.get('start_at'):
            try:
                start_dt = datetime.fromisoformat(result['start_at'].replace('Z', '+00:00'))
                end_dt = start_dt.replace(hour=start_dt.hour + 1)
                result['end_at'] = end_dt.isoformat()
            except ValueError:
                result['end_at'] = result['start_at']  # 파싱 실패시 동일 시간 사용
        
        # extracted_entities 기본값
        result.setdefault('extracted_entities', {
            'datetime': None,
            'location': None,
            'duration': None,
            'participants': None
        })
        
        return result
    
    def _generate_cache_key(self, text: str, context: Dict[str, Any]) -> str:
        """캐시 키를 생성합니다."""
        content = f"{text}_{json.dumps(context, sort_keys=True)}"
        return f"openai_parse_{hashlib.md5(content.encode()).hexdigest()}"
    
    async def test_connection(self) -> bool:
        """OpenAI API 연결 테스트"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "테스트"}],
                max_tokens=10
            )
            return bool(response.choices)
        except Exception as e:
            logger.error("OpenAI API 연결 테스트 실패", error=str(e))
            return False
    
    async def get_usage_info(self) -> Dict[str, Any]:
        """API 사용량 정보를 반환합니다."""
        # OpenAI API에서 직접 사용량 조회는 제한적이므로
        # 로컬 캐시나 데이터베이스에서 추적한 정보 반환
        return {
            "model": self.model,
            "requests_today": 0,  # 실제 구현시 데이터베이스에서 조회
            "tokens_used_today": 0,
            "last_request": None
        }