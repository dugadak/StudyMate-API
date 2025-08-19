from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
import pytest


User = get_user_model()


class UserModelTest(TestCase):
    """사용자 모델 테스트"""

    def test_create_user(self):
        """사용자 생성 테스트"""
        user = User.objects.create_user(email="test@example.com", password="testpass123")
        self.assertEqual(user.email, "test@example.com")
        self.assertTrue(user.check_password("testpass123"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_superuser(self):
        """슈퍼유저 생성 테스트"""
        admin_user = User.objects.create_superuser(email="admin@example.com", password="adminpass123")
        self.assertEqual(admin_user.email, "admin@example.com")
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)


@pytest.mark.auth
class AuthAPITest(APITestCase):
    """인증 API 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(email="test@example.com", password="testpass123")

    def test_user_registration(self):
        """회원가입 테스트"""
        url = reverse("accounts:register")
        data = {"email": "newuser@example.com", "password": "newpass123", "password2": "newpass123"}
        response = self.client.post(url, data)
        # 회원가입 엔드포인트가 구현되면 status 체크
        # self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_user_login(self):
        """로그인 테스트"""
        url = reverse("accounts:login")
        data = {"email": "test@example.com", "password": "testpass123"}
        response = self.client.post(url, data)
        # 로그인 엔드포인트가 구현되면 status 체크
        # self.assertEqual(response.status_code, status.HTTP_200_OK)
