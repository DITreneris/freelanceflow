"""
Cache utility for FreelanceFlow

This module provides caching mechanisms to improve API performance
by storing frequently accessed data in memory.
"""

import functools
import hashlib
import json
import time
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar, Union, cast

from fastapi import Request, Response
from starlette.concurrency import run_in_threadpool

# Type variables for function signature preservation
T = TypeVar('T')
RT = TypeVar('RT')


class CacheStrategy(str, Enum):
    """Cache strategies for different types of data."""
    SHORT = "short"      # 30 seconds
    MEDIUM = "medium"    # 5 minutes
    LONG = "long"        # 1 hour
    DASHBOARD = "dashboard"  # 2 minutes
    USER = "user"        # 10 minutes
    ANALYTICS = "analytics"  # 15 minutes


# Cache configuration with TTL in seconds
CACHE_TTL = {
    CacheStrategy.SHORT: 30,
    CacheStrategy.MEDIUM: 300,
    CacheStrategy.LONG: 3600,
    CacheStrategy.DASHBOARD: 120,
    CacheStrategy.USER: 600,
    CacheStrategy.ANALYTICS: 900,
}

# In-memory cache store
_cache: Dict[str, Dict[str, Any]] = {}

# Track dependencies between cache keys
_dependencies: Dict[str, Set[str]] = {}


def _get_cache_ttl(strategy: CacheStrategy) -> int:
    """Get TTL value in seconds for the given strategy."""
    # Check if we should use an environment variable
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    env_ttl = os.environ.get('CACHE_TTL')
    
    # Production override
    if env_ttl and env_ttl.isdigit():
        base_ttl = int(env_ttl)
        # Scale the TTL based on the strategy
        if strategy == CacheStrategy.SHORT:
            return int(base_ttl * 0.1)  # 10% of base
        elif strategy == CacheStrategy.MEDIUM:
            return int(base_ttl)  # 100% of base
        elif strategy == CacheStrategy.LONG:
            return int(base_ttl * 12)  # 12x of base
        elif strategy == CacheStrategy.DASHBOARD:
            return int(base_ttl * 0.4)  # 40% of base
        elif strategy == CacheStrategy.USER:
            return int(base_ttl * 2)  # 2x of base
        elif strategy == CacheStrategy.ANALYTICS:
            return int(base_ttl * 3)  # 3x of base
    
    # Default TTL from predefined values
    return CACHE_TTL[strategy]


def _generate_cache_key(func: Callable, *args: Any, **kwargs: Any) -> str:
    """Generate a unique cache key based on function and arguments."""
    # Create a string representation of the function and its arguments
    func_name = f"{func.__module__}.{func.__qualname__}"
    
    # Handle special case for request objects (FastAPI)
    # We ignore the request object in cache key generation
    filtered_args = []
    filtered_kwargs = {}
    
    for arg in args:
        if not isinstance(arg, Request) and not isinstance(arg, Response):
            filtered_args.append(arg)
    
    for key, value in kwargs.items():
        if not isinstance(value, Request) and not isinstance(value, Response):
            filtered_kwargs[key] = value
    
    # Create a string representation and hash it
    args_str = str(filtered_args) if filtered_args else ""
    kwargs_str = str(sorted(filtered_kwargs.items())) if filtered_kwargs else ""
    
    key_str = f"{func_name}:{args_str}:{kwargs_str}"
    return hashlib.md5(key_str.encode()).hexdigest()


