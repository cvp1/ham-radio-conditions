"""
Cache Manager for Ham Radio Conditions app.
Provides centralized cache management with versioning, expiration, and cleanup.
"""

import time
import threading
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from collections import OrderedDict
import hashlib
import json

logger = logging.getLogger(__name__)


class CacheEntry:
    """Represents a single cache entry with metadata."""
    
    def __init__(self, key: str, value: Any, max_age: int = 300):
        self.key = key
        self.value = value
        self.created_at = time.time()
        self.last_accessed = time.time()
        self.max_age = max_age
        self.access_count = 0
        self.size = self._calculate_size()
    
    def _calculate_size(self) -> int:
        """Calculate approximate size of the cache entry."""
        try:
            if isinstance(self.value, (dict, list)):
                return len(json.dumps(self.value))
            elif isinstance(self.value, str):
                return len(self.value)
            else:
                return len(str(self.value))
        except:
            return 100  # Default size
    
    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        return time.time() - self.created_at > self.max_age
    
    def access(self):
        """Mark the entry as accessed."""
        self.last_accessed = time.time()
        self.access_count += 1
    
    def get_age(self) -> float:
        """Get the age of the cache entry in seconds."""
        return time.time() - self.created_at
    
    def get_idle_time(self) -> float:
        """Get the idle time since last access in seconds."""
        return time.time() - self.last_accessed


class CacheManager:
    """Centralized cache manager with versioning and cleanup."""
    
    def __init__(self, max_size: int = 100, max_memory_mb: int = 50):
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.caches: Dict[str, Dict[str, CacheEntry]] = {}
        self.cache_configs: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.RLock()
        self.cleanup_thread = None
        self.running = False
        
        # Start cleanup thread
        self._start_cleanup_thread()
    
    def _start_cleanup_thread(self):
        """Start the background cleanup thread."""
        if self.cleanup_thread is None or not self.cleanup_thread.is_alive():
            self.running = True
            self.cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
            self.cleanup_thread.start()
            logger.info("Cache cleanup thread started")
    
    def _cleanup_worker(self):
        """Background worker for cache cleanup."""
        while self.running:
            try:
                time.sleep(300)  # Run cleanup every 5 minutes (production optimized)
                self.cleanup_expired()
                self.cleanup_oversized()
            except Exception as e:
                logger.error(f"Error in cache cleanup worker: {e}")
    
    def register_cache(self, cache_name: str, config: Dict[str, Any]):
        """Register a new cache with configuration."""
        with self.lock:
            if cache_name not in self.caches:
                self.caches[cache_name] = {}
                self.cache_configs[cache_name] = config
                logger.info(f"Registered cache: {cache_name} with config: {config}")
            else:
                logger.warning(f"Cache {cache_name} already exists, updating config")
                self.cache_configs[cache_name] = config
    
    def get(self, cache_name: str, key: str) -> Optional[Any]:
        """Get a value from cache."""
        with self.lock:
            if cache_name not in self.caches:
                logger.warning(f"Cache {cache_name} not found")
                return None
            
            cache = self.caches[cache_name]
            if key not in cache:
                return None
            
            entry = cache[key]
            
            # Check if expired
            if entry.is_expired():
                del cache[key]
                return None
            
            # Mark as accessed
            entry.access()
            return entry.value
    
    def set(self, cache_name: str, key: str, value: Any, max_age: Optional[int] = None) -> bool:
        """Set a value in cache."""
        with self.lock:
            if cache_name not in self.caches:
                logger.warning(f"Cache {cache_name} not found")
                return False
            
            cache = self.caches[cache_name]
            config = self.cache_configs[cache_name]
            
            # Use config max_age if not specified
            if max_age is None:
                max_age = config.get('max_age', 300)
            
            # Create cache entry
            entry = CacheEntry(key, value, max_age)
            
            # Check if we need to make space
            if len(cache) >= config.get('max_size', self.max_size):
                self._evict_entries(cache_name, 1)
            
            # Check memory limits
            if self._get_cache_memory_usage(cache_name) + entry.size > config.get('max_memory_bytes', self.max_memory_bytes):
                self._evict_entries(cache_name, 1)
            
            # Store the entry
            cache[key] = entry
            return True
    
    def delete(self, cache_name: str, key: str) -> bool:
        """Delete a value from cache."""
        with self.lock:
            if cache_name not in self.caches:
                return False
            
            cache = self.caches[cache_name]
            if key in cache:
                del cache[key]
                return True
            return False
    
    def clear(self, cache_name: Optional[str] = None):
        """Clear cache or all caches."""
        with self.lock:
            if cache_name:
                if cache_name in self.caches:
                    self.caches[cache_name].clear()
                    logger.info(f"Cleared cache: {cache_name}")
            else:
                for name in self.caches:
                    self.caches[name].clear()
                logger.info("Cleared all caches")
    
    def cleanup_expired(self):
        """Remove expired entries from all caches."""
        with self.lock:
            total_expired = 0
            for cache_name, cache in self.caches.items():
                expired_keys = [
                    key for key, entry in cache.items()
                    if entry.is_expired()
                ]
                for key in expired_keys:
                    del cache[key]
                    total_expired += 1
            
            if total_expired > 0:
                logger.info(f"Cleaned up {total_expired} expired cache entries")
    
    def cleanup_oversized(self):
        """Remove entries to maintain size and memory limits."""
        with self.lock:
            for cache_name, cache in self.caches.items():
                config = self.cache_configs[cache_name]
                max_size = config.get('max_size', self.max_size)
                max_memory = config.get('max_memory_bytes', self.max_memory_bytes)
                
                # Check size limit
                if len(cache) > max_size:
                    excess = len(cache) - max_size
                    self._evict_entries(cache_name, excess)
                
                # Check memory limit
                current_memory = self._get_cache_memory_usage(cache_name)
                if current_memory > max_memory:
                    # Calculate how much memory to free
                    memory_to_free = current_memory - max_memory
                    self._evict_entries_by_memory(cache_name, memory_to_free)
    
    def _evict_entries(self, cache_name: str, count: int):
        """Evict entries based on LRU policy."""
        cache = self.caches[cache_name]
        if len(cache) <= count:
            cache.clear()
            return
        
        # Sort by last accessed time (oldest first)
        entries = sorted(cache.items(), key=lambda x: x[1].last_accessed)
        
        # Remove oldest entries
        for i in range(count):
            if i < len(entries):
                key = entries[i][0]
                del cache[key]
    
    def _evict_entries_by_memory(self, cache_name: str, memory_to_free: int):
        """Evict entries to free specific amount of memory."""
        cache = self.caches[cache_name]
        freed_memory = 0
        
        # Sort by last accessed time (oldest first)
        entries = sorted(cache.items(), key=lambda x: x[1].last_accessed)
        
        for key, entry in entries:
            if freed_memory >= memory_to_free:
                break
            
            freed_memory += entry.size
            del cache[key]
    
    def _get_cache_memory_usage(self, cache_name: str) -> int:
        """Get current memory usage of a cache."""
        cache = self.caches[cache_name]
        return sum(entry.size for entry in cache.values())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self.lock:
            stats = {
                'total_caches': len(self.caches),
                'caches': {}
            }
            
            total_entries = 0
            total_memory = 0
            
            for cache_name, cache in self.caches.items():
                config = self.cache_configs[cache_name]
                memory_usage = self._get_cache_memory_usage(cache_name)
                
                cache_stats = {
                    'entries': len(cache),
                    'memory_bytes': memory_usage,
                    'memory_mb': round(memory_usage / (1024 * 1024), 2),
                    'max_size': config.get('max_size', self.max_size),
                    'max_memory_mb': round(config.get('max_memory_bytes', self.max_memory_bytes) / (1024 * 1024), 2),
                    'hit_rate': self._calculate_hit_rate(cache),
                    'oldest_entry_age': self._get_oldest_entry_age(cache),
                    'newest_entry_age': self._get_newest_entry_age(cache)
                }
                
                stats['caches'][cache_name] = cache_stats
                total_entries += len(cache)
                total_memory += memory_usage
            
            stats['total_entries'] = total_entries
            stats['total_memory_mb'] = round(total_memory / (1024 * 1024), 2)
            
            return stats
    
    def _calculate_hit_rate(self, cache: Dict[str, CacheEntry]) -> float:
        """Calculate hit rate for a cache."""
        if not cache:
            return 0.0
        
        total_accesses = sum(entry.access_count for entry in cache.values())
        return round(total_accesses / len(cache), 2) if cache else 0.0
    
    def _get_oldest_entry_age(self, cache: Dict[str, CacheEntry]) -> float:
        """Get age of oldest entry in seconds."""
        if not cache:
            return 0.0
        
        oldest_age = max(entry.get_age() for entry in cache.values())
        return round(oldest_age, 2)
    
    def _get_newest_entry_age(self, cache: Dict[str, CacheEntry]) -> float:
        """Get age of newest entry in seconds."""
        if not cache:
            return 0.0
        
        newest_age = min(entry.get_age() for entry in cache.values())
        return round(newest_age, 2)
    
    def shutdown(self):
        """Shutdown the cache manager."""
        self.running = False
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=5)
        logger.info("Cache manager shutdown complete")


