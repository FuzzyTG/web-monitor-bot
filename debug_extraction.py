#!/usr/bin/env python3
"""
Debug the blog extraction to understand what's happening
"""

import os
import sys
import traceback
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def debug_extraction():
    """Debug the extraction process step by step"""
    print("🔍 DEBUG: Blog Post Extraction")
    print("=" * 50)
    
    try:
        # Import our function
        from monitor import extract_blog_posts
        
        print("✓ Successfully imported extract_blog_posts function")
        
        # Test direct extraction
        print("\n📥 Testing direct extraction...")
        posts = extract_blog_posts()
        
        print(f"📊 Results: {len(posts)} posts found")
        
        if posts:
            print(f"\n📋 Post List:")
            for i, post in enumerate(posts, 1):
                title = post.get('title', 'Unknown')[:60]
                url = post.get('url', 'Unknown')
                print(f"  {i}. {title}...")
                print(f"     URL: {url}")
        else:
            print("❌ No posts found - this is the problem!")
            
            # Try manual fetch to debug
            print("\n🔧 Manual debugging...")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            url = 'https://cloud.google.com/blog/products/chrome-enterprise/'
            print(f"Fetching: {url}")
            
            response = requests.get(url, headers=headers, timeout=30)
            print(f"Status: {response.status_code}")
            print(f"Content length: {len(response.content)} bytes")
            
            # Check if we can find any links
            soup = BeautifulSoup(response.content, 'html.parser')
            all_links = soup.find_all('a', href=True)
            print(f"Total links found: {len(all_links)}")
            
            blog_links = [link for link in all_links if '/blog/' in link.get('href', '')]
            print(f"Blog links found: {len(blog_links)}")
            
            chrome_links = [link for link in blog_links if 'chrome' in link.get('href', '').lower()]
            print(f"Chrome-related links: {len(chrome_links)}")
            
    except Exception as e:
        print(f"❌ Error during extraction: {e}")
        print(f"Exception type: {type(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    debug_extraction()
