"""
Accounts 앱 테스트

이 모듈은 accounts 앱의 모든 기능에 대한 포괄적인 테스트를 제공합니다.
- 사용자 인증 및 권한
- 회원가입 및 로그인
- 프로필 관리
- 이메일 인증
- 보안 기능
"""

import pytest
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch, Mock
from datetime import timedelta

from .utils import APITestCase as BaseAPITestCase, MockingTestCase, PerformanceTestMixin
from .factories import UserFactory, AdminUserFactory, UserProfileFactory
from accounts.models import UserProfile, EmailVerificationToken, PasswordResetToken, LoginHistory
from accounts.serializers import UserSerializer, UserRegistrationSerializer

User = get_user_model()


class UserModelTest(TestCase):
    """사용자 모델 테스트"""
    
    def setUp(self):
        self.user_data = {
            'email': 'test@example.com',
            'first_name': '홍',
            'last_name': '길동',
            'password': 'testpass123'
        }
    
    def test_create_user(self):
        """사용자 생성 테스트"""
        user = User.objects.create_user(**self.user_data)
        
        self.assertEqual(user.email, self.user_data['email'])
        self.assertEqual(user.first_name, self.user_data['first_name'])
        self.assertEqual(user.last_name, self.user_data['last_name'])
        self.assertTrue(user.check_password(self.user_data['password']))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
    
    def test_create_superuser(self):
        """관리자 사용자 생성 테스트"""
        admin = User.objects.create_superuser(
            email='admin@example.com',
            password='adminpass123'
        )
        
        self.assertTrue(admin.is_active)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
    
    def test_user_string_representation(self):
        """사용자 문자열 표현 테스트"""
        user = UserFactory(email='test@example.com')
        self.assertEqual(str(user), 'test@example.com')
    
    def test_user_full_name(self):
        """사용자 전체 이름 테스트"""
        user = UserFactory(first_name='홍', last_name='길동')
        self.assertEqual(user.get_full_name(), '홍 길동')
    
    def test_email_uniqueness(self):
        """이메일 유일성 테스트"""
        UserFactory(email='test@example.com')
        
        with self.assertRaises(Exception):
            UserFactory(email='test@example.com')


class UserProfileModelTest(TestCase):
    """사용자 프로필 모델 테스트"""
    
    def test_create_profile(self):
        """프로필 생성 테스트"""
        user = UserFactory()
        profile = UserProfileFactory(user=user)
        
        self.assertEqual(profile.user, user)
        self.assertIsNotNone(profile.name)
        self.assertTrue(profile.is_verified)
    
    def test_profile_string_representation(self):
        """프로필 문자열 표현 테스트"""
        user = UserFactory(email='test@example.com')
        profile = UserProfileFactory(user=user, name='홍길동')
        
        self.assertEqual(str(profile), 'test@example.com - 홍길동')
    
    def test_profile_age_calculation(self):
        """나이 계산 테스트"""
        from datetime import date
        
        birth_date = date(1990, 1, 1)
        profile = UserProfileFactory(birth_date=birth_date)
        
        expected_age = timezone.now().year - 1990
        self.assertEqual(profile.age, expected_age)


