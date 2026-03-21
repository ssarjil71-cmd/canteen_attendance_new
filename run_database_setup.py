#!/usr/bin/env python3
"""
Quick Database Setup Script
Run this to create the database and tables for Smart Canteen System
"""

import os
import sys

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run the setup
from database.setup_database import main

if __name__ == "__main__":
    print("🚀 Smart Canteen System - Database Setup")
    print("=" * 50)
    
    try:
        success = main()
        if success:
            print("\n✅ Setup completed successfully!")
            print("🎯 You can now run your Flask application:")
            print("   python app.py")
        else:
            print("\n❌ Setup failed. Please check the error messages above.")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)