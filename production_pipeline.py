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

# Set default AI model to Pro if not explicitly configured
if not os.getenv('GEMINI_MODEL'):
    os.environ['GEMINI_MODEL'] = 'gemini-2.5-pro'

# Import error handling
try:
    from error_handling import ErrorLogger, create_system_health_check
    error_logger = ErrorLogger()
    print("✅ Enhanced error handling loaded")
except ImportError:
    class DummyLogger:
        def log_error(self, error, context, additional_info=None):
            print(f"Error in {context}: {error}")
    error_logger = DummyLogger()
    print("⚠️ Using basic error handling")

# Import our functions
from monitor import (
    extract_blog_posts, 
    load_previous_posts,
    save_current_posts,
    detect_new_posts,
    sort_posts_by_date,
    get_individual_blog_content, 
    analyze_blog_post_with_ai,
    generate_email_summary,
    generate_html_report,
    generate_report_id,
    save_html_report_to_file,
    publish_report_and_get_url,
    send_concise_notification
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
        
        # Step 7: Generate Email Summaries (NEW - Phase 2)
        print(f"\n📧 STEP 7: GENERATING EMAIL SUMMARIES")
        print("=" * 50)
        
        for i, post in enumerate(analyzed_posts, 1):
            print(f"Generating summary for post {i}/{len(analyzed_posts)}...")
            try:
                post['email_summary'] = generate_email_summary(post)
                print(f"✅ Summary: {post['email_summary'][:60]}...")
            except Exception as e:
                print(f"⚠️ Summary generation failed for post {i}: {e}")
                post['email_summary'] = f"Chrome Enterprise update: {post.get('title', 'Unknown')[:50]}..."
        
        # Step 8: Generate HTML Report (NEW - Phase 2)
        print(f"\n📄 STEP 8: GENERATING HTML REPORT")
        print("=" * 50)
        
        report_id = generate_report_id()
        print(f"📋 Report ID: {report_id}")
        
        filename, html_content = generate_html_report(analyzed_posts, report_id)
        if not filename or not html_content:
            print("❌ HTML report generation failed")
            return False
        
        print(f"✅ HTML report generated: {filename}")
        print(f"📊 Content length: {len(html_content):,} characters")
        
        # Save report to file
        success, file_path, error = save_html_report_to_file(filename, html_content)
        if not success:
            print(f"❌ Failed to save report: {error}")
            return False
        
        print(f"✅ Report saved: {file_path}")
        
        # Step 9: Publish Report (NEW - Phase 2)
        print(f"\n🌐 STEP 9: PUBLISHING REPORT")
        print("=" * 50)
        
        pub_success, report_url, pub_error = publish_report_and_get_url(file_path, report_id)
        
        if pub_success:
            print(f"✅ Report published successfully!")
        else:
            print(f"⚠️ Publishing note: {pub_error}")
        
        print(f"📄 Report URL: {report_url}")
        
        # Step 10: Send Enhanced Email Notification (UPDATED - Phase 2)
        print(f"\n📮 STEP 10: SENDING ENHANCED EMAIL NOTIFICATION")
        print("=" * 50)
        
        notification_type = os.getenv('NOTIFICATION_TYPE', 'new_posts')
        print(f"Sending {notification_type} notification for {len(analyzed_posts)} NEW blog posts...")
        print(f"Report URL: {report_url}")
        
        email_result = send_concise_notification(analyzed_posts, report_url, notification_type)
        
        if email_result['success']:
            print(f"✅ Enhanced email sent successfully!")
            print(f"   Recipient: {os.getenv('EMAIL_TO')}")
            print(f"   Subject: {email_result['subject']}")
            print(f"   NEW Posts included: {email_result['posts_count']}")
            print(f"   Report URL included: {report_url}")
            print(f"   Sent at: {email_result['email_sent_at']}")
            
            # Step 11: Save updated post history and metadata (UPDATED - Phase 2)
            print(f"\n💾 STEP 11: UPDATING POST HISTORY & METADATA")
            print("=" * 50)
            
            save_success = save_current_posts(current_posts, {
                'check_type': 'production_monitoring_v2',
                'new_posts_found': len(new_posts),
                'new_posts_analyzed': len(analyzed_posts),
                'report_id': report_id,
                'report_url': report_url,
                'email_sent': True,
                'email_sent_at': email_result['email_sent_at'],
                'notification_type': notification_type
            })
            
            if save_success:
                print(f"✅ Post history updated - {len(current_posts)} posts now tracked")
            else:
                print(f"⚠️ Warning: Failed to save post history")
            
            # Save report metadata
            try:
                from report_config import ReportMetadata
                metadata_manager = ReportMetadata()
                report_data = {
                    'posts_count': len(analyzed_posts),
                    'high_priority_count': len([p for p in analyzed_posts if p.get('structured_data', {}).get('priority_level') == 'High']),
                    'analysis_success_count': len(analyzed_posts),
                    'file_size_bytes': len(html_content),
                    'urls': {'web_url': report_url},
                    'email_sent': True,
                    'email_sent_at': email_result['email_sent_at']
                }
                metadata_manager.add_report(report_id, report_data)
                print(f"✅ Report metadata saved")
            except Exception as e:
                print(f"⚠️ Metadata saving failed: {e}")
            
            return True
        else:
            print(f"❌ Email sending failed: {email_result['message']}")
            return False
    
    except Exception as e:
        error_logger.log_error(e, "production_monitoring_pipeline", {
            "pipeline_step": "unknown",
            "timestamp": datetime.now().isoformat()
        })
        print(f"❌ Production pipeline failed: {str(e)}")
        print("🔄 Attempting system recovery...")
        
        # Try to save system state for debugging
        try:
            error_state = {
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'pipeline_type': 'production_monitoring',
                'system_health': create_system_health_check() if 'create_system_health_check' in globals() else None
            }
            
            os.makedirs('logs', exist_ok=True)
            with open('logs/pipeline_failure.json', 'w') as f:
                json.dump(error_state, f, indent=2)
            
            print(f"📝 Error state saved to logs/pipeline_failure.json")
            
        except Exception as save_error:
            print(f"⚠️ Failed to save error state: {save_error}")
        
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
    """Main function with enhanced options and CLI support"""
    import sys
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Microsoft Edge Competitive Intelligence - Production Monitoring')
    parser.add_argument('--force', action='store_true', help='Force analysis of all posts (not just new ones)')
    parser.add_argument('--test', action='store_true', help='Run test new post detection')
    parser.add_argument('--simulate', action='store_true', help='Simulate new post scenario')
    parser.add_argument('--notification-type', choices=['new_posts', 'test'], default='new_posts', 
                       help='Type of notification to send')
    parser.add_argument('--config-check', action='store_true', help='Check system configuration and exit')
    parser.add_argument('--cleanup', action='store_true', help='Run report cleanup and exit')
    
    args = parser.parse_args()
    
    # Handle CLI-only operations
    if args.config_check:
        from report_config import get_system_status
        status = get_system_status()
        print("🔧 SYSTEM CONFIGURATION CHECK")
        print("=" * 50)
        print(f"AI Configured: {'✅' if status['config_status']['ai_configured'] else '❌'}")
        print(f"Email Configured: {'✅' if status['config_status']['email_configured'] else '❌'}")
        print(f"GitHub Configured: {'✅' if status['config_status']['github_configured'] else '❌'}")
        print(f"System Ready: {'✅' if status['system_ready'] else '❌'}")
        if status['config_status']['missing_config']:
            print("Missing configuration:")
            for item in status['config_status']['missing_config']:
                print(f"  - {item}")
        return
    
    if args.cleanup:
        try:
            try:
                from report_publisher import cleanup_old_reports
            except ImportError:
                def cleanup_old_reports(days):
                    return False, 0, "Report publisher module not available"
            print("🧹 RUNNING REPORT CLEANUP")
            print("=" * 50)
            success, count, error = cleanup_old_reports(30)
            if success:
                print(f"✅ Cleaned up {count} old reports")
            else:
                print(f"❌ Cleanup failed: {error}")
        except Exception as e:
            print(f"❌ Cleanup error: {e}")
        return
    
    # Set environment variables for GitHub Actions compatibility
    if args.force:
        os.environ['FORCE_ANALYSIS'] = 'true'
    if args.notification_type:
        os.environ['NOTIFICATION_TYPE'] = args.notification_type
    
    # Handle direct CLI commands
    if len(sys.argv) > 1:
        if args.force:
            print("🔄 FORCE MODE: Analyzing all posts (not just new ones)")
            # For force mode, temporarily clear the previous posts to simulate all posts as new
            import tempfile
            import shutil
            backup_file = None
            try:
                if os.path.exists('previous_blog_posts.json'):
                    backup_file = 'previous_blog_posts.json.backup'
                    shutil.copy('previous_blog_posts.json', backup_file)
                    os.remove('previous_blog_posts.json')
                
                success = production_monitoring_pipeline()
                
                # Restore backup
                if backup_file and os.path.exists(backup_file):
                    shutil.move(backup_file, 'previous_blog_posts.json')
                
                return success
            except Exception as e:
                # Restore backup on error
                if backup_file and os.path.exists(backup_file):
                    shutil.move(backup_file, 'previous_blog_posts.json')
                raise e
        
        elif args.test:
            print("🧪 Testing New Post Detection...")
            new_count = test_new_post_detection()
            return new_count >= 0
        
        elif args.simulate:
            print("🎭 Running Simulation...")
            return simulate_new_post_scenario()
        
        else:
            # Default: run production monitoring
            print("🚀 Starting Production Monitoring...")
            return production_monitoring_pipeline()
    
    # Interactive mode (no CLI arguments)
    print("🎯 MICROSOFT EDGE COMPETITIVE INTELLIGENCE - PRODUCTION MONITORING V2")
    print("=" * 85)
    print("Enhanced with Phase 2 features: HTML Reports + GitHub Pages + Concise Emails")
    print("\nChoose your monitoring mode:")
    print("1. Production Monitoring (NEW posts only)")
    print("2. Force Analysis (ALL posts)")
    print("3. Test New Post Detection")
    print("4. Simulate New Post Scenario")
    print("5. Check System Configuration")
    print("6. Run Report Cleanup")
    print("7. Exit")
    
    try:
        choice = input("\nEnter your choice (1-7): ").strip()
        
        if choice == "1":
            print(f"\n🚀 Starting Production Monitoring...")
            success = production_monitoring_pipeline()
            if success:
                print(f"\n✅ Production monitoring completed successfully!")
            else:
                print(f"\n❌ Production monitoring failed")
        
        elif choice == "2":
            print(f"\n🔄 Starting Force Analysis (ALL posts)...")
            # Temporarily backup and clear previous posts
            backup_file = None
            try:
                if os.path.exists('previous_blog_posts.json'):
                    backup_file = 'previous_blog_posts.json.backup'
                    shutil.copy('previous_blog_posts.json', backup_file)
                    os.remove('previous_blog_posts.json')
                
                success = production_monitoring_pipeline()
                
                # Restore backup
                if backup_file and os.path.exists(backup_file):
                    shutil.move(backup_file, 'previous_blog_posts.json')
                
                if success:
                    print(f"\n✅ Force analysis completed successfully!")
                else:
                    print(f"\n❌ Force analysis failed")
            except Exception as e:
                # Restore backup on error
                if backup_file and os.path.exists(backup_file):
                    shutil.move(backup_file, 'previous_blog_posts.json')
                print(f"\n❌ Force analysis error: {e}")
                
        elif choice == "3":
            print(f"\n🧪 Testing New Post Detection...")
            new_count = test_new_post_detection()
            if new_count >= 0:
                print(f"\n✅ Test completed - {new_count} new posts detected")
            else:
                print(f"\n❌ Test failed")
                
        elif choice == "4":
            print(f"\n🎭 Running Simulation...")
            success = simulate_new_post_scenario()
            if success:
                print(f"\n✅ Simulation completed successfully!")
            else:
                print(f"\n❌ Simulation failed")
        
        elif choice == "5":
            from report_config import get_system_status
            status = get_system_status()
            print(f"\n🔧 SYSTEM CONFIGURATION")
            print("=" * 50)
            print(f"AI Configured: {'✅' if status['config_status']['ai_configured'] else '❌'}")
            print(f"Email Configured: {'✅' if status['config_status']['email_configured'] else '❌'}")
            print(f"GitHub Configured: {'✅' if status['config_status']['github_configured'] else '❌'}")
            print(f"System Ready: {'✅' if status['system_ready'] else '❌'}")
            if status['config_status']['github_pages_url']:
                print(f"GitHub Pages URL: {status['config_status']['github_pages_url']}")
            if status['config_status']['missing_config']:
                print("Missing configuration:")
                for item in status['config_status']['missing_config']:
                    print(f"  - {item}")
        
        elif choice == "6":
            try:
                try:
                    from report_publisher import cleanup_old_reports
                except ImportError:
                    def cleanup_old_reports(days):
                        return False, 0, "Report publisher module not available"
                print(f"\n🧹 Running Report Cleanup...")
                success, count, error = cleanup_old_reports(30)
                if success:
                    print(f"✅ Cleaned up {count} old reports")
                else:
                    print(f"❌ Cleanup failed: {error}")
            except Exception as e:
                print(f"❌ Cleanup error: {e}")
                
        elif choice == "7":
            print(f"\n👋 Goodbye!")
            
        else:
            print(f"\n❌ Invalid choice. Please run again.")
            
    except KeyboardInterrupt:
        print("\n\n⏹️ Cancelled by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()
