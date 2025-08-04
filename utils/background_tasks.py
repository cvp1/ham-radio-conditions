"""
Background tasks for Ham Radio Conditions app.
Handles periodic updates and cleanup operations.
"""

import time
import threading
import logging
from typing import Callable, Optional
from utils.cache_manager import cache_get, cache_set, cache_delete

logger = logging.getLogger(__name__)


class TaskManager:
    """Manages background tasks with scheduling and monitoring."""
    
    def __init__(self):
        self.tasks = {}
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
    
    def add_task(self, name: str, task_func: Callable, interval_seconds: int = 300):
        """Add a new background task."""
        with self.lock:
            self.tasks[name] = {
                'func': task_func,
                'interval': interval_seconds,
                'last_run': None,
                'next_run': time.time() + interval_seconds,
                'runs': 0,
                'errors': 0,
                'last_error': None
            }
            logger.info(f"Added task: {name} (interval: {interval_seconds}s)")
    
    def remove_task(self, name: str):
        """Remove a background task."""
        with self.lock:
            if name in self.tasks:
                del self.tasks[name]
                logger.info(f"Removed task: {name}")
    
    def start_all(self):
        """Start all background tasks."""
        with self.lock:
            if self.running:
                logger.warning("Task manager already running")
                return
            
            self.running = True
            self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
            self.thread.start()
            logger.info("Task manager started")
    
    def stop_all(self):
        """Stop all background tasks."""
        with self.lock:
            self.running = False
            if self.thread:
                self.thread.join(timeout=5)
            logger.info("Task manager stopped")
    
    def _run_scheduler(self):
        """Main scheduler loop."""
        while self.running:
            try:
                current_time = time.time()
                
                with self.lock:
                    for name, task_info in self.tasks.items():
                        if current_time >= task_info['next_run']:
                            # Run task in separate thread to avoid blocking
                            threading.Thread(
                                target=self._run_task,
                                args=(name, task_info),
                                daemon=True
                            ).start()
                
                # Sleep for a short interval
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                time.sleep(5)
    
    def _run_task(self, name: str, task_info: dict):
        """Run a single task with error handling."""
        try:
            start_time = time.time()
            
            # Execute the task
            task_info['func']()
            
            # Update task info
            with self.lock:
                task_info['last_run'] = time.time()
                task_info['next_run'] = time.time() + task_info['interval']
                task_info['runs'] += 1
                task_info['last_error'] = None
            
            execution_time = time.time() - start_time
            logger.info(f"Task {name} completed in {execution_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Error running task {name}: {e}")
            
            with self.lock:
                task_info['errors'] += 1
                task_info['last_error'] = str(e)
                # Don't update next_run on error - let it retry on next cycle
    
    def get_status(self) -> dict:
        """Get status of all tasks."""
        with self.lock:
            status = {
                'running': self.running,
                'tasks': {}
            }
            
            for name, task_info in self.tasks.items():
                status['tasks'][name] = {
                    'interval': task_info['interval'],
                    'last_run': task_info['last_run'],
                    'next_run': task_info['next_run'],
                    'runs': task_info['runs'],
                    'errors': task_info['errors'],
                    'last_error': task_info['last_error']
                }
            
            return status


def setup_background_tasks(conditions_updater: Callable, database_cleanup: Callable) -> TaskManager:
    """
    Set up background tasks for the application.
    
    Args:
        conditions_updater: Function to update conditions cache
        database_cleanup: Function to clean up database
    
    Returns:
        TaskManager instance
    """
    task_manager = TaskManager()
    
    # Add conditions update task (every 10 minutes for production)
    task_manager.add_task('conditions_update', conditions_updater, 600)
    
    # Add database cleanup task (every hour)
    task_manager.add_task('database_cleanup', database_cleanup, 3600)
    
    # Add cache cleanup task (every 15 minutes)
    task_manager.add_task('cache_cleanup', cache_cleanup_task, 900)
    
    return task_manager


def create_conditions_updater(ham_conditions, lock: threading.Lock) -> Callable:
    """
    Create a conditions update function.
    
    Args:
        ham_conditions: HamRadioConditions instance
        lock: Threading lock for synchronization
    
    Returns:
        Update function
    """
    def update_conditions_cache():
        """Update the conditions cache."""
        try:
            with lock:
                # Generate new conditions
                new_conditions = ham_conditions.generate_report()
                
                if new_conditions:
                    # Cache the new conditions with production-optimized duration
                    cache_set('conditions', 'current', new_conditions, max_age=600)  # 10 minutes
                    logger.info("Conditions cache updated successfully")
                else:
                    logger.warning("Failed to generate new conditions")
                    
        except Exception as e:
            logger.error(f"Error updating conditions cache: {e}")
    
    return update_conditions_cache


def create_database_cleanup(database) -> Callable:
    """
    Create a database cleanup function.
    
    Args:
        database: Database instance
    
    Returns:
        Cleanup function
    """
    def cleanup_database():
        """Clean up old database entries."""
        try:
            # Clean up old spots and QRZ cache
            cleanup_result = database.cleanup_old_data()
            
            if cleanup_result:
                spots_deleted, qrz_deleted = cleanup_result
                logger.info(f"Database cleanup completed: {spots_deleted} spots, {qrz_deleted} QRZ entries deleted")
            else:
                logger.warning("Database cleanup failed")
                
        except Exception as e:
            logger.error(f"Error in database cleanup: {e}")
    
    return cleanup_database


def cache_cleanup_task():
    """Clean up expired cache entries."""
    try:
        # The cache manager handles cleanup automatically, but we can add additional logic here
        # For now, just log that cleanup is happening
        pass
        
    except Exception as e:
        logger.error(f"Error in cache cleanup: {e}")


def get_task_manager_status() -> dict:
    """Get status of the task manager."""
    # This would need to be called from a context where we have access to the task manager
    # For now, return a placeholder
    return {
        'running': False,
        'tasks': {},
        'message': 'Task manager status not available'
    } 