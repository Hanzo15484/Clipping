#!/usr/bin/env python3
import sqlite3
import sys

def test_database():
    """Test database connection and tables"""
    try:
        conn = sqlite3.connect('database.sqlite')
        cursor = conn.cursor()
        
        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print("📊 Database Tables Found:")
        for table in tables:
            print(f"  - {table[0]}")
            
        # Check users table
        cursor.execute("SELECT * FROM users LIMIT 5")
        users = cursor.fetchall()
        
        print(f"\n👥 Users in database: {len(users)}")
        for user in users:
            print(f"  - {user[1]} (ID: {user[0]})")
            
        # Check if we can insert a test user
        test_id = "1234567890"
        cursor.execute("INSERT OR IGNORE INTO users (discord_id, username) VALUES (?, ?)", 
                      (test_id, "TestUser"))
        conn.commit()
        
        print("\n✅ Database is working correctly!")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def create_test_user():
    """Create a test user"""
    try:
        conn = sqlite3.connect('database.sqlite')
        cursor = conn.cursor()
        
        # Create test user
        test_id = "9999999999"
        cursor.execute("INSERT OR REPLACE INTO users (discord_id, username) VALUES (?, ?)", 
                      (test_id, "DebugUser"))
        conn.commit()
        
        print(f"✅ Created test user: DebugUser (ID: {test_id})")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error creating test user: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Debugging CL Bot Database...")
    print("=" * 50)
    
    if test_database():
        create_test_user()
        
    print("\n💡 Tips:")
    print("1. Make sure your .env file has DISCORD_TOKEN")
    print("2. Check if you have Staff/Admin roles in your Discord server")
    print("3. Try /my-profile command after restarting the bot")
