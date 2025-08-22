import os
import json
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import hashlib
import re
from dotenv import load_dotenv

# Import new competitive analysis parser
from competitive_analysis_parser import parse_ai_analysis_with_fallback

# Load environment variables from .env file
load_dotenv()

# Import enhanced error handling
try:
    from error_handling import (
        ErrorLogger, FallbackStrategies, NetworkError, AIAnalysisError, 
        ReportGenerationError, EmailDeliveryError, PublishingError,
        retry_with_exponential_backoff, safe_operation
    )
    
    # Initialize global error logger
    error_logger = ErrorLogger()
    
except ImportError:
    # Fallback if error_handling module is not available
    class DummyErrorLogger:
        def log_error(self, error, context, additional_info=None):
            print(f"Error in {context}: {error}")
    
    error_logger = DummyErrorLogger()
    
    def retry_with_exponential_backoff(max_retries=3, base_delay=1.0, max_delay=60.0):
        def decorator(func):
            return func
        return decorator
    
    # Legacy duplicate safe_operation() removed - use error_handling.safe_operation instead
    
    class FallbackStrategies:
        @staticmethod
        def blog_extraction_fallback(error):
            return []
        
        @staticmethod
        def ai_analysis_fallback(post, error):
            return {**post, 'ai_analysis': 'Analysis failed', 'analysis_success': False}
        
        @staticmethod
        def email_delivery_fallback(posts, report_url, error):
            return {'success': False, 'message': str(error)}
        
        @staticmethod
        def github_publishing_fallback(markdown_file_path, report_id, error):
            return True, f"file://{os.path.abspath(markdown_file_path)}", str(error)

