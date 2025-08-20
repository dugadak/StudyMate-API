"""
Security utilities for authentication, authorization, and encryption.

Handles JWT tokens, password hashing, and sensitive data encryption.
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union

import structlog
from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import settings

logger = structlog.get_logger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Encryption context for sensitive data
_cipher_suite = Fernet(settings.ENCRYPTION_KEY.encode()[:32].ljust(32, b'0'))


class SecurityManager:
    """Security utilities for the application."""
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            plain_password: Plain text password
            hashed_password: Hashed password
        
        Returns:
            bool: True if password matches
        """
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception as e:
            logger.error("Password verification failed", error=str(e))
            return False
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """
        Hash a password.
        
        Args:
            password: Plain text password
        
        Returns:
            str: Hashed password
        """
        return pwd_context.hash(password)
    
    @staticmethod
    def create_access_token(
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create a JWT access token.
        
        Args:
            data: Token payload data
            expires_delta: Token expiration time
        
        Returns:
            str: Encoded JWT token
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "access"
        })
        
        encoded_jwt = jwt.encode(
            to_encode, 
            settings.SECRET_KEY, 
            algorithm=settings.ALGORITHM
        )
        
        logger.debug("Access token created", user_id=data.get("sub"), expires_at=expire)
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create a JWT refresh token.
        
        Args:
            data: Token payload data
            expires_delta: Token expiration time
        
        Returns:
            str: Encoded JWT refresh token
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                days=settings.REFRESH_TOKEN_EXPIRE_DAYS
            )
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "refresh"
        })
        
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        logger.debug("Refresh token created", user_id=data.get("sub"), expires_at=expire)
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
        """
        Verify and decode a JWT token.
        
        Args:
            token: JWT token to verify
            token_type: Expected token type ("access" or "refresh")
        
        Returns:
            Optional[Dict[str, Any]]: Token payload if valid, None otherwise
        """
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            
            # Verify token type
            if payload.get("type") != token_type:
                logger.warning("Invalid token type", expected=token_type, actual=payload.get("type"))
                return None
            
            # Verify expiration
            exp = payload.get("exp")
            if exp and datetime.fromtimestamp(exp, timezone.utc) < datetime.now(timezone.utc):
                logger.warning("Token expired", user_id=payload.get("sub"))
                return None
            
            return payload
            
        except JWTError as e:
            logger.warning("JWT verification failed", error=str(e))
            return None
        except Exception as e:
            logger.error("Token verification error", error=str(e))
            return None
    
    @staticmethod
    def encrypt_data(data: str) -> str:
        """
        Encrypt sensitive data.
        
        Args:
            data: Data to encrypt
        
        Returns:
            str: Encrypted data (base64 encoded)
        """
        try:
            encrypted_data = _cipher_suite.encrypt(data.encode())
            return encrypted_data.decode()
        except Exception as e:
            logger.error("Data encryption failed", error=str(e))
            raise
    
    @staticmethod
    def decrypt_data(encrypted_data: str) -> str:
        """
        Decrypt sensitive data.
        
        Args:
            encrypted_data: Encrypted data (base64 encoded)
        
        Returns:
            str: Decrypted data
        """
        try:
            decrypted_data = _cipher_suite.decrypt(encrypted_data.encode())
            return decrypted_data.decode()
        except Exception as e:
            logger.error("Data decryption failed", error=str(e))
            raise
    
    @staticmethod
    def generate_secure_token() -> str:
        """
        Generate a cryptographically secure random token.
        
        Returns:
            str: Secure random token
        """
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def generate_state_token() -> str:
        """
        Generate a state token for OAuth flows.
        
        Returns:
            str: OAuth state token
        """
        return secrets.token_urlsafe(16)
    
    @staticmethod
    def constant_time_compare(a: str, b: str) -> bool:
        """
        Compare two strings in constant time to prevent timing attacks.
        
        Args:
            a: First string
            b: Second string
        
        Returns:
            bool: True if strings are equal
        """
        return secrets.compare_digest(a, b)


class TokenManager:
    """Manages token storage and validation."""
    
    def __init__(self):
        self.security = SecurityManager()
    
    def create_token_pair(self, user_id: str, additional_claims: Dict[str, Any] = None) -> Dict[str, str]:
        """
        Create access and refresh token pair.
        
        Args:
            user_id: User identifier
            additional_claims: Additional JWT claims
        
        Returns:
            Dict[str, str]: Access and refresh tokens
        """
        claims = {"sub": user_id}
        if additional_claims:
            claims.update(additional_claims)
        
        access_token = self.security.create_access_token(claims)
        refresh_token = self.security.create_refresh_token({"sub": user_id})
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
    
    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """
        Create new access token from refresh token.
        
        Args:
            refresh_token: Valid refresh token
        
        Returns:
            Optional[str]: New access token if refresh token is valid
        """
        payload = self.security.verify_token(refresh_token, "refresh")
        if not payload:
            return None
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        return self.security.create_access_token({"sub": user_id})


# Global instances
security = SecurityManager()
token_manager = TokenManager()