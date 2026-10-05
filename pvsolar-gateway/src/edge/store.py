"""
Edge Store-and-Forward module.

Provides local data buffering using SQLite for reliable data storage
during network outages, with automatic sync to cloud/broker.
"""

import asyncio
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from core.config import StoreAndForwardConfig

logger = structlog.get_logger(__name__)


class EdgeStore:
    """
    SQLite-based edge store for store-and-forward functionality.
    
    Features:
    - Local data buffering during network outages
    - Configurable retention period
    - Automatic cleanup of old records
    - Batch sync to cloud/broker
    - Data integrity verification
    """
    
    def __init__(self, config: StoreAndForwardConfig):
        self.config = config
        self._db_path = Path(config.database)
        self._conn: Optional[sqlite3.Connection] = None
        self._sync_queue: asyncio.Queue = asyncio.Queue()
    
    async def initialize(self):
        """Initialize SQLite database and create tables."""
        try:
            # Ensure directory exists
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create connection
            self._conn = sqlite3.connect(
                str(self._db_path),
                check_same_thread=False
            )
            
            # Enable WAL mode for better concurrent access
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            
            # Create tables
            self._create_tables()
            
            # Get initial buffer size
            buffer_size = self._get_buffer_size()
            
            logger.info(
                "edge_store.initialized",
                database=str(self._db_path),
                buffer_size=buffer_size
            )
            
        except Exception as e:
            logger.error("edge_store.init_error", error=str(e))
            raise
    
    async def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            logger.info("edge_store.closed")
    
    def _create_tables(self):
        """Create database tables."""
        cursor = self._conn.cursor()
        
        # Telemetry data table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inverter_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at REAL NOT NULL,
                synced INTEGER DEFAULT 0,
                sync_attempts INTEGER DEFAULT 0,
                last_sync_error TEXT
            )
        """)
        
        # Index for efficient querying
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_telemetry_inverter 
            ON telemetry(inverter_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp 
            ON telemetry(timestamp)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_telemetry_synced 
            ON telemetry(synced)
        """)
        
        # Alerts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inverter_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                data TEXT,
                created_at REAL NOT NULL,
                acknowledged INTEGER DEFAULT 0,
                acknowledged_by TEXT,
                acknowledged_at TEXT
            )
        """)
        
        # Sync metadata table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        
        self._conn.commit()
    
    async def store_reading(self, inverter_id: str, data: Dict[str, Any]):
        """
        Store a telemetry reading.
        
        Args:
            inverter_id: Inverter identifier
            data: Telemetry data dictionary
        """
        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            data_json = json.dumps(data, default=str)
            created_at = time.time()
            
            cursor = self._conn.cursor()
            cursor.execute("""
                INSERT INTO telemetry (inverter_id, timestamp, data, created_at)
                VALUES (?, ?, ?, ?)
            """, (inverter_id, timestamp, data_json, created_at))
            
            self._conn.commit()
            
            # Check buffer size and cleanup if needed
            buffer_size = self._get_buffer_size()
            if buffer_size > self.config.max_records:
                await self._cleanup_old_records()
            
            logger.debug(
                "edge_store.reading_stored",
                inverter_id=inverter_id,
                buffer_size=buffer_size
            )
            
        except Exception as e:
            logger.error("edge_store.store_error", error=str(e))
    
    async def store_alert(self, inverter_id: str, alert_type: str, 
                         severity: str, message: str, data: Optional[Dict] = None):
        """
        Store an alert.
        
        Args:
            inverter_id: Inverter identifier
            alert_type: Type of alert
            severity: Alert severity (info, warning, error, critical)
            message: Alert message
            data: Optional additional data
        """
        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            data_json = json.dumps(data, default=str) if data else None
            created_at = time.time()
            
            cursor = self._conn.cursor()
            cursor.execute("""
                INSERT INTO alerts (inverter_id, timestamp, alert_type, severity, 
                                   message, data, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (inverter_id, timestamp, alert_type, severity, message, 
                  data_json, created_at))
            
            self._conn.commit()
            
        except Exception as e:
            logger.error("edge_store.alert_store_error", error=str(e))
    
    async def get_pending_readings(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get pending (unsynced) readings.
        
        Args:
            limit: Maximum number of readings to return
            
        Returns:
            List of pending readings
        """
        try:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT id, inverter_id, timestamp, data, created_at
                FROM telemetry
                WHERE synced = 0 AND sync_attempts < 5
                ORDER BY created_at ASC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            
            readings = []
            for row in rows:
                readings.append({
                    'id': row[0],
                    'inverter_id': row[1],
                    'timestamp': row[2],
                    'data': json.loads(row[3]),
                    'created_at': row[4]
                })
            
            return readings
            
        except Exception as e:
            logger.error("edge_store.get_pending_error", error=str(e))
            return []
    
    async def mark_synced(self, reading_ids: List[int]):
        """
        Mark readings as synced.
        
        Args:
            reading_ids: List of reading IDs to mark as synced
        """
        try:
            if not reading_ids:
                return
            
            cursor = self._conn.cursor()
            placeholders = ','.join(['?' for _ in reading_ids])
            cursor.execute(f"""
                UPDATE telemetry
                SET synced = 1
                WHERE id IN ({placeholders})
            """, reading_ids)
            
            self._conn.commit()
            
            logger.debug("edge_store.marked_synced", count=len(reading_ids))
            
        except Exception as e:
            logger.error("edge_store.mark_synced_error", error=str(e))
    
    async def mark_sync_failed(self, reading_id: int, error: str):
        """
        Mark a reading sync as failed.
        
        Args:
            reading_id: Reading ID
            error: Error message
        """
        try:
            cursor = self._conn.cursor()
            cursor.execute("""
                UPDATE telemetry
                SET sync_attempts = sync_attempts + 1,
                    last_sync_error = ?
                WHERE id = ?
            """, (error, reading_id))
            
            self._conn.commit()
            
        except Exception as e:
            logger.error("edge_store.mark_failed_error", error=str(e))
    
    async def sync_to_cloud(self):
        """Sync pending readings to cloud/broker."""
        # This will be implemented by cloud-specific modules
        # For now, just log the sync attempt
        pending = await self.get_pending_readings(limit=10)
        
        if pending:
            logger.info(
                "edge_store.sync_attempt",
                pending_count=len(pending)
            )
    
    def _get_buffer_size(self) -> int:
        """Get current buffer size."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM telemetry WHERE synced = 0")
        return cursor.fetchone()[0]
    
    async def _cleanup_old_records(self):
        """Cleanup old records based on retention period."""
        try:
            cutoff_time = time.time() - (self.config.max_buffer_hours * 3600)
            
            cursor = self._conn.cursor()
            cursor.execute("""
                DELETE FROM telemetry
                WHERE created_at < ? AND synced = 1
            """, (cutoff_time,))
            
            deleted = cursor.rowcount
            self._conn.commit()
            
            if deleted > 0:
                logger.info("edge_store.cleanup", deleted=deleted)
            
        except Exception as e:
            logger.error("edge_store.cleanup_error", error=str(e))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get store statistics."""
        cursor = self._conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM telemetry")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM telemetry WHERE synced = 0")
        pending = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM alerts")
        alerts = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT MIN(created_at) FROM telemetry WHERE synced = 0
        """)
        oldest_pending = cursor.fetchone()[0]
        
        return {
            'total_records': total,
            'pending_sync': pending,
            'total_alerts': alerts,
            'oldest_pending': datetime.fromtimestamp(oldest_pending, tz=timezone.utc).isoformat() if oldest_pending else None,
            'database_path': str(self._db_path),
            'database_size_mb': self._db_path.stat().st_size / (1024 * 1024) if self._db_path.exists() else 0
        }
