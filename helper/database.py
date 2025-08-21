from psycopg2 import pool, OperationalError, InterfaceError
from config.logging import logger
from helper.common import singleton
import os
import time

class DatabaseError(Exception):
    """Custom exception for database errors with user-friendly messages"""
    def __init__(self, message, original_error=None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)

@singleton
class DatabaseHelper:
    def __init__(self, database, user, password, host, port):
        self.db_config = {
            'dbname': database,
            'user': user,
            'password': password,
            'host': host,
            'port': port
        }
        self.max_retries = 3
        self.retry_delay = 1  # seconds
        self._initialize_pool()

    def _initialize_pool(self):
        try:
            self.pool = pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                **self.db_config
            )
            print(f"[DEBUG] Connection pool initialized successfully: {self.pool}")
            logger.info("Connection pool initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise DatabaseError(
                "Maaf, terjadi kesalahan pada koneksi database. Silakan coba beberapa saat lagi.",
                original_error=e
            )

    def get_connection(self):
        for attempt in range(self.max_retries):
            try:
                conn = self.pool.getconn()
                if conn:
                    # Test connection
                    with conn.cursor() as cursor:
                        cursor.execute("SELECT 1")
                        conn.commit()
                    return conn
            except (OperationalError, InterfaceError) as e:
                logger.error(f"Connection attempt {attempt + 1} failed: {e}")
                if conn:
                    self.pool.putconn(conn)
                if attempt == self.max_retries - 1:
                    logger.info("Reinitializing connection pool")
                    self._initialize_pool()
                else:
                    time.sleep(self.retry_delay)
        raise DatabaseError(
            "Maaf, sistem sedang mengalami gangguan. Silakan coba beberapa saat lagi."
        )

    def fetch_query(self, query, params=None):
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                result = cursor.fetchall()
                conn.commit()
                logger.info(f"Query executed successfully: {query}")
                logger.info(f"Result: {result}")
                
                return result
                
        except DatabaseError:
            # Re-raise DatabaseError with the same message
            raise
        except Exception as e:
            logger.error(f"Error executing fetch query: {e}")
            if conn:
                conn.rollback()
            raise DatabaseError(
                "Maaf, terjadi kesalahan saat mengambil data. Silakan coba beberapa saat lagi.",
                original_error=e
            )
        finally:
            if conn:
                self.pool.putconn(conn)

    def execute_query(self, query, params=None):
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                conn.commit()
                logger.info(f"Query executed successfully: {query}")
                return True
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            if conn:
                conn.rollback()
            raise DatabaseError(
                "Maaf, terjadi kesalahan saat menyimpan data. Silakan coba beberapa saat lagi.",
                original_error=e
            )
        finally:
            if conn:
                self.pool.putconn(conn)

    def close_all(self):
        if hasattr(self, 'pool'):
            self.pool.closeall()
            logger.info("All database connections closed")

# Database configuration
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'database': os.getenv('POSTGRES_DB', 'linkedin'),
    'user': os.getenv('POSTGRES_USER', 'root'),
    'password': os.getenv('POSTGRES_PASSWORD', 'password'),
    'port': int(os.getenv('POSTGRES_PORT', 5432))
}

db_postgres = DatabaseHelper(host=os.getenv('POSTGRES_HOST', 'localhost'),
                                    database=os.getenv('POSTGRES_DB', 'linkedin'),
                                    user=os.getenv('POSTGRES_USER', 'root'),
                                    password=os.getenv('POSTGRES_PASSWORD', 'password'),
                                    port=int(os.getenv('POSTGRES_PORT', 5432))) 
