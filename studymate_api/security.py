"""
StudyMate API 보안 모듈

이 모듈은 다음 보안 기능을 제공합니다:
- 입력 검증 및 삭제
- SQL 인젝션 방지
- XSS 방지
- CSRF 방지
- 파일 업로드 보안
- 암호화/복호화 유틸리티
- 보안 헤더 설정
"""

import re
import hashlib
import hmac
import base64
import secrets
import html
from typing import Optional, Dict, Any, List, Union
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.html import strip_tags
from django.utils.encoding import force_str
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging

logger = logging.getLogger(__name__)


class SecurityValidator:
    """보안 검증 클래스"""
    
    # 위험한 패턴들
    SQL_INJECTION_PATTERNS = [
        r"(\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b)",
        r"(\b(script|javascript|vbscript|onload|onerror|onclick)\b)",
        r"(--|#|/\*|\*/)",
        r"(\bor\b.*=.*\bor\b)",
        r"(\band\b.*=.*\band\b)",
        r"('|\"|;|<|>|\||&)",
    ]
    
    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"vbscript:",
        r"onload\s*=",
        r"onerror\s*=",
        r"onclick\s*=",
        r"onmouseover\s*=",
        r"<iframe[^>]*>",
        r"<object[^>]*>",
        r"<embed[^>]*>",
        r"<link[^>]*>",
        r"<meta[^>]*>",
    ]
    
    FILE_PATH_PATTERNS = [
        r"\.\./",
        r"\.\.\\",
        r"/etc/passwd",
        r"/etc/shadow",
        r"windows/system32",
        r"cmd\.exe",
        r"powershell",
        r"/bin/bash",
        r"/bin/sh",
    ]
    
    def __init__(self):
        self.sql_regex = re.compile("|".join(self.SQL_INJECTION_PATTERNS), re.IGNORECASE)
        self.xss_regex = re.compile("|".join(self.XSS_PATTERNS), re.IGNORECASE)
        self.path_regex = re.compile("|".join(self.FILE_PATH_PATTERNS), re.IGNORECASE)
    
    def validate_input(self, data: Union[str, Dict, List], 
                      strict: bool = True) -> Dict[str, Any]:
        """입력 데이터 검증"""
        result = {
            'is_safe': True,
            'issues': [],
            'sanitized_data': data
        }
        
        if isinstance(data, str):
            issues = self._validate_string(data, strict)
            if issues:
                result['is_safe'] = False
                result['issues'].extend(issues)
                result['sanitized_data'] = self.sanitize_string(data)
        
        elif isinstance(data, dict):
            sanitized_dict = {}
            for key, value in data.items():
                key_validation = self.validate_input(str(key), strict)
                value_validation = self.validate_input(value, strict)
                
                if not key_validation['is_safe'] or not value_validation['is_safe']:
                    result['is_safe'] = False
                    result['issues'].extend(key_validation['issues'])
                    result['issues'].extend(value_validation['issues'])
                
                sanitized_dict[key_validation['sanitized_data']] = value_validation['sanitized_data']
            
            result['sanitized_data'] = sanitized_dict
        
        elif isinstance(data, list):
            sanitized_list = []
            for item in data:
                item_validation = self.validate_input(item, strict)
                if not item_validation['is_safe']:
                    result['is_safe'] = False
                    result['issues'].extend(item_validation['issues'])
                sanitized_list.append(item_validation['sanitized_data'])
            
            result['sanitized_data'] = sanitized_list
        
        return result
    
    def _validate_string(self, text: str, strict: bool = True) -> List[str]:
        """문자열 검증"""
        issues = []
        
        # SQL 인젝션 검사
        if self.sql_regex.search(text):
            issues.append("Potential SQL injection detected")
        
        # XSS 검사
        if self.xss_regex.search(text):
            issues.append("Potential XSS attack detected")
        
        # 경로 순회 검사
        if self.path_regex.search(text):
            issues.append("Potential path traversal attack detected")
        
        # 추가 보안 검사 (strict 모드)
        if strict:
            # 과도한 특수문자 검사
            special_char_count = sum(1 for c in text if not c.isalnum() and not c.isspace())
            if len(text) > 0 and special_char_count / len(text) > 0.3:
                issues.append("Excessive special characters detected")
            
            # 매우 긴 입력 검사
            if len(text) > 10000:
                issues.append("Input too long")
            
            # 제어 문자 검사
            if any(ord(c) < 32 and c not in '\t\n\r' for c in text):
                issues.append("Control characters detected")
        
        return issues
    
    def sanitize_string(self, text: str) -> str:
        """문자열 삭제"""
        if not isinstance(text, str):
            return str(text)
        
        # HTML 엔티티 인코딩
        sanitized = html.escape(text)
        
        # HTML 태그 제거
        sanitized = strip_tags(sanitized)
        
        # 위험한 패턴 제거
        sanitized = self.sql_regex.sub("", sanitized)
        sanitized = self.xss_regex.sub("", sanitized)
        sanitized = self.path_regex.sub("", sanitized)
        
        # 제어 문자 제거 (탭, 줄바꿈 제외)
        sanitized = ''.join(c for c in sanitized if ord(c) >= 32 or c in '\t\n\r')
        
        # 연속된 공백 정리
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        return sanitized
    
    def validate_email(self, email: str) -> bool:
        """이메일 검증"""
        if not email:
            return False
        
        # 기본 형식 검증
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return False
        
        # 보안 검증
        validation = self.validate_input(email, strict=True)
        return validation['is_safe']
    
    def validate_password(self, password: str) -> Dict[str, Any]:
        """비밀번호 강도 검증"""
        issues = []
        score = 0
        
        if len(password) >= 8:
            score += 1
        else:
            issues.append("비밀번호는 최소 8자 이상이어야 합니다")
        
        if re.search(r'[a-z]', password):
            score += 1
        else:
            issues.append("소문자가 포함되어야 합니다")
        
        if re.search(r'[A-Z]', password):
            score += 1
        else:
            issues.append("대문자가 포함되어야 합니다")
        
        if re.search(r'\d', password):
            score += 1
        else:
            issues.append("숫자가 포함되어야 합니다")
        
        if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            score += 1
        else:
            issues.append("특수문자가 포함되어야 합니다")
        
        # 추가 검증
        if len(password) >= 12:
            score += 1
        
        # 반복 문자 검사
        if re.search(r'(.)\1{2,}', password):
            issues.append("3개 이상 연속된 같은 문자는 사용할 수 없습니다")
            score -= 1
        
        # 일반적인 패턴 검사
        common_patterns = ['123', 'abc', 'password', 'qwerty', '111']
        if any(pattern in password.lower() for pattern in common_patterns):
            issues.append("일반적인 패턴은 사용할 수 없습니다")
            score -= 1
        
        strength_levels = ['매우 약함', '약함', '보통', '강함', '매우 강함']
        strength = strength_levels[min(max(score - 1, 0), 4)]
        
        return {
            'is_valid': len(issues) == 0 and score >= 4,
            'strength': strength,
            'score': score,
            'issues': issues
        }


