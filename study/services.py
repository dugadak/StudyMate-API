import openai
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from typing import Dict, Any, Optional, List, Union
import logging
import time
import json
import hashlib
from datetime import timedelta
import backoff
from enum import Enum
import anthropic
import requests

from .models import StudySummary, Subject, StudySettings, StudyProgress
from studymate_api.metrics import (
    track_ai_event, track_system_event, EventType
)
from .tracing_decorators import (
    trace_study_operation, trace_ai_generation, trace_database_operation, trace_cache_access
)
from .ab_testing_integration import generate_summary_with_ab_test

User = get_user_model()
logger = logging.getLogger('study.services')


class AIProvider(Enum):
    """AI 제공업체 열거형"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    TOGETHER = "together"


class AIModelError(Exception):
    """AI 모델 관련 예외"""
    def __init__(self, message: str, provider: str = None, retry_after: int = None):
        super().__init__(message)
        self.provider = provider
        self.retry_after = retry_after


class RateLimitError(AIModelError):
    """레이트 리밋 예외"""
    pass


class ContentFilterError(AIModelError):
    """컨텐츠 필터링 예외"""
    pass


class StudySummaryService:
    """Enhanced Study Summary Service with multiple AI providers and robust error handling"""
    
    def __init__(self):
        self.ai_config = settings.AI_MODELS
        self._setup_clients()
        self._cache_timeout = settings.STUDYMATE_SETTINGS.get('AI_RESPONSE_CACHE_TTL', 3600)
    
    def _setup_clients(self):
        """Initialize AI clients"""
        self.openai_client = None
        self.anthropic_client = None
        
        # OpenAI setup
        openai_config = self.ai_config.get('openai', {})
        if openai_config.get('api_key'):
            openai.api_key = openai_config['api_key']
            openai.organization = openai_config.get('organization')
            self.openai_client = openai
        
        # Anthropic setup
        anthropic_config = self.ai_config.get('anthropic', {})
        if anthropic_config.get('api_key'):
            self.anthropic_client = anthropic.Anthropic(
                api_key=anthropic_config['api_key']
            )
    
    @trace_study_operation("summary_generation", include_user=True, include_subject=True)
    def generate_summary(self, user: User, subject_id: int, 
                        custom_prompt: Optional[str] = None) -> StudySummary:
        """
        Generate study summary with enhanced error handling and fallback strategies
        """
        try:
            with transaction.atomic():
                # Validate inputs
                subject = self._get_subject(subject_id)
                study_settings = self._get_study_settings(user, subject)
                
                # Check daily limits
                self._check_daily_limits(user, study_settings)
                
                # Generate cache key
                cache_key = self._generate_cache_key(user, subject, study_settings, custom_prompt)
                
                # Try to get cached response first
                cached_summary = cache.get(cache_key)
                if cached_summary:
                    logger.info(f"Using cached summary for user {user.email}, subject {subject.name}")
                    return self._create_summary_from_cache(user, subject, cached_summary)
                
                # Generate content using AI with A/B testing
                content, ab_test_info = self._generate_content_with_ab_testing(
                    user, study_settings, custom_prompt, subject_id
                )
                
                # Create summary object with A/B test metadata
                summary = StudySummary.objects.create(
                    user=user,
                    subject=subject,
                    title=f"{subject.name} 학습 요약",
                    content=content,
                    difficulty_level=study_settings.preferred_depth,
                    metadata=ab_test_info  # A/B 테스트 정보 저장
                )
                
                # Cache the result
                cache.set(cache_key, {
                    'title': summary.title,
                    'content': summary.content,
                    'difficulty_level': summary.difficulty_level
                }, self._cache_timeout)
                
                # Update daily count
                self._update_daily_count(user, subject)
                
                logger.info(f"Summary generated successfully for user {user.email}, subject {subject.name}")
                return summary
                
        except Exception as e:
            logger.error(f"Summary generation failed for user {user.email}: {str(e)}")
            raise
    
    def _get_subject(self, subject_id: int) -> Subject:
        """Get and validate subject"""
        try:
            return Subject.objects.get(id=subject_id)
        except Subject.DoesNotExist:
            raise ValueError(f"존재하지 않는 과목입니다. (ID: {subject_id})")
    
    def _get_study_settings(self, user: User, subject: Subject) -> StudySettings:
        """Get or create study settings for user and subject"""
        try:
            return StudySettings.objects.get(user=user, subject=subject)
        except StudySettings.DoesNotExist:
            # Create default settings
            return StudySettings.objects.create(
                user=user,
                subject=subject,
                difficulty_level='beginner',
                current_knowledge="기초 학습자",
                learning_goal="기본 개념 이해",
                preferred_depth='intermediate'
            )
    
    def _check_daily_limits(self, user: User, study_settings: StudySettings) -> None:
        """Check if user has exceeded daily summary limits"""
        today = timezone.now().date()
        daily_count = StudySummary.objects.filter(
            user=user,
            subject=study_settings.subject,
            generated_at__date=today
        ).count()
        
        max_daily = study_settings.daily_summary_count
        if daily_count >= max_daily:
            raise ValueError(f"일일 요약 생성 한도({max_daily}회)를 초과했습니다.")
    
    def _generate_cache_key(self, user: User, subject: Subject, 
                           settings: StudySettings, custom_prompt: Optional[str]) -> str:
        """Generate cache key for the request"""
        key_data = {
            'user_id': user.id,
            'subject_id': subject.id,
            'difficulty': settings.difficulty_level,
            'depth': settings.preferred_depth,
            'knowledge': settings.current_knowledge[:100],  # Truncate for cache key
            'goal': settings.learning_goal[:100],
            'custom_prompt': custom_prompt or '',
            'date': timezone.now().date().isoformat()
        }
        
        key_string = json.dumps(key_data, sort_keys=True)
        return f"study_summary:{hashlib.md5(key_string.encode()).hexdigest()}"
    
    def _create_summary_from_cache(self, user: User, subject: Subject, 
                                 cached_data: Dict[str, Any]) -> StudySummary:
        """Create summary object from cached data"""
        return StudySummary.objects.create(
            user=user,
            subject=subject,
            title=cached_data['title'],
            content=cached_data['content'],
            difficulty_level=cached_data['difficulty_level']
        )
    
    @trace_ai_generation("multi_provider")
    def _generate_content_with_ab_testing(self, user: User, study_settings: StudySettings, 
                                         custom_prompt: Optional[str] = None, subject_id: int = None) -> tuple[str, Dict[str, Any]]:
        """Generate content using A/B testing for AI model selection"""
        try:
            # 프롬프트 텍스트 생성
            prompt_text = custom_prompt or self._create_prompt(study_settings)
            
            # A/B 테스트로 요약 생성
            content, ab_test_info = generate_summary_with_ab_test(
                user_id=user.id,
                text=prompt_text,
                subject_id=subject_id or study_settings.subject.id
            )
            
            return content, ab_test_info
            
        except Exception as e:
            logger.warning(f"A/B testing failed, falling back to traditional method: {e}")
            # A/B 테스트 실패 시 기존 방식으로 폴백
            content = self._generate_content_with_fallback(study_settings, custom_prompt)
            return content, {'model_used': 'fallback', 'ab_test_active': False}

    def _generate_content_with_fallback(self, study_settings: StudySettings, 
                                      custom_prompt: Optional[str] = None) -> str:
        """Generate content with multiple AI providers as fallback"""
        fallback_config = self.ai_config.get('fallback_strategy', {})
        providers = [
            fallback_config.get('primary', 'openai'),
            fallback_config.get('secondary', 'anthropic'),
            fallback_config.get('tertiary', 'together')
        ]
        
        last_error = None
        
        for provider in providers:
            if not provider or provider not in AIProvider.__members__.values():
                continue
                
            try:
                logger.info(f"Attempting content generation with {provider}")
                content = self._generate_with_provider(
                    provider, study_settings, custom_prompt
                )
                
                if content and len(content.strip()) > 100:  # Minimum content length
                    logger.info(f"Content generated successfully with {provider}")
                    return content
                else:
                    logger.warning(f"Generated content too short with {provider}")
                    
            except RateLimitError as e:
                logger.warning(f"Rate limit hit for {provider}: {str(e)}")
                last_error = e
                continue
                
            except ContentFilterError as e:
                logger.warning(f"Content filtered by {provider}: {str(e)}")
                last_error = e
                continue
                
            except Exception as e:
                logger.error(f"Error with {provider}: {str(e)}")
                last_error = e
                continue
        
        # If all providers failed
        if last_error:
            raise AIModelError(f"모든 AI 제공업체에서 오류가 발생했습니다: {str(last_error)}")
        else:
            raise AIModelError("사용 가능한 AI 제공업체가 없습니다.")
    
    def _generate_with_provider(self, provider: str, study_settings: StudySettings,
                              custom_prompt: Optional[str] = None) -> str:
        """Generate content with specific AI provider"""
        if provider == AIProvider.OPENAI.value:
            return self._generate_with_openai(study_settings, custom_prompt)
        elif provider == AIProvider.ANTHROPIC.value:
            return self._generate_with_anthropic(study_settings, custom_prompt)
        elif provider == AIProvider.TOGETHER.value:
            return self._generate_with_together(study_settings, custom_prompt)
        else:
            raise ValueError(f"지원하지 않는 AI 제공업체: {provider}")
    
    @backoff.on_exception(
        backoff.expo,
        (openai.RateLimitError, openai.APIError),
        max_tries=3,
        max_time=300
    )
    @trace_ai_generation("openai", "gpt-3.5-turbo")
    def _generate_with_openai(self, study_settings: StudySettings,
                            custom_prompt: Optional[str] = None) -> str:
        """Generate content using OpenAI GPT"""
        if not self.openai_client:
            raise AIModelError("OpenAI 클라이언트가 설정되지 않았습니다.", "openai")
        
        config = self.ai_config['openai']
        model = config.get('default_model', 'gpt-3.5-turbo')
        model_config = config['models'].get(model, {})
        
        prompt = custom_prompt or self._create_prompt(study_settings)
        
        try:
            start_time = time.time()
            
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system", 
                        "content": "당신은 전문적인 교육 콘텐츠 생성자입니다. 사용자의 학습 수준에 맞는 정확하고 이해하기 쉬운 학습 요약을 제공합니다."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=model_config.get('max_tokens', 2000),
                temperature=model_config.get('temperature', 0.7),
                timeout=config.get('timeout', 30)
            )
            
            generation_time = time.time() - start_time
            content = response.choices[0].message.content.strip()
            
            # Log performance metrics
            logger.info(f"OpenAI generation completed in {generation_time:.2f}s, "
                       f"tokens: {response.usage.total_tokens}")
            
            # Track successful AI request
            track_ai_event(EventType.AI_REQUEST, 'openai', {
                'model': model,
                'response_time': generation_time,
                'total_tokens': response.usage.total_tokens,
                'prompt_tokens': response.usage.prompt_tokens,
                'completion_tokens': response.usage.completion_tokens,
                'status': 'success'
            })
            
            # Validate content
            if not content or len(content) < 50:
                raise ContentFilterError("생성된 콘텐츠가 너무 짧습니다.", "openai")
            
            return content
            
        except openai.RateLimitError as e:
            track_ai_event(EventType.AI_ERROR, 'openai', {
                'error_type': 'rate_limit',
                'error_message': str(e)
            })
            raise RateLimitError(f"OpenAI 요청 한도 초과: {str(e)}", "openai")
        except openai.APIError as e:
            track_ai_event(EventType.AI_ERROR, 'openai', {
                'error_type': 'api_error',
                'error_message': str(e)
            })
            if "content_filter" in str(e).lower():
                raise ContentFilterError(f"OpenAI 콘텐츠 필터: {str(e)}", "openai")
            raise AIModelError(f"OpenAI API 오류: {str(e)}", "openai")
        except Exception as e:
            track_ai_event(EventType.AI_ERROR, 'openai', {
                'error_type': 'general_error',
                'error_message': str(e)
            })
            raise AIModelError(f"OpenAI 요청 실패: {str(e)}", "openai")
    
    def _generate_with_anthropic(self, study_settings: StudySettings,
                               custom_prompt: Optional[str] = None) -> str:
        """Generate content using Anthropic Claude"""
        if not self.anthropic_client:
            raise AIModelError("Anthropic 클라이언트가 설정되지 않았습니다.", "anthropic")
        
        config = self.ai_config['anthropic']
        model = config.get('default_model', 'claude-3-haiku-20240307')
        model_config = config['models'].get(model, {})
        
        prompt = custom_prompt or self._create_prompt(study_settings)
        
        try:
            start_time = time.time()
            
            response = self.anthropic_client.messages.create(
                model=model,
                max_tokens=model_config.get('max_tokens', 2000),
                temperature=model_config.get('temperature', 0.7),
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            generation_time = time.time() - start_time
            content = response.content[0].text.strip()
            
            logger.info(f"Anthropic generation completed in {generation_time:.2f}s")
            
            if not content or len(content) < 50:
                raise ContentFilterError("생성된 콘텐츠가 너무 짧습니다.", "anthropic")
            
            return content
            
        except Exception as e:
            if "rate_limit" in str(e).lower():
                raise RateLimitError(f"Anthropic 요청 한도 초과: {str(e)}", "anthropic")
            elif "content_filter" in str(e).lower():
                raise ContentFilterError(f"Anthropic 콘텐츠 필터: {str(e)}", "anthropic")
            raise AIModelError(f"Anthropic 요청 실패: {str(e)}", "anthropic")
    
    def _generate_with_together(self, study_settings: StudySettings,
                              custom_prompt: Optional[str] = None) -> str:
        """Generate content using Together AI"""
        config = self.ai_config.get('together', {})
        api_key = config.get('api_key')
        
        if not api_key:
            raise AIModelError("Together AI 키가 설정되지 않았습니다.", "together")
        
        model = config.get('default_model', 'mistralai/Mixtral-8x7B-Instruct-v0.1')
        model_config = config['models'].get(model, {})
        
        prompt = custom_prompt or self._create_prompt(study_settings)
        
        try:
            start_time = time.time()
            
            response = requests.post(
                "https://api.together.xyz/inference",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "prompt": prompt,
                    "max_tokens": model_config.get('max_tokens', 2000),
                    "temperature": model_config.get('temperature', 0.7),
                },
                timeout=config.get('timeout', 30)
            )
            
            generation_time = time.time() - start_time
            
            if response.status_code == 429:
                raise RateLimitError("Together AI 요청 한도 초과", "together")
            
            response.raise_for_status()
            result = response.json()
            
            content = result['output']['choices'][0]['text'].strip()
            
            logger.info(f"Together AI generation completed in {generation_time:.2f}s")
            
            if not content or len(content) < 50:
                raise ContentFilterError("생성된 콘텐츠가 너무 짧습니다.", "together")
            
            return content
            
        except requests.exceptions.RequestException as e:
            if "429" in str(e):
                raise RateLimitError(f"Together AI 요청 한도 초과: {str(e)}", "together")
            raise AIModelError(f"Together AI 요청 실패: {str(e)}", "together")
    
    def _create_prompt(self, study_settings: StudySettings) -> str:
        """Create enhanced prompt for AI content generation"""
        return f"""
