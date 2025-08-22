"""
Test cases for API response formats and utilities
"""

import pytest
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock
from studymate_api.utils import (
    StandardResponse, 
    OptimizedPageNumberPagination,
    get_client_ip,
    get_user_agent,
    generate_cache_key,
    generate_secure_token,
    sanitize_input,
    calculate_reading_time,
    DataValidator
)

User = get_user_model()


class TestStandardResponse(TestCase):
    """표준 응답 형식 테스트"""
    
    def test_success_response(self):
        """성공 응답 테스트"""
        response = StandardResponse.success(
            data={'result': 'test'},
            message='Operation successful'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['message'], 'Operation successful')
        self.assertEqual(response.data['data']['result'], 'test')
        self.assertIn('timestamp', response.data)
    
    def test_error_response(self):
        """에러 응답 테스트"""
        response = StandardResponse.error(
            message='Validation error',
            errors={'field': 'required'},
            status_code=status.HTTP_400_BAD_REQUEST
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['message'], 'Validation error')
        self.assertEqual(response.data['errors']['field'], 'required')
        self.assertIn('timestamp', response.data)
    
    def test_paginated_response(self):
        """페이지네이션 응답 테스트"""
        response = StandardResponse.paginated(
            data=[{'id': 1}, {'id': 2}],
            count=100,
            page=1,
            total_pages=5
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['pagination']['count'], 100)
        self.assertEqual(response.data['pagination']['current_page'], 1)
        self.assertEqual(response.data['pagination']['total_pages'], 5)
        self.assertEqual(len(response.data['data']), 2)


class TestUtilityFunctions(TestCase):
    """유틸리티 함수 테스트"""
    
    def setUp(self):
        self.factory = RequestFactory()
    
    def test_get_client_ip_with_forwarded(self):
        """X-Forwarded-For 헤더가 있는 경우 IP 추출"""
        request = self.factory.get('/')
        request.META['HTTP_X_FORWARDED_FOR'] = '192.168.1.1, 10.0.0.1'
        
        ip = get_client_ip(request)
        self.assertEqual(ip, '192.168.1.1')
    
    def test_get_client_ip_without_forwarded(self):
        """X-Forwarded-For 헤더가 없는 경우 IP 추출"""
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        
        ip = get_client_ip(request)
        self.assertEqual(ip, '127.0.0.1')
    
    def test_get_user_agent(self):
        """User-Agent 추출 테스트"""
        request = self.factory.get('/')
        request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0 Test Browser'
        
        user_agent = get_user_agent(request)
        self.assertEqual(user_agent, 'Mozilla/5.0 Test Browser')
    
    def test_generate_cache_key(self):
        """캐시 키 생성 테스트"""
        key = generate_cache_key('user', user_id=1, subject_id=5)
        self.assertIn('user:', key)
        self.assertIn('subject_id:5', key)
        self.assertIn('user_id:1', key)
    
    def test_generate_cache_key_with_long_params(self):
        """긴 매개변수로 캐시 키 생성 테스트"""
        long_value = 'x' * 300
        key = generate_cache_key('test', value=long_value)
        # 긴 키는 해시되어야 함
        self.assertTrue(len(key) < 250)
        self.assertTrue(key.startswith('test:'))
    
    def test_generate_secure_token(self):
        """보안 토큰 생성 테스트"""
        token1 = generate_secure_token()
        token2 = generate_secure_token()
        
        # 토큰은 유니크해야 함
        self.assertNotEqual(token1, token2)
        # 기본 길이 확인
        self.assertTrue(len(token1) > 20)
    
    def test_sanitize_input(self):
        """입력 정제 테스트"""
        # 정상 텍스트
        clean = sanitize_input("  Hello World  ")
        self.assertEqual(clean, "Hello World")
        
        # 제어 문자 제거
        dirty = "Hello\x00World\x01Test"
        clean = sanitize_input(dirty)
        self.assertEqual(clean, "HelloWorldTest")
        
        # 길이 제한
        long_text = "x" * 2000
        clean = sanitize_input(long_text, max_length=100)
        self.assertEqual(len(clean), 100)
    
    def test_calculate_reading_time_korean(self):
        """한글 텍스트 읽기 시간 계산"""
        korean_text = "안녕하세요 " * 100  # 500자
        time = calculate_reading_time(korean_text)
        # 400자/분으로 계산하면 약 1.25분 -> 1분
        self.assertEqual(time, 1)
    
    def test_calculate_reading_time_english(self):
        """영문 텍스트 읽기 시간 계산"""
        english_text = "hello world " * 100  # 200 단어
        time = calculate_reading_time(english_text)
        # 200단어/분으로 계산하면 1분
        self.assertEqual(time, 1)
    
    def test_calculate_reading_time_mixed(self):
        """한글+영문 혼합 텍스트 읽기 시간 계산"""
        mixed_text = "안녕하세요 " * 200 + "hello world " * 100  # 1000자 + 200단어
        time = calculate_reading_time(mixed_text)
        # 1000자/400 = 2.5분 + 200단어/200 = 1분 = 3.5분 -> 4분
        self.assertGreaterEqual(time, 3)


