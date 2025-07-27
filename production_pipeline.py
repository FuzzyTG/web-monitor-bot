#!/usr/bin/env python3
"""
Production Pipeline - Only processes NEW blog posts for email notifications
This is the REAL monitoring system that should be used for production.
"""

import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json

# Load environment variables
load_dotenv()

# Import our functions
from monitor import (
    extract_blog_posts, 
    load_previous_posts,
    save_current_posts,
    detect_new_posts,
    sort_posts_by_date,
    get_individual_blog_content, 
    analyze_blog_post_with_ai, 
    send_blog_notification
)

def production_monitoring_pipeline():
    """
    Production pipeline that only processes NEW blog posts
    This ensures we only send emails about truly new content
    """
    print("🔍 PRODUCTION MONITORING PIPELINE - NEW POSTS ONLY")
    print("=" * 70)
    print("This pipeline will ONLY process and email about NEW blog posts")
    print("that haven't been seen before.\n")
    
    try:
        # Step 1: Load previous posts from storage
        print("📂 STEP 1: LOADING PREVIOUS POST HISTORY")
        print("=" * 50)
        
        previous_posts = load_previous_posts()
        print(f"✅ Loaded {len(previous_posts)} previously seen posts")
        
        # Step 2: Extract current posts
        print(f"\n🔍 STEP 2: EXTRACTING CURRENT BLOG POSTS")
        print("=" * 50)
        
        current_posts = extract_blog_posts()
        if not current_posts:
            print("❌ No current posts found")
            return False
        
        print(f"✅ Found {len(current_posts)} current blog posts")
        
        # Step 3: Detect NEW posts only
        print(f"\n🆕 STEP 3: DETECTING NEW POSTS")
        print("=" * 50)
        
        new_posts = detect_new_posts(current_posts, previous_posts)
        
        if not new_posts:
            print("✅ No new posts detected - no email will be sent")
            print("The system is working correctly - monitoring for new content...")
            
            # Still save current posts to update the tracking
            save_current_posts(current_posts, {
                'check_type': 'production_monitoring',
                'new_posts_found': 0,
                'total_posts_checked': len(current_posts)
            })
            
            return True
        
        print(f"🎯 Found {len(new_posts)} NEW posts to process:")
        for i, post in enumerate(new_posts, 1):
            title = post['title'][:60]
            print(f"  {i}. {title}...")
        
        # Step 4: Sort new posts by date (newest first)
        print(f"\n📅 STEP 4: SORTING NEW POSTS BY DATE")
        print("=" * 50)
        
        sorted_new_posts = sort_posts_by_date(new_posts)
        print(f"✅ Sorted {len(sorted_new_posts)} new posts by publication date")
        
        # Step 5: Extract content for NEW posts only
        print(f"\n📖 STEP 5: EXTRACTING CONTENT (NEW POSTS ONLY)")
        print("=" * 50)
        
        posts_with_content = []
        for i, post in enumerate(sorted_new_posts, 1):
            print(f"\n📖 Processing NEW Post {i}/{len(sorted_new_posts)}: {post['title'][:50]}...")
            enhanced_post = get_individual_blog_content(post)
            if enhanced_post and enhanced_post.get('extraction_success'):
                posts_with_content.append(enhanced_post)
                content_len = enhanced_post.get('content_length', 0)
                print(f"✅ Content extracted: {content_len} characters")
            else:
                print(f"❌ Failed to extract content for post {i}")
        
        if not posts_with_content:
            print("❌ No content extracted successfully from new posts")
            return False
        
        print(f"✅ Successfully extracted content for {len(posts_with_content)} new posts")
        
        # Step 6: AI Analysis for NEW posts only
        print(f"\n🤖 STEP 6: AI ANALYSIS (NEW POSTS ONLY)")
        print("=" * 50)
        
        analyzed_posts = []
        for i, post in enumerate(posts_with_content, 1):
            print(f"\n📊 Analyzing NEW Post {i}/{len(posts_with_content)}: {post['title'][:50]}...")
            analyzed_post = analyze_blog_post_with_ai(post)
            if analyzed_post and analyzed_post.get('analysis_success'):
                analyzed_posts.append(analyzed_post)
                analysis_len = analyzed_post.get('analysis_length', 0)
                print(f"✅ Analysis completed: {analysis_len} characters")
            else:
                print(f"❌ Analysis failed for post {i}")
        
        if not analyzed_posts:
            print("❌ No posts analyzed successfully")
            return False
        
        print(f"✅ Successfully analyzed {len(analyzed_posts)} new posts")
        
        # Step 7: Send email notification (NEW posts only)
        print(f"\n📧 STEP 7: EMAIL NOTIFICATION (NEW POSTS ONLY)")
        print("=" * 50)
        
        print(f"Sending notification for {len(analyzed_posts)} NEW blog posts...")
        email_result = send_blog_notification(analyzed_posts, notification_type="new_posts")
        
        if email_result['success']:
            print(f"✅ Email sent successfully!")
            print(f"   Recipient: {os.getenv('EMAIL_TO')}")
            print(f"   NEW Posts included: {email_result['posts_count']}")
            print(f"   Sent at: {email_result['email_sent_at']}")
            
            # Step 8: Save updated post history
            print(f"\n💾 STEP 8: UPDATING POST HISTORY")
            print("=" * 50)
            
            save_success = save_current_posts(current_posts, {
                'check_type': 'production_monitoring',
                'new_posts_found': len(new_posts),
                'new_posts_analyzed': len(analyzed_posts),
                'email_sent': True,
                'email_sent_at': email_result['email_sent_at']
            })
            
            if save_success:
                print(f"✅ Post history updated - {len(current_posts)} posts now tracked")
            else:
                print(f"⚠️ Warning: Failed to save post history")
            
            return True
        else:
            print(f"❌ Email sending failed: {email_result['message']}")
            return False
    
    except Exception as e:
        print(f"❌ Production pipeline failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_new_post_detection():
    """
    Test the new post detection to show how it works
    """
    print("🧪 TESTING NEW POST DETECTION LOGIC")
    print("=" * 50)
    
    try:
        # Load current posts
        current_posts = extract_blog_posts()
        print(f"Current posts found: {len(current_posts)}")
        
        # Load previous posts
        previous_posts = load_previous_posts()
        print(f"Previous posts tracked: {len(previous_posts)}")
        
        # Detect new posts
        new_posts = detect_new_posts(current_posts, previous_posts)
        print(f"NEW posts detected: {len(new_posts)}")
        
        if new_posts:
            print(f"\n📋 NEW POSTS:")
            for i, post in enumerate(new_posts, 1):
                title = post['title'][:60]
                url = post['url']
                print(f"  {i}. {title}...")
                print(f"     URL: {url}")
        else:
            print("✅ No new posts - system working correctly!")
            
        return len(new_posts)
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return -1

def simulate_new_post_scenario():
    """
    Simulate what happens when there are genuinely new posts
    by temporarily clearing the post history
    """
    print("🎭 SIMULATING NEW POST SCENARIO")
    print("=" * 50)
    print("This will temporarily clear post history to simulate new posts")
    print("Press Enter to continue or Ctrl+C to cancel...")
    
    try:
        input()
        
        # Backup existing history
        try:
            with open('previous_blog_posts.json', 'r') as f:
                backup_data = f.read()
            print("✅ Backed up existing post history")
        except FileNotFoundError:
            backup_data = None
            print("No existing history to backup")
        
        # Clear history temporarily
        if os.path.exists('previous_blog_posts.json'):
            os.remove('previous_blog_posts.json')
        
        print("🧹 Cleared post history - all posts will appear as NEW")
        
        # Run production pipeline
        success = production_monitoring_pipeline()
        
        # Restore backup if it existed
        if backup_data:
            with open('previous_blog_posts.json', 'w') as f:
                f.write(backup_data)
            print("✅ Restored original post history")
        
        return success
        
    except KeyboardInterrupt:
        print("\n⏹️ Simulation cancelled")
        return False

def main():
    """Main function with options"""
    print("🎯 MICROSOFT EDGE COMPETITIVE INTELLIGENCE - PRODUCTION MONITORING")
    print("=" * 80)
    print("Choose your monitoring mode:")
    print("1. Production Monitoring (NEW posts only)")
    print("2. Test New Post Detection")
    print("3. Simulate New Post Scenario")
    print("4. Exit")
    
    try:
        choice = input("\nEnter your choice (1-4): ").strip()
        
        if choice == "1":
            print(f"\n🚀 Starting Production Monitoring...")
            success = production_monitoring_pipeline()
            if success:
                print(f"\n✅ Production monitoring completed successfully!")
            else:
                print(f"\n❌ Production monitoring failed")
                
        elif choice == "2":
            print(f"\n🧪 Testing New Post Detection...")
            new_count = test_new_post_detection()
            if new_count >= 0:
                print(f"\n✅ Test completed - {new_count} new posts detected")
            else:
                print(f"\n❌ Test failed")
                
        elif choice == "3":
            print(f"\n🎭 Running Simulation...")
            success = simulate_new_post_scenario()
            if success:
                print(f"\n✅ Simulation completed successfully!")
            else:
                print(f"\n❌ Simulation failed")
                
        elif choice == "4":
            print(f"\n👋 Goodbye!")
            
        else:
            print(f"\n❌ Invalid choice. Please run again.")
            
    except KeyboardInterrupt:
        print("\n\n⏹️ Cancelled by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()