# Global cache manager instance
_cache_manager = None


def get_cache_manager() -> CacheManager:
    """Get the global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
        
        # Register default caches
        _cache_manager.register_cache('default', {
            'max_size': 20,
            'max_age': 300,  # 5 minutes
            'max_memory_bytes': 5 * 1024 * 1024  # 5MB
        })
        
        _cache_manager.register_cache('conditions', {
            'max_size': 10,
            'max_age': 300,  # 5 minutes
            'max_memory_bytes': 10 * 1024 * 1024  # 10MB
        })
        
        _cache_manager.register_cache('spots', {
            'max_size': 50,
            'max_age': 120,  # 2 minutes
            'max_memory_bytes': 5 * 1024 * 1024  # 5MB
        })
        
        _cache_manager.register_cache('weather', {
            'max_size': 20,
            'max_age': 600,  # 10 minutes
            'max_memory_bytes': 1 * 1024 * 1024  # 1MB
        })
    
    return _cache_manager


def cache_get(cache_name: str, key: str) -> Optional[Any]:
    """Get a value from cache."""
    return get_cache_manager().get(cache_name, key)


def cache_set(cache_name: str, key: str, value: Any, max_age: Optional[int] = None) -> bool:
    """Set a value in cache."""
    return get_cache_manager().set(cache_name, key, value, max_age)


def cache_delete(cache_name: str, key: str) -> bool:
    """Delete a value from cache."""
    return get_cache_manager().delete(cache_name, key)


def cache_clear(cache_name: Optional[str] = None):
    """Clear cache or all caches."""
    get_cache_manager().clear(cache_name)


def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics."""
    return get_cache_manager().get_stats()


def shutdown_cache_manager():
    """Shutdown the cache manager."""
    global _cache_manager
    if _cache_manager:
        _cache_manager.shutdown()
        _cache_manager = None 