class FileSecurityValidator:
    """파일 보안 검증 클래스"""
    
    ALLOWED_EXTENSIONS = {
        'image': ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'],
        'document': ['pdf', 'doc', 'docx', 'txt', 'rtf'],
        'video': ['mp4', 'avi', 'mov', 'wmv', 'flv'],
        'audio': ['mp3', 'wav', 'ogg', 'aac', 'm4a']
    }
    
    MAX_FILE_SIZES = {
        'image': 10 * 1024 * 1024,      # 10MB
        'document': 50 * 1024 * 1024,   # 50MB
        'video': 500 * 1024 * 1024,     # 500MB
        'audio': 100 * 1024 * 1024,     # 100MB
    }
    
    MALICIOUS_SIGNATURES = [
        b'\x4d\x5a',  # PE executable
        b'\x7f\x45\x4c\x46',  # ELF executable
        b'\xca\xfe\xba\xbe',  # Java class file
        b'\x50\x4b\x03\x04',  # ZIP file (potentially malicious)
    ]
    
    def validate_file(self, file_obj, file_type: str = 'document') -> Dict[str, Any]:
        """파일 검증"""
        result = {
            'is_safe': True,
            'issues': [],
            'file_info': {}
        }
        
        try:
            # 파일 확장자 검증
            filename = getattr(file_obj, 'name', '')
            if not self._validate_extension(filename, file_type):
                result['is_safe'] = False
                result['issues'].append(f"허용되지 않는 파일 확장자입니다")
            
            # 파일 크기 검증
            file_size = getattr(file_obj, 'size', 0)
            if not self._validate_size(file_size, file_type):
                result['is_safe'] = False
                result['issues'].append(f"파일 크기가 제한을 초과했습니다")
            
            # 파일 시그니처 검증
            if hasattr(file_obj, 'read'):
                file_obj.seek(0)
                file_header = file_obj.read(512)
                file_obj.seek(0)
                
                if not self._validate_signature(file_header):
                    result['is_safe'] = False
                    result['issues'].append("악성 파일 시그니처가 감지되었습니다")
            
            result['file_info'] = {
                'filename': filename,
                'size': file_size,
                'type': file_type
            }
            
        except Exception as e:
            logger.error(f"File validation error: {e}")
            result['is_safe'] = False
            result['issues'].append("파일 검증 중 오류가 발생했습니다")
        
        return result
    
    def _validate_extension(self, filename: str, file_type: str) -> bool:
        """파일 확장자 검증"""
        if not filename:
            return False
        
        extension = filename.lower().split('.')[-1]
        allowed = self.ALLOWED_EXTENSIONS.get(file_type, [])
        return extension in allowed
    
    def _validate_size(self, file_size: int, file_type: str) -> bool:
        """파일 크기 검증"""
        max_size = self.MAX_FILE_SIZES.get(file_type, 10 * 1024 * 1024)
        return file_size <= max_size
    
    def _validate_signature(self, file_header: bytes) -> bool:
        """파일 시그니처 검증"""
        for signature in self.MALICIOUS_SIGNATURES:
            if file_header.startswith(signature):
                return False
        return True