다음 조건에 맞는 {study_settings.subject.name} 학습 요약을 생성해주세요:

**학습자 정보:**
- 현재 지식 수준: {study_settings.get_difficulty_level_display()}
- 현재 알고 있는 내용: {study_settings.current_knowledge}
- 학습 목표: {study_settings.learning_goal}
- 원하는 학습 깊이: {study_settings.get_preferred_depth_display()}

**요구사항:**
1. 한국어로 작성하되, 전문 용어 사용 시 쉬운 설명 병기
2. 학습자의 현재 수준에 맞는 적절한 난이도 유지
3. 실용적이고 구체적인 예시 포함
4. 핵심 개념을 명확하고 체계적으로 정리
5. 학습 목표 달성에 도움이 되는 내용 우선
6. 800-1200자 분량으로 작성
7. 다음 단계 학습을 위한 가이드 포함

**구조:**
- 개요 (2-3문장)
- 핵심 개념들 (3-5개 주요 포인트)
- 실용적 예시
- 학습 요점 정리
- 다음 단계 제안

학습자가 쉽게 이해하고 실제로 활용할 수 있도록 실용적이고 체계적인 요약을 제공해주세요.
        """
    
    def _update_daily_count(self, user: User, subject: Subject) -> None:
        """Update daily summary count in cache"""
        today = timezone.now().date()
        cache_key = f"daily_summary_count:{user.id}:{subject.id}:{today}"
        current_count = cache.get(cache_key, 0)
        cache.set(cache_key, current_count + 1, 86400)  # 24 hours
    
    def get_usage_statistics(self, user: User, days: int = 30) -> Dict[str, Any]:
        """Get user's AI usage statistics"""
        since_date = timezone.now() - timedelta(days=days)
        
        summaries = StudySummary.objects.filter(
            user=user,
            generated_at__gte=since_date
        )
        
        return {
            'total_summaries': summaries.count(),
            'summaries_by_subject': {
                subject.name: summaries.filter(subject=subject).count()
                for subject in Subject.objects.all()
            },
            'daily_average': summaries.count() / days,
            'most_active_subject': summaries.values('subject__name')
                                            .annotate(count=models.Count('id'))
                                            .order_by('-count')
                                            .first()
        }


