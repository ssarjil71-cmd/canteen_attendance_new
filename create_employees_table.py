#!/usr/bin/env python3
"""
Create employees table directly in MySQL
Run this script to create the missing employees table
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

def create_employees_table():
    """Create the employees table in canteen_db database"""
    
    # SQL to create employees table
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS employees (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        emp_id VARCHAR(100) UNIQUE NOT NULL,
        gender ENUM('Male', 'Female', 'Other') NOT NULL,
        dob DATE NOT NULL,
        company VARCHAR(255) NOT NULL,
        role VARCHAR(255) NOT NULL,
        department VARCHAR(255) NOT NULL,
        shift ENUM('Morning', 'Afternoon', 'Night') NOT NULL,
        joining_date DATE NOT NULL,
        photo VARCHAR(500),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
    
    try:
        # Connect to MySQL database
        print("🔌 Connecting to MySQL database...")
        connection = mysql.connector.connect(**DB_CONFIG)
        
        if connection.is_connected():
            cursor = connection.cursor()
            
            # Create employees table
            print("📋 Creating employees table...")
            cursor.execute(create_table_sql)
            
            # Verify table creation
            cursor.execute("SHOW TABLES LIKE 'employees'")
            result = cursor.fetchone()
            
            if result:
                print("✅ Employees table created successfully!")
                
                # Show table structure
                cursor.execute("DESCRIBE employees")
                columns = cursor.fetchall()
                print("\n📊 Employees table structure:")
                print("-" * 60)
                for column in columns:
                    print(f"   {column[0]:<15} | {column[1]:<20} | {column[2]:<10} | {column[3]}")
                print("-" * 60)
                
                # Show all tables in database
                cursor.execute("SHOW TABLES")
                tables = cursor.fetchall()
                print(f"\n📋 All tables in canteen_db:")
                for table in tables:
                    print(f"   ✓ {table[0]}")
                
                print("\n🎉 Setup completed successfully!")
                print("✅ You can now run your Flask application:")
                print("   python app.py")
                
            else:
                print("❌ Failed to create employees table")
                return False
            
            cursor.close()
            connection.close()
            return True
            
    except Error as e:
        print(f"❌ MySQL Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_connection():
    """Test database connection"""
    try:
        print("🧪 Testing database connection...")
        connection = mysql.connector.connect(**DB_CONFIG)
        
        if connection.is_connected():
            cursor = connection.cursor()
            cursor.execute("SELECT DATABASE()")
            db_name = cursor.fetchone()
            print(f"✅ Connected to database: {db_name[0]}")
            
            cursor.close()
            connection.close()
            return True
        else:
            print("❌ Failed to connect to database")
            return False
            
    except Error as e:
        print(f"❌ Connection test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Smart Canteen System - Create Employees Table")
    print("=" * 60)
    print(f"📍 Host: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"👤 User: {DB_CONFIG['user']}")
    print(f"🗄️  Database: {DB_CONFIG['database']}")
    print("=" * 60)
    
    # Test connection first
    if not test_connection():
        print("\n❌ Cannot connect to database. Please check:")
        print("   - MySQL server is running")
        print("   - Username and password are correct")
        print("   - Database 'canteen_db' exists")
        exit(1)
    
    # Create employees table
    if create_employees_table():
        print("\n🎯 Next steps:")
        print("   1. Run your Flask app: python app.py")
        print("   2. Visit: http://127.0.0.1:5000/manager/add_employee")
        print("   3. Test adding employees!")
    else:
        print("\n❌ Failed to create employees table")
        exit(1)