import mysql.connector
from mysql.connector import Error

from config import Config


def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            autocommit=False,
            charset="utf8mb4",
            collation="utf8mb4_unicode_ci",
        )

        if connection.is_connected():
            return connection

        raise Error("Failed to connect to MySQL database")

    except Error as error:
        print(f"Error connecting to MySQL database: {error}")
        print(f"Host: {Config.DB_HOST}:{Config.DB_PORT}")
        print(f"Database: {Config.DB_NAME}")
        print(f"User: {Config.DB_USER}")
        raise error


def test_database_connection():
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        connection.close()
        return True
    except Error as error:
        print(f"Database test failed: {error}")
        return False