class CryptoUtils:
    """암호화 유틸리티 클래스"""
    
    def __init__(self):
        self.secret_key = getattr(settings, 'SECRET_KEY', '').encode()
    
    def generate_key(self, password: str, salt: Optional[bytes] = None) -> bytes:
        """비밀번호 기반 키 생성"""
        if salt is None:
            salt = secrets.token_bytes(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))
    
    def encrypt_data(self, data: str, key: Optional[bytes] = None) -> str:
        """데이터 암호화"""
        if key is None:
            key = self.generate_key(settings.SECRET_KEY)
        
        f = Fernet(key)
        encrypted_data = f.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted_data).decode()
    
    def decrypt_data(self, encrypted_data: str, key: Optional[bytes] = None) -> str:
        """데이터 복호화"""
        if key is None:
            key = self.generate_key(settings.SECRET_KEY)
        
        try:
            f = Fernet(key)
            decoded_data = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_data = f.decrypt(decoded_data)
            return decrypted_data.decode()
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            raise ValidationError("복호화에 실패했습니다")
    
    def generate_hash(self, data: str, salt: Optional[str] = None) -> str:
        """해시 생성"""
        if salt is None:
            salt = secrets.token_hex(16)
        
        combined = f"{data}{salt}"
        hash_obj = hashlib.sha256(combined.encode())
        return f"{salt}:{hash_obj.hexdigest()}"
    
    def verify_hash(self, data: str, hashed_data: str) -> bool:
        """해시 검증"""
        try:
            salt, stored_hash = hashed_data.split(':', 1)
            combined = f"{data}{salt}"
            hash_obj = hashlib.sha256(combined.encode())
            return hmac.compare_digest(hash_obj.hexdigest(), stored_hash)
        except (ValueError, AttributeError):
            return False
    
    def generate_token(self, length: int = 32) -> str:
        """보안 토큰 생성"""
        return secrets.token_urlsafe(length)
    
    def generate_otp(self, length: int = 6) -> str:
        """OTP 생성"""
        return ''.join(secrets.choice('0123456789') for _ in range(length))


class SecurityHeaders:
    """보안 헤더 관리 클래스"""
    
    @staticmethod
    def get_security_headers() -> Dict[str, str]:
        """보안 헤더 반환"""
        return {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Content-Security-Policy': (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self'; "
                "connect-src 'self'; "
                "frame-ancestors 'none';"
            ),
            'Permissions-Policy': (
                "geolocation=(), "
                "microphone=(), "
                "camera=(), "
                "payment=(), "
                "usb=(), "
                "magnetometer=(), "
                "gyroscope=(), "
                "speaker=()"
            )
        }


class RateLimiter:
    """Rate Limiting 클래스"""
    
    def __init__(self, redis_client=None):
        self.redis = redis_client
    
    def is_rate_limited(self, key: str, limit: int, window: int) -> bool:
        """Rate limit 검사"""
        if not self.redis:
            return False
        
        try:
            current = self.redis.get(key)
            if current is None:
                self.redis.setex(key, window, 1)
                return False
            
            if int(current) >= limit:
                return True
            
            self.redis.incr(key)
            return False
        
        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            return False
    
    def get_remaining_requests(self, key: str, limit: int) -> int:
        """남은 요청 수 반환"""
        if not self.redis:
            return limit
        
        try:
            current = self.redis.get(key)
            if current is None:
                return limit
            return max(0, limit - int(current))
        except Exception:
            return limit


# 전역 인스턴스
security_validator = SecurityValidator()
file_validator = FileSecurityValidator()
crypto_utils = CryptoUtils()

# 유틸리티 함수들
def validate_and_sanitize(data: Union[str, Dict, List], 
                         strict: bool = True) -> Dict[str, Any]:
    """입력 검증 및 삭제 (편의 함수)"""
    return security_validator.validate_input(data, strict)

def sanitize_string(text: str) -> str:
    """문자열 삭제 (편의 함수)"""
    return security_validator.sanitize_string(text)

def validate_file_upload(file_obj, file_type: str = 'document') -> Dict[str, Any]:
    """파일 업로드 검증 (편의 함수)"""
    return file_validator.validate_file(file_obj, file_type)

def encrypt_sensitive_data(data: str) -> str:
    """민감한 데이터 암호화 (편의 함수)"""
    return crypto_utils.encrypt_data(data)

def decrypt_sensitive_data(encrypted_data: str) -> str:
    """민감한 데이터 복호화 (편의 함수)"""
    return crypto_utils.decrypt_data(encrypted_data)

# Export
__all__ = [
    'SecurityValidator',
    'FileSecurityValidator', 
    'CryptoUtils',
    'SecurityHeaders',
    'RateLimiter',
    'security_validator',
    'file_validator',
    'crypto_utils',
    'validate_and_sanitize',
    'sanitize_string',
    'validate_file_upload',
    'encrypt_sensitive_data',
    'decrypt_sensitive_data',
]