def cached(strategy: CacheStrategy, user_dependent: bool = False):
    """
    Cache decorator for API endpoints and expensive functions.
    
    Args:
        strategy: The caching strategy determining the TTL
        user_dependent: Whether the cached result depends on the current user
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            # Skip caching in development mode if requested
            if _is_development_mode() and not _should_cache_in_dev():
                return await func(*args, **kwargs)
            
            # Generate cache key
            base_key = _generate_cache_key(func, *args, **kwargs)
            
            # Add user ID to key if result is user-dependent
            user_id = None
            if user_dependent:
                for arg in args:
                    if hasattr(arg, 'current_user') and getattr(arg, 'current_user'):
                        user_id = getattr(arg, 'current_user').id
                        break
                
                for _, value in kwargs.items():
                    if hasattr(value, 'current_user') and getattr(value, 'current_user'):
                        user_id = getattr(value, 'current_user').id
                        break
            
            cache_key = f"{base_key}:user={user_id}" if user_id else base_key
            
            # Check if result is in cache and not expired
            if cache_key in _cache:
                cache_entry = _cache[cache_key]
                expiry = cache_entry.get('expiry', 0)
                
                if expiry > time.time():
                    return cast(T, cache_entry.get('data'))
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            ttl = _get_cache_ttl(strategy)
            
            _cache[cache_key] = {
                'data': result,
                'expiry': time.time() + ttl,
                'timestamp': datetime.now().isoformat()
            }
            
            # Record dependency on user for faster invalidation
            if user_id:
                if user_id not in _dependencies:
                    _dependencies[user_id] = set()
                _dependencies[user_id].add(cache_key)
            
            return result
            
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            # Skip caching in development mode if requested
            if _is_development_mode() and not _should_cache_in_dev():
                return func(*args, **kwargs)
            
            # Generate cache key
            base_key = _generate_cache_key(func, *args, **kwargs)
            
            # Add user ID to key if result is user-dependent
            user_id = None
            if user_dependent:
                for arg in args:
                    if hasattr(arg, 'current_user') and getattr(arg, 'current_user'):
                        user_id = getattr(arg, 'current_user').id
                        break
                
                for _, value in kwargs.items():
                    if hasattr(value, 'current_user') and getattr(value, 'current_user'):
                        user_id = getattr(value, 'current_user').id
                        break
            
            cache_key = f"{base_key}:user={user_id}" if user_id else base_key
            
            # Check if result is in cache and not expired
            if cache_key in _cache:
                cache_entry = _cache[cache_key]
                expiry = cache_entry.get('expiry', 0)
                
                if expiry > time.time():
                    return cast(T, cache_entry.get('data'))
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            ttl = _get_cache_ttl(strategy)
            
            _cache[cache_key] = {
                'data': result,
                'expiry': time.time() + ttl,
                'timestamp': datetime.now().isoformat()
            }
            
            # Record dependency on user for faster invalidation
            if user_id:
                if user_id not in _dependencies:
                    _dependencies[user_id] = set()
                _dependencies[user_id].add(cache_key)
            
            return result
        
        # Return the appropriate wrapper based on whether the function is async
        if asyncio_is_installed() and is_coroutine_function(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def _is_development_mode() -> bool:
    """Check if the application is running in development mode."""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    env = os.environ.get('ENVIRONMENT', '').lower()
    debug = os.environ.get('DEBUG', '').lower() == 'true'
    
    return env in ('dev', 'development') or debug


def _should_cache_in_dev() -> bool:
    """Check if caching should be enabled in development mode."""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    return os.environ.get('ENABLE_CACHE_IN_DEV', '').lower() == 'true'


def invalidate_user_cache(user_id: str) -> None:
    """
    Invalidate all cache entries associated with a specific user.
    
    Args:
        user_id: The ID of the user whose cache entries should be invalidated
    """
    if user_id in _dependencies:
        for cache_key in _dependencies[user_id]:
            if cache_key in _cache:
                del _cache[cache_key]
        del _dependencies[user_id]


def invalidate_cache_by_prefix(prefix: str) -> None:
    """
    Invalidate all cache entries with keys starting with the specified prefix.
    
    Args:
        prefix: The prefix to match against cache keys
    """
    keys_to_remove = []
    for key in _cache.keys():
        if key.startswith(prefix):
            keys_to_remove.append(key)
    
    for key in keys_to_remove:
        del _cache[key]
    
    # Also update dependencies
    for user_id, keys in _dependencies.items():
        _dependencies[user_id] = {k for k in keys if k not in keys_to_remove}


def clear_all_cache() -> None:
    """Clear the entire cache."""
    global _cache, _dependencies
    _cache = {}
    _dependencies = {}


def get_cache_stats() -> Dict[str, Any]:
    """Get statistics about the current cache state."""
    total_entries = len(_cache)
    expired_entries = sum(1 for entry in _cache.values() if entry.get('expiry', 0) < time.time())
    valid_entries = total_entries - expired_entries
    
    # Group by strategy (approximated from TTL)
    ttl_to_strategy = {ttl: name for name, ttl in CACHE_TTL.items()}
    strategy_counts = {}
    
    for entry in _cache.values():
        expiry = entry.get('expiry', 0)
        timestamp = entry.get('timestamp')
        if timestamp:
            try:
                entry_time = datetime.fromisoformat(timestamp)
                ttl = int(expiry - time.time() + (time.time() - entry_time.timestamp()))
                
                # Find the closest matching strategy
                closest_strategy = None
                min_diff = float('inf')
                
                for defined_ttl, strategy in ttl_to_strategy.items():
                    diff = abs(ttl - defined_ttl)
                    if diff < min_diff:
                        min_diff = diff
                        closest_strategy = strategy
                
                if closest_strategy:
                    strategy_counts[closest_strategy] = strategy_counts.get(closest_strategy, 0) + 1
            except (ValueError, TypeError):
                pass
    
    return {
        'total_entries': total_entries,
        'valid_entries': valid_entries,
        'expired_entries': expired_entries,
        'strategy_distribution': strategy_counts,
        'user_dependencies': {user_id: len(keys) for user_id, keys in _dependencies.items()},
        'memory_usage': _estimate_memory_usage()
    }


def _estimate_memory_usage() -> str:
    """Estimate the memory usage of the cache in a human-readable format."""
    import sys
    
    try:
        size_bytes = sys.getsizeof(_cache)
        for key, value in _cache.items():
            size_bytes += sys.getsizeof(key)
            size_bytes += sys.getsizeof(value)
            for k, v in value.items():
                size_bytes += sys.getsizeof(k)
                size_bytes += sys.getsizeof(v)
        
        # Convert to human-readable format
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024 or unit == 'GB':
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        
        return f"{size_bytes:.2f} GB"
    except Exception:
        return "Unknown"


def clean_expired_cache() -> int:
    """
    Remove expired entries from the cache.
    
    Returns:
        Number of entries removed
    """
    current_time = time.time()
    keys_to_remove = []
    
    for key, entry in _cache.items():
        expiry = entry.get('expiry', 0)
        if expiry < current_time:
            keys_to_remove.append(key)
    
    for key in keys_to_remove:
        del _cache[key]
    
    # Update dependencies
    for user_id, keys in list(_dependencies.items()):
        updated_keys = keys - set(keys_to_remove)
        if not updated_keys:
            del _dependencies[user_id]
        else:
            _dependencies[user_id] = updated_keys
    
    return len(keys_to_remove)


# Helper functions to check if we're dealing with async functions
def asyncio_is_installed() -> bool:
    """Check if asyncio is available."""
    try:
        import asyncio
        import inspect
        return True
    except ImportError:
        return False


def is_coroutine_function(func: Callable) -> bool:
    """Check if a function is a coroutine function."""
    if not asyncio_is_installed():
        return False
    
    import inspect
    return inspect.iscoroutinefunction(func) 