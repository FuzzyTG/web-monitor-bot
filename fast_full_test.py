#!/usr/bin/env python3
"""
Fast Full Pipeline Test - Limited to 1-2 posts for speed
Tests the complete pipeline but with reasonable execution time
"""

import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from monitor import (
    extract_blog_posts, 
    get_individual_blog_content, 
    analyze_blog_post_with_ai, 
    send_blog_notification
)

def fast_full_pipeline_test():
    """
    Test the complete pipeline with only 1-2 posts for speed
    """
    print("⚡ FAST FULL PIPELINE TEST")
    print("=" * 50)
    print("Testing complete pipeline with limited posts for speed")
    print()
    
    try:
        # Step 1: Get blog posts but limit to first 2
        print("📥 Fetching blog posts (limiting to 2 for speed)...")
        all_posts = extract_blog_posts()
        if not all_posts:
            print("❌ No posts found")
            return False
        
        # Limit to first 2 posts only
        test_posts = all_posts[:2]
        print(f"✅ Limited to {len(test_posts)} posts for testing:")
        for i, post in enumerate(test_posts, 1):
            print(f"  {i}. {post['title'][:60]}...")
        
        # Step 2: Extract content
        print(f"\n📖 Extracting content for {len(test_posts)} posts...")
        posts_with_content = []
        for i, post in enumerate(test_posts, 1):
            print(f"  Processing post {i}/{len(test_posts)}...")
            enhanced_post = get_individual_blog_content(post)
            if enhanced_post and enhanced_post.get('extraction_success'):
                posts_with_content.append(enhanced_post)
                print(f"  ✅ Content extracted: {enhanced_post.get('content_length', 0)} chars")
            else:
                print(f"  ❌ Failed to extract content")
        
        if not posts_with_content:
            print("❌ No content extracted")
            return False
        
        # Step 3: AI Analysis
        print(f"\n🤖 AI analysis for {len(posts_with_content)} posts...")
        analyzed_posts = []
        for i, post in enumerate(posts_with_content, 1):
            print(f"  Analyzing post {i}/{len(posts_with_content)}...")
            analyzed_post = analyze_blog_post_with_ai(post)
            if analyzed_post and analyzed_post.get('analysis_success'):
                analyzed_posts.append(analyzed_post)
                print(f"  ✅ Analysis completed: {analyzed_post.get('analysis_length', 0)} chars")
            else:
                print(f"  ❌ Analysis failed")
        
        if not analyzed_posts:
            print("❌ No posts analyzed")
            return False
        
        # Step 4: Send email
        print(f"\n📧 Sending email with {len(analyzed_posts)} analyzed posts...")
        email_result = send_blog_notification(analyzed_posts, notification_type="test")
        
        if email_result['success']:
            print(f"✅ Email sent successfully!")
            print(f"   Recipient: {os.getenv('EMAIL_TO')}")
            print(f"   Posts included: {email_result['posts_count']}")
            print(f"   Sent at: {email_result['email_sent_at']}")
            return True
        else:
            print(f"❌ Email failed: {email_result['message']}")
            return False
    
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🎯 FAST FULL PIPELINE TEST")
    print("=" * 70)
    print("This will test the complete pipeline with only 2 posts")
    print("Expected time: 2-3 minutes instead of 10+ minutes")
    print()
    
    start_time = datetime.now()
    success = fast_full_pipeline_test()
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print(f"\n🏁 TEST SUMMARY")
    print("=" * 50)
    print(f"Success: {'✅ YES' if success else '❌ NO'}")
    print(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
    
    if success:
        print("🎉 Full pipeline working - check your email!")
    else:
        print("❌ Pipeline needs debugging")
