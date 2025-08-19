"""
Zero Trust 보안 관련 API 뷰

디바이스 등록, MFA, 위치 인증 등 Zero Trust 보안 기능을 제공합니다.
"""

import logging
from typing import Dict, Any, Optional, List
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status, serializers
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from studymate_api.zero_trust_security import (
    zero_trust_engine,
    DeviceFingerprint,
    register_trusted_device,
    register_trusted_location,
)

logger = logging.getLogger(__name__)
User = get_user_model()


class DeviceRegistrationSerializer(serializers.Serializer):
    """디바이스 등록 시리얼라이저"""

    device_name = serializers.CharField(max_length=100)
    user_agent = serializers.CharField(max_length=500)
    screen_resolution = serializers.CharField(max_length=20)
    timezone = serializers.CharField(max_length=50)
    language = serializers.CharField(max_length=10)
    platform = serializers.CharField(max_length=50)
    trust_this_device = serializers.BooleanField(default=False)


class MFAChallengeSerializer(serializers.Serializer):
    """MFA 챌린지 시리얼라이저"""

    challenge_type = serializers.ChoiceField(choices=["email", "sms", "totp"])
    verification_code = serializers.CharField(max_length=10, required=False)


class LocationVerificationSerializer(serializers.Serializer):
    """위치 인증 시리얼라이저"""

    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    accuracy = serializers.FloatField()
    trust_this_location = serializers.BooleanField(default=False)


