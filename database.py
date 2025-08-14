import sqlite3
import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = None):
        """Initialize SQLite database"""
        if db_path is None:
            # Create data directory if it doesn't exist
            data_dir = os.path.join(os.getcwd(), 'data')
            os.makedirs(data_dir, exist_ok=True)
            self.db_path = os.path.join(data_dir, "ham_radio.db")
        else:
            self.db_path = db_path
        
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create spots table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS spots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        callsign TEXT NOT NULL,
                        frequency TEXT NOT NULL,
                        mode TEXT,
                        spotter TEXT,
                        comment TEXT,
                        dxcc TEXT,
                        source TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create user_preferences table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_preferences (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        key TEXT UNIQUE NOT NULL,
                        value TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create indexes for better performance
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_spots_timestamp ON spots(timestamp)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_spots_callsign ON spots(callsign)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_spots_frequency ON spots(frequency)')
                
                conn.commit()
                logger.info(f"Database initialized successfully at {self.db_path}")
                
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    def store_spots(self, spots: List[Dict]) -> bool:
        """Store spots in the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for spot in spots:
                    cursor.execute('''
                        INSERT INTO spots (timestamp, callsign, frequency, mode, spotter, comment, dxcc, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        spot.get('timestamp', ''),
                        spot.get('callsign', ''),
                        spot.get('frequency', ''),
                        spot.get('mode', ''),
                        spot.get('spotter', ''),
                        spot.get('comment', ''),
                        spot.get('dxcc', ''),
                        spot.get('source', '')
                    ))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error storing spots: {e}")
            return False
    
    def get_recent_spots(self, hours: int = 24, limit: int = 100) -> List[Dict]:
        """Get recent spots from the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Calculate time threshold
                threshold = datetime.now() - timedelta(hours=hours)
                
                cursor.execute('''
                    SELECT * FROM spots 
                    WHERE datetime(timestamp) >= datetime(?)
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (threshold.strftime('%Y-%m-%d %H:%M:%S'), limit))
                
                rows = cursor.fetchall()
                spots = []
                for row in rows:
                    spots.append({
                        'timestamp': row['timestamp'],
                        'callsign': row['callsign'],
                        'frequency': row['frequency'],
                        'mode': row['mode'],
                        'spotter': row['spotter'],
                        'comment': row['comment'],
                        'dxcc': row['dxcc'],
                        'source': row['source']
                    })
                
                return spots
                
        except Exception as e:
            logger.error(f"Error getting recent spots: {e}")
            return []
    
    def get_spots_summary(self, hours: int = 24) -> Dict:
        """Get summary statistics for recent spots"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Calculate time threshold
                threshold = datetime.now() - timedelta(hours=hours)
                
                # Get total spots
                cursor.execute('''
                    SELECT COUNT(*) FROM spots 
                    WHERE datetime(timestamp) >= datetime(?)
                ''', (threshold.strftime('%Y-%m-%d %H:%M:%S'),))
                total_spots = cursor.fetchone()[0]
                
                # Get unique modes
                cursor.execute('''
                    SELECT DISTINCT mode FROM spots 
                    WHERE datetime(timestamp) >= datetime(?) AND mode != 'Unknown'
                ''', (threshold.strftime('%Y-%m-%d %H:%M:%S'),))
                modes = [row[0] for row in cursor.fetchall()]
                
                # Get unique DXCC entities
                cursor.execute('''
                    SELECT DISTINCT dxcc FROM spots 
                    WHERE datetime(timestamp) >= datetime(?) AND dxcc != ''
                ''', (threshold.strftime('%Y-%m-%d %H:%M:%S'),))
                dxcc_entities = [row[0] for row in cursor.fetchall()]
                
                return {
                    'total_spots': total_spots,
                    'active_modes': sorted(modes),
                    'active_dxcc': sorted(dxcc_entities)[:10],
                    'source': 'Database'
                }
                
        except Exception as e:
            logger.error(f"Error getting spots summary: {e}")
            return {
                'total_spots': 0,
                'active_modes': [],
                'active_dxcc': [],
                'source': 'Database Error'
            }
    
    def store_user_preference(self, key: str, value: str) -> bool:
        """Store a user preference"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO user_preferences (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                ''', (key, value))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error storing user preference: {e}")
            return False
    
    def get_user_preference(self, key: str) -> Optional[str]:
        """Get a user preference"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('SELECT value FROM user_preferences WHERE key = ?', (key,))
                result = cursor.fetchone()
                
                return result[0] if result else None
                
        except Exception as e:
            logger.error(f"Error getting user preference {key}: {e}")
            return None
    
    def cleanup_old_data(self, days: int = 7):
        """Clean up old data from the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Calculate cutoff date
                cutoff = datetime.now() - timedelta(days=days)
                
                # Clean up old spots
                cursor.execute('''
                    DELETE FROM spots 
                    WHERE datetime(timestamp) < datetime(?)
                ''', (cutoff.strftime('%Y-%m-%d %H:%M:%S'),))
                spots_deleted = cursor.rowcount
                
                conn.commit()
                logger.info(f"Cleaned up {spots_deleted} old spots")
                
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
    
    def get_database_stats(self) -> Dict:
        """Get database statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get table sizes
                cursor.execute('SELECT COUNT(*) FROM spots')
                total_spots = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM user_preferences')
                total_preferences = cursor.fetchone()[0]
                
                # Get database file size
                file_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
                
                return {
                    'total_spots': total_spots,
                    'total_preferences': total_preferences,
                    'file_size_mb': round(file_size / (1024 * 1024), 2)
                }
                
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}

# Global database instance
_db_instance = None

def init_database():
    """Initialize the database globally."""
    global _db_instance
    try:
        _db_instance = Database()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

def get_database():
    """Get the global database instance."""
    global _db_instance
    if _db_instance is None:
        init_database()
    return _db_instance

def get_stored_zip_code():
    """Get the stored ZIP code from user preferences."""
    try:
        db = get_database()
        return db.get_user_preference('zip_code')
    except Exception as e:
        logger.error(f"Error getting stored ZIP code: {e}")
        return None 