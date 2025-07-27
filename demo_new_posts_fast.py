#!/usr/bin/env python3
"""
Fast demonstration of "New Post" vs "No New Post" scenarios using mock data
"""

import os
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import our functions
from monitor import (
    load_previous_posts,
    save_current_posts,
    detect_new_posts
)

def create_mock_posts():
    """Create sample blog posts for testing without network calls"""
    return [
        {
            'title': 'Chrome brings seamless work and personal switching to iOS and enhanced enterprise protections to mobile',
            'url': 'https://cloud.google.com/blog/products/chrome-enterprise/chrome-brings-personal-and-work-separation-to-ios-users-and-more-enterprise-protections-to-mobile',
            'author': 'Martin Chown',
            'read_time': '5 minute read',
            'publish_date': 'July 21, 2025',
            'id': 'chrome-brings-personal-and-work-separation-to-ios-users-and-more-enterprise-protections-to-mobile',
            'summary': 'Chrome Enterprise blog post: Chrome brings seamless work and personal switching to iOS and enhanced enterprise protections to mobile...'
        }
    ]

def scenario_1_no_new_posts_fast():
    """
    Scenario 1: No new posts - system should NOT send email (FAST VERSION)
    """
    print("🔍 SCENARIO 1: NO NEW POSTS (FAST VERSION)")
    print("=" * 55)
    print("Using mock data to test new post detection logic")
    print()
    
    try:
        # Step 1: Create mock current posts
        print("📥 Creating mock current blog posts...")
        current_posts = create_mock_posts()
        print(f"✅ Created {len(current_posts)} mock posts")
        
        # Step 2: Save these as "previous" posts (simulate they were seen before)
        print("💾 Saving current posts as 'previously seen'...")
        save_current_posts(current_posts, {'simulation': 'baseline', 'test_mode': True})
        print("✅ Posts saved to history")
        
        # Step 3: Load previous posts (same as current)
        print("📂 Loading previous posts...")
        previous_posts = load_previous_posts()
        print(f"✅ Loaded {len(previous_posts)} previous posts")
        
        # Step 4: Detect new posts (should be ZERO)
        print("🔍 Detecting new posts...")
        new_posts = detect_new_posts(current_posts, previous_posts)
        
        print(f"\n📊 RESULT:")
        print(f"Current posts: {len(current_posts)}")
        print(f"Previous posts: {len(previous_posts)}")
        print(f"NEW posts: {len(new_posts)}")
        
        if len(new_posts) == 0:
            print("✅ SUCCESS: No new posts detected - NO email would be sent")
            print("💡 This is the normal scenario when monitoring an unchanged blog")
        else:
            print("❌ UNEXPECTED: New posts detected when there shouldn't be any")
            
        return len(new_posts)
        
    except Exception as e:
        print(f"❌ Error in scenario 1: {e}")
        return -1

def scenario_2_new_posts_fast():
    """
    Scenario 2: New posts detected - system SHOULD send email (FAST VERSION)
    """
    print("\n🆕 SCENARIO 2: NEW POSTS DETECTED (FAST VERSION)")
    print("=" * 55)
    print("Using mock data to simulate new blog posts")
    print()
    
    try:
        # Step 1: Create mock current posts (with a new post)
        print("📥 Creating mock current blog posts...")
        current_posts = create_mock_posts()
        
        # Add a "new" post
        new_post = {
            'title': 'How ChromeOS propelled Korean Air\'s digital transformation',
            'url': 'https://cloud.google.com/blog/products/chrome-enterprise/how-chromeos-propelled-korean-airs-digital-transformation',
            'author': 'Choi HeeJung',
            'read_time': '6 minute read',
            'publish_date': 'July 22, 2025',
            'id': 'how-chromeos-propelled-korean-airs-digital-transformation',
            'summary': 'Chrome Enterprise blog post: How ChromeOS propelled Korean Air\'s digital transformation...'
        }
        current_posts.append(new_post)
        
        print(f"✅ Created {len(current_posts)} mock posts (including 1 new post)")
        
        # Step 2: Simulate previous posts by saving only the first post
        print("🎭 Simulating previous state (saving only the first post)...")
        simulated_previous_posts = [current_posts[0]]  # Only the first post was "seen before"
        
        # Save the simulated previous state
        temp_data = {
            'posts': simulated_previous_posts,
            'metadata': {
                'simulation': 'previous_state',
                'test_mode': True,
                'last_checked': datetime.now().isoformat(),
                'total_posts': len(simulated_previous_posts)
            }
        }
        
        with open('previous_blog_posts.json', 'w') as f:
            json.dump(temp_data, f, indent=2)
        
        print(f"✅ Simulated {len(simulated_previous_posts)} previous posts")
        
        # Step 3: Load the simulated previous posts
        print("📂 Loading simulated previous posts...")
        previous_posts = load_previous_posts()
        print(f"✅ Loaded {len(previous_posts)} previous posts")
        
        # Step 4: Detect new posts (should be 1)
        print("🔍 Detecting new posts...")
        new_posts = detect_new_posts(current_posts, previous_posts)
        
        print(f"\n📊 RESULT:")
        print(f"Current posts: {len(current_posts)}")
        print(f"Previous posts: {len(previous_posts)}")
        print(f"NEW posts: {len(new_posts)}")
        
        if len(new_posts) > 0:
            print(f"✅ SUCCESS: {len(new_posts)} new posts detected - EMAIL would be sent")
            print("💡 These are the NEW posts that would trigger an email:")
            for i, post in enumerate(new_posts, 1):
                title = post['title'][:60]
                print(f"   {i}. {title}...")
        else:
            print("❌ UNEXPECTED: No new posts detected when there should be some")
            
        return len(new_posts)
        
    except Exception as e:
        print(f"❌ Error in scenario 2: {e}")
        return -1

def cleanup():
    """Clean up test files"""
    try:
        if os.path.exists('previous_blog_posts.json'):
            os.remove('previous_blog_posts.json')
        print("🧹 Cleaned up test files")
    except:
        pass

def main():
    """Run both scenarios with fast mock data"""
    print("🎯 FAST NEW POST DETECTION DEMONSTRATION")
    print("=" * 70)
    print("This will demonstrate how the system behaves using mock data:")
    print("1. No new posts (normal monitoring)")
    print("2. New posts detected (email should be sent)")
    print("⚡ Using mock data for speed - no network calls!")
    print()
    
    try:
        # Run Scenario 1: No new posts
        new_count_1 = scenario_1_no_new_posts_fast()
        
        # Run Scenario 2: New posts
        new_count_2 = scenario_2_new_posts_fast()
        
        # Summary
        print(f"\n🏁 DEMONSTRATION SUMMARY")
        print("=" * 50)
        print(f"Scenario 1 (No new posts): {new_count_1} new posts → {'✅ Correct' if new_count_1 == 0 else '❌ Error'}")
        print(f"Scenario 2 (New posts): {new_count_2} new posts → {'✅ Correct' if new_count_2 > 0 else '❌ Error'}")
        
        if new_count_1 == 0 and new_count_2 > 0:
            print(f"\n🎉 SUCCESS: New post detection is working correctly!")
            print("✅ The system will only send emails when there are genuinely new posts")
            print("✅ It won't spam you with emails about old posts")
            print("⚡ Test completed in seconds instead of minutes!")
        else:
            print(f"\n❌ Issues detected in new post detection logic")
            
    except KeyboardInterrupt:
        print("\n⏹️ Demonstration cancelled")
    except Exception as e:
        print(f"\n❌ Demonstration failed: {e}")
    finally:
        cleanup()

if __name__ == "__main__":
    main()
