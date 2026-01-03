#!/usr/bin/env python3
"""
Quick test to verify the bot structure
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test if all modules can be imported"""
    modules = [
        'database',
        'models',
        'utils.permissions',
        'utils.validators',
        'utils.normalizers',
        'services.database_service',
        'services.view_tracker',
        'services.campaign_service'
    ]
    
    for module in modules:
        try:
            __import__(module)
            print(f"✅ {module}")
        except ImportError as e:
            print(f"❌ {module}: {e}")
            return False
            
    return True

def test_database():
    """Test database initialization"""
    try:
        from database import Database
        db = Database('test.db')
        db.initialize()
        print("✅ Database initialization")
        os.remove('test.db')
        return True
    except Exception as e:
        print(f"❌ Database test: {e}")
        return False

if __name__ == "__main__":
    print("Testing CL Bot structure...\n")
    
    if test_imports() and test_database():
        print("\n✅ All tests passed!")
        print("\nTo run the bot:")
        print("1. Edit .env file with your Discord token")
        print("2. Run: python main.py")
    else:
        print("\n❌ Some tests failed. Please check the errors above.")
