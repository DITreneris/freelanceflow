"""
FastAPI Middleware

This package contains middleware components for the FreelanceFlow application.
"""

from app.middleware.compression import add_compression_middleware, GzipMiddleware

__all__ = ["add_compression_middleware", "GzipMiddleware"] 