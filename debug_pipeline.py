#!/usr/bin/env python3
"""
Debug why only 3 posts are being processed in the pipeline
"""

import os
import traceback
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def debug_pipeline_filtering():
    """Debug why the pipeline is only processing 3 posts"""
    print("🔍 DEBUG: Pipeline Post Processing")
    print("=" * 50)
    
    try:
        from monitor import extract_blog_posts, sort_posts_by_date, get_individual_blog_content
        
        # Step 1: Extract posts
        print("Step 1: Extracting posts...")
        posts = extract_blog_posts()
        print(f"✓ Extracted {len(posts)} posts")
        
        # Step 2: Sort posts
        print("\nStep 2: Sorting posts...")
        sorted_posts = sort_posts_by_date(posts)
        print(f"✓ Sorted {len(sorted_posts)} posts")
        
        # Step 3: Test content extraction for each post
        print(f"\nStep 3: Testing content extraction for all {len(sorted_posts)} posts...")
        print("=" * 60)
        
        successful_extractions = []
        failed_extractions = []
        
        for i, post in enumerate(sorted_posts, 1):
            title = post['title'][:50]
            print(f"\n📖 Testing Post {i}: {title}...")
            
            try:
                enhanced_post = get_individual_blog_content(post)
                if enhanced_post and enhanced_post.get('extraction_success'):
                    successful_extractions.append(enhanced_post)
                    content_len = enhanced_post.get('content_length', 0)
                    print(f"✅ SUCCESS - {content_len} characters extracted")
                else:
                    failed_extractions.append(post)
                    error = enhanced_post.get('extraction_error', 'Unknown error') if enhanced_post else 'No result returned'
                    print(f"❌ FAILED - {error}")
            except Exception as e:
                failed_extractions.append(post)
                print(f"❌ EXCEPTION - {str(e)}")
        
        print(f"\n📊 EXTRACTION RESULTS:")
        print("=" * 30)
        print(f"✅ Successful: {len(successful_extractions)} posts")
        print(f"❌ Failed: {len(failed_extractions)} posts")
        
        if successful_extractions:
            print(f"\n✅ SUCCESSFUL EXTRACTIONS:")
            for i, post in enumerate(successful_extractions, 1):
                title = post['title'][:50]
                content_len = post.get('content_length', 0)
                print(f"  {i}. {title}... ({content_len} chars)")
        
        if failed_extractions:
            print(f"\n❌ FAILED EXTRACTIONS:")
            for i, post in enumerate(failed_extractions, 1):
                title = post['title'][:50]
                url = post.get('url', 'Unknown')
                print(f"  {i}. {title}...")
                print(f"     URL: {url}")
        
        print(f"\n🎯 CONCLUSION:")
        if len(successful_extractions) == 3:
            print("This explains why only 3 posts are processed - content extraction is failing for the other 8 posts!")
        elif len(successful_extractions) == len(sorted_posts):
            print("All posts extract successfully - the issue is elsewhere in the pipeline.")
        else:
            print(f"Mixed results - {len(successful_extractions)} succeed, {len(failed_extractions)} fail.")
            
    except Exception as e:
        print(f"❌ Error during debugging: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    debug_pipeline_filtering()