@pytest.mark.auth
class UserRegistrationAPITest(BaseAPITestCase, MockingTestCase):
    """사용자 회원가입 API 테스트"""
    
    def setUp(self):
        super().setUp()
        self.registration_url = reverse('accounts:register')
        self.mock_email_service()
    
    def test_successful_registration(self):
        """정상 회원가입 테스트"""
        data = {
            'email': 'newuser@example.com',
            'password': 'securepass123',
            'password_confirm': 'securepass123',
            'first_name': '홍',
            'last_name': '길동',
            'agree_to_terms': True,
            'agree_to_privacy': True
        }
        
        response = self.api_post(self.registration_url, data)
        
        self.assert_response_success(response, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email=data['email']).exists())
        
        # 이메일 발송 확인
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('인증', mail.outbox[0].subject)
    
    def test_registration_password_mismatch(self):
        """비밀번호 불일치 테스트"""
        data = {
            'email': 'test@example.com',
            'password': 'password123',
            'password_confirm': 'different123',
            'agree_to_terms': True,
            'agree_to_privacy': True
        }
        
        response = self.api_post(self.registration_url, data)
        self.assert_response_error(response)
    
    def test_registration_duplicate_email(self):
        """중복 이메일 테스트"""
        existing_user = UserFactory(email='test@example.com')
        
        data = {
            'email': 'test@example.com',
            'password': 'password123',
            'password_confirm': 'password123',
            'agree_to_terms': True,
            'agree_to_privacy': True
        }
        
        response = self.api_post(self.registration_url, data)
        self.assert_response_error(response)
    
    def test_registration_terms_required(self):
        """약관 동의 필수 테스트"""
        data = {
            'email': 'test@example.com',
            'password': 'password123',
            'password_confirm': 'password123',
            'agree_to_terms': False,
            'agree_to_privacy': True
        }
        
        response = self.api_post(self.registration_url, data)
        self.assert_response_error(response)
    
    @patch('accounts.views._is_suspicious_registration')
    def test_registration_suspicious_activity(self, mock_suspicious):
        """의심스러운 활동 차단 테스트"""
        mock_suspicious.return_value = True
        
        data = {
            'email': 'test@example.com',
            'password': 'password123',
            'password_confirm': 'password123',
            'agree_to_terms': True,
            'agree_to_privacy': True
        }
        
        response = self.api_post(self.registration_url, data)
        self.assert_response_error(response, status.HTTP_429_TOO_MANY_REQUESTS)


@pytest.mark.auth
class UserLoginAPITest(BaseAPITestCase, MockingTestCase):
    """사용자 로그인 API 테스트"""
    
    def setUp(self):
        super().setUp()
        self.login_url = reverse('accounts:login')
        self.user = UserFactory(email='test@example.com')
        self.user.set_password('testpass123')
        self.user.save()
    
    def test_successful_login(self):
        """정상 로그인 테스트"""
        data = {
            'email': 'test@example.com',
            'password': 'testpass123'
        }
        
        response = self.api_post(self.login_url, data)
        
        self.assert_response_success(response)
        self.assertIn('access_token', response.data['data'])
        self.assertIn('refresh_token', response.data['data'])
        self.assertIn('user', response.data['data'])
        
        # 로그인 기록 확인
        self.assertTrue(
            LoginHistory.objects.filter(
                user=self.user,
                success=True
            ).exists()
        )
    
    def test_login_invalid_credentials(self):
        """잘못된 자격증명 테스트"""
        data = {
            'email': 'test@example.com',
            'password': 'wrongpassword'
        }
        
        response = self.api_post(self.login_url, data)
        self.assert_response_error(response, status.HTTP_401_UNAUTHORIZED)
        
        # 실패 기록 확인
        self.assertTrue(
            LoginHistory.objects.filter(
                user=self.user,
                success=False
            ).exists()
        )
    
    def test_login_inactive_user(self):
        """비활성 사용자 로그인 테스트"""
        self.user.is_active = False
        self.user.save()
        
        data = {
            'email': 'test@example.com',
            'password': 'testpass123'
        }
        
        response = self.api_post(self.login_url, data)
        self.assert_response_error(response, status.HTTP_401_UNAUTHORIZED)
    
    def test_login_missing_fields(self):
        """필수 필드 누락 테스트"""
        response = self.api_post(self.login_url, {'email': 'test@example.com'})
        self.assert_response_error(response)
        
        response = self.api_post(self.login_url, {'password': 'testpass123'})
        self.assert_response_error(response)
    
    @patch('accounts.views._is_suspicious_login')
    def test_login_suspicious_activity(self, mock_suspicious):
        """의심스러운 로그인 차단 테스트"""
        mock_suspicious.return_value = True
        
        data = {
            'email': 'test@example.com',
            'password': 'testpass123'
        }
        
        response = self.api_post(self.login_url, data)
        self.assert_response_error(response, status.HTTP_429_TOO_MANY_REQUESTS)


