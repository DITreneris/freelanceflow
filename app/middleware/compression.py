"""
Response Compression Middleware

This module provides middleware for compressing HTTP responses
to reduce bandwidth usage and improve page load times.
"""

import gzip
from typing import Callable, List, Optional, Set

from fastapi import FastAPI, Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send


class GzipMiddleware(BaseHTTPMiddleware):
    """Middleware for compressing responses with gzip."""

    def __init__(
        self,
        app: ASGIApp,
        minimum_size: int = 500,
        compression_level: int = 6,
        exclude_paths: Optional[List[str]] = None,
        exclude_content_types: Optional[List[str]] = None
    ):
        """
        Initialize the compression middleware.
        
        Args:
            app: The ASGI application
            minimum_size: Minimum response size in bytes to apply compression
            compression_level: Gzip compression level (1-9)
            exclude_paths: List of paths to exclude from compression
            exclude_content_types: List of content types to exclude from compression
        """
        super().__init__(app)
        self.minimum_size = minimum_size
        self.compression_level = min(max(compression_level, 1), 9)  # Ensure it's between 1-9
        self.exclude_paths = set(exclude_paths or [])
        self.exclude_content_types = set(exclude_content_types or [])
        
        # Default content types to exclude (e.g. already compressed formats)
        self.exclude_content_types.update([
            "image/jpeg", "image/png", "image/gif", "image/webp",
            "audio/mpeg", "video/mp4", "application/zip", "application/gzip",
            "application/x-gzip", "application/pdf"
        ])

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and compress the response if applicable."""
        # Check if path should be excluded
        path = request.url.path
        if any(path.startswith(excluded) for excluded in self.exclude_paths):
            return await call_next(request)
        
        # Check if client accepts gzip encoding
        accept_encoding = request.headers.get("Accept-Encoding", "").lower()
        if "gzip" not in accept_encoding:
            return await call_next(request)
        
        # Get the original response
        response = await call_next(request)
        
        # Check if we should compress the response
        content_type = response.headers.get("Content-Type", "").lower()
        content_encoding = response.headers.get("Content-Encoding", "").lower()
        
        # Skip compression if any of these conditions apply
        if (
            # Already compressed
            content_encoding and content_encoding != "identity"
            # Excluded content type
            or any(excluded in content_type for excluded in self.exclude_content_types)
            # Response body is a streaming response
            or hasattr(response, "body_iterator")
        ):
            return response
        
        # Get response body
        response_body = b""
        if hasattr(response, "body"):
            response_body = response.body
        
        # Skip compression if response is too small
        if len(response_body) < self.minimum_size:
            return response
        
        # Compress the response
        compressed_body = gzip.compress(response_body, compresslevel=self.compression_level)
        
        # Create a new response with compressed body
        new_response = Response(
            content=compressed_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type
        )
        
        # Add Content-Encoding header
        new_response.headers["Content-Encoding"] = "gzip"
        new_response.headers["Content-Length"] = str(len(compressed_body))
        new_response.headers["Vary"] = "Accept-Encoding"
        
        return new_response


def add_compression_middleware(
    app: FastAPI,
    minimum_size: int = 500,
    compression_level: int = 6,
    exclude_paths: Optional[List[str]] = None,
    exclude_content_types: Optional[List[str]] = None
) -> None:
    """
    Add the compression middleware to the FastAPI application.
    
    Args:
        app: The FastAPI application
        minimum_size: Minimum response size in bytes to apply compression
        compression_level: Gzip compression level (1-9)
        exclude_paths: List of paths to exclude from compression
        exclude_content_types: List of content types to exclude from compression
    """
    app.add_middleware(
        GzipMiddleware,
        minimum_size=minimum_size,
        compression_level=compression_level,
        exclude_paths=exclude_paths,
        exclude_content_types=exclude_content_types
    ) 