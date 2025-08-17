"""
StudyMate API 사용자 정의 검증자

Django 및 DRF에서 사용할 수 있는 다양한 검증자들을 제공합니다.
"""

import re
import json
from typing import Any, Dict, List, Optional, Union
from django.core.exceptions import ValidationError
from django.core.validators import BaseValidator, RegexValidator
from django.utils.deconstruct import deconstructible
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from .security import security_validator, validate_and_sanitize


@deconstructible
class ContentSecurityValidator(BaseValidator):
    """콘텐츠 보안 검증자"""
    
    message = _('입력된 내용에 보안 위험이 있습니다.')
    code = 'security_risk'
    
    def __init__(self, strict: bool = True):
        self.strict = strict
    
    def __call__(self, value: Any) -> None:
        """검증 실행"""
        if not isinstance(value, (str, dict, list)):
            return
        
        validation_result = validate_and_sanitize(value, self.strict)
        
        if not validation_result['is_safe']:
            raise ValidationError(
                self.message,
                code=self.code,
                params={
                    'value': value,
                    'issues': validation_result['issues']
                }
            )


@deconstructible
class PasswordStrengthValidator:
    """비밀번호 강도 검증자"""
    
    def __init__(self, min_length: int = 8, require_uppercase: bool = True,
                 require_lowercase: bool = True, require_numbers: bool = True,
                 require_symbols: bool = True):
        self.min_length = min_length
        self.require_uppercase = require_uppercase
        self.require_lowercase = require_lowercase
        self.require_numbers = require_numbers
        self.require_symbols = require_symbols
    
    def __call__(self, password: str) -> None:
        """비밀번호 검증"""
        validation_result = security_validator.validate_password(password)
        
        if not validation_result['is_valid']:
            raise ValidationError(
                validation_result['issues'],
                code='password_too_weak'
            )
    
    def get_help_text(self) -> str:
        """도움말 텍스트 반환"""
        requirements = []
        
        if self.min_length > 0:
            requirements.append(f"최소 {self.min_length}자")
        if self.require_uppercase:
            requirements.append("대문자 포함")
        if self.require_lowercase:
            requirements.append("소문자 포함")
        if self.require_numbers:
            requirements.append("숫자 포함")
        if self.require_symbols:
            requirements.append("특수문자 포함")
        
        return f"비밀번호는 {', '.join(requirements)}이어야 합니다."


@deconstructible
class EmailDomainValidator:
    """이메일 도메인 검증자"""
    
    def __init__(self, allowed_domains: Optional[List[str]] = None,
                 blocked_domains: Optional[List[str]] = None):
        self.allowed_domains = allowed_domains or []
        self.blocked_domains = blocked_domains or [
            'tempmail.org', '10minutemail.com', 'guerrillamail.com',
            'mailinator.com', 'yopmail.com', 'spam4.me'
        ]
    
    def __call__(self, email: str) -> None:
        """이메일 도메인 검증"""
        if not email or '@' not in email:
            raise ValidationError(
                '유효한 이메일 주소를 입력해주세요.',
                code='invalid_email'
            )
        
        domain = email.split('@')[1].lower()
        
        # 차단된 도메인 검사
        if domain in self.blocked_domains:
            raise ValidationError(
                '임시 이메일 주소는 사용할 수 없습니다.',
                code='blocked_domain'
            )
        
        # 허용된 도메인 검사 (설정된 경우)
        if self.allowed_domains and domain not in self.allowed_domains:
            raise ValidationError(
                f'허용된 도메인: {", ".join(self.allowed_domains)}',
                code='domain_not_allowed'
            )


@deconstructible
class PhoneNumberValidator:
    """전화번호 검증자"""
    
    def __init__(self, country_code: str = 'KR'):
        self.country_code = country_code
        self.patterns = {
            'KR': r'^(\+82|82|0)?([1-9]\d{8,9})$',
            'US': r'^(\+1|1)?([2-9]\d{9})$',
            'JP': r'^(\+81|81|0)?([1-9]\d{8,10})$',
        }
    
    def __call__(self, phone: str) -> None:
        """전화번호 검증"""
        if not phone:
            return
        
        # 공백과 하이픈 제거
        cleaned_phone = re.sub(r'[\s\-\(\)]', '', phone)
        
        pattern = self.patterns.get(self.country_code)
        if not pattern:
            raise ValidationError(
                f'지원되지 않는 국가 코드: {self.country_code}',
                code='unsupported_country'
            )
        
        if not re.match(pattern, cleaned_phone):
            raise ValidationError(
                '유효한 전화번호를 입력해주세요.',
                code='invalid_phone'
            )


@deconstructible
class JSONValidator:
    """JSON 형식 검증자"""
    
    def __init__(self, schema: Optional[Dict] = None):
        self.schema = schema
    
    def __call__(self, value: str) -> None:
        """JSON 검증"""
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            raise ValidationError(
                '유효한 JSON 형식이 아닙니다.',
                code='invalid_json'
            )
        
        # 스키마 검증 (간단한 버전)
        if self.schema:
            self._validate_schema(parsed, self.schema)
    
    def _validate_schema(self, data: Any, schema: Dict) -> None:
        """간단한 스키마 검증"""
        if 'type' in schema:
            expected_type = schema['type']
            type_mapping = {
                'object': dict,
                'array': list,
                'string': str,
                'number': (int, float),
                'boolean': bool,
                'null': type(None)
            }
            
            expected_python_type = type_mapping.get(expected_type)
            if expected_python_type and not isinstance(data, expected_python_type):
                raise ValidationError(
                    f'Expected {expected_type}, got {type(data).__name__}',
                    code='schema_validation_error'
                )