class StudyProgressService:
    """Enhanced Study Progress Service with detailed tracking"""
    
    @staticmethod
    def update_progress(user: User, subject: Subject, action_type: str = 'summary_read',
                       topics: Optional[List[str]] = None) -> StudyProgress:
        """Update user's study progress with enhanced tracking"""
        
        try:
            with transaction.atomic():
                progress, created = StudyProgress.objects.get_or_create(
                    user=user,
                    subject=subject,
                    defaults={
                        'topics_learned': [],
                        'total_summaries_read': 0,
                        'total_quizzes_completed': 0,
                        'current_streak': 0
                    }
                )
                
                # Update based on action type
                if action_type == 'summary_read':
                    progress.total_summaries_read += 1
                elif action_type == 'quiz_completed':
                    progress.total_quizzes_completed += 1
                
                # Update topics learned
                if topics:
                    current_topics = set(progress.topics_learned)
                    new_topics = set(topics)
                    progress.topics_learned = list(current_topics.union(new_topics))
                
                # Update streak
                progress.current_streak = StudyProgressService._calculate_streak(user, subject)
                
                # Update last activity
                progress.last_activity_date = timezone.now().date()
                progress.save()
                
                # Update user profile stats
                StudyProgressService._update_user_profile_stats(user)
                
                logger.info(f"Progress updated for user {user.email}, subject {subject.name}, "
                           f"action: {action_type}")
                
                return progress
                
        except Exception as e:
            logger.error(f"Failed to update progress for user {user.email}: {str(e)}")
            raise
    
    @staticmethod
    def _calculate_streak(user: User, subject: Subject) -> int:
        """Calculate current study streak for user and subject"""
        from django.db import models
        
        # Get recent activity dates
        recent_summaries = StudySummary.objects.filter(
            user=user,
            subject=subject,
            is_read=True
        ).order_by('-generated_at')
        
        if not recent_summaries.exists():
            return 0
        
        # Calculate consecutive days
        today = timezone.now().date()
        streak = 0
        
        # Check if user studied today or yesterday
        last_activity = recent_summaries.first().generated_at.date()
        if (today - last_activity).days > 1:
            return 0
        
        # Count consecutive days
        activity_dates = set(
            summary.generated_at.date() 
            for summary in recent_summaries[:30]  # Check last 30 entries
        )
        
        current_date = today
        while current_date in activity_dates:
            streak += 1
            current_date -= timedelta(days=1)
        
        return streak
    
    @staticmethod
    def _update_user_profile_stats(user: User) -> None:
        """Update user profile with aggregated study statistics"""
        try:
            profile = user.profile
            
            # Calculate total study time (estimate based on summaries read)
            total_summaries = StudySummary.objects.filter(user=user, is_read=True).count()
            estimated_minutes = total_summaries * 10  # Assume 10 minutes per summary
            profile.total_study_time = timedelta(minutes=estimated_minutes)
            
            # Calculate max streak across all subjects
            max_streak = StudyProgress.objects.filter(user=user).aggregate(
                max_streak=models.Max('current_streak')
            )['max_streak'] or 0
            profile.streak_days = max_streak
            
            profile.save(update_fields=['total_study_time', 'streak_days'])
            
        except Exception as e:
            logger.error(f"Failed to update profile stats for user {user.email}: {str(e)}")
    
    @staticmethod
    def get_comprehensive_progress(user: User) -> Dict[str, Any]:
        """Get comprehensive progress data for user"""
        progress_data = StudyProgress.objects.filter(user=user).select_related('subject')
        
        total_progress = {
            'total_subjects': progress_data.count(),
            'total_summaries_read': sum(p.total_summaries_read for p in progress_data),
            'total_quizzes_completed': sum(p.total_quizzes_completed for p in progress_data),
            'max_streak': max((p.current_streak for p in progress_data), default=0),
            'total_topics_learned': len(set(
                topic for p in progress_data for topic in p.topics_learned
            )),
            'subjects_progress': []
        }
        
        for progress in progress_data:
            subject_data = {
                'subject_name': progress.subject.name,
                'summaries_read': progress.total_summaries_read,
                'quizzes_completed': progress.total_quizzes_completed,
                'current_streak': progress.current_streak,
                'topics_learned': len(progress.topics_learned),
                'last_activity': progress.last_activity_date.isoformat() if progress.last_activity_date else None,
                'progress_percentage': min(
                    (progress.total_summaries_read + progress.total_quizzes_completed) * 5, 100
                )
            }
            total_progress['subjects_progress'].append(subject_data)
        
        return total_progress