from typing import Dict, Any, Optional
from datetime import datetime
import structlog

from app.clients.openai_client import OpenAIClient
from app.core.exceptions import ExternalServiceError, ValidationError
from app.core.config import settings

logger = structlog.get_logger(__name__)

class NLPService:
    """OpenAI ChatGPT 기반 자연어 처리 서비스"""
    
    def __init__(self):
        if not settings.OPENAI_API_KEY:
            logger.error("OpenAI API 키가 설정되지 않았습니다")
            raise ValueError("OPENAI_API_KEY 환경변수를 설정해주세요")
        
        self.openai_client = OpenAIClient()
        logger.info("OpenAI ChatGPT 기반 NLP 서비스 초기화 완료")
    
    async def parse_natural_language_to_event(
        self, 
        text: str, 
        user_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        자연어 텍스트를 이벤트 데이터로 변환합니다.
        
        OpenAI ChatGPT를 사용하여 한국어 자연어를 TimeTree 이벤트 형식으로 파싱합니다.
        """
        if not text or not text.strip():
            raise ValidationError("빈 텍스트는 파싱할 수 없습니다")
        
        text = text.strip()
        if len(text) > 1000:  # 텍스트 길이 제한
            raise ValidationError("텍스트가 너무 깁니다. 1000자 이내로 입력해주세요")
        
        user_context = user_context or {}
        
        logger.info("ChatGPT 자연어 파싱 시작", 
                   text_length=len(text),
                   has_context=bool(user_context))
        
        try:
            # OpenAI ChatGPT로 파싱
            result = await self.openai_client.parse_text_to_event(text, user_context)
            
            # 결과 검증 및 보완
            validated_result = self._validate_and_enhance_result(result, text)
            
            # 처리 메타데이터 추가
            validated_result['ai_provider'] = 'openai-chatgpt'
            validated_result['model'] = 'gpt-4o'
            validated_result['processing_timestamp'] = datetime.utcnow().isoformat()
            validated_result['original_text'] = text
            
            logger.info("ChatGPT 파싱 성공", 
                       confidence=validated_result.get('confidence', 0),
                       title=validated_result.get('title', 'Unknown'),
                       category=validated_result.get('category', 'other'))
            
            return validated_result
            
        except ValidationError:
            # ValidationError는 그대로 전파
            raise
            
        except ExternalServiceError:
            # ExternalServiceError도 그대로 전파  
            raise
            
        except Exception as e:
            logger.error("ChatGPT 파싱 중 예상치 못한 오료", error=str(e))
            raise ExternalServiceError(f"AI 파싱 중 오류가 발생했습니다: {str(e)}")
    
    def _validate_and_enhance_result(self, result: Dict[str, Any], original_text: str) -> Dict[str, Any]:
        """파싱 결과를 검증하고 보완합니다."""
        if not isinstance(result, dict):
            raise ValidationError("AI 응답 형식이 올바르지 않습니다")
        
        # 필수 필드 확인
        required_fields = ['title', 'start_at']
        missing_fields = [field for field in required_fields if not result.get(field)]
        if missing_fields:
            raise ValidationError(f"필수 필드가 누락되었습니다: {', '.join(missing_fields)}")
        
        # 신뢰도 검증
        confidence = result.get('confidence', 0.0)
        if not isinstance(confidence, (int, float)) or confidence < 0.0 or confidence > 1.0:
            logger.warning("신뢰도 값이 비정상적입니다", confidence=confidence)
            result['confidence'] = 0.5  # 기본값 설정
        
        if confidence < 0.3:
            raise ValidationError(
                "파싱 신뢰도가 너무 낮습니다. 더 구체적이고 명확한 정보를 제공해주세요.\n"
                f"예: '내일 오후 3시에 강남역에서 김과장과 회의' 형태로 작성해주세요."
            )
        
        # 카테고리 검증 및 기본값 설정
        valid_categories = {
            'work', 'personal', 'health', 'family', 
            'social', 'travel', 'education', 'other'
        }
        if result.get('category') not in valid_categories:
            result['category'] = 'other'
        
        # 날짜 형식 검증 (간단한 체크)
        start_at = result.get('start_at', '')
        if not isinstance(start_at, str) or len(start_at) < 19:  # YYYY-MM-DDTHH:MM:SS 최소 길이
            raise ValidationError("시작 시간 형식이 올바르지 않습니다")
        
        # 기본값 설정
        result.setdefault('description', None)
        result.setdefault('all_day', False)
        result.setdefault('location', None)
        result.setdefault('recurrence_rule', None)
        result.setdefault('start_timezone', 'Asia/Seoul')
        result.setdefault('end_timezone', 'Asia/Seoul')
        result.setdefault('suggestions', [])
        
        # extracted_entities 기본 구조 확인
        entities = result.setdefault('extracted_entities', {})
        entities.setdefault('datetime', None)
        entities.setdefault('location', None) 
        entities.setdefault('duration', None)
        entities.setdefault('participants', None)
        
        # 품질 점수 계산
        quality_score = self._calculate_quality_score(result, original_text)
        result['quality_score'] = quality_score
        
        return result
    
    def _calculate_quality_score(self, result: Dict[str, Any], original_text: str) -> float:
        """파싱 결과의 품질 점수를 계산합니다."""
        score = 0.0
        
        # 기본 필드 존재 여부 (40점)
        if result.get('title'):
            score += 20
        if result.get('start_at'):
            score += 20
        
        # 추가 정보 풍부도 (30점)
        if result.get('location'):
            score += 10
        if result.get('description'):
            score += 10  
        if result.get('end_at'):
            score += 10
        
        # 카테고리 분류 정확도 (15점)
        if result.get('category') and result['category'] != 'other':
            score += 15
        
        # 추출된 엔터티 정보 (15점)
        entities = result.get('extracted_entities', {})
        entity_count = sum(1 for v in entities.values() if v)
        score += min(entity_count * 3.75, 15)
        
        return min(score / 100.0, 1.0)  # 0.0-1.0 범위로 정규화
    
    async def get_service_status(self) -> Dict[str, Any]:
        """OpenAI ChatGPT 서비스 상태를 확인합니다."""
        try:
            is_available = await self.openai_client.test_connection()
            usage_info = await self.openai_client.get_usage_info()
            
            return {
                'provider': 'openai-chatgpt',
                'model': 'gpt-4o',
                'available': is_available,
                'status': 'healthy' if is_available else 'unhealthy',
                'usage': usage_info,
                'last_check': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("ChatGPT 상태 확인 중 오류", error=str(e))
            return {
                'provider': 'openai-chatgpt', 
                'model': 'gpt-4o',
                'available': False,
                'status': 'error',
                'error': str(e),
                'last_check': datetime.utcnow().isoformat()
            }
    
    async def get_parsing_tips(self, failed_text: Optional[str] = None) -> Dict[str, Any]:
        """사용자에게 더 나은 파싱을 위한 팁을 제공합니다."""
        tips = {
            'general_tips': [
                "날짜와 시간을 구체적으로 명시해주세요 (예: '내일 오후 3시')",
                "장소나 위치 정보를 포함해주세요 (예: '강남역 스타벅스에서')",
                "참석자나 관련된 사람을 언급해주세요 (예: '김과장과 함께')",
                "일정의 목적이나 내용을 간단히 설명해주세요"
            ],
            'good_examples': [
                "내일 오후 2시에 강남역 스타벅스에서 김대리와 프로젝트 회의",
                "다음주 월요일 오전 9시 병원에서 정기검진 받기",
                "매주 화요일 저녁 7시 헬스장에서 운동하기",
                "12월 25일 저녁 6시 부모님댁에서 크리스마스 저녁식사"
            ],
            'avoid_examples': [
                "언젠가 만나기",
                "나중에 연락",
                "시간 날 때 커피",
                "적당한 시간에"
            ]
        }
        
        if failed_text:
            # 실패한 텍스트 분석해서 구체적인 개선 제안 추가
            suggestions = []
            text_lower = failed_text.lower()
            
            if not any(time_word in text_lower for time_word in ['시', '오전', '오후', '새벽', '밤']):
                suggestions.append("구체적인 시간을 추가해보세요 (예: '오후 3시')")
                
            if not any(date_word in text_lower for date_word in ['오늘', '내일', '모레', '월요일', '화요일', '수요일']):
                suggestions.append("날짜 정보를 명확히 해주세요 (예: '내일', '다음주 금요일')")
                
            if len(failed_text.split()) < 3:
                suggestions.append("더 자세한 설명을 추가해주세요")
            
            tips['specific_suggestions'] = suggestions
        
        return tips

# 전역 서비스 인스턴스
nlp_service = NLPService()