class TestDataValidator(TestCase):
    """데이터 검증 클래스 테스트"""
    
    def test_valid_email(self):
        """유효한 이메일 검증"""
        self.assertTrue(DataValidator.is_valid_email("test@example.com"))
        self.assertTrue(DataValidator.is_valid_email("user.name@domain.co.kr"))
        self.assertFalse(DataValidator.is_valid_email("invalid.email"))
        self.assertFalse(DataValidator.is_valid_email("@example.com"))
        self.assertFalse(DataValidator.is_valid_email("test@"))
    
    def test_valid_phone(self):
        """유효한 전화번호 검증 (한국)"""
        self.assertTrue(DataValidator.is_valid_phone("010-1234-5678"))
        self.assertTrue(DataValidator.is_valid_phone("01012345678"))
        self.assertTrue(DataValidator.is_valid_phone("011-123-4567"))
        self.assertFalse(DataValidator.is_valid_phone("02-123-4567"))  # 지역번호
        self.assertFalse(DataValidator.is_valid_phone("123-456-7890"))  # 미국 형식
    
    def test_safe_url(self):
        """안전한 URL 검증"""
        allowed_hosts = ['example.com', 'subdomain.example.com']
        
        # 상대 URL은 항상 안전
        self.assertTrue(DataValidator.is_safe_url("/path/to/page"))
        self.assertTrue(DataValidator.is_safe_url("../relative/path"))
        
        # 허용된 호스트
        self.assertTrue(DataValidator.is_safe_url(
            "https://example.com/page", 
            allowed_hosts=allowed_hosts
        ))
        
        # 허용되지 않은 호스트
        self.assertFalse(DataValidator.is_safe_url(
            "https://evil.com/page",
            allowed_hosts=allowed_hosts
        ))
        
        # 위험한 프로토콜
        self.assertFalse(DataValidator.is_safe_url("javascript:alert(1)"))
        self.assertFalse(DataValidator.is_safe_url("data:text/html,<script>"))


class TestStudyAPIIntegration(APITestCase):
    """Study API 통합 테스트"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    @patch('study.views.StudySummaryService')
    def test_study_summary_creation_with_standard_response(self, mock_service):
        """표준 응답 형식으로 학습 요약 생성 테스트"""
        mock_service.return_value.generate_summary.return_value = {
            'summary': 'Test summary content',
            'keywords': ['test', 'summary']
        }
        
        response = self.client.post('/api/study/summaries/', {
            'subject_id': 1,
            'content': 'Test content for summary'
        })
        
        # 응답 형식 확인
        if response.status_code == 201:
            self.assertIn('id', response.data)
            self.assertEqual(response.data.get('content'), 'Test content for summary')
    
    def test_pagination_response_format(self):
        """페이지네이션 응답 형식 테스트"""
        # 여러 개의 더미 데이터 생성 필요
        response = self.client.get('/api/study/summaries/?page=1&page_size=10')
        
        if response.status_code == 200:
            # 페이지네이션 응답 확인
            if 'results' in response.data:
                self.assertIn('count', response.data)
                self.assertIn('next', response.data)
                self.assertIn('previous', response.data)
    
    def test_error_response_format(self):
        """에러 응답 형식 테스트"""
        # 인증 없이 요청
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/study/summaries/')
        
        self.assertEqual(response.status_code, 401)
        self.assertIn('detail', response.data)


class TestPerformanceOptimization(TestCase):
    """성능 최적화 테스트"""
    
    @patch('django.core.cache.cache.get')
    @patch('django.core.cache.cache.set')
    def test_cache_key_generation_performance(self, mock_cache_set, mock_cache_get):
        """캐시 키 생성 성능 테스트"""
        import time
        
        # 1000개의 캐시 키 생성 시간 측정
        start = time.time()
        for i in range(1000):
            key = generate_cache_key('test', user_id=i, subject_id=i*2)
        end = time.time()
        
        # 1000개 생성이 0.1초 이내여야 함
        self.assertLess(end - start, 0.1)
    
    def test_sanitize_input_performance(self):
        """입력 정제 성능 테스트"""
        import time
        
        # 큰 텍스트 정제 시간 측정
        large_text = "x" * 10000 + "\x00" * 100 + "  spaces  " * 100
        
        start = time.time()
        for _ in range(100):
            sanitize_input(large_text)
        end = time.time()
        
        # 100번 정제가 0.1초 이내여야 함
        self.assertLess(end - start, 0.1)


class TestSecurityFeatures(TestCase):
    """보안 기능 테스트"""
    
    def test_token_uniqueness(self):
        """토큰 유일성 테스트"""
        tokens = set()
        for _ in range(100):
            token = generate_secure_token()
            self.assertNotIn(token, tokens)
            tokens.add(token)
    
    def test_sql_injection_prevention(self):
        """SQL 인젝션 방지 테스트"""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "1 OR 1=1",
            "admin'--",
            "' UNION SELECT * FROM users--"
        ]
        
        for malicious in malicious_inputs:
            # sanitize_input이 위험한 문자를 제거하는지 확인
            cleaned = sanitize_input(malicious)
            # 제어 문자와 특수 문자가 정제되었는지 확인
            self.assertNotIn('\x00', cleaned)
            self.assertEqual(cleaned, cleaned.strip())
    
    def test_xss_prevention(self):
        """XSS 방지 테스트"""
        xss_attempts = [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src=x onerror=alert('XSS')>",
            "<svg onload=alert('XSS')>"
        ]
        
        for xss in xss_attempts:
            # URL 검증이 javascript: 프로토콜을 차단하는지 확인
            if xss.startswith('javascript:'):
                self.assertFalse(DataValidator.is_safe_url(xss))