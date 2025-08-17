"""
Custom exception classes and error handling for StudyMate API

This module provides:
- Custom exception classes for different error types
- Standardized error response formatting
- Exception logging and monitoring
- Error tracking and analytics
"""

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError
from django.http import Http404
from django.utils import timezone
from typing import Dict, Any, Optional, List
import logging
import traceback
import uuid

logger = logging.getLogger(__name__)


class StudyMateBaseException(Exception):
    """Base exception class for StudyMate API"""
    
    default_message = "An error occurred"
    default_code = "STUDYMATE_ERROR"
    default_status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    
    def __init__(self, message: str = None, code: str = None, details: Dict[str, Any] = None):
        self.message = message or self.default_message
        self.code = code or self.default_code
        self.details = details or {}
        self.error_id = str(uuid.uuid4())
        self.timestamp = timezone.now()
        
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API response"""
        return {
            'error': True,
            'error_id': self.error_id,
            'code': self.code,
            'message': self.message,
            'details': self.details,
            'timestamp': self.timestamp.isoformat()
        }


class ValidationException(StudyMateBaseException):
    """Exception for validation errors"""
    
    default_message = "Validation failed"
    default_code = "VALIDATION_ERROR"
    default_status_code = status.HTTP_400_BAD_REQUEST
    
    def __init__(self, field_errors: Dict[str, List[str]] = None, **kwargs):
        super().__init__(**kwargs)
        self.field_errors = field_errors or {}
        if self.field_errors:
            self.details['field_errors'] = self.field_errors


class AuthenticationException(StudyMateBaseException):
    """Exception for authentication errors"""
    
    default_message = "Authentication failed"
    default_code = "AUTHENTICATION_ERROR"
    default_status_code = status.HTTP_401_UNAUTHORIZED


class PermissionException(StudyMateBaseException):
    """Exception for permission errors"""
    
    default_message = "Permission denied"
    default_code = "PERMISSION_ERROR"
    default_status_code = status.HTTP_403_FORBIDDEN


class ResourceNotFoundException(StudyMateBaseException):
    """Exception for resource not found errors"""
    
    default_message = "Resource not found"
    default_code = "RESOURCE_NOT_FOUND"
    default_status_code = status.HTTP_404_NOT_FOUND
    
    def __init__(self, resource_type: str = None, resource_id: str = None, **kwargs):
        super().__init__(**kwargs)
        if resource_type:
            self.details['resource_type'] = resource_type
        if resource_id:
            self.details['resource_id'] = resource_id


class BusinessLogicException(StudyMateBaseException):
    """Exception for business logic errors"""
    
    default_message = "Business logic error"
    default_code = "BUSINESS_LOGIC_ERROR"
    default_status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class ExternalServiceException(StudyMateBaseException):
    """Exception for external service errors (OpenAI, Stripe, etc.)"""
    
    default_message = "External service error"
    default_code = "EXTERNAL_SERVICE_ERROR"
    default_status_code = status.HTTP_502_BAD_GATEWAY
    
    def __init__(self, service_name: str = None, service_error: str = None, **kwargs):
        super().__init__(**kwargs)
        if service_name:
            self.details['service_name'] = service_name
        if service_error:
            self.details['service_error'] = service_error


class RateLimitException(StudyMateBaseException):
    """Exception for rate limiting errors"""
    
    default_message = "Rate limit exceeded"
    default_code = "RATE_LIMIT_EXCEEDED"
    default_status_code = status.HTTP_429_TOO_MANY_REQUESTS
    
    def __init__(self, retry_after: int = None, **kwargs):
        super().__init__(**kwargs)
        if retry_after:
            self.details['retry_after'] = retry_after


class SubscriptionException(StudyMateBaseException):
    """Exception for subscription-related errors"""
    
    default_message = "Subscription error"
    default_code = "SUBSCRIPTION_ERROR"
    default_status_code = status.HTTP_402_PAYMENT_REQUIRED
    
    def __init__(self, subscription_status: str = None, required_plan: str = None, **kwargs):
        super().__init__(**kwargs)
        if subscription_status:
            self.details['subscription_status'] = subscription_status
        if required_plan:
            self.details['required_plan'] = required_plan


class AIServiceException(ExternalServiceException):
    """Exception for AI service specific errors"""
    
    default_message = "AI service error"
    default_code = "AI_SERVICE_ERROR"
    
    def __init__(self, model_name: str = None, prompt_tokens: int = None, **kwargs):
        super().__init__(service_name="AI_SERVICE", **kwargs)
        if model_name:
            self.details['model_name'] = model_name
        if prompt_tokens:
            self.details['prompt_tokens'] = prompt_tokens


class QuizGenerationException(AIServiceException):
    """Exception for quiz generation errors"""
    
    default_message = "Quiz generation failed"
    default_code = "QUIZ_GENERATION_ERROR"


class SummaryGenerationException(AIServiceException):
    """Exception for summary generation errors"""
    
    default_message = "Summary generation failed"
    default_code = "SUMMARY_GENERATION_ERROR"


def custom_exception_handler(exc, context):
    """
    Custom exception handler that provides detailed error responses
    
    Features:
    - Standardized error response format
    - Error logging with context
    - Error tracking and monitoring
    - Sensitive information filtering
    """
    
    # Get the default response first
    response = exception_handler(exc, context)
    
    # Get request context
    request = context.get('request')
    view = context.get('view')
    
    # Generate error ID for tracking
    error_id = str(uuid.uuid4())
    timestamp = timezone.now()
    
    # Handle custom StudyMate exceptions
    if isinstance(exc, StudyMateBaseException):
        custom_response_data = exc.to_dict()
        
        # Log the error with context
        logger.error(
            f"StudyMate Exception [{exc.code}] {error_id}: {exc.message}",
            extra={
                'error_id': error_id,
                'error_code': exc.code,
                'error_message': exc.message,
                'error_details': exc.details,
                'user_id': getattr(request.user, 'id', None) if request and hasattr(request, 'user') else None,
                'request_path': request.path if request else None,
                'request_method': request.method if request else None,
                'view_name': view.__class__.__name__ if view else None,
                'timestamp': timestamp.isoformat(),
                'traceback': traceback.format_exc()
            }
        )
        
        return Response(
            custom_response_data,
            status=exc.default_status_code
        )
    
    # Handle standard DRF/Django exceptions
    if response is not None:
        # Standard error response format
        custom_response_data = {
            'error': True,
            'error_id': error_id,
            'code': get_error_code_from_exception(exc),
            'message': get_error_message_from_exception(exc),
            'details': get_error_details_from_response(response.data),
            'timestamp': timestamp.isoformat()
        }
        
        # Log the error
        logger.error(
            f"API Exception [{custom_response_data['code']}] {error_id}: {custom_response_data['message']}",
            extra={
                'error_id': error_id,
                'error_code': custom_response_data['code'],
                'error_message': custom_response_data['message'],
                'user_id': getattr(request.user, 'id', None) if request and hasattr(request, 'user') else None,
                'request_path': request.path if request else None,
                'request_method': request.method if request else None,
                'view_name': view.__class__.__name__ if view else None,
                'response_status': response.status_code,
                'timestamp': timestamp.isoformat(),
                'traceback': traceback.format_exc()
            }
        )
        
        response.data = custom_response_data
        return response
    
    # Handle unhandled exceptions
    logger.critical(
        f"Unhandled Exception {error_id}: {str(exc)}",
        extra={
            'error_id': error_id,
            'exception_type': exc.__class__.__name__,
            'exception_message': str(exc),
            'user_id': getattr(request.user, 'id', None) if request and hasattr(request, 'user') else None,
            'request_path': request.path if request else None,
            'request_method': request.method if request else None,
            'view_name': view.__class__.__name__ if view else None,
            'timestamp': timestamp.isoformat(),
            'traceback': traceback.format_exc()
        }
    )
    
    # Return generic error for unhandled exceptions
    return Response(
        {
            'error': True,
            'error_id': error_id,
            'code': 'INTERNAL_SERVER_ERROR',
            'message': 'An unexpected error occurred. Please try again later.',
            'details': {},
            'timestamp': timestamp.isoformat()
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )


def get_error_code_from_exception(exc) -> str:
    """Get error code from exception type"""
    if isinstance(exc, ValidationError):
        return 'VALIDATION_ERROR'
    elif isinstance(exc, Http404):
        return 'RESOURCE_NOT_FOUND'
    elif hasattr(exc, 'default_code'):
        return exc.default_code
    else:
        return exc.__class__.__name__.upper()


def get_error_message_from_exception(exc) -> str:
    """Get user-friendly error message from exception"""
    if isinstance(exc, ValidationError):
        return 'Validation failed'
    elif isinstance(exc, Http404):
        return 'Resource not found'
    elif hasattr(exc, 'detail'):
        # DRF exceptions
        detail = exc.detail
        if isinstance(detail, dict):
            # Get first error message
            for key, value in detail.items():
                if isinstance(value, list) and value:
                    return f"{key}: {value[0]}"
                return f"{key}: {value}"
        elif isinstance(detail, list) and detail:
            return str(detail[0])
        else:
            return str(detail)
    else:
        return str(exc)


def get_error_details_from_response(response_data) -> Dict[str, Any]:
    """Extract error details from DRF response data"""
    if isinstance(response_data, dict):
        return response_data
    elif isinstance(response_data, list):
        return {'errors': response_data}
    else:
        return {'message': str(response_data)}


class ErrorTracker:
    """Error tracking and analytics"""
    
    @staticmethod
    def track_error(exception: Exception, context: Dict[str, Any] = None):
        """Track error for analytics and monitoring"""
        error_data = {
            'exception_type': exception.__class__.__name__,
            'message': str(exception),
            'context': context or {},
            'timestamp': timezone.now().isoformat(),
            'traceback': traceback.format_exc()
        }
        
        # Log for external monitoring systems
        logger.info(
            f"Error tracked: {exception.__class__.__name__}",
            extra={'error_tracking': error_data}
        )
        
        # Here you could integrate with external error tracking services
        # like Sentry, Rollbar, or custom analytics
    
    @staticmethod
    def get_error_statistics(days: int = 30) -> Dict[str, Any]:
        """Get error statistics for monitoring dashboard"""
        # This would typically query a database or external service
        # For now, return a placeholder
        return {
            'total_errors': 0,
            'error_types': {},
            'error_trends': [],
            'most_common_errors': [],
            'error_rate': 0.0
        }


# Export main classes and functions
__all__ = [
    'StudyMateBaseException',
    'ValidationException',
    'AuthenticationException', 
    'PermissionException',
    'ResourceNotFoundException',
    'BusinessLogicException',
    'ExternalServiceException',
    'RateLimitException',
    'SubscriptionException',
    'AIServiceException',
    'QuizGenerationException',
    'SummaryGenerationException',
    'custom_exception_handler',
    'ErrorTracker'
]