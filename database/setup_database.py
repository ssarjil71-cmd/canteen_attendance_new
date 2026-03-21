#!/usr/bin/env python3
"""
Database Setup Script for Smart Canteen System
Run this script to create the database and tables
"""

import mysql.connector
import sys
import os

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

def create_database():
    """Create the database if it doesn't exist"""
    try:
        # Connect to MySQL server (without specifying database)
        connection = mysql.connector.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD
        )
        cursor = connection.cursor()
        
        # Create database
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {Config.DB_NAME}")
        print(f"✅ Database '{Config.DB_NAME}' created successfully!")
        
        cursor.close()
        connection.close()
        return True
    except mysql.connector.Error as err:
        print(f"❌ Error creating database: {err}")
        return False

def create_tables():
    """Create all necessary tables"""
    try:
        # Connect to the specific database
        connection = mysql.connector.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME
        )
        cursor = connection.cursor()
        
        # Create employees table
        employees_table = """
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
        )
        """
        cursor.execute(employees_table)
        print("✅ Employees table created successfully!")
        
        # Create contractors table
        contractors_table = """
        CREATE TABLE IF NOT EXISTS contractors (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            company VARCHAR(255) NOT NULL,
            phone VARCHAR(20),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """
        cursor.execute(contractors_table)
        print("✅ Contractors table created successfully!")
        
        # Create companies table
        companies_table = """
        CREATE TABLE IF NOT EXISTS companies (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL UNIQUE,
            address TEXT,
            phone VARCHAR(20),
            email VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """
        cursor.execute(companies_table)
        print("✅ Companies table created successfully!")
        
        # Create managers table
        managers_table = """
        CREATE TABLE IF NOT EXISTS managers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255),
            company_id INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE SET NULL
        )
        """
        cursor.execute(managers_table)
        print("✅ Managers table created successfully!")
        
        # Commit changes
        connection.commit()
        
        # Show tables
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print("\n📋 Tables in database:")
        for table in tables:
            print(f"   - {table[0]}")
        
        # Show employees table structure
        cursor.execute("DESCRIBE employees")
        columns = cursor.fetchall()
        print("\n📊 Employees table structure:")
        for column in columns:
            print(f"   - {column[0]}: {column[1]} {column[2]} {column[3]}")
        
        cursor.close()
        connection.close()
        return True
        
    except mysql.connector.Error as err:
        print(f"❌ Error creating tables: {err}")
        return False

def test_connection():
    """Test database connection"""
    try:
        connection = mysql.connector.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME
        )
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        cursor.close()
        connection.close()
        print("✅ Database connection test successful!")
        return True
    except mysql.connector.Error as err:
        print(f"❌ Database connection test failed: {err}")
        return False

def main():
    """Main setup function"""
    print("🚀 Setting up Smart Canteen System Database...")
    print(f"📍 Host: {Config.DB_HOST}:{Config.DB_PORT}")
    print(f"👤 User: {Config.DB_USER}")
    print(f"🗄️  Database: {Config.DB_NAME}")
    print("-" * 50)
    
    # Step 1: Create database
    if not create_database():
        print("❌ Failed to create database. Exiting...")
        return False
    
    # Step 2: Create tables
    if not create_tables():
        print("❌ Failed to create tables. Exiting...")
        return False
    
    # Step 3: Test connection
    if not test_connection():
        print("❌ Database connection test failed. Exiting...")
        return False
    
    print("\n🎉 Database setup completed successfully!")
    print("✅ You can now run your Flask application.")
    return True

if __name__ == "__main__":
    main()