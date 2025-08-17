"""
테스트 유틸리티 함수들

이 모듈은 테스트에서 공통으로 사용되는 유틸리티 함수들을 제공합니다.
- 데이터 생성 헬퍼
- API 테스트 헬퍼
- 모킹 헬퍼
- 어서션 헬퍼
"""

import json
from typing import Dict, Any, Optional, List
from unittest.mock import Mock, patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
import factory
import faker
from datetime import datetime, timedelta

User = get_user_model()
fake = faker.Faker('ko_KR')


class BaseTestCase(TestCase):
    """기본 테스트 케이스 클래스"""
    
    def setUp(self):
        """테스트 설정"""
        self.client = APIClient()
        self.fake = fake
        
    def tearDown(self):
        """테스트 정리"""
        pass
    
    def assert_response_success(self, response, expected_status=status.HTTP_200_OK):
        """성공 응답 검증"""
        self.assertEqual(response.status_code, expected_status)
        if hasattr(response, 'data'):
            self.assertTrue(response.data.get('success', True))
    
    def assert_response_error(self, response, expected_status=status.HTTP_400_BAD_REQUEST):
        """에러 응답 검증"""
        self.assertEqual(response.status_code, expected_status)
        if hasattr(response, 'data'):
            self.assertTrue(response.data.get('error', False))
            self.assertIn('error_id', response.data)
            self.assertIn('code', response.data)
            self.assertIn('message', response.data)
    
    def assert_paginated_response(self, response, expected_count=None):
        """페이지네이션 응답 검증"""
        self.assert_response_success(response)
        self.assertIn('count', response.data)
        self.assertIn('results', response.data)
        if expected_count is not None:
            self.assertEqual(len(response.data['results']), expected_count)
    
    def create_test_image(self, name='test.jpg', size=(100, 100)):
        """테스트용 이미지 파일 생성"""
        from PIL import Image
        from io import BytesIO
        
        image = Image.new('RGB', size, color='red')
        temp_file = BytesIO()
        image.save(temp_file, format='JPEG')
        temp_file.seek(0)
        
        return SimpleUploadedFile(
            name=name,
            content=temp_file.read(),
            content_type='image/jpeg'
        )


class APITestCase(BaseTestCase):
    """API 테스트를 위한 기본 클래스"""
    
    def setUp(self):
        super().setUp()
        self.api_client = APIClient()
        
    def authenticate_user(self, user):
        """사용자 인증"""
        refresh = RefreshToken.for_user(user)
        self.api_client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}'
        )
        return refresh.access_token
    
    def unauthenticate(self):
        """인증 해제"""
        self.api_client.credentials()
    
    def api_get(self, url, data=None, **kwargs):
        """API GET 요청"""
        return self.api_client.get(url, data, format='json', **kwargs)
    
    def api_post(self, url, data=None, **kwargs):
        """API POST 요청"""
        return self.api_client.post(url, data, format='json', **kwargs)
    
    def api_put(self, url, data=None, **kwargs):
        """API PUT 요청"""
        return self.api_client.put(url, data, format='json', **kwargs)
    
    def api_patch(self, url, data=None, **kwargs):
        """API PATCH 요청"""
        return self.api_client.patch(url, data, format='json', **kwargs)
    
    def api_delete(self, url, **kwargs):
        """API DELETE 요청"""
        return self.api_client.delete(url, format='json', **kwargs)


class MockingTestCase(BaseTestCase):
    """모킹을 위한 테스트 케이스"""
    
    def setUp(self):
        super().setUp()
        self.mocks = {}
        self.patches = {}
    
    def tearDown(self):
        """모든 패치 정리"""
        for patch_obj in self.patches.values():
            patch_obj.stop()
        super().tearDown()
    
    def mock_openai_service(self, response_text="테스트 응답"):
        """OpenAI 서비스 모킹"""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = response_text
        mock_response.usage.total_tokens = 100
        
        patcher = patch('openai.ChatCompletion.create', return_value=mock_response)
        self.patches['openai'] = patcher
        return patcher.start()
    
    def mock_stripe_service(self):
        """Stripe 서비스 모킹"""
        mock_customer = Mock()
        mock_customer.id = 'cus_test123'
        
        mock_subscription = Mock()
        mock_subscription.id = 'sub_test123'
        mock_subscription.status = 'active'
        
        customer_patcher = patch('stripe.Customer.create', return_value=mock_customer)
        subscription_patcher = patch('stripe.Subscription.create', return_value=mock_subscription)
        
        self.patches['stripe_customer'] = customer_patcher
        self.patches['stripe_subscription'] = subscription_patcher
        
        return customer_patcher.start(), subscription_patcher.start()
    
    def mock_email_service(self):
        """이메일 서비스 모킹"""
        patcher = patch('django.core.mail.send_mail', return_value=True)
        self.patches['email'] = patcher
        return patcher.start()
    
    def mock_cache_service(self):
        """캐시 서비스 모킹"""
        mock_cache = {}
        
        def mock_get(key, default=None):
            return mock_cache.get(key, default)
        
        def mock_set(key, value, timeout=None):
            mock_cache[key] = value
        
        def mock_delete(key):
            mock_cache.pop(key, None)
        
        cache_patcher = patch('django.core.cache.cache')
        mock_cache_obj = cache_patcher.start()
        mock_cache_obj.get = mock_get
        mock_cache_obj.set = mock_set
        mock_cache_obj.delete = mock_delete
        
        self.patches['cache'] = cache_patcher
        return mock_cache_obj


