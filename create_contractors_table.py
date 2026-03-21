#!/usr/bin/env python3
"""
Create contractors table in MySQL
"""

import mysql.connector
from mysql.connector import Error

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'Dattu@1234',
    'database': 'canteen_db'
}

def create_contractors_table():
    """Create the contractors table"""
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS contractors (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        company VARCHAR(255) NOT NULL,
        phone VARCHAR(20),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
    
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()
        
        print("📋 Creating contractors table...")
        cursor.execute(create_table_sql)
        
        cursor.execute("SHOW TABLES LIKE 'contractors'")
        result = cursor.fetchone()
        
        if result:
            print("✅ Contractors table created successfully!")
        
        cursor.close()
        connection.close()
        return True
        
    except Error as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    create_contractors_table()