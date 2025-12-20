"""
SOA1 Error Handling Module

Standardized error classes for consistent error handling across the SOA1 system.
"""

from fastapi import HTTPException
from typing import Optional, Dict, Any


class SOA1Error(HTTPException):
    """Base error class for SOA1 system"""
    
    def __init__(self, status_code: int, error_code: str, message: str, details: Optional[Dict] = None):
        self.error_code = error_code
        self.details = details or {}
        
        super().__init__(
            status_code=status_code,
            detail={
                "error": error_code,
                "message": message,
                "details": details
            }
        )


class ValidationError(SOA1Error):
    """Input validation errors"""
    
    def __init__(self, message: str, field: str, value: Any):
        super().__init__(
            400, 
            "VALIDATION_ERROR",
            message,
            {"field": field, "value": str(value)}
        )


class AuthenticationError(SOA1Error):
    """Authentication failures"""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(401, "AUTH_ERROR", message)


class RateLimitError(SOA1Error):
    """Rate limit exceeded"""
    
    def __init__(self, retry_after: int):
        super().__init__(
            429, 
            "RATE_LIMIT_EXCEEDED",
            f"Rate limit exceeded. Try again in {retry_after} seconds",
            {"retry_after": retry_after}
        )


class ServiceError(SOA1Error):
    """External service failures"""
    
    def __init__(self, service: str, message: str):
        super().__init__(
            503, 
            "SERVICE_UNAVAILABLE",
            f"{service} service unavailable",
            {"service": service, "error": message}
        )


class InternalError(SOA1Error):
    """Internal server errors"""
    
    def __init__(self, message: str = "Internal server error"):
        super().__init__(500, "INTERNAL_ERROR", message)


class NotFoundError(SOA1Error):
    """Resource not found errors"""
    
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            404,
            "RESOURCE_NOT_FOUND",
            f"{resource} not found",
            {"resource": resource, "identifier": identifier}
        )


class ConflictError(SOA1Error):
    """Conflict errors (e.g., duplicate resources)"""
    
    def __init__(self, resource: str, message: str):
        super().__init__(
            409,
            "CONFLICT",
            message,
            {"resource": resource}
        )


class PermissionError(SOA1Error):
    """Permission denied errors"""
    
    def __init__(self, resource: str, action: str):
        super().__init__(
            403,
            "PERMISSION_DENIED",
            f"Permission denied for {action} on {resource}",
            {"resource": resource, "action": action}
        )