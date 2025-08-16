import openai
from django.conf import settings
from .models import StudySummary, Subject, StudySettings
from django.contrib.auth import get_user_model

User = get_user_model()


class StudySummaryService:
    def __init__(self):
        openai.api_key = settings.OPENAI_API_KEY
    
    def generate_summary(self, user, subject_id):
        try:
            subject = Subject.objects.get(id=subject_id)
            study_settings = StudySettings.objects.get(user=user, subject=subject)
            
            prompt = self._create_prompt(study_settings)
            
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "당신은 전문적인 교육 콘텐츠 생성자입니다."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            
            content = response.choices[0].message.content.strip()
            
            summary = StudySummary.objects.create(
                user=user,
                subject=subject,
                title=f"{subject.name} 학습 요약",
                content=content,
                difficulty_level=study_settings.preferred_depth
            )
            
            return summary
            
        except Exception as e:
            raise Exception(f"요약 생성 중 오류가 발생했습니다: {str(e)}")
    
    def _create_prompt(self, study_settings):
        return f"""
        다음 조건에 맞는 {study_settings.subject.name} 학습 요약을 생성해주세요:
        
        - 대상자: {study_settings.current_knowledge}
        - 학습 목표: {study_settings.learning_goal}
        - 난이도: {study_settings.get_preferred_depth_display()}
        - 현재 지식 수준: {study_settings.get_difficulty_level_display()}
        
        요구사항:
        1. 한국어로 작성
        2. 명확하고 이해하기 쉬운 설명
        3. 실용적인 예시 포함
        4. 핵심 개념 강조
        5. 800-1000자 분량
        
        주제별 핵심 내용을 체계적으로 정리하여 제공해주세요.
        """


class StudyProgressService:
    @staticmethod
    def update_progress(user, subject, action_type='summary_read'):
        from .models import StudyProgress
        
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
        
        if action_type == 'summary_read':
            progress.total_summaries_read += 1
        elif action_type == 'quiz_completed':
            progress.total_quizzes_completed += 1
        
        progress.save()
        return progress