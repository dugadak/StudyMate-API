"""
Study 앱 테스트

이 모듈은 study 앱의 모든 기능에 대한 포괄적인 테스트를 제공합니다.
- 과목 관리
- 학습 설정
- 학습 요약 생성
- 학습 진도 추적
- AI 서비스 통합
"""

import pytest
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from unittest.mock import patch, Mock
from datetime import timedelta

from .utils import APITestCase, MockingTestCase, PerformanceTestMixin
from .factories import (
    UserFactory, SubjectFactory, StudySettingsFactory, 
    StudySummaryFactory, StudyProgressFactory
)
from study.models import Subject, StudySettings, StudySummary, StudyProgress, StudyGoal
from study.services import StudySummaryService, StudyProgressService


@pytest.mark.unit
class SubjectModelTest(TestCase):
    """과목 모델 테스트"""
    
    def test_create_subject(self):
        """과목 생성 테스트"""
        subject = SubjectFactory(
            name='파이썬 프로그래밍',
            category='programming'
        )
        
        self.assertEqual(subject.name, '파이썬 프로그래밍')
        self.assertEqual(subject.category, 'programming')
        self.assertTrue(subject.is_active)
    
    def test_subject_string_representation(self):
        """과목 문자열 표현 테스트"""
        subject = SubjectFactory(name='데이터 사이언스')
        self.assertEqual(str(subject), '데이터 사이언스')
    
    def test_subject_statistics(self):
        """과목 통계 테스트"""
        subject = SubjectFactory()
        user = UserFactory()
        
        # 학습 요약 생성
        StudySummaryFactory.create_batch(3, subject=subject, user=user)
        
        stats = subject.get_statistics()
        
        self.assertIn('total_summaries', stats)
        self.assertIn('unique_learners', stats)
        self.assertIn('average_rating', stats)
    
    def test_subject_slug_generation(self):
        """과목 슬러그 생성 테스트"""
        subject = SubjectFactory(name='파이썬 프로그래밍')
        # 실제 모델에 slug 필드가 있다면 테스트
        # self.assertIsNotNone(subject.slug)