@pytest.mark.auth
class UserProfileAPITest(BaseAPITestCase):
    """사용자 프로필 API 테스트"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.profile = UserProfileFactory(user=self.user)
        self.authenticate_user(self.user)
        self.profile_url = reverse('accounts:profile')
    
    def test_get_profile(self):
        """프로필 조회 테스트"""
        response = self.api_get(self.profile_url)
        
        self.assert_response_success(response)
        data = response.data['data'] if 'data' in response.data else response.data
        self.assertEqual(data['name'], self.profile.name)
        self.assertEqual(data['user']['email'], self.user.email)
    
    def test_update_profile(self):
        """프로필 수정 테스트"""
        update_data = {
            'name': '새로운 이름',
            'bio': '새로운 소개',
            'preferred_language': 'en'
        }
        
        response = self.api_patch(self.profile_url, update_data)
        
        self.assert_response_success(response)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.name, update_data['name'])
        self.assertEqual(self.profile.bio, update_data['bio'])
    
    def test_profile_unauthenticated(self):
        """인증되지 않은 프로필 접근 테스트"""
        self.unauthenticate()
        response = self.api_get(self.profile_url)
        self.assert_response_error(response, status.HTTP_401_UNAUTHORIZED)
    
    def test_profile_image_upload(self):
        """프로필 이미지 업로드 테스트"""
        image = self.create_test_image()
        
        response = self.api_patch(
            self.profile_url,
            {'profile_image': image},
            format='multipart'
        )
        
        self.assert_response_success(response)
        self.profile.refresh_from_db()
        self.assertIsNotNone(self.profile.profile_image)


@pytest.mark.auth
class EmailVerificationTest(BaseAPITestCase, MockingTestCase):
    """이메일 인증 테스트"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory(is_active=False)
        self.mock_email_service()
        self.verify_url = reverse('accounts:verify-email')
    
    def test_email_verification_success(self):
        """이메일 인증 성공 테스트"""
        # 인증 토큰 생성
        token = EmailVerificationToken.objects.create(user=self.user)
        
        response = self.api_post(self.verify_url, {'token': str(token.token)})
        
        self.assert_response_success(response)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        
        # 토큰이 사용되었는지 확인
        token.refresh_from_db()
        self.assertTrue(token.is_used)
    
    def test_email_verification_invalid_token(self):
        """잘못된 토큰 테스트"""
        response = self.api_post(self.verify_url, {'token': 'invalid-token'})
        self.assert_response_error(response)
    
    def test_email_verification_expired_token(self):
        """만료된 토큰 테스트"""
        token = EmailVerificationToken.objects.create(
            user=self.user,
            expires_at=timezone.now() - timedelta(days=1)
        )
        
        response = self.api_post(self.verify_url, {'token': str(token.token)})
        self.assert_response_error(response)


