"""
Claude AI client for natural language processing and event parsing.

Handles communication with Anthropic's Claude API for parsing Korean text into structured event data.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from anthropic import AsyncAnthropic

from app.core.config import settings
from app.core.logger import log_ai_request, mask_sensitive_data
from app.schemas.event import ParsedEventData

logger = structlog.get_logger(__name__)


class ClaudeAPIError(Exception):
    """Base exception for Claude API errors."""
    
    def __init__(self, message: str, error_type: str = None, details: Dict[str, Any] = None):
        self.message = message
        self.error_type = error_type
        self.details = details or {}
        super().__init__(message)


class ClaudeParseError(ClaudeAPIError):
    """Exception raised when Claude response cannot be parsed."""
    
    def __init__(self, response_text: str, parse_error: str):
        self.response_text = response_text
        self.parse_error = parse_error
        super().__init__(f"Failed to parse Claude response: {parse_error}", "parse_error")


class ClaudeClient:
    """
    Claude AI client for natural language processing.
    
    Specialized for parsing Korean text into structured calendar event data.
    """
    
    def __init__(self):
        self.client = AsyncAnthropic(api_key=settings.CLAUDE_API_KEY)
        self.model = settings.CLAUDE_MODEL
        self.timeout = settings.AI_TIMEOUT_SECONDS
        self.max_retries = settings.MAX_RETRY_ATTEMPTS
        
        # Load the system prompt
        self.system_prompt = self._load_system_prompt()
    
    def _load_system_prompt(self) -> str:
        """Load the system prompt from file."""
        try:
            prompt_path = Path(__file__).parent.parent.parent / "ai" / "prompts" / "timetree_event_parser.md"
            with open(prompt_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            logger.info("System prompt loaded successfully", 
                       prompt_size=len(content))
            return content
            
        except Exception as e:
            logger.error("Failed to load system prompt", error=str(e))
            raise ClaudeAPIError(f"Failed to load system prompt: {str(e)}", "prompt_load_error")
    
    def _get_current_context(self) -> Dict[str, Any]:
        """Get current date/time context for the AI."""
        now = datetime.now(timezone.utc)
        seoul_time = now.astimezone(timezone.utc).replace(tzinfo=None)  # Simplified for example
        
        return {
            "current_date": seoul_time.strftime("%Y-%m-%d"),
            "current_time": seoul_time.strftime("%H:%M"),
            "current_day": seoul_time.strftime("%A"),
            "current_week": seoul_time.isocalendar()[1],
            "timezone": "Asia/Seoul"
        }
    
    async def parse_natural_language(
        self,
        text: str,
        user_timezone: str = "Asia/Seoul",
        additional_context: Dict[str, Any] = None
    ) -> ParsedEventData:
        """
        Parse natural language text into structured event data.
        
        Args:
            text: Natural language text to parse
            user_timezone: User's timezone
            additional_context: Additional context for parsing
        
        Returns:
            ParsedEventData: Structured event data
        
        Raises:
            ClaudeAPIError: On API or parsing errors
        """
        try:
            # Prepare context
            context = self._get_current_context()
            context["user_timezone"] = user_timezone
            
            if additional_context:
                context.update(additional_context)
            
            # Prepare the prompt
            user_prompt = f"""
현재 컨텍스트:
- 오늘 날짜: {context['current_date']}
- 현재 시간: {context['current_time']}
- 요일: {context['current_day']}
- 시간대: {context['user_timezone']}

파싱할 텍스트: "{text}"