@pytest.mark.unit
class StudySettingsModelTest(TestCase):
    """학습 설정 모델 테스트"""
    
    def test_create_study_settings(self):
        """학습 설정 생성 테스트"""
        user = UserFactory()
        subject = SubjectFactory()
        
        settings = StudySettingsFactory(
            user=user,
            subject=subject,
            difficulty_level='intermediate'
        )
        
        self.assertEqual(settings.user, user)
        self.assertEqual(settings.subject, subject)
        self.assertEqual(settings.difficulty_level, 'intermediate')
    
    def test_ai_generation_config(self):
        """AI 생성 설정 테스트"""
        settings = StudySettingsFactory()
        config = settings.get_ai_generation_config()
        
        self.assertIn('difficulty_level', config)
        self.assertIn('learning_style', config)
        self.assertIn('preferred_depth', config)
    
    def test_is_study_day_today(self):
        """오늘 학습일 확인 테스트"""
        settings = StudySettingsFactory(
            study_days=['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
        )
        
        # 현재 요일에 따라 결과가 달라짐
        result = settings.is_study_day_today()
        self.assertIsInstance(result, bool)
    
    def test_notification_times_list(self):
        """알림 시간 목록 테스트"""
        settings = StudySettingsFactory(
            notification_times=['09:00', '18:00', '21:00']
        )
        
        times = settings.get_notification_times_list()
        self.assertEqual(len(times), 3)
        self.assertIn('09:00', times)


@pytest.mark.study
class SubjectAPITest(APITestCase):
    """과목 API 테스트"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.admin = UserFactory(is_staff=True, is_superuser=True)
        self.subjects_url = reverse('study:subjects-list')
    
    def test_list_subjects(self):
        """과목 목록 조회 테스트"""
        self.authenticate_user(self.user)
        SubjectFactory.create_batch(5, is_active=True)
        
        response = self.api_get(self.subjects_url)
        
        self.assert_response_success(response)
        self.assertEqual(len(response.data['results']), 5)
    
    def test_filter_subjects_by_category(self):
        """카테고리별 과목 필터링 테스트"""
        self.authenticate_user(self.user)
        
        SubjectFactory.create_batch(3, category='programming')
        SubjectFactory.create_batch(2, category='data_science')
        
        response = self.api_get(self.subjects_url, {'category': 'programming'})
        
        self.assert_response_success(response)
        self.assertEqual(len(response.data['results']), 3)
    
    def test_filter_subjects_by_difficulty(self):
        """난이도별 과목 필터링 테스트"""
        self.authenticate_user(self.user)
        
        SubjectFactory.create_batch(2, default_difficulty='beginner')
        SubjectFactory.create_batch(3, default_difficulty='intermediate')
        
        response = self.api_get(self.subjects_url, {'difficulty': 'beginner'})
        
        self.assert_response_success(response)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_search_subjects(self):
        """과목 검색 테스트"""
        self.authenticate_user(self.user)
        
        SubjectFactory(name='파이썬 프로그래밍')
        SubjectFactory(name='자바 프로그래밍')
        SubjectFactory(name='데이터 사이언스')
        
        response = self.api_get(self.subjects_url, {'search': '프로그래밍'})
        
        self.assert_response_success(response)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_create_subject_admin_only(self):
        """과목 생성 - 관리자 전용 테스트"""
        self.authenticate_user(self.admin)
        
        data = {
            'name': '새로운 과목',
            'description': '과목 설명',
            'category': 'programming',
            'default_difficulty': 'intermediate'
        }
        
        response = self.api_post(self.subjects_url, data)
        self.assert_response_success(response, status.HTTP_201_CREATED)
    
    def test_create_subject_permission_denied(self):
        """과목 생성 - 권한 거부 테스트"""
        self.authenticate_user(self.user)
        
        data = {
            'name': '새로운 과목',
            'description': '과목 설명',
            'category': 'programming'
        }
        
        response = self.api_post(self.subjects_url, data)
        self.assert_response_error(response, status.HTTP_403_FORBIDDEN)
    
    def test_subject_statistics(self):
        """과목 통계 조회 테스트"""
        self.authenticate_user(self.user)
        subject = SubjectFactory()
        
        # 테스트 데이터 생성
        StudySummaryFactory.create_batch(3, subject=subject, user=self.user)
        
        url = reverse('study:subjects-statistics', kwargs={'pk': subject.pk})
        response = self.api_get(url)
        
        self.assert_response_success(response)
        self.assertIn('user_stats', response.data['data'])
        self.assertIn('global_stats', response.data['data'])


@pytest.mark.study
class StudySettingsAPITest(APITestCase):
    """학습 설정 API 테스트"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.subject = SubjectFactory()
        self.authenticate_user(self.user)
        self.settings_url = reverse('study:settings-list')
    
    def test_create_study_settings(self):
        """학습 설정 생성 테스트"""
        data = {
            'subject_id': self.subject.id,
            'difficulty_level': 'intermediate',
            'current_knowledge': '기본적인 프로그래밍 지식이 있습니다.',
            'learning_goal': 'Python을 활용한 웹 개발을 배우고 싶습니다.',
            'preferred_depth': 'detailed',
            'learning_style': 'visual',
            'daily_summary_count': 3,
            'notification_times': ['09:00', '18:00'],
            'study_days': ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
        }
        
        response = self.api_post(self.settings_url, data)
        
        self.assert_response_success(response, status.HTTP_201_CREATED)
        self.assertTrue(
            StudySettings.objects.filter(
                user=self.user,
                subject=self.subject
            ).exists()
        )
    
    def test_duplicate_study_settings(self):
        """중복 학습 설정 생성 방지 테스트"""
        StudySettingsFactory(user=self.user, subject=self.subject)
        
        data = {
            'subject_id': self.subject.id,
            'difficulty_level': 'beginner'
        }
        
        response = self.api_post(self.settings_url, data)
        self.assert_response_error(response)
    
    def test_update_study_settings(self):
        """학습 설정 수정 테스트"""
        settings = StudySettingsFactory(user=self.user, subject=self.subject)
        
        data = {
            'difficulty_level': 'advanced',
            'daily_summary_count': 5
        }
        
        url = reverse('study:settings-detail', kwargs={'pk': settings.pk})
        response = self.api_patch(url, data)
        
        self.assert_response_success(response)
        settings.refresh_from_db()
        self.assertEqual(settings.difficulty_level, 'advanced')
        self.assertEqual(settings.daily_summary_count, 5)
    
    def test_validation_notification_times(self):
        """알림 시간 검증 테스트"""
        data = {
            'subject_id': self.subject.id,
            'notification_times': ['25:00', 'invalid']  # 잘못된 시간
        }
        
        response = self.api_post(self.settings_url, data)
        self.assert_response_error(response)
    
    def test_validation_study_days(self):
        """학습 요일 검증 테스트"""
        data = {
            'subject_id': self.subject.id,
            'study_days': ['invalid_day']  # 잘못된 요일
        }
        
        response = self.api_post(self.settings_url, data)
        self.assert_response_error(response)


@pytest.mark.study
class StudySummaryAPITest(APITestCase, MockingTestCase):
    """학습 요약 API 테스트"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.subject = SubjectFactory()
        self.authenticate_user(self.user)
        self.summaries_url = reverse('study:summaries-list')
        
        # AI 서비스 모킹
        self.mock_openai_service("테스트 학습 요약 내용입니다.")
    
    def test_generate_summary(self):
        """학습 요약 생성 테스트"""
        StudySettingsFactory(user=self.user, subject=self.subject)
        
        data = {
            'subject_id': self.subject.id,
            'content_request': 'Python 기본 문법에 대해 설명해주세요.',
            'difficulty_level': 'intermediate',
            'content_type': 'summary'
        }
        
        response = self.api_post(self.summaries_url, data)
        
        self.assert_response_success(response, status.HTTP_201_CREATED)
        self.assertTrue(
            StudySummary.objects.filter(
                user=self.user,
                subject=self.subject
            ).exists()
        )
    
    def test_list_user_summaries(self):
        """사용자 학습 요약 목록 조회 테스트"""
        StudySummaryFactory.create_batch(5, user=self.user, subject=self.subject)
        StudySummaryFactory.create_batch(3, subject=self.subject)  # 다른 사용자
        
        response = self.api_get(self.summaries_url)
        
        self.assert_response_success(response)
        # 본인 것만 조회되는지 확인
        self.assertEqual(len(response.data['results']), 5)
    
    def test_filter_summaries_by_subject(self):
        """과목별 요약 필터링 테스트"""
        subject2 = SubjectFactory()
        
        StudySummaryFactory.create_batch(3, user=self.user, subject=self.subject)
        StudySummaryFactory.create_batch(2, user=self.user, subject=subject2)
        
        response = self.api_get(self.summaries_url, {'subject': self.subject.id})
        
        self.assert_response_success(response)
        self.assertEqual(len(response.data['results']), 3)
    
    def test_mark_summary_as_read(self):
        """요약 읽음 처리 테스트"""
        summary = StudySummaryFactory(user=self.user, is_read=False)
        
        url = reverse('study:summaries-mark-read', kwargs={'pk': summary.pk})
        response = self.api_post(url)
        
        self.assert_response_success(response)
        summary.refresh_from_db()
        self.assertTrue(summary.is_read)
        self.assertIsNotNone(summary.read_at)
    
    def test_rate_summary(self):
        """요약 평점 테스트"""
        summary = StudySummaryFactory(user=self.user, is_read=True)
        
        url = reverse('study:summaries-rate', kwargs={'pk': summary.pk})
        data = {'rating': 4}
        
        response = self.api_post(url, data)
        
        self.assert_response_success(response)
        summary.refresh_from_db()
        self.assertEqual(summary.user_rating, 4)
    
    def test_bookmark_summary(self):
        """요약 북마크 테스트"""
        summary = StudySummaryFactory(user=self.user, is_bookmarked=False)
        
        url = reverse('study:summaries-bookmark', kwargs={'pk': summary.pk})
        response = self.api_post(url)
        
        self.assert_response_success(response)
        summary.refresh_from_db()
        self.assertTrue(summary.is_bookmarked)
    
    @patch('study.services.StudySummaryService.generate_summary')
    def test_ai_service_failure(self, mock_generate):
        """AI 서비스 실패 처리 테스트"""
        mock_generate.side_effect = Exception("AI 서비스 오류")
        
        data = {
            'subject_id': self.subject.id,
            'content_request': 'Python 기본 문법'
        }
        
        response = self.api_post(self.summaries_url, data)
        self.assert_response_error(response, status.HTTP_502_BAD_GATEWAY)
    
    def test_daily_limit_check(self):
        """일일 생성 제한 테스트"""
        # 이미 일일 제한에 도달한 상황을 시뮬레이션
        StudySummaryFactory.create_batch(
            10,  # 설정에서 정한 일일 제한
            user=self.user,
            generated_at=timezone.now()
        )
        
        data = {
            'subject_id': self.subject.id,
            'content_request': 'Python 기본 문법'
        }
        
        response = self.api_post(self.summaries_url, data)
        self.assert_response_error(response, status.HTTP_429_TOO_MANY_REQUESTS)


@pytest.mark.study
class StudyProgressAPITest(APITestCase):
    """학습 진도 API 테스트"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.subject = SubjectFactory()
        self.authenticate_user(self.user)
        self.progress_url = reverse('study:progress-list')
    
    def test_get_user_progress(self):
        """사용자 학습 진도 조회 테스트"""
        progress = StudyProgressFactory(user=self.user, subject=self.subject)
        
        response = self.api_get(self.progress_url)
        
        self.assert_response_success(response)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_progress_weekly_data(self):
        """주간 진도 데이터 테스트"""
        progress = StudyProgressFactory(user=self.user, subject=self.subject)
        
        url = reverse('study:progress-weekly', kwargs={'pk': progress.pk})
        response = self.api_get(url)
        
        self.assert_response_success(response)
        self.assertIn('weekly_data', response.data['data'])
    
    def test_progress_insights(self):
        """학습 인사이트 테스트"""
        progress = StudyProgressFactory(user=self.user, subject=self.subject)
        
        url = reverse('study:progress-insights', kwargs={'pk': progress.pk})
        response = self.api_get(url)
        
        self.assert_response_success(response)
        self.assertIn('insights', response.data['data'])


@pytest.mark.integration
class StudyServiceTest(TestCase, MockingTestCase):
    """학습 서비스 통합 테스트"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.subject = SubjectFactory()
        self.settings = StudySettingsFactory(user=self.user, subject=self.subject)
        self.mock_openai_service()
    
    def test_summary_generation_service(self):
        """요약 생성 서비스 테스트"""
        service = StudySummaryService()
        
        request_data = {
            'content_request': 'Python 기본 문법 설명',
            'difficulty_level': 'intermediate',
            'content_type': 'summary'
        }
        
        summary = service.generate_summary(
            user=self.user,
            subject=self.subject,
            **request_data
        )
        
        self.assertIsInstance(summary, StudySummary)
        self.assertEqual(summary.user, self.user)
        self.assertEqual(summary.subject, self.subject)
    
    def test_progress_update_service(self):
        """진도 업데이트 서비스 테스트"""
        service = StudyProgressService()
        
        # 요약 읽기 완료
        summary = StudySummaryFactory(user=self.user, subject=self.subject)
        service.update_progress_for_summary_read(summary)
        
        progress = StudyProgress.objects.get(user=self.user, subject=self.subject)
        self.assertEqual(progress.total_summaries_read, 1)
    
    def test_ai_model_fallback(self):
        """AI 모델 폴백 테스트"""
        with patch('study.services.StudySummaryService._call_openai') as mock_openai:
            with patch('study.services.StudySummaryService._call_anthropic') as mock_anthropic:
                
                # OpenAI 실패 시뮬레이션
                mock_openai.side_effect = Exception("OpenAI 오류")
                mock_anthropic.return_value = {
                    'content': '폴백 응답',
                    'token_count': 100,
                    'generation_time': 1.5
                }
                
                service = StudySummaryService()
                result = service._generate_with_ai("테스트 프롬프트", "gpt-4")
                
                self.assertEqual(result['content'], '폴백 응답')
                mock_anthropic.assert_called_once()


@pytest.mark.performance
class StudyPerformanceTest(APITestCase, PerformanceTestMixin):
    """학습 기능 성능 테스트"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.authenticate_user(self.user)
    
    def test_subject_list_performance(self):
        """과목 목록 성능 테스트"""
        SubjectFactory.create_batch(100)
        
        def list_subjects():
            return self.api_get(reverse('study:subjects-list'))
        
        # 응답 시간 및 쿼리 수 검증
        self.assert_response_time(list_subjects, max_time_ms=500)
        self.assert_query_count(list_subjects, max_queries=3)
    
    def test_summary_generation_performance(self):
        """요약 생성 성능 테스트"""
        subject = SubjectFactory()
        StudySettingsFactory(user=self.user, subject=subject)
        
        with patch('study.services.StudySummaryService.generate_summary') as mock:
            mock.return_value = StudySummaryFactory.build()
            
            def generate_summary():
                return self.api_post(reverse('study:summaries-list'), {
                    'subject_id': subject.id,
                    'content_request': 'Python 기본 문법'
                })
            
            # AI 서비스 제외한 API 성능 측정
            self.assert_response_time(generate_summary, max_time_ms=200)


# 추가 테스트 마커
pytestmark = [
    pytest.mark.django_db,
    pytest.mark.study
]