@pytest.mark.auth
class PasswordResetTest(BaseAPITestCase, MockingTestCase):
    """비밀번호 재설정 테스트"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory(email='test@example.com')
        self.mock_email_service()
        self.reset_request_url = reverse('accounts:password-reset-request')
        self.reset_confirm_url = reverse('accounts:password-reset-confirm')
    
    def test_password_reset_request(self):
        """비밀번호 재설정 요청 테스트"""
        data = {'email': 'test@example.com'}
        
        response = self.api_post(self.reset_request_url, data)
        
        self.assert_response_success(response)
        self.assertTrue(
            PasswordResetToken.objects.filter(user=self.user).exists()
        )
        self.assertEqual(len(mail.outbox), 1)
    
    def test_password_reset_confirm(self):
        """비밀번호 재설정 확인 테스트"""
        token = PasswordResetToken.objects.create(user=self.user)
        
        data = {
            'token': str(token.token),
            'new_password': 'newpassword123'
        }
        
        response = self.api_post(self.reset_confirm_url, data)
        
        self.assert_response_success(response)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newpassword123'))


@pytest.mark.auth
class UserPermissionTest(BaseAPITestCase):
    """사용자 권한 테스트"""
    
    def setUp(self):
        super().setUp()
        self.admin = AdminUserFactory()
        self.user = UserFactory()
        self.admin_only_url = reverse('admin:index')  # 관리자 전용 URL
    
    def test_admin_access(self):
        """관리자 접근 테스트"""
        self.authenticate_user(self.admin)
        # 관리자 전용 기능 테스트는 실제 뷰에 따라 구현
        
        self.assertTrue(self.admin.is_staff)
        self.assertTrue(self.admin.is_superuser)
    
    def test_regular_user_access(self):
        """일반 사용자 접근 테스트"""
        self.authenticate_user(self.user)
        
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)


@pytest.mark.unit
class UserSerializerTest(TestCase):
    """사용자 시리얼라이저 테스트"""
    
    def test_user_serializer_validation(self):
        """사용자 시리얼라이저 검증 테스트"""
        data = {
            'email': 'test@example.com',
            'first_name': '홍',
            'last_name': '길동'
        }
        
        serializer = UserSerializer(data=data)
        self.assertTrue(serializer.is_valid())
    
    def test_registration_serializer_validation(self):
        """회원가입 시리얼라이저 검증 테스트"""
        data = {
            'email': 'test@example.com',
            'password': 'securepass123',
            'password_confirm': 'securepass123',
            'first_name': '홍',
            'last_name': '길동',
            'agree_to_terms': True,
            'agree_to_privacy': True
        }
        
        serializer = UserRegistrationSerializer(data=data)
        self.assertTrue(serializer.is_valid())


@pytest.mark.integration
class AccountsIntegrationTest(BaseAPITestCase, PerformanceTestMixin):
    """계정 통합 테스트"""
    
    def test_complete_user_journey(self):
        """완전한 사용자 여정 테스트"""
        # 1. 회원가입
        registration_data = {
            'email': 'journey@example.com',
            'password': 'securepass123',
            'password_confirm': 'securepass123',
            'first_name': '여정',
            'last_name': '테스트',
            'agree_to_terms': True,
            'agree_to_privacy': True
        }
        
        with patch('django.core.mail.send_mail'):
            response = self.api_post(reverse('accounts:register'), registration_data)
            self.assert_response_success(response, status.HTTP_201_CREATED)
        
        # 2. 이메일 인증
        user = User.objects.get(email='journey@example.com')
        token = EmailVerificationToken.objects.create(user=user)
        
        response = self.api_post(
            reverse('accounts:verify-email'),
            {'token': str(token.token)}
        )
        self.assert_response_success(response)
        
        # 3. 로그인
        login_data = {
            'email': 'journey@example.com',
            'password': 'securepass123'
        }
        
        response = self.api_post(reverse('accounts:login'), login_data)
        self.assert_response_success(response)
        
        access_token = response.data['data']['access_token']
        
        # 4. 프로필 조회
        self.api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.api_get(reverse('accounts:profile'))
        self.assert_response_success(response)
        
        # 5. 프로필 수정
        profile_data = {
            'name': '새로운 이름',
            'bio': '자기소개'
        }
        
        response = self.api_patch(reverse('accounts:profile'), profile_data)
        self.assert_response_success(response)
    
    def test_account_performance(self):
        """계정 성능 테스트"""
        user = UserFactory()
        
        # 로그인 성능 테스트
        def login_test():
            return self.api_post(reverse('accounts:login'), {
                'email': user.email,
                'password': 'testpass123'
            })
        
        # 1초 이내 응답 확인
        self.assert_response_time(login_test, max_time_ms=1000)
        
        # 프로필 조회 성능 테스트
        self.authenticate_user(user)
        
        def profile_test():
            return self.api_get(reverse('accounts:profile'))
        
        # 쿼리 수 제한 (5개 이하)
        self.assert_query_count(profile_test, max_queries=5)


# 추가 테스트 마커
pytestmark = [
    pytest.mark.django_db,
    pytest.mark.accounts
]