@deconstructible
class FileExtensionValidator:
    """파일 확장자 검증자"""
    
    def __init__(self, allowed_extensions: List[str]):
        self.allowed_extensions = [ext.lower() for ext in allowed_extensions]
    
    def __call__(self, file) -> None:
        """파일 확장자 검증"""
        if not hasattr(file, 'name') or not file.name:
            raise ValidationError(
                '파일명이 필요합니다.',
                code='missing_filename'
            )
        
        extension = file.name.lower().split('.')[-1]
        
        if extension not in self.allowed_extensions:
            raise ValidationError(
                f'허용된 파일 확장자: {", ".join(self.allowed_extensions)}',
                code='invalid_extension'
            )


@deconstructible
class FileSizeValidator:
    """파일 크기 검증자"""
    
    def __init__(self, max_size: int):
        self.max_size = max_size
    
    def __call__(self, file) -> None:
        """파일 크기 검증"""
        if hasattr(file, 'size') and file.size > self.max_size:
            size_mb = self.max_size / (1024 * 1024)
            raise ValidationError(
                f'파일 크기는 {size_mb:.1f}MB를 초과할 수 없습니다.',
                code='file_too_large'
            )


@deconstructible
class URLValidator:
    """URL 검증자"""
    
    def __init__(self, allowed_schemes: Optional[List[str]] = None):
        self.allowed_schemes = allowed_schemes or ['http', 'https']
        self.pattern = re.compile(
            r'^(?:(?P<scheme>[a-zA-Z][a-zA-Z0-9+.-]*):\/\/)?'
            r'(?P<host>(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?)'
            r'(?P<port>:\d+)?'
            r'(?P<path>\/[^\s]*)?$',
            re.IGNORECASE
        )
    
    def __call__(self, url: str) -> None:
        """URL 검증"""
        if not url:
            return
        
        match = self.pattern.match(url)
        if not match:
            raise ValidationError(
                '유효한 URL을 입력해주세요.',
                code='invalid_url'
            )
        
        scheme = match.group('scheme')
        if scheme and scheme.lower() not in self.allowed_schemes:
            raise ValidationError(
                f'허용된 스킴: {", ".join(self.allowed_schemes)}',
                code='invalid_scheme'
            )


# DRF Serializer 필드 검증자들
class SecurityValidatedCharField(serializers.CharField):
    """보안 검증된 CharField"""
    
    def __init__(self, strict: bool = True, **kwargs):
        self.strict = strict
        super().__init__(**kwargs)
    
    def validate(self, value):
        """보안 검증"""
        value = super().validate(value)
        
        if value:
            validation_result = validate_and_sanitize(value, self.strict)
            if not validation_result['is_safe']:
                raise serializers.ValidationError(
                    f"보안 위험 감지: {', '.join(validation_result['issues'])}"
                )
        
        return value


class SecureEmailField(serializers.EmailField):
    """보안 강화 이메일 필드"""
    
    def __init__(self, allowed_domains=None, blocked_domains=None, **kwargs):
        self.domain_validator = EmailDomainValidator(
            allowed_domains=allowed_domains,
            blocked_domains=blocked_domains
        )
        super().__init__(**kwargs)
    
    def validate(self, value):
        """이메일 도메인 검증"""
        value = super().validate(value)
        
        if value:
            try:
                self.domain_validator(value)
            except ValidationError as e:
                raise serializers.ValidationError(str(e))
        
        return value


class PasswordField(serializers.CharField):
    """비밀번호 필드"""
    
    def __init__(self, **kwargs):
        kwargs.setdefault('write_only', True)
        kwargs.setdefault('style', {'input_type': 'password'})
        self.password_validator = PasswordStrengthValidator()
        super().__init__(**kwargs)
    
    def validate(self, value):
        """비밀번호 강도 검증"""
        value = super().validate(value)
        
        if value:
            try:
                self.password_validator(value)
            except ValidationError as e:
                raise serializers.ValidationError(e.messages)
        
        return value


class SecureFileField(serializers.FileField):
    """보안 파일 필드"""
    
    def __init__(self, allowed_extensions=None, max_size=None, file_type='document', **kwargs):
        self.allowed_extensions = allowed_extensions
        self.max_size = max_size
        self.file_type = file_type
        super().__init__(**kwargs)
    
    def validate(self, value):
        """파일 보안 검증"""
        value = super().validate(value)
        
        if value:
            from .security import validate_file_upload
            validation_result = validate_file_upload(value, self.file_type)
            
            if not validation_result['is_safe']:
                raise serializers.ValidationError(
                    f"파일 보안 검증 실패: {', '.join(validation_result['issues'])}"
                )
        
        return value


# 정규식 검증자들
korean_name_validator = RegexValidator(
    regex=r'^[가-힣]{2,10}$',
    message='한글 이름 2-10자를 입력해주세요.',
    code='invalid_korean_name'
)

username_validator = RegexValidator(
    regex=r'^[a-zA-Z0-9_]{3,20}$',
    message='영문, 숫자, 언더스코어만 사용하여 3-20자로 입력해주세요.',
    code='invalid_username'
)

slug_validator = RegexValidator(
    regex=r'^[-a-zA-Z0-9_]+$',
    message='영문, 숫자, 하이픈, 언더스코어만 사용할 수 있습니다.',
    code='invalid_slug'
)

# Export
__all__ = [
    'ContentSecurityValidator',
    'PasswordStrengthValidator', 
    'EmailDomainValidator',
    'PhoneNumberValidator',
    'JSONValidator',
    'FileExtensionValidator',
    'FileSizeValidator',
    'URLValidator',
    'SecurityValidatedCharField',
    'SecureEmailField',
    'PasswordField',
    'SecureFileField',
    'korean_name_validator',
    'username_validator',
    'slug_validator',
]