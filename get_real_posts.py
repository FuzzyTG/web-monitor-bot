#!/usr/bin/env python3
"""
Quick test to get real Google Cloud blog URLs for testing
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
from bs4 import BeautifulSoup
from monitor import extract_blog_posts

def get_real_blog_posts():
    """Get real blog posts from Google Cloud blog"""
    try:
        print("Fetching Google Cloud Chrome Enterprise blog...")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        url = "https://cloud.google.com/blog/products/chrome-enterprise"
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        posts = extract_blog_posts(soup)
        
        print(f"Found {len(posts)} posts")
        
        # Show first few posts
        for i, post in enumerate(posts[:3]):
            print(f"\nPost {i+1}:")
            print(f"  Title: {post['title']}")
            print(f"  URL: {post['url']}")
            print(f"  Author: {post['author']}")
        
        return posts
        
    except Exception as e:
        print(f"Error: {e}")
        return []

if __name__ == "__main__":
    posts = get_real_blog_posts()
