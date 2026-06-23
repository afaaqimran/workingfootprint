"""
Log Manager — File-based logging with 5-day retention
Handles log file rotation, compression, and automatic cleanup of old logs
"""

import os
import logging
import gzip
import shutil
from datetime import datetime, timedelta
from pathlib import Path

class LogManager:
    """Manages application logs with file rotation and 5-day retention"""
    
    def __init__(self, log_dir='logs', retention_days=5):
        """
        Initialize log manager
        
        Args:
            log_dir: Directory to store log files (default: 'logs')
            retention_days: Number of days to keep logs (default: 5)
        """
        self.log_dir = log_dir
        self.retention_days = retention_days
        self.logger = None
        
        # Create logs directory if it doesn't exist
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)
        
        # Setup logger
        self._setup_logger()
        
        # Cleanup old logs on startup
        self.cleanup_old_logs()
    
    def _setup_logger(self):
        """Setup logging configuration"""
        self.logger = logging.getLogger('footprint_app')
        
        # Prevent duplicate handlers if called multiple times
        if self.logger.handlers:
            return self.logger
        
        # Set logger level to DEBUG (log everything)
        self.logger.setLevel(logging.DEBUG)
        
        # Create formatters
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)-8s - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console Handler (INFO level - less verbose)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        
        # File Handler (DEBUG level - all logs)
        log_file = os.path.join(self.log_dir, f'footprint_{datetime.now().strftime("%Y%m%d")}.log')
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        
        # Add handlers to logger
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
        
        return self.logger
    
    def get_logger(self):
        """Get the configured logger instance"""
        return self.logger
    
    def cleanup_old_logs(self):
        """
        Delete log files older than retention_days
        Runs automatically on startup and can be called periodically
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            
            # Find all log files in the logs directory
            log_files = Path(self.log_dir).glob('footprint_*.log*')
            deleted_count = 0
            
            for log_file in log_files:
                # Get file creation/modification time
                file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                
                # If file is older than retention period, delete it
                if file_mtime < cutoff_date:
                    try:
                        log_file.unlink()
                        print(f"🧹 Deleted old log: {log_file.name}")
                        deleted_count += 1
                    except Exception as e:
                        print(f"⚠️ Error deleting log {log_file.name}: {e}")
            
            if deleted_count > 0:
                print(f"🧹 Cleanup complete: Deleted {deleted_count} log file(s) older than {self.retention_days} days")
        
        except Exception as e:
            print(f"❌ Error during log cleanup: {e}")
    
    def log_info(self, message):
        """Log info level message"""
        if self.logger:
            self.logger.info(message)
    
    def log_error(self, message):
        """Log error level message"""
        if self.logger:
            self.logger.error(message)
    
    def log_warning(self, message):
        """Log warning level message"""
        if self.logger:
            self.logger.warning(message)
    
    def log_debug(self, message):
        """Log debug level message"""
        if self.logger:
            self.logger.debug(message)
    
    def log_critical(self, message):
        """Log critical level message"""
        if self.logger:
            self.logger.critical(message)
    
    def get_log_stats(self):
        """Get statistics about current logs"""
        try:
            log_files = list(Path(self.log_dir).glob('footprint_*.log*'))
            total_size = sum(f.stat().st_size for f in log_files)
            
            return {
                'log_count': len(log_files),
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'log_dir': self.log_dir,
                'retention_days': self.retention_days,
                'logs': [
                    {
                        'name': f.name,
                        'size_mb': round(f.stat().st_size / (1024 * 1024), 2),
                        'created': datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                    }
                    for f in sorted(log_files, key=lambda x: x.stat().st_mtime, reverse=True)
                ]
            }
        except Exception as e:
            return {'error': str(e)}


# Global logger instance
_log_manager = None

def initialize_logging(log_dir='logs', retention_days=5):
    """Initialize global logging (call this once at app startup)"""
    global _log_manager
    _log_manager = LogManager(log_dir=log_dir, retention_days=retention_days)
    return _log_manager.get_logger()

def get_log_manager():
    """Get the global log manager instance"""
    global _log_manager
    if _log_manager is None:
        initialize_logging()
    return _log_manager

def log_info(message):
    """Convenience function to log info message"""
    logger = get_log_manager().get_logger()
    logger.info(message)

def log_error(message):
    """Convenience function to log error message"""
    logger = get_log_manager().get_logger()
    logger.error(message)

def log_warning(message):
    """Convenience function to log warning message"""
    logger = get_log_manager().get_logger()
    logger.warning(message)

def log_debug(message):
    """Convenience function to log debug message"""
    logger = get_log_manager().get_logger()
    logger.debug(message)

def log_critical(message):
    """Convenience function to log critical message"""
    logger = get_log_manager().get_logger()
    logger.critical(message)

def get_logger():
    """Get the configured logger instance"""
    return get_log_manager().get_logger()