class DeviceRegistrationView(APIView):
    """디바이스 등록 API"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """새 디바이스 등록"""
        serializer = DeviceRegistrationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            data = serializer.validated_data

            # 디바이스 지문 생성
            device_fingerprint = DeviceFingerprint(
                user_agent=data["user_agent"],
                screen_resolution=data["screen_resolution"],
                timezone=data["timezone"],
                language=data["language"],
                platform=data["platform"],
                browser_hash="",  # 자동 생성됨
            )

            fingerprint_hash = device_fingerprint.generate_fingerprint()

            # 디바이스 정보 저장
            device_info = {
                "name": data["device_name"],
                "fingerprint": fingerprint_hash,
                "registered_at": timezone.now().isoformat(),
                "last_used": timezone.now().isoformat(),
                "trusted": data["trust_this_device"],
            }

            cache_key = f"user_devices:{request.user.id}"
            user_devices = cache.get(cache_key, [])

            # 기존 디바이스 확인
            for device in user_devices:
                if device["fingerprint"] == fingerprint_hash:
                    device.update(device_info)
                    cache.set(cache_key, user_devices, timeout=86400 * 30)
                    return Response(
                        {
                            "message": "디바이스 정보가 업데이트되었습니다.",
                            "device_id": fingerprint_hash[:8],
                            "trusted": device["trusted"],
                        }
                    )

            # 새 디바이스 추가
            user_devices.append(device_info)
            cache.set(cache_key, user_devices[-10:], timeout=86400 * 30)  # 최대 10개

            # 신뢰 디바이스로 등록
            if data["trust_this_device"]:
                register_trusted_device(request.user.id, fingerprint_hash)

            logger.info(f"New device registered for user {request.user.id}")

            return Response(
                {
                    "message": "디바이스가 성공적으로 등록되었습니다.",
                    "device_id": fingerprint_hash[:8],
                    "trusted": data["trust_this_device"],
                    "requires_verification": not data["trust_this_device"],
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            logger.error(f"Device registration error: {e}")
            return Response(
                {"error": "device_registration_failed", "message": "디바이스 등록 중 오류가 발생했습니다."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def get(self, request):
        """사용자의 등록된 디바이스 목록"""
        cache_key = f"user_devices:{request.user.id}"
        user_devices = cache.get(cache_key, [])

        # 민감한 정보 제거
        safe_devices = []
        for device in user_devices:
            safe_devices.append(
                {
                    "device_id": device["fingerprint"][:8],
                    "name": device["name"],
                    "registered_at": device["registered_at"],
                    "last_used": device["last_used"],
                    "trusted": device["trusted"],
                }
            )

        return Response({"devices": safe_devices, "total_count": len(safe_devices)})

    def delete(self, request):
        """디바이스 삭제"""
        device_id = request.query_params.get("device_id")
        if not device_id:
            return Response(
                {"error": "device_id_required", "message": "디바이스 ID가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST
            )

        cache_key = f"user_devices:{request.user.id}"
        user_devices = cache.get(cache_key, [])

        # 디바이스 찾기 및 삭제
        for i, device in enumerate(user_devices):
            if device["fingerprint"].startswith(device_id):
                removed_device = user_devices.pop(i)
                cache.set(cache_key, user_devices, timeout=86400 * 30)

                # 신뢰 디바이스에서도 제거
                trust_key = f"known_device:{request.user.id}:{removed_device['fingerprint']}"
                cache.delete(trust_key)

                logger.info(f"Device removed for user {request.user.id}: {device_id}")

                return Response({"message": "디바이스가 삭제되었습니다.", "device_name": removed_device["name"]})

        return Response({"error": "device_not_found", "message": "디바이스를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)


class MFAChallengeView(APIView):
    """MFA 챌린지 API"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """MFA 챌린지 요청"""
        serializer = MFAChallengeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        challenge_type = data["challenge_type"]

        try:
            # 챌린지 코드 생성
            challenge_code = self._generate_challenge_code()

            # 챌린지 저장
            cache_key = f"mfa_challenge:{request.user.id}"
            challenge_data = {
                "code": challenge_code,
                "type": challenge_type,
                "created_at": timezone.now().isoformat(),
                "attempts": 0,
                "verified": False,
            }
            cache.set(cache_key, challenge_data, timeout=300)  # 5분

            # 챌린지 발송
            if challenge_type == "email":
                self._send_email_challenge(request.user.email, challenge_code)
            elif challenge_type == "sms":
                self._send_sms_challenge(request.user.phone_number, challenge_code)

            logger.info(f"MFA challenge sent to user {request.user.id} via {challenge_type}")

            return Response(
                {
                    "message": f"{challenge_type.upper()} 인증 코드가 전송되었습니다.",
                    "challenge_type": challenge_type,
                    "expires_in": 300,
                }
            )

        except Exception as e:
            logger.error(f"MFA challenge error: {e}")
            return Response(
                {"error": "mfa_challenge_failed", "message": "MFA 챌린지 생성 중 오류가 발생했습니다."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request):
        """MFA 챌린지 검증"""
        serializer = MFAChallengeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        verification_code = data.get("verification_code")

        if not verification_code:
            return Response(
                {"error": "verification_code_required", "message": "인증 코드가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            cache_key = f"mfa_challenge:{request.user.id}"
            challenge_data = cache.get(cache_key)

            if not challenge_data:
                return Response(
                    {"error": "no_active_challenge", "message": "활성화된 챌린지가 없습니다."}, status=status.HTTP_400_BAD_REQUEST
                )

            # 시도 횟수 체크
            if challenge_data["attempts"] >= 3:
                cache.delete(cache_key)
                return Response(
                    {"error": "too_many_attempts", "message": "시도 횟수를 초과했습니다. 새로운 챌린지를 요청하세요."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

            # 코드 검증
            if challenge_data["code"] == verification_code:
                challenge_data["verified"] = True
                cache.set(cache_key, challenge_data, timeout=300)

                # 세션에 MFA 완료 표시
                request.session["mfa_verified"] = True
                request.session["mfa_verified_at"] = timezone.now().isoformat()

                logger.info(f"MFA verification successful for user {request.user.id}")

                return Response({"message": "MFA 인증이 완료되었습니다.", "verified": True})
            else:
                challenge_data["attempts"] += 1
                cache.set(cache_key, challenge_data, timeout=300)

                return Response(
                    {
                        "error": "invalid_code",
                        "message": "잘못된 인증 코드입니다.",
                        "attempts_remaining": 3 - challenge_data["attempts"],
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except Exception as e:
            logger.error(f"MFA verification error: {e}")
            return Response(
                {"error": "mfa_verification_failed", "message": "MFA 인증 중 오류가 발생했습니다."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _generate_challenge_code(self) -> str:
        """챌린지 코드 생성"""
        import random

        return str(random.randint(100000, 999999))

    def _send_email_challenge(self, email: str, code: str):
        """이메일 챌린지 발송"""
        # 실제 구현에서는 이메일 발송 서비스 사용
        logger.info(f"Sending email challenge to {email}: {code}")
        pass

    def _send_sms_challenge(self, phone: str, code: str):
        """SMS 챌린지 발송"""
        # 실제 구현에서는 SMS 발송 서비스 사용
        logger.info(f"Sending SMS challenge to {phone}: {code}")
        pass


class LocationVerificationView(APIView):
    """위치 인증 API"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """위치 인증"""
        serializer = LocationVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        try:
            # 위치 정보 저장
            location_data = {
                "latitude": data["latitude"],
                "longitude": data["longitude"],
                "accuracy": data["accuracy"],
                "verified_at": timezone.now().isoformat(),
                "trusted": data["trust_this_location"],
            }

            # 사용자의 위치 기록에 추가
            cache_key = f"user_locations:{request.user.id}"
            user_locations = cache.get(cache_key, [])
            user_locations.append(location_data)
            cache.set(cache_key, user_locations[-10:], timeout=86400 * 7)  # 7일, 최대 10개

            # 신뢰 위치로 등록
            if data["trust_this_location"]:
                # 대략적인 지역 정보로 저장 (개인정보 보호)
                region_data = {
                    "country": self._get_country_from_coords(data["latitude"], data["longitude"]),
                    "region": self._get_region_from_coords(data["latitude"], data["longitude"]),
                }
                register_trusted_location(request.user.id, region_data)

            logger.info(f"Location verified for user {request.user.id}")

            return Response(
                {"message": "위치 인증이 완료되었습니다.", "trusted": data["trust_this_location"], "accuracy": data["accuracy"]}
            )

        except Exception as e:
            logger.error(f"Location verification error: {e}")
            return Response(
                {"error": "location_verification_failed", "message": "위치 인증 중 오류가 발생했습니다."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _get_country_from_coords(self, lat: float, lng: float) -> str:
        """좌표에서 국가 정보 추출"""
        # 실제 구현에서는 역지오코딩 서비스 사용
        return "Unknown"

    def _get_region_from_coords(self, lat: float, lng: float) -> str:
        """좌표에서 지역 정보 추출"""
        # 실제 구현에서는 역지오코딩 서비스 사용
        return "Unknown"


class SecurityStatusView(APIView):
    """보안 상태 API"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """사용자의 현재 보안 상태"""
        try:
            # Zero Trust 평가
            action, context = zero_trust_engine.evaluate_request(request, request.user)

            # 보안 상태 정보
            security_status = {
                "trust_score": context.get("trust_score", 0.0),
                "threat_level": context.get("threat_level", "unknown"),
                "security_action": action.value,
                "mfa_verified": request.session.get("mfa_verified", False),
                "device_trusted": self._is_device_trusted(request),
                "location_trusted": self._is_location_trusted(request),
                "last_security_check": timezone.now().isoformat(),
            }

            # 보안 권장사항
            recommendations = self._get_security_recommendations(security_status)

            return Response(
                {
                    "security_status": security_status,
                    "recommendations": recommendations,
                    "additional_measures": context.get("additional_measures", {}),
                }
            )

        except Exception as e:
            logger.error(f"Security status check error: {e}")
            return Response(
                {"error": "security_status_failed", "message": "보안 상태 확인 중 오류가 발생했습니다."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _is_device_trusted(self, request) -> bool:
        """디바이스 신뢰 여부 확인"""
        # 구현 필요
        return False

    def _is_location_trusted(self, request) -> bool:
        """위치 신뢰 여부 확인"""
        # 구현 필요
        return False

    def _get_security_recommendations(self, status: Dict[str, Any]) -> List[str]:
        """보안 권장사항 생성"""
        recommendations = []

        if status["trust_score"] < 0.7:
            recommendations.append("신뢰 점수가 낮습니다. MFA 인증을 완료하세요.")

        if not status["mfa_verified"]:
            recommendations.append("추가 인증(MFA)을 완료하세요.")

        if not status["device_trusted"]:
            recommendations.append("이 디바이스를 신뢰 디바이스로 등록하세요.")

        if not status["location_trusted"]:
            recommendations.append("현재 위치를 신뢰 위치로 등록하세요.")

        return recommendations
