"""
Background tasks for Ham Radio Conditions app.
Handles periodic tasks like cache updates and database cleanup.
"""

import threading
import time
import atexit
from typing import Optional, Callable
from utils.logging_config import get_logger
from config import get_config

logger = get_logger(__name__)


class BackgroundTaskManager:
    """Manages background tasks for the application."""
    
    def __init__(self):
        self.tasks = {}
        self.running = False
        self.threads = {}
        self._shutdown_registered = False
    
    def add_task(
        self,
        name: str,
        task_func: Callable,
        interval: int,
        daemon: bool = True
    ) -> None:
        """
        Add a background task.
        
        Args:
            name: Task name
            task_func: Function to run
            interval: Interval in seconds
            daemon: Whether the thread should be daemon
        """
        self.tasks[name] = {
            'func': task_func,
            'interval': interval,
            'daemon': daemon
        }
        logger.info(f"Added background task: {name} (interval: {interval}s)")
    
    def start_task(self, name: str) -> None:
        """Start a specific background task."""
        if name not in self.tasks:
            logger.error(f"Task {name} not found")
            return
        
        if name in self.threads and self.threads[name].is_alive():
            logger.warning(f"Task {name} is already running")
            return
        
        task = self.tasks[name]
        thread = threading.Thread(
            target=self._run_task,
            args=(name, task['func'], task['interval']),
            daemon=task['daemon'],
            name=f"BackgroundTask-{name}"
        )
        
        self.threads[name] = thread
        thread.start()
        logger.info(f"Started background task: {name}")
    
    def stop_task(self, name: str) -> None:
        """Stop a specific background task."""
        if name in self.threads:
            # Note: We can't actually stop threads, but we can mark them for cleanup
            logger.info(f"Marked task {name} for cleanup")
    
    def start_all(self) -> None:
        """Start all background tasks."""
        if self.running:
            logger.warning("Background tasks already running")
            return
            
        self.running = True
        
        # Register shutdown handler only once
        if not self._shutdown_registered:
            atexit.register(self.stop_all)
            self._shutdown_registered = True
        
        for name in self.tasks:
            self.start_task(name)
        logger.info("Started all background tasks")
    
    def stop_all(self) -> None:
        """Stop all background tasks."""
        if not self.running:
            return
            
        self.running = False
        logger.info("Stopped all background tasks")
    
    def _run_task(self, name: str, task_func: Callable, interval: int) -> None:
        """Run a background task in a loop."""
        logger.info(f"Background task {name} started")
        
        while self.running:
            try:
                task_func()
                logger.debug(f"Background task {name} completed successfully")
            except Exception as e:
                logger.error(f"Error in background task {name}: {e}")
            
            # Sleep for the interval, but check running status periodically
            for _ in range(interval):
                if not self.running:
                    break
                time.sleep(1)
        
        logger.info(f"Background task {name} stopped")


# Global task manager instance
task_manager = BackgroundTaskManager()


def setup_background_tasks(
    update_conditions_func: Callable,
    cleanup_database_func: Callable
) -> BackgroundTaskManager:
    """
    Set up background tasks for the application.
    
    Args:
        update_conditions_func: Function to update conditions cache
        cleanup_database_func: Function to cleanup database
    
    Returns:
        Configured task manager
    """
    config = get_config()
    
    # Add tasks
    task_manager.add_task(
        'update_conditions',
        update_conditions_func,
        config.CACHE_UPDATE_INTERVAL
    )
    
    task_manager.add_task(
        'cleanup_database',
        cleanup_database_func,
        config.CLEANUP_INTERVAL
    )
    
    return task_manager


def create_conditions_updater(ham_conditions, cache_lock):
    """Create a conditions cache updater function."""
    def update_conditions_cache():
        """Update the conditions cache in the background."""
        try:
            with cache_lock:
                ham_conditions._conditions_cache = ham_conditions.generate_report()
                ham_conditions._conditions_cache_time = time.time()
            logger.info("Updated conditions cache")
        except Exception as e:
            logger.error(f"Error updating conditions cache: {e}")
    
    return update_conditions_cache


def create_database_cleanup(db):
    """Create a database cleanup function."""
    config = get_config()
    
    def cleanup_database():
        """Clean up old database data periodically."""
        try:
            db.cleanup_old_data(days=config.DATA_RETENTION_DAYS)
            logger.info("Database cleanup completed")
        except Exception as e:
            logger.error(f"Error in database cleanup: {e}")
    
    return cleanup_database 