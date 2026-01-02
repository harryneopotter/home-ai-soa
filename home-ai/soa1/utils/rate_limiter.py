"""
SOA1 Rate Limiting Module

Token bucket rate limiting implementation for API endpoints.
"""

from datetime import datetime, timedelta
from typing import Dict, Optional
import time


class RateLimiter:
    """Simple token bucket rate limiter"""

    def __init__(self, rate: int, period: int):
        """
        Args:
            rate: Number of requests allowed
            period: Time period in seconds
        """
        self.rate = rate
        self.period = period
        self.tokens: Dict[str, list] = {}  # client_ip -> [timestamps]

    def check(self, client_ip: str) -> bool:
        """Check if request should be allowed"""
        now = time.time()

        # Initialize if first request
        if client_ip not in self.tokens:
            self.tokens[client_ip] = [now]
            return True

        # Remove old tokens
        cutoff = now - self.period
        self.tokens[client_ip] = [t for t in self.tokens[client_ip] if t > cutoff]

        # Check if under limit
        if len(self.tokens[client_ip]) < self.rate:
            self.tokens[client_ip].append(now)
            return True

        return False

    def get_retry_after(self, client_ip: str) -> int:
        """Get seconds until next request allowed"""
        if client_ip not in self.tokens or not self.tokens[client_ip]:
            return 0

        oldest = min(self.tokens[client_ip])
        return max(0, int(oldest + self.period - time.time()))

    def reset(self, client_ip: str):
        """Reset rate limit for client"""
        if client_ip in self.tokens:
            del self.tokens[client_ip]


# Global rate limiters with sensible defaults
api_limiter = RateLimiter(rate=100, period=60)  # 100 requests/minute
tts_limiter = RateLimiter(rate=20, period=60)  # 20 TTS requests/minute
pdf_limiter = RateLimiter(rate=10, period=60)  # 10 PDF operations/minute


def get_limiter_for_endpoint(endpoint: str) -> RateLimiter:
    """Get appropriate limiter for endpoint"""
    if endpoint.startswith("/ask-with-tts"):
        return tts_limiter
    elif endpoint.startswith("/upload-batch") or endpoint.startswith("/upload-pdf"):
        return pdf_limiter
    else:
        return api_limiter