위 텍스트를 분석하여 JSON 형태의 이벤트 데이터로 변환해주세요.
"""
            
            start_time = datetime.now(timezone.utc)
            
            # Make API request
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                temperature=0.1,  # Low temperature for consistent parsing
                system=self.system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ]
            )
            
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            # Extract response text
            response_text = response.content[0].text.strip()
            
            # Log API request
            log_ai_request(
                provider="claude",
                model=self.model,
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                duration_ms=duration_ms,
                success=True,
                input_text=text[:100] + "..." if len(text) > 100 else text
            )
            
            # Parse JSON response
            try:
                parsed_data = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error("Failed to parse Claude JSON response",
                           response_text=response_text[:500],
                           error=str(e))
                
                # Try to extract JSON from response if it contains additional text
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    try:
                        cleaned_response = response_text[json_start:json_end]
                        parsed_data = json.loads(cleaned_response)
                        logger.info("Successfully extracted JSON from Claude response")
                    except json.JSONDecodeError:
                        raise ClaudeParseError(response_text, str(e))
                else:
                    raise ClaudeParseError(response_text, str(e))
            
            # Validate and create ParsedEventData
            try:
                event_data = ParsedEventData(**parsed_data)
                
                logger.info("Successfully parsed natural language",
                           input_text=text[:50] + "..." if len(text) > 50 else text,
                           confidence=event_data.confidence,
                           title=event_data.title)
                
                return event_data
                
            except Exception as e:
                logger.error("Failed to validate parsed data",
                           parsed_data=parsed_data,
                           error=str(e))
                raise ClaudeAPIError(f"Invalid parsed data structure: {str(e)}", "validation_error")
        
        except ClaudeAPIError:
            raise
        except Exception as e:
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            log_ai_request(
                provider="claude",
                model=self.model,
                duration_ms=duration_ms,
                success=False,
                error=str(e),
                input_text=text[:100] + "..." if len(text) > 100 else text
            )
            
            logger.error("Claude API request failed", error=str(e))
            raise ClaudeAPIError(f"API request failed: {str(e)}", "api_error")
    
    async def parse_with_retry(
        self,
        text: str,
        user_timezone: str = "Asia/Seoul",
        additional_context: Dict[str, Any] = None,
        retry_count: int = 0
    ) -> ParsedEventData:
        """
        Parse natural language with automatic retry on failures.
        
        Args:
            text: Natural language text to parse
            user_timezone: User's timezone
            additional_context: Additional context for parsing
            retry_count: Current retry attempt
        
        Returns:
            ParsedEventData: Structured event data
        """
        try:
            return await self.parse_natural_language(text, user_timezone, additional_context)
            
        except (ClaudeParseError, ClaudeAPIError) as e:
            if retry_count < self.max_retries:
                logger.warning("Parse attempt failed, retrying",
                             retry_count=retry_count,
                             error=str(e))
                
                # Add retry context
                retry_context = additional_context or {}
                retry_context.update({
                    "retry_attempt": retry_count + 1,
                    "previous_error": str(e),
                    "instruction": "이전 시도에서 오류가 발생했습니다. 더 정확한 JSON 형태로 응답해주세요."
                })
                
                return await self.parse_with_retry(
                    text, user_timezone, retry_context, retry_count + 1
                )
            else:
                logger.error("Max retries exceeded for natural language parsing",
                           text=text[:100],
                           final_error=str(e))
                raise
    
    async def validate_event_data(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and normalize event data using AI.
        
        Args:
            event_data: Event data to validate
        
        Returns:
            Dict[str, Any]: Validation results and suggestions
        """
        try:
            validation_prompt = f"""
다음 이벤트 데이터를 검증하고 개선사항을 제안해주세요:

{json.dumps(event_data, ensure_ascii=False, indent=2)}

다음 형식으로 응답해주세요:
{{
  "is_valid": true/false,
  "issues": ["문제점 목록"],
  "suggestions": ["개선사항 목록"],
  "confidence_score": 0.0-1.0,
  "recommended_changes": {{
    "field_name": "suggested_value"
  }}
}}
"""
            
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                temperature=0.2,
                system="You are a calendar event validation assistant. Respond only in JSON format.",
                messages=[
                    {
                        "role": "user",
                        "content": validation_prompt
                    }
                ]
            )
            
            response_text = response.content[0].text.strip()
            validation_result = json.loads(response_text)
            
            logger.info("Event data validated",
                       is_valid=validation_result.get("is_valid"),
                       confidence=validation_result.get("confidence_score"))
            
            return validation_result
            
        except Exception as e:
            logger.error("Event validation failed", error=str(e))
            return {
                "is_valid": True,  # Default to valid if validation fails
                "issues": [],
                "suggestions": [],
                "confidence_score": 0.5,
                "recommended_changes": {}
            }
    
    async def suggest_similar_events(
        self,
        parsed_event: ParsedEventData,
        user_history: List[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Suggest similar events based on parsed event and user history.
        
        Args:
            parsed_event: Recently parsed event
            user_history: User's event history
        
        Returns:
            List[Dict[str, Any]]: Similar event suggestions
        """
        try:
            history_context = ""
            if user_history:
                recent_events = user_history[-10:]  # Last 10 events
                history_context = "사용자의 최근 이벤트:\n"
                for event in recent_events:
                    history_context += f"- {event.get('title', '')}: {event.get('start_at', '')}\n"
            
            suggestion_prompt = f"""
다음 이벤트와 유사한 이벤트들을 제안해주세요:

새 이벤트:
제목: {parsed_event.title}
시간: {parsed_event.start_at}
카테고리: {parsed_event.category}

{history_context}

다음 형식으로 3-5개의 유사한 이벤트를 제안해주세요:
{{
  "suggestions": [
    {{
      "title": "제안 이벤트 제목",
      "reason": "제안 이유",
      "similarity_score": 0.0-1.0,
      "suggested_time": "추천 시간",
      "category": "카테고리"
    }}
  ]
}}
"""
            
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                temperature=0.3,
                system="You are a calendar event suggestion assistant. Respond only in JSON format.",
                messages=[
                    {
                        "role": "user",
                        "content": suggestion_prompt
                    }
                ]
            )
            
            response_text = response.content[0].text.strip()
            suggestions = json.loads(response_text)
            
            logger.info("Event suggestions generated",
                       count=len(suggestions.get("suggestions", [])))
            
            return suggestions.get("suggestions", [])
            
        except Exception as e:
            logger.error("Event suggestion failed", error=str(e))
            return []


# Global Claude client instance
claude_client = ClaudeClient()