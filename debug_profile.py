#!/usr/bin/env python3
import sqlite3
import sys
import os

def check_database():
    """Check what's in the database"""
    print("🔍 Checking database for profiles...")
    
    try:
        conn = sqlite3.connect('database.sqlite')
        cursor = conn.cursor()
        
        # Check users
        cursor.execute("SELECT discord_id, username FROM users")
        users = cursor.fetchall()
        print(f"\n👥 Users ({len(users)}):")
        for user in users:
            print(f"  - {user[1]} (ID: {user[0]})")
        
        # Check social profiles
        cursor.execute("SELECT id, discord_id, platform, profile_url, status FROM social_profiles")
        profiles = cursor.fetchall()
        print(f"\n📱 Social Profiles ({len(profiles)}):")
        for profile in profiles:
            print(f"  - ID: {profile[0]}, User: {profile[1]}, Platform: {profile[2]}")
            print(f"    URL: {profile[3]}")
            print(f"    Status: {profile[4]}")
            print()
        
        # Check campaigns
        cursor.execute("SELECT id, name, platform, status FROM campaigns")
        campaigns = cursor.fetchall()
        print(f"\n🎯 Campaigns ({len(campaigns)}):")
        for campaign in campaigns:
            print(f"  - ID: {campaign[0]}, Name: {campaign[1]}, Platform: {campaign[2]}, Status: {campaign[3]}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_profile_lookup():
    """Test if we can find a profile"""
    print("\n🔎 Testing profile lookup...")
    
    try:
        conn = sqlite3.connect('database.sqlite')
        cursor = conn.cursor()
        
        # Get a test user ID
        cursor.execute("SELECT discord_id FROM users LIMIT 1")
        user = cursor.fetchone()
        
        if user:
            user_id = user[0]
            print(f"Testing with user ID: {user_id}")
            
            # Find their profiles
            cursor.execute(
                "SELECT profile_url, status FROM social_profiles WHERE discord_id = ?",
                (user_id,)
            )
            profiles = cursor.fetchall()
            
            print(f"Found {len(profiles)} profile(s) for this user:")
            for profile in profiles:
                print(f"  - URL: {profile[0]}, Status: {profile[1]}")
                
                # Test exact match
                cursor.execute(
                    "SELECT * FROM social_profiles WHERE discord_id = ? AND profile_url = ?",
                    (user_id, profile[0])
                )
                exact_match = cursor.fetchone()
                print(f"    Exact match found: {'✅' if exact_match else '❌'}")
                
                # Test case-insensitive match
                cursor.execute(
                    "SELECT * FROM social_profiles WHERE discord_id = ? AND LOWER(profile_url) = LOWER(?)",
                    (user_id, profile[0])
                )
                case_insensitive = cursor.fetchone()
                print(f"    Case-insensitive match: {'✅' if case_insensitive else '❌'}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("🐛 Debug Profile Submission Issue")
    print("=" * 50)
    
    if check_database() and test_profile_lookup():
        print("\n✅ Database check complete!")
        print("\n💡 If /submit says 'Profile not found or not approved':")
        print("1. Make sure the profile URL matches EXACTLY")
        print("2. Check that status is 'approved' not 'pending'")
        print("3. Use /check-profile command to verify status")
        print("4. Try using the exact profile URL from /my-profiles")
    else:
        print("\n❌ There were issues with the database.")