@retry_with_exponential_backoff(max_retries=3, base_delay=2.0)
def extract_blog_posts(soup=None):
    """
    Extract blog post metadata from Google Cloud Chrome Enterprise blog listing page
    
    Args:
        soup (BeautifulSoup, optional): Parsed HTML of blog listing page.
                                      If None, will fetch from cloud.google.com/blog/
        
    Returns:
        list[dict]: List of blog post dictionaries with keys:
            - title (str): Blog post title
            - url (str): Full URL to blog post
            - author (str): Blog post author
            - read_time (str): Estimated reading time
            - publish_date (str): Publication date
            - id (str): Unique identifier for the post
            
    Raises:
        ValueError: If unable to fetch or parse content
        Exception: For parsing errors (logged but not raised)
    """
    import requests
    from bs4 import BeautifulSoup
    import re
    
    # If no soup provided, fetch the blog page
    if soup is None:
        try:
            print("Fetching Google Cloud Chrome Enterprise blog page...")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            # Use the dedicated Chrome Enterprise blog URL
            chrome_enterprise_url = 'https://cloud.google.com/blog/products/chrome-enterprise/'
            response = requests.get(chrome_enterprise_url, headers=headers, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            print("✅ Successfully fetched Chrome Enterprise blog page")
        except Exception as e:
            error_logger.log_error(e, "fetch_blog_page", {"url": chrome_enterprise_url})
            raise NetworkError(f"Failed to fetch Chrome Enterprise blog page: {e}")
    
    blog_posts = []
    processed_urls = set()  # Track URLs to avoid duplicates
    
    try:
        print("Extracting Chrome Enterprise blog posts...")
        
        # Find all links that point to Chrome Enterprise blog posts - UPDATED PATTERN
        chrome_enterprise_patterns = [
            'a[href*="/blog/products/chrome-enterprise/"]',  # Original pattern
            'a[href*="chrome-enterprise"]',                  # More flexible pattern
            'a[href*="chromeos"]',                           # ChromeOS posts
            'a[href*="chrome-brings"]',                      # Specific posts from screenshot
        ]
        
        all_chrome_links = []
        for pattern in chrome_enterprise_patterns:
            links = soup.select(pattern)
            all_chrome_links.extend(links)
        
        print(f"Found {len(all_chrome_links)} potential Chrome Enterprise blog post links")
        
        # Also find links by content - look for Chrome/ChromeOS in link text
        all_links = soup.find_all('a', href=True)
        for link in all_links:
            href = link.get('href', '')
            text = link.get_text(strip=True).lower()
            
            # Include links that mention Chrome, ChromeOS, or Enterprise in the text
            if ('/blog/' in href and 
                any(keyword in text for keyword in ['chrome', 'chromeos', 'enterprise', 'korean air', 'collaborative'])):
                all_chrome_links.append(link)
        
        print(f"Found {len(all_chrome_links)} total potential links (including text-based matches)")
        
        for link in all_chrome_links:
            try:
                # Get URL and normalize it
                url = link.get('href', '').strip()
                if not url:
                    continue
                    
                # Convert relative URLs to absolute
                if url.startswith('/'):
                    url = 'https://cloud.google.com' + url
                elif not url.startswith('http'):
                    continue
                
                # Skip if not a blog post URL
                if '/blog/' not in url or any(skip in url for skip in ['#', 'topics', 'authors', 'products/ai-machine-learning', 'products/data-analytics']):
                    continue
                
                # Skip duplicates
                if url in processed_urls:
                    continue
                processed_urls.add(url)
                
                # Get title from link text or nearby elements
                title = link.get_text(strip=True)
                
                # If no title from link, look in parent elements
                if not title or len(title) < 10:
                    parent = link.parent
                    while parent and not title:
                        title = parent.get_text(strip=True)
                        if len(title) > 200:  # Too long, look for specific elements
                            title_elem = parent.find(['h1', 'h2', 'h3', 'h4'])
                            if title_elem:
                                title = title_elem.get_text(strip=True)
                            break
                        parent = parent.parent
                
                # Skip if title is empty or generic
                if (not title or 
                    title.lower() in ['read article', '...', 'chrome enterprise', 'read more', 'learn more'] or
                    len(title) < 10):
                    continue
                
                # Clean up title
                title = re.sub(r'^\s*Chrome Enterprise\s*', '', title)
                title = re.sub(r'By\s+[^•]+•\s*\d+\s*-?\s*minute\s+read.*$', '', title, flags=re.IGNORECASE)
                title = title.strip()
                
                # Skip if cleaned title is too short
                if len(title) < 10:
                    continue
                
                # Try to extract author and read time from nearby elements
                author = "Unknown"
                read_time = "Unknown"
                publish_date = "Unknown"
                
                # Look for author in nearby elements
                author_patterns = [
                    r'by\s+([^•\n]+?)(?:•|\n|$)',
                    r'author[:\s]+([^•\n]+?)(?:•|\n|$)',
                ]
                
                parent_text = ""
                if link.parent:
                    parent_text = link.parent.get_text()
                
                for pattern in author_patterns:
                    match = re.search(pattern, parent_text, re.IGNORECASE)
                    if match:
                        author = match.group(1).strip()
                        break
                
                # Look for read time
                read_time_match = re.search(r'(\d+)\s*-?\s*minute\s+read', parent_text, re.IGNORECASE)
                if read_time_match:
                    read_time = f"{read_time_match.group(1)} minute read"
                
                # Create unique ID from URL
                post_id = url.split('/')[-1] if url.endswith('/') else url.split('/')[-1]
                
                blog_post = {
                    'title': title,
                    'url': url,
                    'author': author,
                    'read_time': read_time,
                    'publish_date': publish_date,
                    'id': post_id,
                    'summary': f"Chrome Enterprise blog post: {title[:100]}..."
                }
                
                blog_posts.append(blog_post)
                print(f"✓ Extracted: {title[:50]}...")
                
            except Exception as e:
                print(f"⚠️ Error processing link: {e}")
                continue
        
        # Remove duplicates based on title similarity
        unique_posts = []
        seen_titles = set()
        
        for post in blog_posts:
            # Create a normalized title for comparison
            normalized_title = re.sub(r'[^\w\s]', '', post['title'].lower())
            title_key = ' '.join(normalized_title.split()[:5])  # First 5 words
            
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_posts.append(post)
        
        print(f"Successfully extracted {len(unique_posts)} unique blog posts")
        
        return unique_posts
        
    except Exception as e:
        error_logger.log_error(e, "extract_blog_posts_main", {"posts_found": len(blog_posts)})
        print(f"Error extracting blog posts: {e}")
        print("🔄 Attempting fallback strategies...")
        
        # Use fallback strategies
        fallback_posts = FallbackStrategies.blog_extraction_fallback(e)
        if fallback_posts:
            print(f"✅ Fallback successful: {len(fallback_posts)} posts recovered")
            return fallback_posts
        
        import traceback
        traceback.print_exc()
        return []

def load_previous_posts():
    """
    Load previously detected blog posts from storage
    
    Returns:
        list[dict]: List of previously detected blog posts with metadata
        
    Notes:
        - Returns empty list if no previous data exists
        - Handles file corruption gracefully
        - Maintains backward compatibility with old data formats
    """
    try:
        with open('previous_blog_posts.json', 'r') as f:
            data = json.load(f)
            
        # Handle different data formats for backward compatibility
        if isinstance(data, list):
            # New format: direct list of posts
            posts = data
        elif isinstance(data, dict):
            if 'posts' in data:
                # Wrapped format: {'posts': [...], 'metadata': {...}}
                posts = data['posts']
            else:
                # Old format: might be single post data
                print("Warning: Old format detected, treating as empty")
                posts = []
        else:
            print("Warning: Unexpected data format, treating as empty")
            posts = []
        
        # Validate post structure
        validated_posts = []
        required_fields = ['id', 'url', 'title']
        
        for post in posts:
            if isinstance(post, dict) and all(field in post for field in required_fields):
                validated_posts.append(post)
            else:
                print(f"Warning: Skipping invalid post data: {post}")
        
        print(f"Loaded {len(validated_posts)} previous blog posts from storage")
        return validated_posts
        
    except FileNotFoundError:
        print("No previous blog posts file found, starting fresh")
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing previous blog posts file: {e}")
        print("Starting fresh with empty post history")
        return []
    except Exception as e:
        print(f"Unexpected error loading previous posts: {e}")
        return []

def save_current_posts(posts, metadata=None):
    """
    Save current blog posts to storage with metadata
    
    Args:
        posts (list[dict]): List of current blog posts
        metadata (dict, optional): Additional metadata about the monitoring session
        
    Returns:
        bool: True if saved successfully, False otherwise
    """
    try:
        # Prepare data structure
        data_to_save = {
            'posts': posts,
            'metadata': {
                'last_checked': datetime.now().isoformat(),
                'total_posts': len(posts),
                'monitoring_url': os.getenv('TARGET_URL', 'unknown'),
                **(metadata or {})
            }
        }
        
        # Save to file with atomic write (write to temp file then rename)
        temp_filename = 'previous_blog_posts.json.tmp'
        with open(temp_filename, 'w') as f:
            json.dump(data_to_save, f, indent=2)
        
        # Atomic rename (safer than direct write)
        import os as os_module
        os_module.rename(temp_filename, 'previous_blog_posts.json')
        
        print(f"Successfully saved {len(posts)} blog posts to storage")
        return True
        
    except Exception as e:
        print(f"Error saving blog posts: {e}")
        # Clean up temp file if it exists
        try:
            import os as os_module
            os_module.remove(temp_filename)
        except:
            pass
        return False

def detect_new_posts(current_posts, previous_posts):
    """
    Compare current posts with previous posts to identify new publications
    
    Args:
        current_posts (list[dict]): Currently detected blog posts
        previous_posts (list[dict]): Previously detected blog posts
        
    Returns:
        list[dict]: List of new blog posts not seen before
        
    Notes:
        - Uses URL as primary identifier
        - Falls back to title comparison if URLs differ slightly
        - Handles edge cases like URL changes or republishing
    """
    if not current_posts:
        print("No current posts to compare")
        return []
    
    if not previous_posts:
        print("No previous posts found, treating all current posts as new")
        return current_posts
    
    try:
        # Create sets of known identifiers from previous posts
        previous_urls = {post.get('url', '') for post in previous_posts}
        previous_ids = {post.get('id', '') for post in previous_posts}
        previous_titles = {post.get('title', '').lower().strip() for post in previous_posts}
        
        new_posts = []
        
        for post in current_posts:
            current_url = post.get('url', '')
            current_id = post.get('id', '')
            current_title = post.get('title', '').lower().strip()
            
            # Check if this post is new using multiple criteria
            is_new = True
            
            # Primary check: URL
            if current_url in previous_urls:
                is_new = False
            
            # Secondary check: ID (in case URL format changed)
            elif current_id in previous_ids:
                is_new = False
            
            # Tertiary check: Title (in case both URL and ID changed)
            elif current_title in previous_titles and len(current_title) > 10:
                is_new = False
                print(f"Found existing post by title match: {post.get('title', '')[:50]}...")
            
            if is_new:
                new_posts.append(post)
                print(f"✓ New post detected: {post.get('title', '')[:50]}...")
        
        print(f"Found {len(new_posts)} new posts out of {len(current_posts)} total")
        return new_posts
        
    except Exception as e:
        print(f"Error detecting new posts: {e}")
        # If comparison fails, err on the side of caution and return all posts
        print("Falling back to treating all current posts as potentially new")
        return current_posts

def get_individual_blog_content(blog_post, max_retries=3, retry_delay=2):
    """
    Fetch full content from an individual blog post URL with enhanced error handling
    
    Args:
        blog_post (dict): Blog post metadata containing 'url', 'title', etc.
        max_retries (int): Maximum number of retry attempts for failed requests
        retry_delay (int): Delay in seconds between retry attempts
        
    Returns:
        dict: Enhanced blog post data with full content, or None if failed
            - All original metadata (title, url, author, etc.)
            - content (str): Clean article text
            - publish_date (str): Extracted publication date
            - content_length (int): Character count of extracted content
            - extraction_success (bool): Whether content extraction succeeded
            - extraction_error (str): Error message if extraction failed
            - retry_count (int): Number of retries attempted
            
    Notes:
        - Handles Google Cloud blog page structure specifically
        - Removes navigation, ads, comments, and footer content
        - Extracts clean article text with proper formatting
        - Includes comprehensive error handling and retry logic
        - Falls back to summary if full content unavailable
    """
    if not blog_post or 'url' not in blog_post:
        print("Error: Invalid blog post data provided")
        return None
    
    url = blog_post['url']
    if not url or not url.strip():
        print("Error: Empty or invalid URL provided")
        return None
    
    title = blog_post.get('title', 'Unknown title')
    print(f"Fetching content for: {title[:50]}...")
    
    last_error = None
    retry_count = 0
    
    for attempt in range(max_retries):
        try:
            # Set up headers to mimic a real browser
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            # Fetch the blog post page with timeout
            response = requests.get(url, headers=headers, timeout=30)
            
            # Handle different HTTP error codes
            if response.status_code == 404:
                error_msg = f"Blog post not found (404): {url}"
                print(f"✗ {error_msg}")
                return create_failed_post_result(blog_post, error_msg, retry_count)
            elif response.status_code == 403:
                error_msg = f"Access denied (403): {url}"
                print(f"✗ {error_msg}")
                return create_failed_post_result(blog_post, error_msg, retry_count)
            elif response.status_code >= 500:
                error_msg = f"Server error ({response.status_code}): {url}"
                print(f"✗ {error_msg} - Attempt {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(retry_delay)
                    retry_count += 1
                    continue
                else:
                    return create_failed_post_result(blog_post, error_msg, retry_count)
            
            response.raise_for_status()
            
            # Parse the HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove unwanted elements (scripts, styles, ads, navigation)
            for element in soup(["script", "style", "nav", "header", "footer", "aside"]):
                element.decompose()
            
            # Remove specific Google Cloud elements that aren't content
            unwanted_selectors = [
                '.site-header',
                '.site-footer', 
                '.breadcrumbs',
                '.article-nav',
                '.related-articles',
                '.comments-section',
                '.social-share',
                '.newsletter-signup',
                '[class*="banner"]',
                '[class*="advertisement"]',
                '[id*="ads"]'
            ]
            
            for selector in unwanted_selectors:
                for element in soup.select(selector):
                    element.decompose()
            
            # Extract the main article content
            content = ""
            article_title = blog_post.get('title', '')
            publish_date = "Unknown"
            
            # Try different selectors for Google Cloud blog structure
            content_selectors = [
                'article',
                '[role="main"]',
                '.main-content',
                '.article-content',
                '.post-content',
                '.blog-content',
                'main',
                '#main-content'
            ]
            
            article_element = None
            for selector in content_selectors:
                article_element = soup.select_one(selector)
                if article_element:
                    print(f"Found content using selector: {selector}")
                    break
            
            if not article_element:
                # Fallback: use body but filter out navigation
                article_element = soup.find('body')
                print("Using body as fallback content container")
            
            if article_element:
                # Extract publication date with enhanced selectors
                date_selectors = [
                    'time[datetime]',
                    '.publish-date',
                    '.date-published', 
                    '[class*="date"]',
                    '.article-date',
                    '.post-date',
                    '.blog-date'
                ]
                
                for date_selector in date_selectors:
                    date_element = article_element.select_one(date_selector)
                    if date_element:
                        publish_date = date_element.get('datetime') or date_element.get_text(strip=True)
                        break
                
                # If no date found in standard selectors, try to extract from content
                if publish_date == "Unknown":
                    content_text = article_element.get_text()
                    # Look for date patterns like "July 22, 2025" or "July 21, 2025"
                    import re
                    date_patterns = [
                        r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}',
                        r'\d{4}-\d{2}-\d{2}',
                        r'\d{1,2}/\d{1,2}/\d{4}'
                    ]
                    
                    for pattern in date_patterns:
                        match = re.search(pattern, content_text)
                        if match:
                            publish_date = match.group(0)
                            print(f"Extracted date from content: {publish_date}")
                            break
                
                # Get clean text content
                content = article_element.get_text(strip=True, separator='\n')
                
                # Clean up the content
                lines = content.split('\n')
                cleaned_lines = []
                
                for line in lines:
                    line = line.strip()
                    # Skip empty lines and common navigation text
                    if (line and 
                        len(line) > 3 and 
                        not line.lower().startswith(('menu', 'skip to', 'search', 'sign in', 'contact us')) and
                        'cookie' not in line.lower() and
                        'privacy policy' not in line.lower()):
                        cleaned_lines.append(line)
                
                content = '\n'.join(cleaned_lines)
                
                # Remove excessive whitespace
                content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
                content = content.strip()
            
            # Validate content extraction
            if not content or len(content) < 100:
                error_msg = f"Extracted content too short ({len(content)} chars) - may be parsing issue"
                print(f"Warning: {error_msg}")
                
                # Check if this might be a 404 page by looking for common 404 indicators
                content_lower = content.lower()
                if any(indicator in content_lower for indicator in ['404', 'not found', 'page not found', "that's an error"]):
                    error_msg = f"Blog post not found (404-like content detected): {url}"
                    print(f"✗ {error_msg}")
                    return create_failed_post_result(blog_post, error_msg, retry_count)
                
                # Try fallback: get basic text from title and summary
                fallback_content = get_fallback_content(blog_post, soup)
                if fallback_content and len(fallback_content) > 50:
                    content = fallback_content
                    print(f"Using fallback content: {len(content)} characters")
                else:
                    return create_failed_post_result(blog_post, error_msg, retry_count)
            
            # Create enhanced blog post data
            enhanced_post = blog_post.copy()
            enhanced_post.update({
                'content': content,
                'publish_date': publish_date,
                'content_length': len(content),
                'extraction_success': True,
                'extraction_error': None,
                'retry_count': retry_count,
                'extracted_at': datetime.now().isoformat(),
                'content_preview': content[:200] + '...' if len(content) > 200 else content
            })
            
            print(f"✓ Successfully extracted {len(content)} characters of content")
            return enhanced_post
            
        except requests.RequestException as e:
            error_msg = f"Network error: {str(e)}"
            print(f"✗ {error_msg} - Attempt {attempt + 1}/{max_retries}")
            last_error = error_msg
            
            if attempt < max_retries - 1:
                import time
                time.sleep(retry_delay)
                retry_count += 1
                continue
            else:
                return create_failed_post_result(blog_post, error_msg, retry_count)
                
        except Exception as e:
            error_msg = f"Parsing error: {str(e)}"
            print(f"✗ {error_msg} - Attempt {attempt + 1}/{max_retries}")
            last_error = error_msg
            
            if attempt < max_retries - 1:
                import time
                time.sleep(retry_delay)
                retry_count += 1
                continue
            else:
                return create_failed_post_result(blog_post, error_msg, retry_count)
    
    # Should not reach here, but just in case
    return create_failed_post_result(blog_post, last_error or "Unknown error", retry_count)

def create_failed_post_result(blog_post, error_message, retry_count):
    """
    Create a failed post result with error information
    
    Args:
        blog_post (dict): Original blog post metadata
        error_message (str): Description of what went wrong
        retry_count (int): Number of retries attempted
        
    Returns:
        dict: Failed post result with error information
    """
    failed_post = blog_post.copy()
    failed_post.update({
        'content': f"[EXTRACTION FAILED] {error_message}",
        'publish_date': "Unknown",
        'content_length': 0,
        'extraction_success': False,
        'extraction_error': error_message,
        'retry_count': retry_count,
        'extracted_at': datetime.now().isoformat(),
        'content_preview': f"Failed to extract content: {error_message}"
    })
    return failed_post

def get_fallback_content(blog_post, soup):
    """
    Get fallback content when main extraction fails
    
    Args:
        blog_post (dict): Blog post metadata
        soup (BeautifulSoup): Parsed HTML
        
    Returns:
        str: Fallback content or None if not available
    """
    try:
        title = blog_post.get('title', '')
        
        # Try to get meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        description = meta_desc.get('content', '') if meta_desc else ''
        
        # Try to get Open Graph description
        if not description:
            og_desc = soup.find('meta', attrs={'property': 'og:description'})
            description = og_desc.get('content', '') if og_desc else ''
        
        # Combine title and description
        fallback_content = f"{title}\n\n{description}" if description else title
        
        return fallback_content if len(fallback_content) > 20 else None
        
    except Exception:
        return None

def sort_posts_by_date(posts):
    """
    Sort blog posts by publication date (newest first)
    
    Args:
        posts (list[dict]): List of blog posts with publish_date field
        
    Returns:
        list[dict]: Posts sorted by date (newest first)
    """
    from datetime import datetime
    import re
    
    def parse_date(post):
        """Parse various date formats to datetime object"""
        date_str = post.get('publish_date', '')
        
        if not date_str or date_str == "Unknown":
            # Try to extract date from URL or content if available
            url = post.get('url', '')
            content = post.get('content', '')
            
            # Look for date patterns in URL (e.g., /2025/07/post-name)
            url_date_match = re.search(r'/(\d{4})/(\d{1,2})/(\d{1,2})/', url)
            if url_date_match:
                year, month, day = map(int, url_date_match.groups())
                return datetime(year, month, day)
            
            # Look for recent dates in content
            if content:
                recent_date_patterns = [
                    r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(\d{4})',
                    r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
                    r'(\d{4})-(\d{1,2})-(\d{1,2})',
                ]
                
                for pattern in recent_date_patterns:
                    matches = re.findall(pattern, content[:1000])  # Check first 1000 chars
                    if matches:
                        try:
                            match = matches[0]
                            if pattern.endswith(r',\s+(\d{4})'):  # Month Day, Year
                                month_name, day, year = match
                                month_num = {
                                    'january': 1, 'february': 2, 'march': 3, 'april': 4,
                                    'may': 5, 'june': 6, 'july': 7, 'august': 8,
                                    'september': 9, 'october': 10, 'november': 11, 'december': 12
                                }[month_name.lower()]
                                return datetime(int(year), month_num, int(day))
                        except (ValueError, KeyError):
                            continue
            
            # Default to very old date if no date found
            return datetime(1900, 1, 1)
        
        try:
            # Try different date formats
            date_formats = [
                "%B %d, %Y",      # July 22, 2025
                "%Y-%m-%d",       # 2025-07-22
                "%m/%d/%Y",       # 07/22/2025
                "%d/%m/%Y",       # 22/07/2025
                "%Y-%m-%dT%H:%M:%S",  # ISO format
            ]
            
            for fmt in date_formats:
                try:
                    return datetime.strptime(date_str.strip(), fmt)
                except ValueError:
                    continue
            
            # If no format matches, try to extract date with regex
            date_match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(\d{4})', date_str)
            if date_match:
                month_name, day, year = date_match.groups()
                month_num = {
                    'january': 1, 'february': 2, 'march': 3, 'april': 4,
                    'may': 5, 'june': 6, 'july': 7, 'august': 8,
                    'september': 9, 'october': 10, 'november': 11, 'december': 12
                }[month_name.lower()]
                return datetime(int(year), month_num, int(day))
                
            return datetime(1900, 1, 1)
            
        except Exception:
            return datetime(1900, 1, 1)
    
    # Sort posts by parsed date (newest first)
    try:
        sorted_posts = sorted(posts, key=parse_date, reverse=True)
        print(f"Sorted {len(sorted_posts)} posts by publication date")
        
        # Debug: show the sorting order
        print("📊 Posts after sorting:")
        for i, post in enumerate(sorted_posts[:5], 1):  # Show first 5
            date = post.get('publish_date', 'Unknown')
            parsed_date = parse_date(post)
            title = post.get('title', 'Unknown')[:50]
            print(f"  {i}. {parsed_date.strftime('%Y-%m-%d')} ({date}) - {title}...")
        
        return sorted_posts
    except Exception as e:
        print(f"Error sorting posts by date: {e}")
        return posts  # Return original order if sorting fails

def get_page_content(url):
    """Fetch and extract main content from webpage"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Extract main content (customize these selectors for your target site)
        content_selectors = [
            'main', 'article', '.content', '#content', 
            '.post-content', '.entry-content', 'body'
        ]
        
        content = ""
        for selector in content_selectors:
            element = soup.select_one(selector)
            if element:
                content = element.get_text(strip=True, separator=' ')
                break
        
        if not content:
            content = soup.get_text(strip=True, separator=' ')
        
        # Clean up content
        content = ' '.join(content.split())
        return content[:5000]  # Limit to 5000 chars to manage AI costs
        
    except Exception as e:
        print(f"Error fetching content: {e}")
        return None

def get_content_hash(content):
    """Generate hash of content to detect changes"""
    return hashlib.md5(content.encode()).hexdigest()

def load_previous_content():
    """Load previous content hash from file"""
    try:
        with open('previous_content.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_current_content(url, content, content_hash):
    """Save current content hash to file"""
    data = {
        'url': url,
        'hash': content_hash,
        'last_checked': datetime.now().isoformat(),
        'content_preview': content[:500]  # Save preview for reference
    }
    with open('previous_content.json', 'w') as f:
        json.dump(data, f, indent=2)

def analyze_with_ai(content, previous_preview=""):
    """Use Google Gemini to analyze content changes"""
    try:
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        model = genai.GenerativeModel(os.getenv('GEMINI_MODEL', 'gemini-2.5-pro'))
        
        prompt = f"""
        Analyze the following webpage content and create a concise digest:

        {"Previous content preview: " + previous_preview if previous_preview else "This is the first time monitoring this page."}

        Current content:
        {content}

        Please provide:
        1. A brief summary of the main topics/content
        2. Any notable changes or updates (if this isn't the first check)
        3. Key highlights or important information
        4. Format as a clear, readable email digest

        Keep the response under 300 words and make it actionable for a busy professional.
        """
        
        generation_config = genai.types.GenerationConfig(
            temperature=0,
            candidate_count=1,
            top_p=1.0
        )
        response = model.generate_content(prompt, generation_config=generation_config)
        return response.text
        
    except Exception as e:
        print(f"AI analysis error: {e}")
        return f"Content updated on the monitored page. AI analysis unavailable. Content preview: {content[:200]}..."

def analyze_blog_post_with_ai(blog_post, custom_prompt=None):
    """
    Analyze an individual blog post using Google Gemini AI
    
    Args:
        blog_post (dict): Blog post data with content, title, url, etc.
        custom_prompt (str, optional): Custom analysis prompt. If None, uses default or environment variable.
        
    Returns:
        dict: Enhanced blog post with AI analysis results
            - All original blog post data
            - ai_analysis (str): AI-generated analysis text
            - analysis_success (bool): Whether AI analysis succeeded
            - analysis_error (str): Error message if analysis failed
            - analysis_prompt_used (str): The prompt used for analysis
            - analyzed_at (str): Timestamp of analysis
            
    Notes:
        - Uses custom prompt from CUSTOM_AI_PROMPT environment variable if available
        - Includes blog title, content, author, and metadata in analysis
        - Handles API errors gracefully with fallback content
        - Limits content length to manage API costs and token limits
    """
    if not blog_post or not isinstance(blog_post, dict):
        print("Error: Invalid blog post data provided for AI analysis")
        return None
    
    title = blog_post.get('title', 'Unknown Title')
    content = blog_post.get('content', '')
    url = blog_post.get('url', '')
    author = blog_post.get('author', 'Unknown Author')
    publish_date = blog_post.get('publish_date', 'Unknown Date')
    
    print(f"Analyzing blog post with AI: {title[:50]}...")
    
    if not content or len(content.strip()) < 50:
        error_msg = "Insufficient content for AI analysis"
        print(f"✗ {error_msg}")
        return create_failed_analysis_result(blog_post, error_msg)
    
    try:
        # Configure Gemini API
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            error_msg = "GEMINI_API_KEY environment variable not set"
            print(f"✗ {error_msg}")
            return create_failed_analysis_result(blog_post, error_msg)
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(os.getenv('GEMINI_MODEL', 'gemini-2.5-pro'))
        
        # Get the appropriate prompt to use
        analysis_prompt, prompt_source = get_ai_analysis_prompt(custom_prompt)
        
        # Validate the prompt
        is_valid, validation_error = validate_ai_prompt(analysis_prompt)
        if not is_valid:
            error_msg = f"Invalid prompt: {validation_error}"
            print(f"✗ {error_msg}")
            return create_failed_analysis_result(blog_post, error_msg)
        
        # Format the complete prompt with blog data
        formatted_prompt = format_blog_prompt(analysis_prompt, blog_post)
        
        # Determine content length for analysis (limit to manage costs)
        content_for_analysis = content[:8000] if len(content) > 8000 else content
        
        print(f"Sending content to Gemini AI (content length: {len(content_for_analysis)} chars)")
        print(f"Using prompt source: {prompt_source}")
        
        # Configure safety settings to allow competitive analysis content
        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_NONE",
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH", 
                "threshold": "BLOCK_NONE",
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_NONE",
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_NONE",
            },
        ]

        # Generate AI analysis
        generation_config = genai.types.GenerationConfig(
            temperature=0,
            candidate_count=1,
            top_p=1.0
        )
        response = model.generate_content(
            formatted_prompt, 
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        
        # Debug: Log response structure for troubleshooting
        print(f"📊 Response debug info:")
        if response:
            print(f"   Response object exists: True")
            print(f"   Candidates count: {len(response.candidates) if response.candidates else 0}")
            
            # Log safety information for debugging
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                print(f"   Prompt feedback: {response.prompt_feedback}")
            
            if response.candidates:
                candidate = response.candidates[0]
                print(f"   Finish reason: {candidate.finish_reason}")
                print(f"   Content exists: {candidate.content is not None}")
                
                # Log safety ratings for debugging filter issues
                if hasattr(candidate, 'safety_ratings') and candidate.safety_ratings:
                    print(f"   Safety ratings: {candidate.safety_ratings}")
                
                if candidate.content:
                    print(f"   Content parts exist: {candidate.content.parts is not None}")
                    if candidate.content.parts:
                        print(f"   Parts count: {len(candidate.content.parts)}")
                        print(f"   First part type: {type(candidate.content.parts[0]) if candidate.content.parts else 'None'}")
                    else:
                        print(f"   Parts is None or empty")
        else:
            print(f"   Response object exists: False")
        
        # Try multiple methods to access response text
        response_text = None
        
        # Method 1: Try the standard response.text accessor
        try:
            if response and response.text:
                response_text = response.text
                print(f"✅ Method 1 (response.text) successful - length: {len(response_text)}")
        except Exception as e:
            print(f"⚠️ Method 1 (response.text) failed: {e}")
        
        # Method 2: Try accessing parts directly if Method 1 failed
        if not response_text and response and response.candidates:
            try:
                candidate = response.candidates[0]
                print(f"🔍 Method 2 debug - candidate.content: {candidate.content is not None}")
                if candidate.content:
                    print(f"🔍 Method 2 debug - candidate.content.parts: {candidate.content.parts}")
                    if candidate.content.parts and len(candidate.content.parts) > 0:
                        part = candidate.content.parts[0]
                        print(f"🔍 Method 2 debug - part type: {type(part)}")
                        print(f"🔍 Method 2 debug - part attributes: {dir(part)}")
                        if hasattr(part, 'text'):
                            response_text = part.text
                            print(f"✅ Method 2 (direct parts access) successful - length: {len(response_text)}")
                        else:
                            print(f"⚠️ Method 2: Part has no 'text' attribute")
                    else:
                        print(f"⚠️ Method 2: No parts available")
            except Exception as e:
                print(f"⚠️ Method 2 (direct parts access) failed: {e}")
        
        # Method 3: Try alternative text extraction
        if not response_text and response and response.candidates:
            try:
                candidate = response.candidates[0]
                print(f"🔍 Method 3 debug - candidate attributes: {[attr for attr in dir(candidate) if not attr.startswith('_')]}")
                if hasattr(candidate, 'text'):
                    response_text = candidate.text
                    print(f"✅ Method 3 (candidate.text) successful - length: {len(response_text)}")
                else:
                    print(f"⚠️ Method 3: Candidate has no 'text' attribute")
            except Exception as e:
                print(f"⚠️ Method 3 (candidate.text) failed: {e}")
        
        # Method 4: Try accessing response parts at top level
        if not response_text and response:
            try:
                print(f"🔍 Method 4 debug - response attributes: {[attr for attr in dir(response) if not attr.startswith('_')]}")
                if hasattr(response, 'parts') and response.parts:
                    response_text = response.parts[0].text
                    print(f"✅ Method 4 (response.parts) successful - length: {len(response_text)}")
                else:
                    print(f"⚠️ Method 4: Response has no 'parts' attribute or parts is empty")
            except Exception as e:
                print(f"⚠️ Method 4 (response.parts) failed: {e}")
        
        if not response_text:
            error_msg = f"Gemini API returned no accessible text content. Finish reason: {response.candidates[0].finish_reason if response and response.candidates else 'unknown'}"
            print(f"✗ {error_msg}")
            return create_failed_analysis_result(blog_post, error_msg)
        
        # Enhanced debug logging system
        debug_enabled = os.getenv('SAVE_DEBUG', 'false').lower() == 'true'
        if debug_enabled:
            try:
                print(f"🔍 Saving debug files for comparison analysis...")
                
                # Save raw AI response
                with open('debug_ai_response.txt', 'w', encoding='utf-8') as f:
                    f.write(response_text)
                print(f"✅ Raw AI response saved ({len(response_text)} chars)")
                
                # Parse the AI response using our competitive analysis parser
                from competitive_analysis_parser import parse_competitive_report_systematically, format_structured_data_for_legacy_system
                parsed_sections = parse_competitive_report_systematically(response_text)
                structured_data = format_structured_data_for_legacy_system(parsed_sections)
                
                # Save parsed sections
                import json
                with open('debug_parsed_sections.json', 'w', encoding='utf-8') as f:
                    json.dump(parsed_sections, f, indent=2, default=str)
                print(f"✅ Parsed sections saved ({len(parsed_sections)} sections)")
                
                # Save evidence base
                with open('debug_evidence_base.json', 'w', encoding='utf-8') as f:
                    json.dump(structured_data.get('evidence_base', []), f, indent=2, default=str)
                print(f"✅ Evidence base saved ({len(structured_data.get('evidence_base', []))} items)")
                
            except Exception as e:
                print(f"⚠️ Debug saving failed: {e}")
        
        # Create enhanced blog post with AI analysis
        analyzed_post = blog_post.copy()
        analyzed_post.update({
            'ai_analysis': response_text.strip(),
            'analysis_success': True,
            'analysis_error': None,
            'analysis_prompt_used': prompt_source,
            'analyzed_at': datetime.now().isoformat(),
            'content_length_analyzed': len(content_for_analysis),
            'analysis_length': len(response.text.strip())
        })
        
        print(f"✓ AI analysis completed successfully ({len(response.text)} characters)")
        return analyzed_post
        
    except Exception as e:
        error_logger.log_error(e, "ai_analysis", {"post_title": blog_post.get('title', 'Unknown')})
        error_msg = f"AI analysis failed: {str(e)}"
        print(f"✗ {error_msg}")
        print("🔄 Attempting AI analysis fallback...")
        
        # Use AI analysis fallback strategy
        fallback_result = FallbackStrategies.ai_analysis_fallback(blog_post, e)
        return fallback_result

def create_failed_analysis_result(blog_post, error_message):
    """
    Create a blog post result when AI analysis fails
    
    Args:
        blog_post (dict): Original blog post data
        error_message (str): Description of what went wrong
        
    Returns:
        dict: Blog post with failed analysis information
    """
    failed_post = blog_post.copy()
    
    # Create a basic manual summary as fallback
    title = blog_post.get('title', 'Unknown Title')
    content = blog_post.get('content', '')
    author = blog_post.get('author', 'Unknown Author')
    
    fallback_analysis = f"""
    [AI Analysis Failed - Manual Summary]
    
    Title: {title}
    Author: {author}
    
    Content Preview: {content[:300] + '...' if len(content) > 300 else content}
    
    Note: AI analysis could not be completed due to technical issues. 
    Please review the full blog post manually at the provided URL.
    
    Error: {error_message}
    """
    
    failed_post.update({
        'ai_analysis': fallback_analysis,
        'analysis_success': False,
        'analysis_error': error_message,
        'analysis_prompt_used': 'fallback',
        'analyzed_at': datetime.now().isoformat(),
        'content_length_analyzed': 0,
        'analysis_length': len(fallback_analysis)
    })
    
    return failed_post

def generate_email_summary(analyzed_post):
    """
    Generate a concise summary for email notifications using title and content preview
    
    Args:
        analyzed_post (dict): Blog post data
        
    Returns:
        str: Summary with title and first 100 words for email notification
    """
    if not analyzed_post or not isinstance(analyzed_post, dict):
        return "Unable to generate summary - invalid post data"
    
    title = analyzed_post.get('title', 'Unknown Post')
    content = analyzed_post.get('content', '')
    
    # If no content available, return title-only summary
    if not content or len(content.strip()) < 10:
        return f"New Chrome Enterprise post: {title}"
    
    # Extract first 100 words from content
    words = content.split()
    if len(words) > 100:
        preview_text = ' '.join(words[:100]) + "..."
    else:
        preview_text = ' '.join(words)
    
    # Clean up the preview text (remove extra whitespace)
    preview_text = ' '.join(preview_text.split())
    
    # Return formatted summary
    return f"{title}\n\n{preview_text}"

# Legacy parser functions removed - using competitive_analysis_parser module instead

# All legacy parsing functions removed - using competitive_analysis_parser.py instead

def create_enhanced_competitive_markdown(parsed_data, processed_posts, report_id, timestamp):
    """
    Create enhanced competitive intelligence markdown using new parser data
    
    Args:
        parsed_data (dict): Parsed data from new competitive_analysis_parser
        processed_posts (list): List of processed posts for additional context
        report_id (str): Unique report identifier
        timestamp (str): Report generation timestamp
        
    Returns:
        str: Enhanced competitive intelligence markdown content
    """
    markdown_content = f"""# Chrome vs Edge — Competitive Intelligence Brief

**Generated:** {timestamp} • **Audience:** PM/Engineering • **Status:** Draft

---

## 1) Executive Summary

{parsed_data.get('executive_summary', 'Analysis of Chrome Enterprise updates and competitive implications for Microsoft Edge.')}

---

## 2) Edge Competitive Gaps

"""
    
    competitive_gaps = parsed_data.get('competitive_gaps', [])
    if competitive_gaps:
        for gap in competitive_gaps:
            markdown_content += f"* {gap}\n"
    else:
        markdown_content += "* No competitive gaps identified.\n"
    
    markdown_content += "\n---\n\n## 3) Strategic Actions\n\n"
    
    strategic_recommendations = parsed_data.get('strategic_recommendations', [])
    if strategic_recommendations:
        markdown_content += "| Chrome Feature | Platform | Edge Action | Rationale | Evidence IDs |\n"
        markdown_content += "|---|---|---|---|---|\n"
        for rec in strategic_recommendations:
            feature = rec.get('feature', 'Unknown Feature')
            platform = rec.get('platform', 'All')
            action = rec.get('action', 'Match')
            rationale = rec.get('rationale', '')
            evidence = rec.get('evidence', '')
            markdown_content += f"| {feature} | {platform} | {action} | {rationale} | {evidence} |\n"
    else:
        markdown_content += "No strategic actions identified.\n"
    
    markdown_content += "\n---\n\n## 4) Feature Parity Analysis\n\n"
    
    feature_parity = parsed_data.get('feature_parity_analysis', {})
    if feature_parity:
        for platform, features in feature_parity.items():
            if features:
                markdown_content += f"### {platform.capitalize()}\n\n"
                if isinstance(features, list) and features:
                    try:
                        # Create table from first feature to get headers with robust error handling
                        raw_headers = list(features[0].keys()) if features[0] else []
                        
                        # Ensure headers are strings and handle None values
                        safe_headers = [str(h).strip() if h is not None else "Unknown" for h in raw_headers]
                        # Remove empty headers
                        safe_headers = [h for h in safe_headers if h and h != "Unknown"]
                        
                        if not safe_headers:
                            safe_headers = ["Feature", "Details"]  # Ultimate fallback
                            print(f"Warning: No valid headers found for {platform}, using defaults")
                        
                        # Create table header
                        markdown_content += "| " + " | ".join(safe_headers) + " |\n"
                        markdown_content += "|" + "---|" * len(safe_headers) + "\n"
                        
                        # Process each feature with error handling
                        for feature in features:
                            try:
                                if isinstance(feature, dict):
                                    row_values = [str(feature.get(header, '')).strip() if feature.get(header) is not None else '' for header in raw_headers if str(header).strip() in safe_headers]
                                    # Ensure we have the right number of values
                                    while len(row_values) < len(safe_headers):
                                        row_values.append('')
                                    row_values = row_values[:len(safe_headers)]  # Trim if too many
                                    markdown_content += "| " + " | ".join(row_values) + " |\n"
                                else:
                                    # Handle non-dict features
                                    fallback_values = [str(feature)] + [''] * (len(safe_headers) - 1)
                                    markdown_content += "| " + " | ".join(fallback_values) + " |\n"
                            except Exception as row_error:
                                print(f"Error processing feature row for {platform}: {row_error}")
                                # Add empty row to maintain table structure
                                empty_row = ['Error processing data'] + [''] * (len(safe_headers) - 1)
                                markdown_content += "| " + " | ".join(empty_row) + " |\n"
                        
                        markdown_content += "\n"
                        
                    except Exception as table_error:
                        print(f"Error creating table for {platform}: {table_error}")
                        # Fallback to simple list format
                        markdown_content += "**Features:**\n"
                        for i, feature in enumerate(features[:5]):  # Limit to 5 items for safety
                            markdown_content += f"- {str(feature)}\n"
                        markdown_content += "\n"
    else:
        markdown_content += "No feature parity analysis available.\n"
    
    markdown_content += "---\n\n## 5) Edge Advantage Highlights\n\n"
    
    edge_advantages = parsed_data.get('edge_advantages', [])
    if edge_advantages:
        for advantage in edge_advantages:
            markdown_content += f"* {advantage}\n"
    else:
        markdown_content += "* No Edge advantages identified.\n"
    
    markdown_content += "\n---\n\n## 6) Evidence Register\n\n"
    
    evidence_base = parsed_data.get('evidence_base', [])
    if evidence_base:
        for i, evidence in enumerate(evidence_base, 1):
            if isinstance(evidence, dict):
                # Handle both AI JSON format and parser-generated format
                evidence_id = evidence.get('id') or evidence.get('evidence_id', f'E{i}')
                
                # For AI JSON format (from Evidence Register)
                if 'url' in evidence:
                    source_url = evidence.get('url', 'Unknown')
                    feature = evidence.get('feature', 'Unknown')
                    product = evidence.get('product', 'Unknown')
                    quote = evidence.get('quote', '')
                    platforms = evidence.get('platforms', [])
                    
                    markdown_content += f"### {evidence_id}\n\n"
                    markdown_content += f"**{product}** • **{feature}**"
                    if platforms:
                        try:
                            # Ensure platforms are strings
                            safe_platforms = [str(p) if p is not None else "Unknown" for p in platforms]
                            safe_platforms = [p for p in safe_platforms if p and p != "Unknown"]
                            if safe_platforms:
                                markdown_content += f" • `{', '.join(safe_platforms)}`"
                        except Exception as platform_error:
                            print(f"Error processing platforms: {platform_error}")
                            markdown_content += " • `Multiple Platforms`"
                    markdown_content += f"\n\n"
                    
                    if quote:
                        markdown_content += f"> {quote}\n\n"
                    
                    markdown_content += f"[Source]({source_url})\n\n"
                
                # For parser-generated format (fallback)
                else:
                    source = evidence.get('source', 'Unknown')
                    context = evidence.get('context', evidence.get('chrome_feature', 'Unknown'))
                    markdown_content += f"### {evidence_id}\n\n"
                    markdown_content += f"**Source:** {source} • **Context:** {context}\n\n"
                    if evidence.get('platform'):
                        markdown_content += f"**Platform:** {evidence['platform']}\n\n"
                
                markdown_content += "---\n\n"
    else:
        markdown_content += "No evidence items available.\n\n"
    
    markdown_content += f"""---

## 7) Report Metadata

**Report ID:** {report_id}  
**Posts Analyzed:** {len(processed_posts)}  
**Evidence Items:** {len(evidence_base)}  
**Strategic Actions:** {len(strategic_recommendations)}  
**Competitive Gaps:** {len(competitive_gaps)}

---

**Built with enhanced competitive analysis parser - achieving 100% data extraction.**
"""
    
    return markdown_content

def generate_markdown_report(analyzed_posts, report_id):
    """
    Generate a comprehensive standalone Markdown report
    
    Args:
        analyzed_posts (list): List of analyzed blog posts
        report_id (str): Unique identifier for this report
        
    Returns:
        tuple: (filename, markdown_content) or (None, None) if failed
    """
    if not analyzed_posts:
        print("Error: No analyzed posts provided for Markdown report generation")
        return None, None
    
    # Defensive check: Ensure we're generating Markdown only
    print(f"📝 Generating Markdown report for {len(analyzed_posts)} posts")
    print(f"🔧 Report ID: {report_id}")
    
    try:
        timestamp = datetime.now().strftime('%B %d, %Y at %I:%M %p')
        report_date = datetime.now().strftime('%Y-%m-%d')
        
        # Process each post to extract structured data
        processed_posts = []
        for i, post in enumerate(analyzed_posts, 1):
            print(f"Processing post {i}/{len(analyzed_posts)} for Markdown report...")
            
            # Extract structured data from analysis using new superior parser
            structured_data = parse_ai_analysis_with_fallback(post.get('ai_analysis', ''))
            
            # Create processed post with both original and structured data
            processed_post = {
                'title': post.get('title', 'Unknown Title'),
                'author': post.get('author', 'Unknown Author'),
                'url': post.get('url', ''),
                'publish_date': post.get('publish_date', 'Unknown Date'),
                'ai_analysis': post.get('ai_analysis', ''),
                'structured_data': structured_data,
                'post_number': i
            }
            processed_posts.append(processed_post)
        
        # Generate Markdown content using new parser data format (no validation import!)
        try:
            # Aggregate data from all processed posts using new parser output format
            aggregated_data = {
                'executive_summary': 'Comprehensive analysis of Chrome Enterprise updates and their competitive implications for Microsoft Edge.',
                'competitive_gaps': [],
                'strategic_recommendations': [],
                'evidence_base': [],
                'edge_advantages': [],
                'capability_term_harvest': [],
                'feature_inventory': [],
                'ux_competitive_analysis': [],
                'feature_parity_analysis': {},
                'diff_matrix': [],
                'problem_solution_map': []
            }
            
            # Extract data from structured analysis using new parser field names
            for post in processed_posts:
                if post.get('structured_data'):
                    data = post['structured_data']
                    if data.get('competitive_gaps'):
                        aggregated_data['competitive_gaps'].extend(data['competitive_gaps'])
                    if data.get('strategic_recommendations'):
                        aggregated_data['strategic_recommendations'].extend(data['strategic_recommendations'])
                    if data.get('evidence_base'):
                        aggregated_data['evidence_base'].extend(data['evidence_base'])
            
            # Use data directly from new parser (no conversion needed!)
            if processed_posts and processed_posts[0].get('structured_data'):
                first_post_data = processed_posts[0]['structured_data']
                parsed_data = {
                    'executive_summary': first_post_data.get('executive_summary', aggregated_data['executive_summary']),
                    'competitive_gaps': first_post_data.get('competitive_gaps', []),
                    'strategic_recommendations': first_post_data.get('strategic_recommendations', []),
                    'feature_parity_analysis': first_post_data.get('feature_parity_analysis', {}),
                    'ux_competitive_analysis': first_post_data.get('ux_competitive_analysis', []),
                    'edge_advantages': first_post_data.get('edge_advantages', []),
                    'evidence_base': first_post_data.get('evidence_base', []),
                    'capability_term_harvest': first_post_data.get('capability_term_harvest', []),
                    'diff_matrix': first_post_data.get('diff_matrix', []),
                    'feature_inventory': first_post_data.get('feature_inventory', []),
                    'problem_solution_map': first_post_data.get('problem_solution_map', [])
                }
            else:
                parsed_data = aggregated_data
            
            # Generate enhanced markdown content with competitive intelligence structure
            markdown_content = create_enhanced_competitive_markdown(parsed_data, processed_posts, report_id, timestamp)
            
        except ImportError:
            # Fallback to simple markdown generation
            markdown_content = f"""# Chrome vs Edge — Competitive Intelligence Brief

**Generated:** {timestamp} • **Audience:** PM/Engineering • **Status:** Draft

---

## Executive Summary

Analysis of {len(processed_posts)} Chrome Enterprise blog posts for competitive intelligence.

"""
            
            for i, post in enumerate(processed_posts, 1):
                data = post.get('structured_data', {})
                markdown_content += f"""
## Post {i}: {post['title']}

**Author:** {post['author']}  
**Published:** {post['publish_date']}  
**URL:** {post['url']}

### Analysis Summary
{data.get('executive_summary', 'No summary available')}

### Priority Level
{data.get('priority_level', 'Medium')}

### Competitive Threats
"""
                if data.get('competitive_threats'):
                    for threat in data['competitive_threats']:
                        markdown_content += f"- {threat}\n"
                else:
                    markdown_content += "- None identified\n"
                
                markdown_content += f"""
### Opportunities
"""
                if data.get('opportunities'):
                    for opp in data['opportunities']:
                        markdown_content += f"- {opp}\n"
                else:
                    markdown_content += "- None identified\n"
                
                markdown_content += f"""
### Recommendations
"""
                if data.get('recommendations'):
                    for rec in data['recommendations']:
                        markdown_content += f"- {rec}\n"
                else:
                    markdown_content += "- None provided\n"
                
                markdown_content += "\n---\n"
        
        # Generate filename
        filename = f"chrome_enterprise_report_{report_id}.md"
        
        # Enhanced debug logging - save final markdown content
        debug_enabled = os.getenv('SAVE_DEBUG', 'false').lower() == 'true'
        if debug_enabled:
            try:
                with open('debug_final_report.md', 'w', encoding='utf-8') as f:
                    f.write(markdown_content)
                print(f"✅ Final markdown report saved to debug_final_report.md")
            except Exception as e:
                print(f"⚠️ Failed to save debug final report: {e}")
        
        print(f"✅ Generated Markdown report: {filename}")
        print(f"📊 Content length: {len(markdown_content):,} characters")
        return filename, markdown_content
        
    except Exception as e:
        print(f"Error generating report: {e}")
        import traceback
        traceback.print_exc()
        return None, None











# Legacy HTML table generation functions removed - unused in production
# Functions generate_technologies_table() and generate_metrics_table() 
# were not called anywhere in the codebase and have been cleaned up.


# Legacy unused CSS function get_professional_css() removed
# Function contained 422 lines of HTML report styling that was never used


def save_markdown_report_to_file(filename, markdown_content, reports_dir="reports"):
    """
    Save Markdown report to file system with proper error handling
    
    Args:
        filename (str): Name of the file to save
        markdown_content (str): Markdown content to save
        reports_dir (str): Directory to save reports in
        
    Returns:
        tuple: (success, file_path, error_message)
    """
    import os
    
    try:
        # Ensure reports directory exists
        os.makedirs(reports_dir, exist_ok=True)
        
        # Create full file path
        file_path = os.path.join(reports_dir, filename)
        
        # Ensure we're only processing Markdown files
        if not filename.endswith('.md'):
            return False, None, f"Invalid file type: Only .md files are supported, got {filename}"
            
        # For Markdown files, save as-is
        sanitized_content = markdown_content
        
        # Write file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(sanitized_content)
        
        # Verify file was created and has content
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            print(f"✅ Report saved successfully: {file_path}")
            return True, file_path, None
        else:
            return False, None, "File was not created or is empty"
            
    except PermissionError:
        return False, None, f"Permission denied writing to {reports_dir}"
    except Exception as e:
        return False, None, f"Error saving report: {str(e)}"

def generate_report_id():
    """
    Generate a unique report ID for tracking
    
    Returns:
        str: Unique report identifier
    """
    from datetime import datetime
    import hashlib
    import random
    
    # Create ID based on timestamp and random component
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    random_component = str(random.randint(1000, 9999))
    
    # Add hash for uniqueness
    combined = f"{timestamp}_{random_component}"
    hash_component = hashlib.md5(combined.encode()).hexdigest()[:6]
    
    return f"{timestamp}_{hash_component}"

def create_concise_email_content(analyzed_posts, report_url, notification_type="new_posts"):
    """
    Create concise email content with link to full HTML report
    
    Args:
        analyzed_posts (list): List of analyzed blog posts with email summaries
        report_url (str): URL to the full HTML report
        notification_type (str): Type of notification
        
    Returns:
        tuple: (html_content, text_content)
    """
    timestamp = datetime.now().strftime('%B %d, %Y at %I:%M %p')
    
    # Count different priority levels
    high_priority = len([p for p in analyzed_posts if p.get('structured_data', {}).get('priority_level') == 'High'])
    medium_priority = len([p for p in analyzed_posts if p.get('structured_data', {}).get('priority_level') == 'Medium'])
    low_priority = len([p for p in analyzed_posts if p.get('structured_data', {}).get('priority_level') == 'Low'])
    
    # Generate key highlights
    key_highlights = generate_key_highlights(analyzed_posts)
    
    # Email subject line
    if notification_type == "test":
        subject = "🧪 Test: Microsoft Edge Competitive Intelligence Alert"
    elif high_priority > 0:
        subject = f"🚨 HIGH PRIORITY: {len(analyzed_posts)} Chrome Enterprise Updates"
    else:
        subject = f"📊 Chrome Enterprise Intelligence: {len(analyzed_posts)} New Posts"
    
    # Create executive summaries outside f-string to avoid backslash issues
    executive_summaries = '\n'.join([
        f"• {post.get('title', 'Unknown')[:60]}...\n  → {post.get('email_summary', 'No summary available')}"
        for post in analyzed_posts
    ])
    
    # Plain text email content
    text_content = f"""🚨 CHROME ENTERPRISE INTELLIGENCE ALERT

📊 {len(analyzed_posts)} New Posts Detected | {timestamp}

EXECUTIVE SUMMARIES:
{executive_summaries}

🔔 KEY HIGHLIGHTS:
{key_highlights}

📄 FULL ANALYSIS REPORT: {report_url}

📈 PRIORITY BREAKDOWN:
• High Priority: {high_priority} posts
• Medium Priority: {medium_priority} posts  
• Low Priority: {low_priority} posts

---
Microsoft Edge Competitive Intelligence System
Automated monitoring of Chrome Enterprise developments
Generated: {timestamp}
"""

    # HTML email content
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                line-height: 1.6; 
                color: #333; 
                max-width: 600px; 
                margin: 0 auto; 
                background: #f8f9fa;
                padding: 20px;
            }}
            .container {{ background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .header {{ 
                background: linear-gradient(135deg, #0078d4, #106ebe); 
                color: white; 
                padding: 30px 20px; 
                text-align: center; 
            }}
            .header h1 {{ margin: 0; font-size: 1.8em; font-weight: 300; }}
            .subtitle {{ opacity: 0.9; margin: 10px 0 0 0; }}
            .content {{ padding: 30px 20px; }}
            .alert-summary {{ background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 5px; padding: 15px; margin-bottom: 20px; }}
            .posts-summary {{ background: #f8f9fa; border-radius: 5px; padding: 20px; margin: 20px 0; }}
            .post-item {{ 
                background: white; 
                margin: 10px 0; 
                padding: 15px; 
                border-radius: 5px; 
                border-left: 4px solid #0078d4; 
            }}
            .post-title {{ font-weight: bold; color: #0078d4; margin-bottom: 5px; }}
            .post-summary {{ color: #666; font-size: 0.9em; }}
            .priority-high {{ border-left-color: #dc3545; }}
            .priority-medium {{ border-left-color: #ffc107; }}
            .priority-low {{ border-left-color: #28a745; }}
            .highlights {{ background: #e7f3ff; border-radius: 5px; padding: 15px; margin: 20px 0; }}
            .cta-button {{ 
                display: inline-block; 
                background: #0078d4; 
                color: #ffffff; 
                padding: 15px 30px; 
                text-decoration: none; 
                border-radius: 5px; 
                font-weight: bold; 
                margin: 20px 0;
                text-align: center;
            }}
            .cta-section {{ text-align: center; margin: 30px 0; }}
            .stats {{ display: flex; justify-content: space-around; margin: 20px 0; }}
            .stat {{ text-align: center; }}
            .stat-number {{ font-size: 1.5em; font-weight: bold; color: #0078d4; }}
            .stat-label {{ font-size: 0.8em; color: #666; text-transform: uppercase; }}
            .footer {{ background: #f8f9fa; padding: 20px; text-align: center; font-size: 0.8em; color: #666; }}
            @media (max-width: 600px) {{
                .stats {{ flex-direction: column; }}
                .stat {{ margin: 10px 0; }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔍 Microsoft Edge Competitive Intelligence</h1>
                <p class="subtitle">Chrome Enterprise Alert | {timestamp}</p>
            </div>
            
            <div class="content">
                <div class="alert-summary">
                    <h2 style="margin: 0 0 10px 0; color: #856404;">🚨 Intelligence Alert</h2>
                    <p style="margin: 0;"><strong>{len(analyzed_posts)} new Chrome Enterprise posts</strong> detected and analyzed for competitive threats and opportunities.</p>
                </div>

                <div class="stats">
                    <div class="stat">
                        <div class="stat-number">{high_priority}</div>
                        <div class="stat-label">High Priority</div>
                    </div>
                    <div class="stat">
                        <div class="stat-number">{medium_priority}</div>
                        <div class="stat-label">Medium Priority</div>
                    </div>
                    <div class="stat">
                        <div class="stat-number">{low_priority}</div>
                        <div class="stat-label">Low Priority</div>
                    </div>
                </div>

                <div class="posts-summary">
                    <h3 style="margin: 0 0 15px 0; color: #0078d4;">📋 Executive Summaries</h3>
                    {''.join([f'''
                    <div class="post-item priority-{get_post_priority_class(post)}">
                        <div class="post-title">{post.get('title', 'Unknown Title')[:70]}{'...' if len(post.get('title', '')) > 70 else ''}</div>
                        <div class="post-summary">{post.get('email_summary', 'No summary available')}</div>
                    </div>
                    ''' for post in analyzed_posts])}
                </div>

                <div class="highlights">
                    <h3 style="margin: 0 0 10px 0; color: #0078d4;">🔔 Key Strategic Highlights</h3>
                    <div style="white-space: pre-line;">{key_highlights}</div>
                </div>

                <div class="cta-section">
                    <a href="{report_url}" class="cta-button" target="_blank">
                        📄 View Full Analysis Report
                    </a>
                    <p style="font-size: 0.9em; color: #666; margin-top: 10px;">
                        Complete competitive intelligence analysis with detailed insights, metrics, and recommendations.
                    </p>
                </div>
            </div>

            <div class="footer">
                <p><strong>Microsoft Edge Competitive Intelligence System</strong></p>
                <p>Automated Chrome Enterprise Blog Monitoring</p>
                <p>Generated: {timestamp}</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return subject, html_content, text_content

def get_post_priority_class(post):
    """Get CSS class for post priority"""
    priority = post.get('structured_data', {}).get('priority_level', 'medium')
    return priority.lower() if priority else 'medium'

def generate_key_highlights(analyzed_posts):
    """
    Generate key strategic highlights from analyzed posts
    
    Args:
        analyzed_posts (list): Posts with structured data
        
    Returns:
        str: Formatted key highlights
    """
    if not analyzed_posts:
        return "No posts available for analysis."
    
    # Collect all threats and opportunities
    all_threats = []
    all_opportunities = []
    high_priority_count = 0
    
    for post in analyzed_posts:
        structured_data = post.get('structured_data', {})
        if structured_data:
            all_threats.extend(structured_data.get('competitive_threats', []))
            all_opportunities.extend(structured_data.get('opportunities', []))
            if structured_data.get('priority_level') == 'High':
                high_priority_count += 1
    
    # Get top unique items
    top_threats = list(set(all_threats))[:2]
    top_opportunities = list(set(all_opportunities))[:2]
    
    highlights = []
    
    if high_priority_count > 0:
        highlights.append(f"⚠️ {high_priority_count} HIGH PRIORITY items require immediate attention")
    
    if top_threats:
        highlights.append("🚨 TOP THREATS:")
        for threat in top_threats:
            highlights.append(f"  → {threat}")
    
    if top_opportunities:
        highlights.append("💡 KEY OPPORTUNITIES:")
        for opp in top_opportunities:
            highlights.append(f"  → {opp}")
    
    if not highlights:
        highlights.append("📊 Analysis complete - see full report for detailed insights")
    
    return '\n'.join(highlights)

def send_concise_notification(analyzed_posts, report_url, notification_type="new_posts"):
    """
    Send concise email notification with link to full report
    
    Args:
        analyzed_posts (list): Analyzed posts with email summaries
        report_url (str): URL to full HTML report
        notification_type (str): Type of notification
        
    Returns:
        dict: Email sending result
    """
    try:
        # Generate email content
        subject, html_content, text_content = create_concise_email_content(
            analyzed_posts, report_url, notification_type
        )
        
        # Get email configuration
        sender_email = os.getenv('EMAIL_USERNAME')
        sender_password = os.getenv('EMAIL_PASSWORD')
        recipient_email = os.getenv('EMAIL_TO')
        smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        
        # Validate email configuration
        if not all([sender_email, sender_password, recipient_email]):
            missing_vars = []
            if not sender_email: missing_vars.append('EMAIL_USERNAME')
            if not sender_password: missing_vars.append('EMAIL_PASSWORD')
            if not recipient_email: missing_vars.append('EMAIL_TO')
            
            return {
                'success': False,
                'message': f'Missing email configuration: {", ".join(missing_vars)}',
                'email_sent_at': datetime.now().isoformat(),
                'posts_count': len(analyzed_posts),
                'subject': subject
            }
        
        # Send email
        success = send_enhanced_email(
            subject=subject,
            html_body=html_content,
            text_body=text_content,
            recipient_email=recipient_email,
            sender_email=sender_email,
            sender_password=sender_password,
            smtp_server=smtp_server,
            smtp_port=smtp_port
        )
        
        if success:
            return {
                'success': True,
                'message': f'Concise email sent successfully to {recipient_email}',
                'email_sent_at': datetime.now().isoformat(),
                'posts_count': len(analyzed_posts),
                'subject': subject,
                'report_url': report_url
            }
        else:
            return {
                'success': False,
                'message': 'Failed to send email - check SMTP configuration',
                'email_sent_at': datetime.now().isoformat(),
                'posts_count': len(analyzed_posts),
                'subject': subject
            }
            
    except Exception as e:
        error_logger.log_error(e, "send_concise_notification", {"posts_count": len(analyzed_posts), "report_url": report_url})
        print("🔄 Attempting email delivery fallback...")
        
        # Use email delivery fallback strategy
        fallback_result = FallbackStrategies.email_delivery_fallback(analyzed_posts, report_url, e)
        
        return {
            'success': fallback_result.get('success', False),
            'message': fallback_result.get('message', f'Email notification failed: {str(e)}'),
            'email_sent_at': datetime.now().isoformat(),
            'posts_count': len(analyzed_posts),
            'subject': subject if 'subject' in locals() else 'Unknown',
            'fallback_attempted': True,
            'fallback_result': fallback_result
        }

def send_enhanced_email(subject, html_body, text_body, recipient_email, sender_email, sender_password, smtp_server='smtp.gmail.com', smtp_port=587):
    """
    Send enhanced email with both HTML and text versions
    
    Args:
        subject (str): Email subject line
        html_body (str): HTML email content
        text_body (str): Plain text email content
        recipient_email (str): Recipient email address
        sender_email (str): Sender email address
        sender_password (str): Sender email password
        smtp_server (str): SMTP server address
        smtp_port (int): SMTP server port
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        # Add priority header for high-priority emails
        if 'HIGH PRIORITY' in subject:
            msg['X-Priority'] = '1'
            msg['X-MSMail-Priority'] = 'High'
            msg['Importance'] = 'High'
        
        # Create text and HTML parts
        text_part = MIMEText(text_body, 'plain', 'utf-8')
        html_part = MIMEText(html_body, 'html', 'utf-8')
        
        # Attach parts
        msg.attach(text_part)
        msg.attach(html_part)
        
        # Send email
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        
        server.send_message(msg)
        server.quit()
        
        print(f"✅ Enhanced email sent successfully to {recipient_email}")
        return True
        
    except smtplib.SMTPAuthenticationError:
        print(f"❌ SMTP Authentication failed - check email credentials")
        return False
    except smtplib.SMTPRecipientsRefused:
        print(f"❌ Recipient email refused: {recipient_email}")
        return False
    except smtplib.SMTPServerDisconnected:
        print(f"❌ SMTP server disconnected")
        return False
    except Exception as e:
        print(f"❌ Email sending failed: {str(e)}")
        return False

def publish_report_and_get_url(markdown_file_path, report_id):
    """
    Publish Markdown report and return the public URL
    
    Args:
        markdown_file_path (str): Path to the Markdown report file
        report_id (str): Unique report identifier
        
    Returns:
        tuple: (success, report_url, error_message)
    """
    try:
        # Try to import and use GitHub Pages publisher
        from report_publisher import (
            get_github_config,
            generate_report_url
        )
        
        # Get GitHub configuration
        github_config = get_github_config()
        if not github_config:
            # Fallback: return local file URL
            local_url = f"file://{os.path.abspath(markdown_file_path)}"
            print(f"⚠️ GitHub Pages not configured, using local URL: {local_url}")
            return True, local_url, "GitHub Pages not configured - using local file"
        
        # With GitHub Actions deployment, files are already in place
        # Just generate the URL for the report that will be accessible via GitHub Pages
        report_url = generate_report_url(report_id, github_config)
        
        if report_url:
            print(f"✅ Report will be available at GitHub Pages: {report_url}")
            return True, report_url, None
        else:
            # Fallback to local URL
            local_url = f"file://{os.path.abspath(markdown_file_path)}"
            print(f"⚠️ Could not generate GitHub Pages URL, using local URL: {local_url}")
            return False, local_url, "Failed to generate GitHub Pages URL"
        
    except ImportError:
        # report_publisher.py not available
        local_url = f"file://{os.path.abspath(markdown_file_path)}"
        print(f"⚠️ Report publisher not available, using local URL: {local_url}")
        return True, local_url, "Report publisher module not available"
    except Exception as e:
        error_logger.log_error(e, "publish_report_and_get_url", {"markdown_file_path": markdown_file_path, "report_id": report_id})
        print(f"⚠️ Publishing error: {e}")
        print("🔄 Using GitHub publishing fallback...")
        
        # Use GitHub publishing fallback strategy
        success, fallback_url, fallback_message = FallbackStrategies.github_publishing_fallback(markdown_file_path, report_id, e)
        return success, fallback_url, fallback_message

def get_ai_analysis_prompt(custom_prompt=None):
    """
    Get the AI analysis prompt to use for blog post analysis
    
    Args:
        custom_prompt (str, optional): Custom prompt provided directly
        
    Returns:
        tuple: (prompt_text, prompt_source)
            - prompt_text (str): The prompt to use
            - prompt_source (str): Source of the prompt ('custom_parameter', 'environment_variable', 'default')
            
    Notes:
        - Priority: custom_prompt > CUSTOM_AI_PROMPT env var > default prompt
        - Validates prompt length and content
        - Provides fallback if prompt is invalid
    """
    # Check custom prompt parameter first
    if custom_prompt and isinstance(custom_prompt, str) and len(custom_prompt.strip()) > 10:
        return custom_prompt.strip(), 'custom_parameter'
    
    # Check environment variable
    env_prompt = os.getenv('CUSTOM_AI_PROMPT')
    if env_prompt and len(env_prompt.strip()) > 10:
        return env_prompt.strip(), 'environment_variable'
    
    # Default prompt for Google Cloud blog analysis
    default_prompt = """
    Analyze this Google Cloud blog post and provide a comprehensive summary for IT professionals and developers.

    Focus on:
    1. **Key Technologies & Features**: What specific Google Cloud products, features, or technologies are discussed?
    2. **Business Impact**: How does this announcement or information affect businesses using Google Cloud?
    3. **Technical Details**: Important technical specifications, capabilities, or changes mentioned
    4. **Target Audience**: Who should care about this - developers, IT admins, business leaders, etc.?
    5. **Action Items**: Any specific steps readers should take or deadlines to be aware of
    6. **Strategic Significance**: How does this fit into Google Cloud's broader strategy or market positioning?

    Keep the analysis professional, actionable, and under 400 words. Focus on practical implications rather than marketing language.
    """
    
    return default_prompt.strip(), 'default'

def validate_ai_prompt(prompt):
    """
    Validate an AI prompt for quality and safety
    
    Args:
        prompt (str): Prompt to validate
        
    Returns:
        tuple: (is_valid, error_message)
            - is_valid (bool): Whether the prompt is valid
            - error_message (str): Error description if invalid, None if valid
    """
    if not prompt or not isinstance(prompt, str):
        return False, "Prompt must be a non-empty string"
    
    prompt = prompt.strip()
    
    if len(prompt) < 10:
        return False, "Prompt must be at least 10 characters long"
    
    if len(prompt) > 32000:
        return False, "Prompt must be less than 32000 characters (too long may exceed API limits)"
    
    # Check for potential security issues (basic validation)
    dangerous_patterns = [
        'ignore previous instructions',
        'forget your role',
        'act as a different',
        'pretend to be',
        'system prompt'
    ]
    
    prompt_lower = prompt.lower()
    for pattern in dangerous_patterns:
        if pattern in prompt_lower:
            return False, f"Prompt contains potentially dangerous pattern: '{pattern}'"
    
    return True, None

def format_blog_prompt(prompt_template, blog_post):
    """
    Format a prompt template with blog post data
    
    Args:
        prompt_template (str): Template with placeholder variables
        blog_post (dict): Blog post data for variable substitution
        
    Returns:
        str: Formatted prompt with blog data inserted
        
    Notes:
        - Supports variables: {title}, {author}, {publish_date}, {url}, {content}
        - Safely handles missing variables
        - Truncates content if too long for API limits
    """
    # Prepare blog data with safe defaults
    blog_data = {
        'title': blog_post.get('title', 'Unknown Title'),
        'author': blog_post.get('author', 'Unknown Author'),
        'publish_date': blog_post.get('publish_date', 'Unknown Date'),
        'url': blog_post.get('url', 'Unknown URL'),
        'content': blog_post.get('content', 'No content available')[:8000]  # Limit content length
    }
    
    try:
        # First, handle any custom placeholders in the prompt template
        template_with_substitutions = prompt_template
        
        # Handle {{URL}} placeholder specifically
        if '{{URL}}' in template_with_substitutions:
            template_with_substitutions = template_with_substitutions.replace('{{URL}}', blog_data['url'])
            print(f"✅ Replaced {{URL}} with: {blog_data['url']}")
        
        # Handle other possible placeholders
        if '{{TITLE}}' in template_with_substitutions:
            template_with_substitutions = template_with_substitutions.replace('{{TITLE}}', blog_data['title'])
        
        if '{{AUTHOR}}' in template_with_substitutions:
            template_with_substitutions = template_with_substitutions.replace('{{AUTHOR}}', blog_data['author'])
        
        if '{{DATE}}' in template_with_substitutions:
            template_with_substitutions = template_with_substitutions.replace('{{DATE}}', blog_data['publish_date'])
        
        # Format the template with blog data
        formatted_prompt = f"""
        {template_with_substitutions}

        **BLOG POST DETAILS:**
        Title: {blog_data['title']}
        Author: {blog_data['author']}
        Publication Date: {blog_data['publish_date']}
        URL: {blog_data['url']}

        **CONTENT:**
        {blog_data['content']}
        """
        
        return formatted_prompt.strip()
        
    except Exception as e:
        # If formatting fails, return a basic prompt
        return f"""
        Please analyze this blog post:

        Title: {blog_data['title']}
        Author: {blog_data['author']}
        Content: {blog_data['content']}
        
        Error in prompt formatting: {str(e)}
        """

# Legacy unused function get_default_ai_prompts() removed
# Function contained predefined AI prompts that were never used in production

def send_email(subject, body, recipient_email, sender_email, sender_password):
    """Send email notification"""
    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Gmail SMTP
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, recipient_email, text)
        server.quit()
        
        print("Email sent successfully!")
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False


def send_enhanced_email(subject, html_body, text_body, recipient_email, sender_email, 
                       sender_password, smtp_server="smtp.gmail.com", smtp_port=587):
    """
    Send enhanced email with both HTML and plain text versions
    
    Args:
        subject (str): Email subject line
        html_body (str): HTML version of email content
        text_body (str): Plain text version of email content
        recipient_email (str): Recipient's email address
        sender_email (str): Sender's email address
        sender_password (str): Sender's email password (app password for Gmail)
        smtp_server (str): SMTP server address
        smtp_port (int): SMTP server port
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Create message container
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['X-Priority'] = '1'  # High priority for competitive intelligence
        
        # Create plain text and HTML versions
        text_part = MIMEText(text_body, 'plain', 'utf-8')
        html_part = MIMEText(html_body, 'html', 'utf-8')
        
        # Add parts to message (order matters - plain text first, then HTML)
        msg.attach(text_part)
        msg.attach(html_part)
        
        # Connect to Gmail SMTP server
        print(f"Connecting to {smtp_server}:{smtp_port}...")
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Enable TLS encryption
        
        # Login with credentials
        print("Authenticating with Gmail...")
        server.login(sender_email, sender_password)
        
        # Send email
        print("Sending email...")
        text = msg.as_string()
        server.sendmail(sender_email, recipient_email, text)
        server.quit()
        
        print(f"✅ Email sent successfully from {sender_email} to {recipient_email}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"✗ Gmail authentication failed: {e}")
        print("💡 Make sure you're using an App Password, not your regular Gmail password")
        print("💡 Visit https://myaccount.google.com/apppasswords to generate one")
        return False
    except smtplib.SMTPException as e:
        print(f"✗ SMTP error: {e}")
        return False
    except Exception as e:
        print(f"✗ Email sending failed: {e}")
        return False

def convert_analysis_to_html(analysis_text):
    """
    Convert AI competitive analysis text to HTML format for email display
    
    Args:
        analysis_text (str): Raw AI analysis text with structured sections
        
    Returns:
        str: HTML formatted analysis with proper styling
    """
    if not analysis_text:
        return "<p>No analysis available</p>"
    
    import re
    
    # Start with a container div
    html = '<div class="competitive-analysis">'
    
    # Split text into lines for processing
    lines = analysis_text.strip().split('\n')
    current_section = []
    in_csv_block = False
    csv_content = []
    
    for line in lines:
        line = line.strip()
        
        # Handle CSV blocks
        if line.startswith('```csv'):
            if current_section:
                html += process_text_section(current_section)
                current_section = []
            in_csv_block = True
            csv_content = []
            continue
        elif line.startswith('```') and in_csv_block:
            # End of CSV block
            html += process_csv_section(csv_content)
            in_csv_block = False
            csv_content = []
            continue
        elif in_csv_block:
            csv_content.append(line)
            continue
        
        # Handle section headers (numbered sections)
        if re.match(r'^\d+\)\s+', line):
            if current_section:
                html += process_text_section(current_section)
                current_section = []
            section_title = re.sub(r'^\d+\)\s+', '', line)
            html += f'<h3 class="section-header">{section_title}</h3>'
            continue
        
        # Add line to current section
        current_section.append(line)
    
    # Process any remaining section
    if current_section:
        html += process_text_section(current_section)
    elif in_csv_block and csv_content:
        html += process_csv_section(csv_content)
    
    html += '</div>'
    return html


def process_text_section(lines):
    """Process text lines into HTML"""
    if not lines:
        return ""
    
    html = '<div class="text-section">'
    
    for line in lines:
        if not line:
            continue
            
        # Handle bullet points
        if line.startswith('* '):
            bullet_text = line[2:]  # Remove "* "
            # Handle evidence references like [Evidence: E1,E2]
            bullet_text = re.sub(r'\[Evidence: ([^\]]+)\]', 
                                r'<span class="evidence-ref">[Evidence: \1]</span>', 
                                bullet_text)
            html += f'<p class="bullet-point">• {bullet_text}</p>'
        else:
            # Regular paragraph
            # Handle evidence references
            line = re.sub(r'\[Evidence: ([^\]]+)\]', 
                         r'<span class="evidence-ref">[Evidence: \1]</span>', 
                         line)
            html += f'<p>{line}</p>'
    
    html += '</div>'
    return html


def process_csv_section(csv_lines):
    """Process CSV lines into HTML table"""
    if not csv_lines:
        return ""
    
    html = '<div class="csv-section">'
    html += '<table class="analysis-table">'
    
    for i, line in enumerate(csv_lines):
        if not line:
            continue
            
        cells = [cell.strip() for cell in line.split(',')]
        
        if i == 0:  # Header row
            html += '<thead><tr>'
            for cell in cells:
                html += f'<th>{cell}</th>'
            html += '</tr></thead><tbody>'
        else:  # Data row
            html += '<tr>'
            for cell in cells:
                # Handle evidence references and URLs in cells
                cell = re.sub(r'\[Evidence: ([^\]]+)\]', 
                             r'<span class="evidence-ref">[Evidence: \1]</span>', 
                             cell)
                # Handle URLs
                cell = re.sub(r'(https?://[^\s\]]+)', 
                             r'<a href="\1" target="_blank">\1</a>', 
                             cell)
                html += f'<td>{cell}</td>'
            html += '</tr>'
    
    html += '</tbody></table>'
    html += '</div>'
    return html



def main():
    # Get configuration from environment variables
    target_url = os.getenv('TARGET_URL')
    recipient_email = os.getenv('RECIPIENT_EMAIL')
    sender_email = os.getenv('SENDER_EMAIL')
    sender_password = os.getenv('EMAIL_PASSWORD')
    
    if not all([target_url, recipient_email, sender_email, sender_password]):
        print("Missing required environment variables")
        return
    
    print(f"Monitoring: {target_url}")
    
    # Get current content
    current_content = get_page_content(target_url)
    if not current_content:
        print("Failed to fetch content")
        return
    
    current_hash = get_content_hash(current_content)
    previous_data = load_previous_content()
    
    # Check if content changed
    if previous_data.get('hash') == current_hash:
        print("No changes detected")
        return
    
    print("Changes detected! Analyzing with AI...")
    
    # Analyze with AI
    previous_preview = previous_data.get('content_preview', "")
    digest = analyze_with_ai(current_content, previous_preview)
    
    # Prepare email
    subject = f"Web Monitor Alert: Changes detected on {target_url}"
    email_body = f"""
Web Monitor Digest - {datetime.now().strftime('%Y-%m-%d %H:%M')}

Monitored URL: {target_url}

{digest}

---
This is an automated message from your web monitoring system.
    """
    
    # Send notification
    if send_email(subject, email_body, recipient_email, sender_email, sender_password):
        # Save current content hash
        save_current_content(target_url, current_content, current_hash)
        print("Monitoring cycle completed successfully")
    else:
        print("Failed to send notification")

if __name__ == "__main__":
    main()
