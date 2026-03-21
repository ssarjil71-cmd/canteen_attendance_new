import mysql.connector
from mysql.connector import Error
from config import Config
import sys

def get_db_connection():
    """
    Get MySQL database connection with proper error handling
    """
    try:
        connection = mysql.connector.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            autocommit=False,  # Explicit transaction control
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
        
        if connection.is_connected():
            return connection
        else:
            raise Error("Failed to connect to MySQL database")
            
    except Error as e:
        print(f"Error connecting to MySQL database: {e}")
        print(f"Host: {Config.DB_HOST}:{Config.DB_PORT}")
        print(f"Database: {Config.DB_NAME}")
        print(f"User: {Config.DB_USER}")
        
        # Check if it's a database not found error
        if "Unknown database" in str(e):
            print("\n❌ Database does not exist!")
            print("🔧 Please run the database setup script:")
            print("   python database/setup_database.py")
        
        # Check if it's a table not found error
        elif "doesn't exist" in str(e):
            print("\n❌ Required tables do not exist!")
            print("🔧 Please run the database setup script:")
            print("   python database/setup_database.py")
        
        raise e

def test_database_connection():
    """
    Test database connection and table existence
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Test employees table
        cursor.execute("SELECT COUNT(*) FROM employees")
        cursor.fetchone()
        
        cursor.close()
        conn.close()
        return True
        
    except Error as e:
        print(f"Database test failed: {e}")
        return False