# 데이터 생성 헬퍼 함수들
def create_test_user(email=None, password='testpass123', **kwargs):
    """테스트 사용자 생성"""
    if email is None:
        email = fake.email()
    
    user_data = {
        'email': email,
        'first_name': fake.first_name(),
        'last_name': fake.last_name(),
        'is_active': True,
        **kwargs
    }
    
    user = User.objects.create_user(password=password, **user_data)
    return user


def create_admin_user(**kwargs):
    """관리자 사용자 생성"""
    return create_test_user(
        email='admin@test.com',
        is_staff=True,
        is_superuser=True,
        **kwargs
    )


def create_test_subject(**kwargs):
    """테스트 과목 생성"""
    from study.models import Subject
    
    subject_data = {
        'name': fake.word() + ' 학습',
        'description': fake.text(max_nb_chars=200),
        'category': 'programming',
        'default_difficulty': 'intermediate',
        'is_active': True,
        **kwargs
    }
    
    return Subject.objects.create(**subject_data)


def create_test_quiz(**kwargs):
    """테스트 퀴즈 생성"""
    from quiz.models import Quiz
    
    quiz_data = {
        'title': fake.sentence(nb_words=4),
        'description': fake.text(max_nb_chars=200),
        'difficulty_level': 'intermediate',
        'is_active': True,
        **kwargs
    }
    
    return Quiz.objects.create(**quiz_data)


def create_test_subscription_plan(**kwargs):
    """테스트 구독 플랜 생성"""
    from subscription.models import SubscriptionPlan
    
    plan_data = {
        'name': fake.word() + ' 플랜',
        'description': fake.text(max_nb_chars=200),
        'price': fake.pydecimal(left_digits=3, right_digits=2, positive=True),
        'billing_period': 'monthly',
        'is_active': True,
        **kwargs
    }
    
    return SubscriptionPlan.objects.create(**plan_data)


# API 테스트 헬퍼 함수들
def assert_api_success(response, status_code=status.HTTP_200_OK):
    """API 성공 응답 검증"""
    assert response.status_code == status_code
    if hasattr(response, 'data') and isinstance(response.data, dict):
        assert response.data.get('success') is not False


def assert_api_error(response, status_code=status.HTTP_400_BAD_REQUEST):
    """API 에러 응답 검증"""
    assert response.status_code == status_code
    if hasattr(response, 'data') and isinstance(response.data, dict):
        assert 'error' in response.data or 'detail' in response.data


def assert_field_required(response, field_name):
    """필수 필드 검증"""
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    if hasattr(response, 'data'):
        if isinstance(response.data, dict):
            # DRF 표준 에러 형식
            assert field_name in response.data
        elif 'details' in response.data and 'field_errors' in response.data['details']:
            # 커스텀 에러 형식
            assert field_name in response.data['details']['field_errors']


def assert_permission_denied(response):
    """권한 거부 검증"""
    assert response.status_code in [
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN
    ]


# 성능 테스트 헬퍼
class PerformanceTestMixin:
    """성능 테스트를 위한 믹스인"""
    
    def assert_response_time(self, func, max_time_ms=1000):
        """응답 시간 검증"""
        import time
        
        start_time = time.time()
        result = func()
        end_time = time.time()
        
        duration_ms = (end_time - start_time) * 1000
        assert duration_ms < max_time_ms, f"응답 시간이 너무 깁니다: {duration_ms:.2f}ms > {max_time_ms}ms"
        
        return result
    
    def assert_query_count(self, func, max_queries=10):
        """쿼리 수 검증"""
        from django.test.utils import override_settings
        from django.db import connection
        
        with override_settings(DEBUG=True):
            initial_queries = len(connection.queries)
            result = func()
            query_count = len(connection.queries) - initial_queries
            
            assert query_count <= max_queries, f"쿼리가 너무 많습니다: {query_count} > {max_queries}"
            
        return result


# 내보낼 클래스 및 함수들
__all__ = [
    'BaseTestCase',
    'APITestCase', 
    'MockingTestCase',
    'PerformanceTestMixin',
    'create_test_user',
    'create_admin_user',
    'create_test_subject',
    'create_test_quiz',
    'create_test_subscription_plan',
    'assert_api_success',
    'assert_api_error',
    'assert_field_required',
    'assert_permission_denied',
]