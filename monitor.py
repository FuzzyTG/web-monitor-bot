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
    
    def safe_operation(fallback_value=None, error_logger=None):
        def decorator(func):
            return func
        return decorator
    
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
        def github_publishing_fallback(html_file_path, report_id, error):
            return True, f"file://{os.path.abspath(html_file_path)}", str(error)

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
        content_for_analysis = content[:4000] if len(content) > 4000 else content
        
        print(f"Sending content to Gemini AI (content length: {len(content_for_analysis)} chars)")
        print(f"Using prompt source: {prompt_source}")
        
        # Generate AI analysis
        generation_config = genai.types.GenerationConfig(
            temperature=0,
            candidate_count=1,
            top_p=1.0
        )
        response = model.generate_content(formatted_prompt, generation_config=generation_config)
        
        # Debug: Log response structure for troubleshooting
        print(f"📊 Response debug info:")
        if response:
            print(f"   Response object exists: True")
            print(f"   Candidates count: {len(response.candidates) if response.candidates else 0}")
            if response.candidates:
                candidate = response.candidates[0]
                print(f"   Finish reason: {candidate.finish_reason}")
                print(f"   Content exists: {candidate.content is not None}")
                if candidate.content and candidate.content.parts:
                    print(f"   Parts count: {len(candidate.content.parts)}")
                    print(f"   First part type: {type(candidate.content.parts[0]) if candidate.content.parts else 'None'}")
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
                if candidate.content and candidate.content.parts:
                    response_text = candidate.content.parts[0].text
                    print(f"✅ Method 2 (direct parts access) successful - length: {len(response_text)}")
            except Exception as e:
                print(f"⚠️ Method 2 (direct parts access) failed: {e}")
        
        # Method 3: Try alternative text extraction
        if not response_text and response and response.candidates:
            try:
                candidate = response.candidates[0]
                if hasattr(candidate, 'text'):
                    response_text = candidate.text
                    print(f"✅ Method 3 (candidate.text) successful - length: {len(response_text)}")
            except Exception as e:
                print(f"⚠️ Method 3 (candidate.text) failed: {e}")
        
        if not response_text:
            error_msg = f"Gemini API returned no accessible text content. Finish reason: {response.candidates[0].finish_reason if response and response.candidates else 'unknown'}"
            print(f"✗ {error_msg}")
            return create_failed_analysis_result(blog_post, error_msg)
        
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
    Generate a concise one-line summary for email notifications
    
    Args:
        analyzed_post (dict): Blog post with AI analysis
        
    Returns:
        str: Concise summary (max 100 characters) for email
    """
    if not analyzed_post or not isinstance(analyzed_post, dict):
        return "Unable to generate summary - invalid post data"
    
    # Check if we have successful AI analysis
    analysis = analyzed_post.get('ai_analysis', '')
    title = analyzed_post.get('title', 'Unknown Post')
    
    if not analysis or not analyzed_post.get('analysis_success', False):
        # Fallback to title-based summary
        return f"New post: {title[:60]}..." if len(title) > 60 else f"New post: {title}"
    
    try:
        # Configure Gemini API for summary generation
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            return f"Chrome Enterprise update: {title[:50]}..."
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(os.getenv('GEMINI_MODEL', 'gemini-2.5-pro'))
        
        # Create focused prompt for email summary
        summary_prompt = f"""
        Create a single-line executive summary (max 80 characters) for this Chrome Enterprise analysis.
        
        Focus on the KEY business impact or competitive threat for Microsoft Edge.
        
        Format examples:
        - "New Chrome security features may challenge Edge's enterprise positioning"
        - "Google expands workspace integration, potential Edge threat identified"
        - "Chrome Enterprise pricing changes could benefit Microsoft strategy"
        
        Analysis to summarize:
        {analysis[:800]}
        
        Return ONLY the summary line, no explanations.
        """
        
        generation_config = genai.types.GenerationConfig(
            temperature=0,
            candidate_count=1,
            top_p=1.0
        )
        response = model.generate_content(summary_prompt, generation_config=generation_config)
        
        if response and response.text:
            summary = response.text.strip()
            # Ensure it's not too long
            if len(summary) > 100:
                summary = summary[:97] + "..."
            return summary
        else:
            # Fallback if AI doesn't respond
            return f"Chrome Enterprise update: {title[:50]}..."
            
    except Exception as e:
        print(f"Warning: Failed to generate AI summary: {e}")
        # Fallback summary based on title
        return f"Chrome Enterprise update: {title[:50]}..."

def extract_structured_data_from_analysis(analysis_text):
    """
    Extract structured data from AI competitive intelligence analysis
    Handles the new regulated Gemini format with clean section numbering
    
    Args:
        analysis_text (str): Raw AI analysis text with regulated format
        
    Returns:
        dict: Structured competitive intelligence data or None if extraction fails
    """
    if not analysis_text or len(analysis_text.strip()) < 50:
        return None
    
    try:
        import re
        import json
        
        # Initialize structured data container
        structured_data = {
            "evidence_register": [],
            "feature_inventory": [],
            "capability_term_harvest": [],
            "diff_matrix": [],
            "edge_competitive_gaps": [],
            "strategic_actions": [],
            "feature_parity_chart": {},
            "ux_delta_teardown": [],
            "edge_advantage_highlights": [],
            "executive_summary": "",
            "problem_solution_map": []
        }
        
        # Extract numbered sections with their specific formats
        
        # 1) Edge Competitive Gaps — bullets
        gaps_pattern = r'1\) Edge Competitive Gaps[^\n]*\n(.*?)(?=2\)|$)'
        gaps_match = re.search(gaps_pattern, analysis_text, re.DOTALL | re.IGNORECASE)
        if gaps_match:
            gaps_text = gaps_match.group(1).strip()
            gaps = re.findall(r'(?:\*|•|-)\s*(.*?)(?=\n(?:\*|•|-)|$)', gaps_text, re.DOTALL)
            # Clean up gaps by removing extra whitespace and newlines
            gaps = [gap.strip().replace('\n', ' ') for gap in gaps if gap.strip()]
            structured_data["edge_competitive_gaps"] = gaps
            print(f"✅ Parsed Edge Competitive Gaps: {len(gaps)} items")
        
        # 2) Strategic Actions — CSV
        strategic_pattern = r'2\) Strategic Actions[^\n]*\n```csv\s*(.*?)\s*```'
        strategic_match = re.search(strategic_pattern, analysis_text, re.DOTALL | re.IGNORECASE)
        if strategic_match:
            strategic_csv = strategic_match.group(1).strip()
            strategic_actions = parse_csv_section(strategic_csv)
            structured_data["strategic_actions"] = strategic_actions
            print(f"✅ Parsed Strategic Actions: {len(strategic_actions)} items")
        
        # 3) Feature Parity Chart (Multi-platform CSV)
        parity_pattern = r'3\) Feature Parity Chart[^\n]*\n(.*?)(?=4\)|$)'
        parity_match = re.search(parity_pattern, analysis_text, re.DOTALL | re.IGNORECASE)
        if parity_match:
            parity_text = parity_match.group(1).strip()
            parity_data = parse_feature_parity_chart_regulated(parity_text)
            structured_data["feature_parity_chart"] = parity_data
            total_parity_items = sum(len(platform_data) for platform_data in parity_data.values())
            print(f"✅ Parsed Feature Parity Chart: {total_parity_items} items across platforms")
        
        # 4) UX Delta Teardown — CSV
        ux_pattern = r'4\) UX Delta Teardown[^\n]*\n```csv\s*(.*?)\s*```'
        ux_match = re.search(ux_pattern, analysis_text, re.DOTALL | re.IGNORECASE)
        if ux_match:
            ux_csv = ux_match.group(1).strip()
            ux_teardown = parse_csv_section(ux_csv)
            structured_data["ux_delta_teardown"] = ux_teardown
            print(f"✅ Parsed UX Delta Teardown: {len(ux_teardown)} items")
        
        # 5) Edge Advantage Highlights — bullets or N/A
        advantages_pattern = r'5\) Edge Advantage Highlights[^\n]*\n((?:(?:\*|•|-).*?\n?)*|N/A)'
        advantages_match = re.search(advantages_pattern, analysis_text, re.DOTALL | re.IGNORECASE)
        if advantages_match:
            advantages_text = advantages_match.group(1).strip()
            if advantages_text == "N/A":
                structured_data["edge_advantage_highlights"] = []
            else:
                advantages = re.findall(r'(?:\*|•|-)\s*(.*)', advantages_text)
                structured_data["edge_advantage_highlights"] = advantages
            print(f"✅ Parsed Edge Advantage Highlights: {len(structured_data['edge_advantage_highlights'])} items")
        
        # 6) Executive Summary
        exec_summary_pattern = r'6\) Executive Summary[^\n]*\n(.*?)(?=7\)|$)'
        exec_match = re.search(exec_summary_pattern, analysis_text, re.DOTALL | re.IGNORECASE)
        if exec_match:
            structured_data["executive_summary"] = exec_match.group(1).strip()
            print(f"✅ Parsed Executive Summary")
        
        # 7) Evidence Register — JSON
        evidence_pattern = r'7\) Evidence Register[^\n]*\n```json\s*(.*?)\s*```'
        evidence_match = re.search(evidence_pattern, analysis_text, re.DOTALL | re.IGNORECASE)
        if evidence_match:
            try:
                evidence_json = json.loads(evidence_match.group(1))
                structured_data["evidence_register"] = evidence_json
                print(f"✅ Parsed Evidence Register: {len(evidence_json)} items")
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse Evidence Register JSON: {e}")
        
        # 8) Capability Term Harvest — JSON
        capability_pattern = r'8\) Capability Term Harvest[^\n]*\n```json\s*(.*?)\s*```'
        capability_match = re.search(capability_pattern, analysis_text, re.DOTALL | re.IGNORECASE)
        if capability_match:
            try:
                capability_json = json.loads(capability_match.group(1))
                structured_data["capability_term_harvest"] = capability_json
                print(f"✅ Parsed Capability Term Harvest: {len(capability_json)} items")
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse Capability Term Harvest JSON: {e}")
        
        # 9) Diff Matrix — JSON
        diff_pattern = r'9\) Diff Matrix[^\n]*\n```json\s*(.*?)\s*```'
        diff_match = re.search(diff_pattern, analysis_text, re.DOTALL | re.IGNORECASE)
        if diff_match:
            try:
                diff_json = json.loads(diff_match.group(1))
                structured_data["diff_matrix"] = diff_json
                print(f"✅ Parsed Diff Matrix: {len(diff_json)} items")
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse Diff Matrix JSON: {e}")
        
        # 10) Feature Inventory — JSON
        inventory_pattern = r'10\) Feature Inventory[^\n]*\n```json\s*(.*?)\s*```'
        inventory_match = re.search(inventory_pattern, analysis_text, re.DOTALL | re.IGNORECASE)
        if inventory_match:
            try:
                inventory_json = json.loads(inventory_match.group(1))
                structured_data["feature_inventory"] = inventory_json
                print(f"✅ Parsed Feature Inventory: {len(inventory_json)} items")
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse Feature Inventory JSON: {e}")
        
        # 11) Problem–Solution Map — CSV
        problem_pattern = r'11\) Problem[–-]Solution Map[^\n]*\n```csv\s*(.*?)\s*```'
        problem_match = re.search(problem_pattern, analysis_text, re.DOTALL | re.IGNORECASE)
        if problem_match:
            problem_csv = problem_match.group(1).strip()
            problem_solution = parse_csv_section(problem_csv)
            structured_data["problem_solution_map"] = problem_solution
            print(f"✅ Parsed Problem-Solution Map: {len(problem_solution)} items")
        
        # Extract text-based sections using pattern matching
        
        # Executive Summary
        exec_summary_pattern = r'Executive Summary[^\n]*\n(.*?)(?=\n\d+\)|$)'
        exec_match = re.search(exec_summary_pattern, analysis_text, re.DOTALL | re.IGNORECASE)
        if exec_match:
            structured_data["executive_summary"] = exec_match.group(1).strip()
        
        # Note: Edge Competitive Gaps parsing is handled above in numbered sections
        # Edge Advantage Highlights (bullet points)
        advantages_pattern = r'Edge Advantage Highlights[^\n]*\n((?:(?:•|-).*?\n?)*)'
        advantages_match = re.search(advantages_pattern, analysis_text, re.DOTALL | re.IGNORECASE)
        if advantages_match:
            advantages_text = advantages_match.group(1)
            advantages = re.findall(r'(?:•|-)\s*(.*)', advantages_text)
            structured_data["edge_advantage_highlights"] = advantages
        
        # Extract CSV-based sections using pattern matching
        
        # Strategic Actions (CSV format)
        strategic_pattern = r'2\) Strategic Actions[^\n]*\n([^3\)]*?)(?=3\)|$)'
        strategic_match = re.search(strategic_pattern, analysis_text, re.DOTALL | re.IGNORECASE)
        if strategic_match:
            strategic_text = strategic_match.group(1).strip()
            strategic_actions = parse_csv_section(strategic_text)
            structured_data["strategic_actions"] = strategic_actions
            print(f"✅ Parsed Strategic Actions: {len(strategic_actions)} items")
        
        # UX Delta Teardown (CSV format)
        ux_pattern = r'4\) UX Delta Teardown[^\n]*\n([^5\)]*?)(?=5\)|$)'
        ux_match = re.search(ux_pattern, analysis_text, re.DOTALL | re.IGNORECASE)
        if ux_match:
            ux_text = ux_match.group(1).strip()
            ux_teardown = parse_csv_section(ux_text)
            structured_data["ux_delta_teardown"] = ux_teardown
            print(f"✅ Parsed UX Delta Teardown: {len(ux_teardown)} items")
        
        
        # Feature Parity Chart (Complex CSV format with platform sections)
        parity_pattern = r'3\) Feature Parity Chart[^\n]*\n(.*?)(?=4\)|$)'
        parity_match = re.search(parity_pattern, analysis_text, re.DOTALL | re.IGNORECASE)
        if parity_match:
            parity_text = parity_match.group(1).strip()
            parity_data = parse_feature_parity_chart(parity_text)
            structured_data["feature_parity_chart"] = parity_data
            total_parity_items = sum(len(platform_data) for platform_data in parity_data.values())
            print(f"✅ Parsed Feature Parity Chart: {total_parity_items} items across platforms")
        
        # Check if we extracted meaningful data
        total_items = (len(structured_data["evidence_register"]) + 
                      len(structured_data["feature_inventory"]) + 
                      len(structured_data["capability_term_harvest"]) +
                      len(structured_data["diff_matrix"]) +
                      len(structured_data["strategic_actions"]) +
                      len(structured_data["ux_delta_teardown"]) +
                      len(structured_data["problem_solution_map"]))
        
        if total_items > 0:
            print(f"✅ Successfully extracted enhanced competitive intelligence data ({total_items} total items)")
            return structured_data
        else:
            print("Warning: No structured data found in analysis")
            return None
            
    except Exception as e:
        print(f"Warning: Failed to extract structured data: {e}")
        return None

def parse_csv_section(csv_text):
    """Parse CSV text into structured data"""
    try:
        import csv
        from io import StringIO
        
        # Handle case where csv_text might be a list or other non-string type
        if not isinstance(csv_text, str):
            print(f"Warning: Expected string, got {type(csv_text)}: {csv_text}")
            return []
        
        # Clean and normalize the text
        csv_text = csv_text.strip()
        if not csv_text:
            return []
            
        lines = csv_text.split('\n')
        if len(lines) < 2:
            return []
        
        # Find the header line (usually the one with commas)
        header_line = None
        data_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:  # Skip empty lines
                continue
                
            if ',' in line and (not header_line):
                header_line = line
            elif ',' in line and header_line:
                data_lines.append(line)
        
        if not header_line or not data_lines:
            return []
        
        # Parse CSV data
        csv_data = []
        reader = csv.DictReader(StringIO(header_line + '\n' + '\n'.join(data_lines)))
        
        for row in reader:
            # Clean up keys and values
            cleaned_row = {}
            for key, value in row.items():
                # Handle None values for keys and values
                if key is None:
                    clean_key = 'unknown'
                else:
                    clean_key = str(key).strip() if str(key).strip() else 'unknown'
                
                if value is None:
                    clean_value = ''
                else:
                    clean_value = str(value).strip()
                    
                cleaned_row[clean_key] = clean_value
            csv_data.append(cleaned_row)
        
        return csv_data
        
    except Exception as e:
        print(f"Warning: Failed to parse CSV section: {e}")
        return []

def parse_feature_parity_chart_regulated(parity_text):
    """Parse the new regulated Feature Parity Chart with platform-separated CSV blocks"""
    try:
        platform_data = {}
        
        # Find platform sections (iOS, Android, Desktop)
        platform_pattern = r'(iOS|Android|Desktop)\s*\n```csv\s*(.*?)\s*```'
        platform_matches = re.findall(platform_pattern, parity_text, re.DOTALL | re.IGNORECASE)
        
        for platform, csv_content in platform_matches:
            # Parse the CSV content while preserving all column headers
            csv_data = parse_csv_section(csv_content.strip())
            if csv_data:
                platform_data[platform] = csv_data
                print(f"✓ Parsed {platform}: {len(csv_data)} features with full column structure")
        
        return platform_data
        
    except Exception as e:
        print(f"Warning: Failed to parse regulated Feature Parity Chart: {e}")
        return {}

def parse_feature_parity_chart(parity_text):
    """Parse the complex Feature Parity Chart with platform sections"""
    try:
        platform_data = {}
        current_platform = None
        
        lines = parity_text.split('\n')
        for line in lines:
            line = line.strip()
            
            # Check for platform headers
            if line in ['iOS', 'Android', 'Desktop']:
                current_platform = line
                platform_data[current_platform] = []
            elif current_platform and ',' in line and 'Chrome Feature' not in line:
                # This is a data line for the current platform
                csv_data = parse_csv_section(f"Chrome Feature,Chrome DeliveryMode,Chrome AdminPlane,Chrome Granularity,Chrome RedirectSupport,Edge Capability,Edge DeliveryMode,Edge AdminPlane,Edge Granularity,Edge RedirectSupport,Delta & Rationale,Parity Rating,Evidence IDs\n{line}")
                if csv_data:
                    platform_data[current_platform].extend(csv_data)
        
        return platform_data
        
    except Exception as e:
        print(f"Warning: Failed to parse Feature Parity Chart: {e}")
        return {}

def extract_legacy_structured_data_from_analysis(analysis_text):
    """
    Fallback: Extract structured data using Gemini for legacy format
    
    Args:
        analysis_text (str): Raw AI analysis text
        
    Returns:
        dict: Structured data or None if extraction fails
    """
    if not analysis_text or len(analysis_text.strip()) < 50:
        return None
    
    try:
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            return None
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(os.getenv('GEMINI_MODEL', 'gemini-2.5-pro'))
        
        extraction_prompt = f"""
        Extract structured information from this competitive intelligence analysis. Return ONLY valid JSON with this exact structure:
        
        {{
            "executive_summary": "one paragraph summary of key findings",
            "key_technologies": [
                {{"name": "technology name", "description": "what it does", "impact": "business impact"}}
            ],
            "business_impact": "brief description of overall business implications",
            "competitive_threats": ["threat 1", "threat 2"],
            "opportunities": ["opportunity 1", "opportunity 2"],
            "recommendations": ["actionable recommendation 1", "actionable recommendation 2"],
            "priority_level": "High|Medium|Low",
            "key_metrics": [
                {{"metric": "metric name", "value": "metric value", "significance": "why it matters"}}
            ]
        }}
        
        Analysis text: {analysis_text[:2000]}
        
        Return only the JSON, no explanations or markdown formatting.
        """
        
        generation_config = genai.types.GenerationConfig(
            temperature=0,
            candidate_count=1,
            top_p=1.0
        )
        response = model.generate_content(extraction_prompt, generation_config=generation_config)
        
        if response and response.text:
            # Clean up the response (remove markdown if present)
            json_text = response.text.strip()
            if json_text.startswith('```json'):
                json_text = json_text.replace('```json', '').replace('```', '')
            
            # Parse JSON
            import json
            structured_data = json.loads(json_text)
            return structured_data
            
    except Exception as e:
        print(f"Warning: Failed to extract structured data: {e}")
        return None

def generate_html_report(analyzed_posts, report_id):
    """
    Generate a comprehensive standalone HTML report
    
    Args:
        analyzed_posts (list): List of analyzed blog posts
        report_id (str): Unique identifier for this report
        
    Returns:
        tuple: (filename, html_content) or (None, None) if failed
    """
    if not analyzed_posts:
        print("Error: No analyzed posts provided for HTML report generation")
        return None, None
    
    try:
        timestamp = datetime.now().strftime('%B %d, %Y at %I:%M %p')
        report_date = datetime.now().strftime('%Y-%m-%d')
        
        # Process each post to extract structured data
        processed_posts = []
        for i, post in enumerate(analyzed_posts, 1):
            print(f"Processing post {i}/{len(analyzed_posts)} for HTML report...")
            
            # Extract structured data from analysis
            structured_data = extract_structured_data_from_analysis(post.get('ai_analysis', ''))
            
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
        
        # Generate HTML content
        html_content = create_professional_html_report(processed_posts, report_id, timestamp, report_date)
        
        # Generate filename
        filename = f"chrome_enterprise_report_{report_id}.html"
        
        print(f"✅ Generated HTML report: {filename}")
        return filename, html_content
        
    except Exception as e:
        print(f"Error generating HTML report: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def create_enhanced_competitive_html_report(processed_posts, aggregated_data, reports_dir, report_date):
    """
    Create working competitive intelligence HTML report using proven template format
    Based on the user's chrome-vs-edge-ios-redirect-gap-report-v13.html structure
    
    Args:
        processed_posts (list): Posts with structured data
        aggregated_data (dict): Aggregated analysis data
        reports_dir (str): Reports directory 
        report_date (str): Date in YYYY-MM-DD format
        
    Returns:
        str: Complete working HTML content
    """
    from datetime import datetime
    
    # Extract data from aggregated_data
    gaps = aggregated_data.get('edge_competitive_gaps', [])
    strategic_actions = aggregated_data.get('strategic_actions', [])
    evidence_base = aggregated_data.get('evidence_base', [])
    executive_summary = aggregated_data.get('executive_summary', 'No executive summary available.')
    edge_advantages = aggregated_data.get('edge_advantages', [])
    capability_terms = aggregated_data.get('capability_term_harvest', [])
    feature_inventory = aggregated_data.get('feature_inventory', [])
    ux_analysis = aggregated_data.get('ux_competitive_analysis', [])
    feature_parity = aggregated_data.get('feature_parity_analysis', {})
    
    # Generate strategic actions table
    def generate_strategic_actions_table():
        if not strategic_actions:
            return "<p>No strategic actions available.</p>"
        
        html = '''<div class="table-wrap">
      <table>
        <thead><tr><th>Chrome Feature</th><th>Platform</th><th>Edge Action (Defend|Match|Leapfrog|Deprioritize)</th><th>Rationale (<=20 words)</th><th>Evidence IDs</th></tr></thead>
        <tbody>'''
        
        for action in strategic_actions:
            evidence_links = ""
            if action.get('evidence_ids'):
                evidence_links = ', '.join([f'<a href="#{eid}" class="evid-link">{eid}</a>' for eid in action['evidence_ids']])
            
            html += f'''
          <tr><td>{action.get('chrome_feature', 'Unknown')}</td><td>{action.get('platform', 'Unknown')}</td><td>{action.get('edge_action', 'Unknown')}</td><td>{action.get('rationale', 'No rationale provided')}</td><td>{evidence_links}</td></tr>'''
        
        html += '''
        </tbody>
      </table>
    </div>'''
        return html
    
    # Generate feature parity tables for each platform
    def generate_feature_parity_tables():
        if not feature_parity:
            return "<p>No feature parity data available.</p>"
        
        html_sections = []
        
        for platform, features in feature_parity.items():
            if not features:
                continue
                
            platform_title = platform.title()
            html_sections.append(f'''    <section><h2>3) Feature Parity Chart — {platform_title}</h2>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Chrome Feature</th><th>Chrome DeliveryMode</th><th>Chrome AdminPlane</th><th>Chrome Granularity</th><th>Chrome RedirectSupport</th><th>Edge Capability</th><th>Edge DeliveryMode</th><th>Edge AdminPlane</th><th>Edge Granularity</th><th>Edge RedirectSupport</th><th>Delta &amp; Rationale</th><th>Parity Rating</th><th>Evidence IDs</th></tr></thead>
        <tbody>''')
            
            for feature in features:
                evidence_links = ""
                if feature.get('evidence_ids'):
                    evidence_links = ', '.join([f'<a href="#{eid}" class="evid-link">{eid}</a>' for eid in feature['evidence_ids']])
                
                html_sections.append(f'''
          <tr><td>{feature.get('chrome_feature', 'Unknown')}</td><td>{feature.get('chrome_delivery_mode', 'Unknown')}</td><td>{feature.get('chrome_admin_plane', 'Unknown')}</td><td>{feature.get('chrome_granularity', 'Unknown')}</td><td>{feature.get('chrome_redirect_support', 'Unknown')}</td><td>{feature.get('edge_capability', 'Unknown')}</td><td>{feature.get('edge_delivery_mode', 'Unknown')}</td><td>{feature.get('edge_admin_plane', 'Unknown')}</td><td>{feature.get('edge_granularity', 'Unknown')}</td><td>{feature.get('edge_redirect_support', 'Unknown')}</td><td>{feature.get('delta_rationale', 'No rationale provided')}</td><td>{feature.get('parity_rating', 'Unknown')}</td><td>{evidence_links}</td></tr>''')
            
            html_sections.append('''
        </tbody>
      </table>
    </div>
    </section>''')
        
        return '\n'.join(html_sections)
    
    # Generate UX Delta Teardown table
    def generate_ux_teardown_table():
        if not ux_analysis:
            return "<p>No UX teardown data available.</p>"
        
        html = '''<div class="table-wrap">
      <table>
        <thead><tr><th>Feature</th><th>Platform</th><th>Entry Trigger</th><th>Block/Switch Mechanism</th><th>Data/Account Boundary</th><th>Admin/Policy Controls</th><th>Redirect Path</th><th>Recovery Path</th><th>Notes</th><th>Evidence IDs</th></tr></thead>
        <tbody>'''
        
        for ux in ux_analysis:
            evidence_links = ""
            if ux.get('evidence_ids'):
                evidence_links = ', '.join([f'<a href="#{eid}" class="evid-link">{eid}</a>' for eid in ux['evidence_ids']])
            
            html += f'''
          <tr><td>{ux.get('feature', 'Unknown')}</td><td>{ux.get('platform', 'Unknown')}</td><td>{ux.get('entry_trigger', 'Unknown')}</td><td>{ux.get('block_switch_mechanism', 'Unknown')}</td><td>{ux.get('data_account_boundary', 'Unknown')}</td><td>{ux.get('admin_policy_controls', 'Unknown')}</td><td>{ux.get('redirect_path', 'Unknown')}</td><td>{ux.get('recovery_path', 'Unknown')}</td><td>{ux.get('notes', 'Unknown')}</td><td>{evidence_links}</td></tr>'''
        
        html += '''
        </tbody>
      </table>
    </div>'''
        return html
    
    # Generate evidence cards
    def generate_evidence_cards():
        if not evidence_base:
            return "<p>No evidence available.</p>"
        
        html_cards = []
        for evidence in evidence_base:
            platforms_str = ', '.join(evidence.get('platforms', ['Unknown']))
            
            html_cards.append(f'''    <div class="card" id="{evidence.get('id', 'N/A')}">
      <div class="card-head"><span class="badge">{evidence.get('id', 'N/A')}</span> {evidence.get('product', 'Unknown')} · {evidence.get('feature', 'Unknown Feature')} · <span class="mono">{platforms_str}</span></div>
      <div class="card-quote">"{evidence.get('quote', evidence.get('content', 'No quote available'))}"</div>
      <div class="card-link"><a href="{evidence.get('url', evidence.get('source', '#'))}" target="_blank" rel="noopener">Source</a></div>
    </div>''')
        
        return '\n    \n\n'.join(html_cards)
    
    # Generate capability term harvest table
    def generate_capability_terms_table():
        if not capability_terms:
            return "<p>No capability terms available.</p>"
        
        html = '''<div class="table-wrap">
      <table>
        <thead><tr><th>Term</th><th>Class</th><th>Feature Name</th><th>Platforms (in sentence)</th><th>Quote</th><th>Evidence</th></tr></thead>
        <tbody>'''
        
        for term in capability_terms:
            platforms_str = ', '.join(term.get('platforms_in_sentence', ['Unknown']))
            evidence_link = f'<a href="#{term.get("evidence_id", "N/A")}">{term.get("evidence_id", "N/A")}</a>' if term.get('evidence_id') else 'N/A'
            
            html += f'''
          <tr><td>{term.get('term', 'Unknown')}</td><td>{term.get('class', 'Unknown')}</td><td>{term.get('feature_name', 'Unknown')}</td><td>{platforms_str}</td><td>{term.get('quote', 'No quote available')}</td><td>&lt;a href=&quot;#{term.get("evidence_id", "N/A")}&quot;&gt;{term.get("evidence_id", "N/A")}&lt;/a&gt;</td></tr>'''
        
        html += '''
        </tbody>
      </table>
    </div>'''
        return html
    
    # Generate feature inventory table
    def generate_feature_inventory_table():
        if not feature_inventory:
            return "<p>No feature inventory available.</p>"
        
        html = '''<div class="table-wrap">
      <table>
        <thead><tr><th>Name</th><th>Purpose</th><th>Direct Quote (≤40w)</th><th>Platforms in Source</th></tr></thead>
        <tbody>'''
        
        for feature in feature_inventory:
            platforms_str = ', '.join(feature.get('platforms_in_source', ['Unknown']))
            
            html += f'''
          <tr><td>{feature.get('name', 'Unknown')}</td><td>{feature.get('one_line_purpose', 'Unknown purpose')}</td><td>{feature.get('direct_quote', 'No quote available')}</td><td>{platforms_str}</td></tr>'''
        
        html += '''
        </tbody>
      </table>
    </div>'''
        return html
    
    # Generate Edge advantages list
    def generate_edge_advantages():
        if not edge_advantages:
            return "<p>No Edge advantages identified.</p>"
        
        advantages_html = []
        for advantage in edge_advantages:
            advantages_html.append(f'<li>{advantage}</li>')
        
        return f'<ul>{"".join(advantages_html)}</ul>'
    
    # Generate competitive gaps list
    def generate_gaps_list():
        if not gaps:
            return "<p>No competitive gaps identified.</p>"
        
        gaps_html = []
        for gap in gaps:
            gaps_html.append(f'<li>{gap}</li>')
        
        return f'<ul>{"".join(gaps_html)}</ul>'
    
    # Main HTML template based on user's working format
    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Chrome vs Edge — Competitive Intelligence Brief</title>
  <style>
:root{{--ink:#0f172a;--muted:#475569;--bg:#ffffff;--accent:#2563eb;--soft:#f1f5f9;--card:#f8fafc;}}
*{{box-sizing:border-box}} body{{font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;color:var(--ink);background:var(--bg);margin:0;line-height:1.5}}
header{{padding:28px 24px;border-bottom:1px solid #e2e8f0;background:#fff;position:sticky;top:0}}
header h1{{margin:0 0 4px 0;font-size:20px}}
header .meta{{color:var(--muted);font-size:12px}}
main{{padding:24px;max-width:1200px;margin:0 auto}}
section{{margin:28px 0;padding:16px;border:1px solid #e2e8f0;border-radius:12px;background:#fff}}
h2{{margin:0 0 12px 0;font-size:18px}}
p{{margin:0 0 12px 0}}
ul{{margin:8px 0 8px 20px}}
.badge{{display:inline-block;padding:2px 8px;border-radius:999px;background:var(--soft);color:var(--muted);font-size:12px;margin-right:8px}}
.table-wrap{{overflow:auto;border:1px solid #e2e8f0;border-radius:10px}}
table{{border-collapse:separate;border-spacing:0;width:100%;font-size:13px}}
th,td{{padding:10px 12px;border-bottom:1px solid #e2e8f0;vertical-align:top}}
thead th{{position:sticky;top:0;background:#f8fafc;text-align:left;font-weight:600}}
tbody tr:hover{{background:#f9fbff}}
.card{{padding:12px;border:1px solid #e2e8f0;border-radius:10px;margin:10px 0;background:var(--card)}}
.card-head{{font-weight:600;margin-bottom:6px}}
.card-quote{{color:var(--muted);font-style:italic;margin:6px 0}}
.card-link a{{color:var(--accent);text-decoration:none}}
.small{{font-size:12px;color:var(--muted)}}
.mono{{font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace}}
footer{{padding:24px;border-top:1px solid #e2e8f0;color:var(--muted);font-size:12px}}
.evid-link{{white-space:nowrap}}
@media print{{header{{position:static}} section{{page-break-inside:avoid}} a[href^="http"]::after{{content:" (" attr(href) ")";font-size:10px;color:#94a3b8}}}}
</style>
</head>
<body>
  <header>
    <h1>Chrome vs Edge — Competitive Intelligence Brief</h1>
    <div class="meta">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} · Audience: PM/Engineering · Status: Draft</div>
  </header>
  <main>
    <section><h2>6) Executive Summary</h2><p>{executive_summary}</p></section>
    <section><h2>1) Edge Competitive Gaps</h2>{generate_gaps_list()}</section>
    <section><h2>2) Strategic Actions</h2>
    {generate_strategic_actions_table()}
    </section>
    {generate_feature_parity_tables()}
    <section><h2>4) UX Delta Teardown</h2>
    {generate_ux_teardown_table()}
    </section>
    <section><h2>5) Edge Advantage Highlights</h2>{generate_edge_advantages()}</section>
    <section><h2>7) Evidence Register</h2>
    {generate_evidence_cards()}
    </section>
    <section><h2>8) Capability Term Harvest</h2>
    {generate_capability_terms_table()}
    </section>
    <section><h2>10) Feature Inventory</h2>
    {generate_feature_inventory_table()}
    </section>
  </main>
  <footer>
    <div>Built for rapid competitive readouts. Evidence IDs link to sources above.</div>
  </footer>
</body>
</html>'''
    
    # Generate filename for consistency with other report functions
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"chrome_enterprise_competitive_report_{timestamp}.html"
    
    return filename, html_content

def generate_capability_classification_html(capabilities):
    """Generate HTML for capability term harvest classification"""
    if not capabilities:
        return "<p>No capability terms available.</p>"
    
    # Group capabilities by class
    capability_classes = {}
    for cap in capabilities:
        class_name = cap.get('class', 'Unknown')
        if class_name not in capability_classes:
            capability_classes[class_name] = []
        capability_classes[class_name].append(cap)
    
    html_sections = []
    for class_name, class_caps in capability_classes.items():
        html_sections.append(f"""
        <div class="capability-class">
            <h4 class="capability-class-title">{class_name}</h4>
            <div class="capability-terms">
        """)
        
        for cap in class_caps:
            platforms = ', '.join(cap.get('platforms_in_sentence', ['Unknown']))
            html_sections.append(f"""
                <div class="capability-term">
                    <strong>{cap.get('term', 'Unknown')}</strong>
                    <span class="capability-platforms">({platforms})</span>
                    <p class="capability-quote">"{cap.get('quote', 'No quote available')}"</p>
                    <small class="capability-evidence">Evidence: {cap.get('evidence_id', 'N/A')}</small>
                </div>
            """)
        
        html_sections.append("</div></div>")
    
    return ''.join(html_sections)

def generate_executive_summaries_html(summaries):
    """Generate HTML for executive summaries"""
    if not summaries:
        return "<p>No executive summaries available.</p>"
    
    html = ""
    for i, summary in enumerate(summaries, 1):
        html += f"""
        <div class="feature-card">
            <div class="feature-name">Analysis {i}</div>
            <p>{summary}</p>
        </div>
        """
    return html

def generate_gaps_html(gaps):
    """Generate HTML for competitive gaps"""
    if not gaps:
        return "<p>No competitive gaps identified.</p>"
    
    html = ""
    for gap in gaps:
        html += f"""
        <div class="gap-item">
            <div class="gap-platform">Competitive Gap</div>
            <p>{gap}</p>
        </div>
        """
    return html

def generate_evidence_cards_html(evidence_list):
    """Generate HTML cards for evidence"""
    if not evidence_list:
        return "<p>No evidence data available.</p>"
    
    html = ""
    for evidence in evidence_list:
        product_class = evidence.get('product', '').lower()
        platforms = evidence.get('platforms', [])
        
        platform_badges = ""
        for platform in platforms:
            platform_class = platform.lower()
            platform_badges += f'<span class="platform-badge {platform_class}">{platform}</span>'
        
        html += f"""
        <div class="evidence-card" data-product="{product_class}" data-platforms="{','.join([p.lower() for p in platforms])}">
            <div class="evidence-id">{evidence.get('id', 'N/A')}</div>
            <span class="evidence-product {product_class}">{evidence.get('product', 'Unknown')}</span>
            <div class="evidence-feature">{evidence.get('feature', 'Unknown Feature')}</div>
            <div class="evidence-quote">"{evidence.get('quote', 'No quote available')}"</div>
            <div class="evidence-platforms">{platform_badges}</div>
            <div style="margin-top: 10px; font-size: 0.8rem; color: #666;">
                <a href="{evidence.get('url', '#')}" target="_blank">View Source</a>
            </div>
        </div>
        """
    return html

def generate_detailed_gaps_html(gaps, capabilities):
    """Generate detailed HTML for gap analysis"""
    if not gaps:
        return "<p>No competitive gaps identified.</p>"
    
    # Group gaps by platform and extract evidence
    platform_gaps = {}
    for gap in gaps:
        # Extract platform from gap text
        platform = "General"
        gap_lower = gap.lower()
        if "ios:" in gap_lower:
            platform = "iOS"
        elif "android:" in gap_lower:
            platform = "Android"
        elif "desktop:" in gap_lower:
            platform = "Desktop"
        
        # Extract evidence ID if present
        evidence_match = re.search(r'\[Evidence: (E\d+)\]', gap)
        evidence_id = evidence_match.group(1) if evidence_match else None
        
        # Clean gap text (remove Evidence reference for display)
        clean_gap = re.sub(r'\s*\[Evidence: E\d+\]', '', gap).strip()
        
        if platform not in platform_gaps:
            platform_gaps[platform] = []
        platform_gaps[platform].append({
            'text': clean_gap,
            'evidence_id': evidence_id,
            'original': gap
        })
    
    html = f"""
    <div class="mb-8 text-center">
        <div class="inline-block bg-red-100 border border-red-300 rounded-lg p-6">
            <div class="text-4xl font-bold text-red-600">{len(gaps)}</div>
            <div class="text-lg text-red-800 font-medium">Total Competitive Gaps</div>
        </div>
    </div>
    """
    
    for platform, platform_gap_list in platform_gaps.items():
        html += f"""
        <div class="mb-8">
            <h3 class="text-xl font-semibold text-ms-blue mb-4 pb-2 border-b-2 border-gray-200">{platform} Platform ({len(platform_gap_list)} gaps)</h3>
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        """
        
        for i, gap_info in enumerate(platform_gap_list):
            # Extract Chrome feature and Edge gap
            if ' vs Chrome ' in gap_info['text']:
                parts = gap_info['text'].split(' vs Chrome ', 1)
                edge_gap = parts[0].replace(f"{platform}:", "").strip() if parts[0] else gap_info['text']
                chrome_feature = parts[1] if len(parts) > 1 else "Chrome feature"
            else:
                edge_gap = gap_info['text']
                chrome_feature = "Chrome advantage"
            
            evidence_badge = f"""<span class="bg-green-500 text-white text-xs px-2 py-1 rounded-full cursor-help" title="Evidence ID: {gap_info['evidence_id']}">📋 {gap_info['evidence_id']}</span>""" if gap_info['evidence_id'] else ""
            
            html += f"""
                <div class="gap-card bg-white border border-gray-200 rounded-lg shadow-sm hover:shadow-md transition-all duration-200 overflow-hidden">
                    <div class="bg-gray-50 px-4 py-3 border-b border-gray-200 flex items-center justify-between">
                        <div class="flex items-center space-x-2">
                            <span class="bg-ms-blue text-white text-xs px-2 py-1 rounded-full font-bold">#{i+1}</span>
                            <span class="bg-gray-600 text-white text-xs px-2 py-1 rounded font-medium">{platform}</span>
                        </div>
                        {evidence_badge}
                    </div>
                    <div class="p-4 space-y-4">
                        <div>
                            <strong class="text-red-600 text-sm font-semibold">Edge Gap:</strong>
                            <p class="text-gray-700 text-sm mt-1 leading-relaxed">{edge_gap}</p>
                        </div>
                        <div>
                            <strong class="text-green-600 text-sm font-semibold">Chrome Advantage:</strong>
                            <p class="text-gray-700 text-sm mt-1 leading-relaxed">{chrome_feature}</p>
                        </div>
                    </div>
                </div>
            """
        
        html += """
            </div>
        </div>
        """
    
    return html

def generate_feature_cards_html(features):
    """Generate HTML cards for features"""
    if not features:
        return "<p>No feature inventory available.</p>"
    
    html = ""
    for feature in features:
        platforms = feature.get('platforms_in_source', [])
        platform_badges = ""
        for platform in platforms:
            platform_class = platform.lower()
            platform_badges += f'<span class="platform-badge {platform_class}">{platform}</span>'
        
        html += f"""
        <div class="feature-card">
            <div class="feature-name">{feature.get('name', 'Unknown Feature')}</div>
            <div class="feature-purpose">{feature.get('one_line_purpose', 'No description available')}</div>
            <div class="feature-quote">"{feature.get('direct_quote_≤40w', 'No quote available')}"</div>
            <div style="margin-top: 12px;">{platform_badges}</div>
        </div>
        """
    return html

def generate_raw_analysis_html(processed_posts):
    """Generate HTML for raw analysis data"""
    html = ""
    for i, post in enumerate(processed_posts, 1):
        html += f"""
        <div class="post-card">
            <h3>Post {i}: {post.get('title', 'Unknown Title')}</h3>
            <p><strong>URL:</strong> <a href="{post.get('url', '#')}" target="_blank">{post.get('url', 'N/A')}</a></p>
            <p><strong>Date:</strong> {post.get('publish_date', 'Unknown')}</p>
            <p><strong>Author:</strong> {post.get('author', 'Unknown')}</p>
            
            <h4>AI Analysis</h4>
            <div class="analysis-content">
                <pre style="white-space: pre-wrap; font-family: inherit; font-size: 0.9rem;">{post.get('ai_analysis', 'No analysis available')}</pre>
            </div>
        </div>
        """
    return html

def generate_strategic_actions_html(posts):
    """Generate HTML for Strategic Actions table"""
    html = ""
    for post in posts:
        data = post.get('structured_data', {})
        strategic_actions = data.get('strategic_actions', [])
        
        if strategic_actions:
            html += """
            <div class="mb-8">
                <div class="overflow-x-auto shadow-lg rounded-lg border border-gray-200">
                    <table class="w-full text-sm text-left">
                        <thead class="bg-gray-50 border-b-2 border-gray-200">
                            <tr>
                                <th class="px-6 py-4 font-semibold text-gray-900">Chrome Feature</th>
                                <th class="px-6 py-4 font-semibold text-gray-900">Edge Action</th>
                                <th class="px-6 py-4 font-semibold text-gray-900">Rationale</th>
                                <th class="px-6 py-4 font-semibold text-gray-900">Evidence IDs</th>
                            </tr>
                        </thead>
                        <tbody class="bg-white divide-y divide-gray-200">
            """
            
            for action in strategic_actions:
                feature = action.get('Chrome Feature', 'Unknown')
                edge_action = action.get('Edge Action (Defend|Match|Leapfrog|Deprioritize)', 'Unknown')
                rationale = action.get('Rationale (<=20 words)', action.get('Rationale (≤20 words)', 'No rationale provided'))
                evidence_ids = action.get('Evidence IDs', '')
                
                # Color-code actions with Tailwind classes
                action_lower = edge_action.lower()
                if 'defend' in action_lower:
                    action_class = "bg-blue-100 text-blue-800 border border-blue-200"
                elif 'match' in action_lower:
                    action_class = "bg-green-100 text-green-800 border border-green-200"
                elif 'leapfrog' in action_lower:
                    action_class = "bg-purple-100 text-purple-800 border border-purple-200"
                elif 'deprioritize' in action_lower:
                    action_class = "bg-red-100 text-red-800 border border-red-200"
                else:
                    action_class = "bg-gray-100 text-gray-800 border border-gray-200"
                
                html += f"""
                        <tr class="hover:bg-gray-50 transition-colors duration-150">
                            <td class="px-6 py-4 font-medium text-gray-900">{feature}</td>
                            <td class="px-6 py-4">
                                <span class="inline-flex px-2 py-1 text-xs font-semibold rounded-full {action_class}">
                                    {edge_action}
                                </span>
                            </td>
                            <td class="px-6 py-4 text-gray-700">{rationale}</td>
                            <td class="px-6 py-4 text-blue-600 font-mono text-xs">{evidence_ids}</td>
                        </tr>
                """
            
            html += """
                        </tbody>
                    </table>
                </div>
            </div>
            """
    
    return html if html else '<div class="text-center py-8 text-gray-500">No strategic actions data available.</div>'

def generate_ux_teardown_html(posts):
    """Generate HTML for UX Delta Teardown visualization"""
    html = ""
    for post in posts:
        data = post.get('structured_data', {})
        ux_teardown = data.get('ux_delta_teardown', [])
        
        if ux_teardown:
            html += """
            <div class="mb-8">
                <p class="text-gray-600 mb-6 text-center">Detailed comparison of user experience flows between Chrome and Edge</p>
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            """
            
            for ux_item in ux_teardown:
                feature = ux_item.get('Feature', 'Unknown Feature')
                platform = ux_item.get('Platform', 'Unknown')
                
                # Platform-specific styling
                platform_lower = platform.lower()
                if 'ios' in platform_lower:
                    platform_class = "bg-blue-100 text-blue-800"
                elif 'android' in platform_lower:
                    platform_class = "bg-green-100 text-green-800"
                elif 'desktop' in platform_lower:
                    platform_class = "bg-purple-100 text-purple-800"
                else:
                    platform_class = "bg-gray-100 text-gray-800"
                
                html += f"""
                <div class="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition-shadow duration-200">
                    <div class="bg-gradient-to-r from-blue-50 to-indigo-50 px-6 py-4 border-b border-gray-200">
                        <div class="flex items-center justify-between">
                            <h4 class="font-semibold text-gray-900 text-lg">{feature}</h4>
                            <span class="px-3 py-1 text-xs font-medium rounded-full {platform_class}">{platform}</span>
                        </div>
                    </div>
                    <div class="p-6 space-y-4">
                        <div class="grid grid-cols-1 gap-3">
                            <div class="flex items-start space-x-3">
                                <span class="inline-flex items-center justify-center w-6 h-6 bg-blue-100 text-blue-600 rounded-full text-xs font-bold">1</span>
                                <div class="flex-1">
                                    <span class="text-sm font-medium text-gray-700">Entry Trigger:</span>
                                    <p class="text-sm text-gray-600 mt-1">{ux_item.get('Entry Trigger', 'N/A')}</p>
                                </div>
                            </div>
                            <div class="flex items-start space-x-3">
                                <span class="inline-flex items-center justify-center w-6 h-6 bg-green-100 text-green-600 rounded-full text-xs font-bold">2</span>
                                <div class="flex-1">
                                    <span class="text-sm font-medium text-gray-700">Block/Switch Mechanism:</span>
                                    <p class="text-sm text-gray-600 mt-1">{ux_item.get('Block/Switch Mechanism', 'N/A')}</p>
                                </div>
                            </div>
                            <div class="flex items-start space-x-3">
                                <span class="inline-flex items-center justify-center w-6 h-6 bg-yellow-100 text-yellow-600 rounded-full text-xs font-bold">3</span>
                                <div class="flex-1">
                                    <span class="text-sm font-medium text-gray-700">Data Boundary:</span>
                                    <p class="text-sm text-gray-600 mt-1">{ux_item.get('Data/Account Boundary', 'N/A')}</p>
                                </div>
                            </div>
                            <div class="flex items-start space-x-3">
                                <span class="inline-flex items-center justify-center w-6 h-6 bg-purple-100 text-purple-600 rounded-full text-xs font-bold">4</span>
                                <div class="flex-1">
                                    <span class="text-sm font-medium text-gray-700">Admin Controls:</span>
                                    <p class="text-sm text-gray-600 mt-1">{ux_item.get('Admin/Policy Controls', 'N/A')}</p>
                                </div>
                            </div>
                            <div class="flex items-start space-x-3">
                                <span class="inline-flex items-center justify-center w-6 h-6 bg-red-100 text-red-600 rounded-full text-xs font-bold">5</span>
                                <div class="flex-1">
                                    <span class="text-sm font-medium text-gray-700">Recovery Path:</span>
                                    <p class="text-sm text-gray-600 mt-1">{ux_item.get('Recovery Path', 'N/A')}</p>
                                </div>
                            </div>
                        </div>
                        <div class="border-t border-gray-200 pt-4 space-y-3">
                            <div class="bg-gray-50 rounded-lg p-3">
                                <span class="text-sm font-medium text-gray-700">Notes:</span>
                                <p class="text-sm text-gray-600 mt-1">{ux_item.get('Notes', 'No additional notes')}</p>
                            </div>
                            <div class="flex items-center justify-between">
                                <span class="text-sm font-medium text-gray-700">Evidence:</span>
                                <span class="text-xs font-mono bg-blue-50 text-blue-700 px-2 py-1 rounded">{ux_item.get('Evidence IDs', 'N/A')}</span>
                            </div>
                        </div>
                    </div>
                </div>
                """
            
            html += """
                </div>
            </div>
            """
    
    return html if html else '<div class="text-center py-8 text-gray-500">No UX teardown data available.</div>'

def generate_problem_solution_html(posts):
    """Generate HTML for Problem-Solution Map"""
    html = ""
    for post in posts:
        data = post.get('structured_data', {})
        problem_solution = data.get('problem_solution_map', [])
        
        if problem_solution:
            # Group by category
            categories = {}
            for item in problem_solution:
                category = item.get('Category', 'Other')
                if category not in categories:
                    categories[category] = []
                categories[category].append(item)
            
            html += """
            <div class="mb-8">
                <p class="text-gray-600 mb-6 text-center">Chrome's strategic positioning and problem-solving approach</p>
            """
            
            for category, items in categories.items():
                html += f"""
                <div class="mb-8">
                    <h4 class="text-xl font-semibold text-gray-900 mb-4 pb-2 border-b-2 border-gray-200">{category}</h4>
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                """
                
                for item in items:
                    html += f"""
                    <div class="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition-shadow duration-200">
                        <div class="bg-gradient-to-r from-orange-50 to-red-50 px-6 py-4 border-b border-gray-200">
                            <h5 class="font-semibold text-gray-900 text-lg">{item.get('Problem', 'Unknown Problem')}</h5>
                        </div>
                        <div class="p-6 space-y-4">
                            <div class="space-y-3">
                                <div class="bg-green-50 rounded-lg p-3">
                                    <span class="text-sm font-medium text-green-800">Chrome Solution:</span>
                                    <p class="text-sm text-green-700 mt-1">{item.get('Chrome Feature', 'N/A')}</p>
                                </div>
                                <div class="bg-red-50 rounded-lg p-3">
                                    <span class="text-sm font-medium text-red-800">Pain Point:</span>
                                    <p class="text-sm text-red-700 mt-1">{item.get('Pain Point Addressed', 'N/A')}</p>
                                </div>
                                <div class="bg-blue-50 rounded-lg p-3">
                                    <span class="text-sm font-medium text-blue-800">Value Proposition:</span>
                                    <p class="text-sm text-blue-700 mt-1">{item.get('Value Proposition', 'N/A')}</p>
                                </div>
                            </div>
                            <div class="border-t border-gray-200 pt-3 flex items-center justify-between">
                                <span class="text-sm font-medium text-gray-700">Evidence:</span>
                                <span class="text-xs font-mono bg-blue-50 text-blue-700 px-2 py-1 rounded">{item.get('Evidence IDs', 'N/A')}</span>
                            </div>
                        </div>
                    </div>
                    """
                
                html += """
                    </div>
                </div>
                """
            
            html += "</div>"
    
    return html if html else '<div class="text-center py-8 text-gray-500">No problem-solution mapping data available.</div>'

def generate_feature_parity_html(posts):
    """Generate HTML for enhanced Feature Parity Chart"""
    html = ""
    for post in posts:
        data = post.get('structured_data', {})
        parity_chart = data.get('feature_parity_chart', {})
        
        if parity_chart:
            html += """
            <div class="mb-8">
                <div class="flex flex-wrap justify-center gap-2 mb-6">
            """
            
            # Create platform tabs
            platforms = ['iOS', 'Android', 'Desktop']
            for i, platform in enumerate(platforms):
                if platform in parity_chart:
                    active_class = "bg-blue-600 text-white active" if i == 0 else "bg-gray-200 text-gray-700 hover:bg-gray-300"
                    html += f"""
                    <button class="parity-tab px-4 py-2 rounded-lg font-medium transition-colors duration-200 {active_class}" onclick="showParityPlatform('{platform.lower()}')" id="tab-{platform.lower()}">{platform}</button>
                    """
            
            html += "</div>"
            
            # Create platform content
            for i, platform in enumerate(platforms):
                if platform in parity_chart:
                    active_class = "active" if i == 0 else ""
                    platform_data = parity_chart[platform]
                    
                    html += f"""
                    <div id="parity-{platform.lower()}" class="parity-platform-content {active_class}">
                        <h5 class="text-xl font-semibold text-gray-900 mb-4 text-center">{platform} Feature Parity</h5>
                        <div class="overflow-x-auto shadow-lg rounded-lg border border-gray-200">
                            <table class="min-w-full text-xs table-fixed">
                                <thead class="bg-gray-50 border-b-2 border-gray-200">
                                    <tr>
                                        <th class="px-2 py-2 font-semibold text-gray-900 text-xs w-32">Chrome Feature</th>
                                        <th class="px-2 py-2 font-semibold text-gray-900 text-xs w-20">Chr DeliveryMode</th>
                                        <th class="px-2 py-2 font-semibold text-gray-900 text-xs w-20">Chr AdminPlane</th>
                                        <th class="px-2 py-2 font-semibold text-gray-900 text-xs w-16">Chr Granularity</th>
                                        <th class="px-2 py-2 font-semibold text-gray-900 text-xs w-16">Chr Redirect</th>
                                        <th class="px-2 py-2 font-semibold text-gray-900 text-xs w-32">Edge Capability</th>
                                        <th class="px-2 py-2 font-semibold text-gray-900 text-xs w-20">Edge DeliveryMode</th>
                                        <th class="px-2 py-2 font-semibold text-gray-900 text-xs w-20">Edge AdminPlane</th>
                                        <th class="px-2 py-2 font-semibold text-gray-900 text-xs w-16">Edge Granularity</th>
                                        <th class="px-2 py-2 font-semibold text-gray-900 text-xs w-16">Edge Redirect</th>
                                        <th class="px-2 py-2 font-semibold text-gray-900 text-xs w-48">Delta & Rationale</th>
                                        <th class="px-2 py-2 font-semibold text-gray-900 text-xs w-20">Parity Rating</th>
                                        <th class="px-2 py-2 font-semibold text-gray-900 text-xs w-16">Evidence</th>
                                    </tr>
                                </thead>
                                <tbody class="bg-white divide-y divide-gray-200">
                    """
                    
                    for feature in platform_data:
                        parity_rating = feature.get('Parity Rating', 'Unknown')
                        # Color-code parity ratings
                        parity_lower = parity_rating.lower()
                        if 'full' in parity_lower or 'complete' in parity_lower:
                            parity_class = "bg-green-100 text-green-800 border border-green-200"
                        elif 'partial' in parity_lower or 'limited' in parity_lower:
                            parity_class = "bg-yellow-100 text-yellow-800 border border-yellow-200"
                        elif 'none' in parity_lower or 'missing' in parity_lower:
                            parity_class = "bg-red-100 text-red-800 border border-red-200"
                        else:
                            parity_class = "bg-gray-100 text-gray-800 border border-gray-200"
                        
                        html += f"""
                                    <tr class="hover:bg-gray-50 transition-colors duration-150">
                                        <td class="px-2 py-2 font-medium text-gray-900 text-xs w-32 break-words">{feature.get('Chrome Feature', 'N/A')}</td>
                                        <td class="px-2 py-2 text-gray-700 text-xs w-20 break-words">{feature.get('Chrome DeliveryMode', 'N/A')}</td>
                                        <td class="px-2 py-2 text-gray-700 text-xs w-20 break-words">{feature.get('Chrome AdminPlane', 'N/A')}</td>
                                        <td class="px-2 py-2 text-gray-700 text-xs w-16 break-words">{feature.get('Chrome Granularity', 'N/A')}</td>
                                        <td class="px-2 py-2 text-gray-700 text-xs w-16 break-words">{feature.get('Chrome RedirectSupport', 'N/A')}</td>
                                        <td class="px-2 py-2 text-gray-700 text-xs w-32 break-words">{feature.get('Edge Capability', 'N/A')}</td>
                                        <td class="px-2 py-2 text-gray-700 text-xs w-20 break-words">{feature.get('Edge DeliveryMode', 'N/A')}</td>
                                        <td class="px-2 py-2 text-gray-700 text-xs w-20 break-words">{feature.get('Edge AdminPlane', 'N/A')}</td>
                                        <td class="px-2 py-2 text-gray-700 text-xs w-16 break-words">{feature.get('Edge Granularity', 'N/A')}</td>
                                        <td class="px-2 py-2 text-gray-700 text-xs w-16 break-words">{feature.get('Edge RedirectSupport', 'N/A')}</td>
                                        <td class="px-2 py-2 text-gray-700 text-xs w-48 break-words leading-tight">{feature.get('Delta & Rationale', 'N/A')}</td>
                                        <td class="px-2 py-2 w-20">
                                            <span class="inline-flex px-1 py-1 text-xs font-semibold rounded {parity_class}">
                                                {parity_rating}
                                            </span>
                                        </td>
                                        <td class="px-2 py-2 text-blue-600 font-mono text-xs w-16 break-words">{feature.get('Evidence IDs', 'N/A')}</td>
                                    </tr>
                        """
                    
                    html += """
                                </tbody>
                            </table>
                        </div>
                    </div>
                    """
            
            html += "</div>"
    
    return html if html else '<div class="text-center py-8 text-gray-500">No feature parity data available.</div>'

def get_enhanced_competitive_js():
    """Return JavaScript for enhanced competitive intelligence features"""
    return """
        // Tab switching functionality
        function showTab(tabName) {
            // Hide all tab contents
            const tabContents = document.querySelectorAll('.tab-content');
            tabContents.forEach(tab => tab.classList.remove('active'));
            
            // Remove active class from all nav tabs
            const navTabs = document.querySelectorAll('.nav-tab');
            navTabs.forEach(tab => tab.classList.remove('active'));
            
            // Show selected tab content
            document.getElementById(tabName).classList.add('active');
            
            // Add active class to clicked nav tab
            event.target.classList.add('active');
        }
        
        // Evidence filtering
        let currentProductFilter = 'all';
        let currentPlatformFilter = 'all';
        let currentSearchTerm = '';
        
        function filterByProduct(product) {
            currentProductFilter = product;
            updateEvidenceDisplay();
            
            // Update button states
            document.querySelectorAll('.evidence-filters .filter-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            event.target.classList.add('active');
        }
        
        function filterByPlatform(platform) {
            currentPlatformFilter = platform;
            updateEvidenceDisplay();
        }
        
        function filterEvidence() {
            currentSearchTerm = event.target.value.toLowerCase();
            updateEvidenceDisplay();
        }
        
        function updateEvidenceDisplay() {
            const evidenceCards = document.querySelectorAll('.evidence-card');
            
            evidenceCards.forEach(card => {
                const product = card.getAttribute('data-product');
                const platforms = card.getAttribute('data-platforms').split(',');
                const text = card.textContent.toLowerCase();
                
                let showCard = true;
                
                // Product filter
                if (currentProductFilter !== 'all' && product !== currentProductFilter) {
                    showCard = false;
                }
                
                // Platform filter
                if (currentPlatformFilter !== 'all' && !platforms.includes(currentPlatformFilter)) {
                    showCard = false;
                }
                
                // Search filter
                if (currentSearchTerm && !text.includes(currentSearchTerm)) {
                    showCard = false;
                }
                
                card.style.display = showCard ? 'block' : 'none';
            });
        }
        
        // Feature Parity Platform switching
        function showParityPlatform(platform) {
            // Hide all platform contents
            const platformContents = document.querySelectorAll('.parity-platform-content');
            platformContents.forEach(content => {
                content.classList.remove('active');
                content.style.display = 'none';
            });
            
            // Remove active styling from all parity tabs
            const parityTabs = document.querySelectorAll('.parity-tab');
            parityTabs.forEach(tab => {
                tab.classList.remove('active', 'bg-blue-600', 'text-white');
                tab.classList.add('bg-gray-200', 'text-gray-700');
            });
            
            // Show selected platform content
            const targetContent = document.getElementById('parity-' + platform);
            if (targetContent) {
                targetContent.classList.add('active');
                targetContent.style.display = 'block';
            }
            
            // Activate selected tab with blue styling
            const targetTab = document.getElementById('tab-' + platform);
            if (targetTab) {
                targetTab.classList.add('active', 'bg-blue-600', 'text-white');
                targetTab.classList.remove('bg-gray-200', 'text-gray-700');
            }
        }
        
        // Enhanced search across all data
        function searchAllData() {
            const searchTerm = event.target.value.toLowerCase();
            
            // Search evidence cards
            const evidenceCards = document.querySelectorAll('.evidence-card');
            evidenceCards.forEach(card => {
                const text = card.textContent.toLowerCase();
                card.style.display = text.includes(searchTerm) ? 'block' : 'none';
            });
            
            // Search UX flow cards
            const uxCards = document.querySelectorAll('.ux-flow-card');
            uxCards.forEach(card => {
                const text = card.textContent.toLowerCase();
                card.style.display = text.includes(searchTerm) ? 'block' : 'none';
            });
            
            // Search problem-solution cards
            const problemCards = document.querySelectorAll('.problem-solution-card');
            problemCards.forEach(card => {
                const text = card.textContent.toLowerCase();
                card.style.display = text.includes(searchTerm) ? 'block' : 'none';
            });
            
            // Search table rows
            const tableRows = document.querySelectorAll('.enhanced-table tbody tr, .parity-detailed-table tbody tr');
            tableRows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(searchTerm) ? 'table-row' : 'none';
            });
        }
        
        // Initialize on page load
        document.addEventListener('DOMContentLoaded', function() {
            console.log('Enhanced competitive intelligence report loaded with Phase 1 improvements');
            
            // Add global search functionality
            const searchInputs = document.querySelectorAll('.search-input');
            searchInputs.forEach(input => {
                input.addEventListener('input', searchAllData);
            });
            
            // Initialize first parity platform tab
            const firstParityTab = document.querySelector('.parity-tab');
            if (firstParityTab) {
                firstParityTab.click();
            }
        });
    """

def create_professional_html_report(processed_posts, report_id, timestamp, report_date):
    """
    Create the actual HTML content for the report (enhanced version)
    
    Args:
        processed_posts (list): Posts with structured data
        report_id (str): Report identifier
        timestamp (str): Human-readable timestamp
        report_date (str): Date in YYYY-MM-DD format
        
    Returns:
        str: Complete HTML content
    """
    # Check if we have competitive intelligence data
    has_competitive_data = any(
        post.get('structured_data') and 
        (post['structured_data'].get('evidence_register') or 
         post['structured_data'].get('feature_inventory'))
        for post in processed_posts
    )
    
    # Debug: Print which function will be called
    print(f"📊 Report type decision: {'Enhanced' if has_competitive_data else 'Legacy'}")
    if processed_posts and processed_posts[0].get('structured_data'):
        data = processed_posts[0]['structured_data']
        print(f"   Evidence register items: {len(data.get('evidence_register', []))}")
        print(f"   Feature inventory items: {len(data.get('feature_inventory', []))}")
    
    if has_competitive_data:
        print("✅ Using Markdown report generation")
        # Import the markdown generation function
        try:
            from generate_report_from_input import create_competitive_intelligence_markdown
            # Create systematic parsing data format
            parsed_data = {
                'executive_summary': processed_posts[0].get('structured_data', {}).get('executive_summary', ''),
                'edge_competitive_gaps': processed_posts[0].get('structured_data', {}).get('edge_competitive_gaps', []),
                'strategic_actions': processed_posts[0].get('structured_data', {}).get('strategic_actions', []),
                'feature_parity_analysis': processed_posts[0].get('structured_data', {}).get('feature_parity_chart', {}),
                'ux_competitive_analysis': processed_posts[0].get('structured_data', {}).get('ux_delta_teardown', []),
                'edge_advantages': processed_posts[0].get('structured_data', {}).get('edge_advantage_highlights', []),
                'evidence_base': processed_posts[0].get('structured_data', {}).get('evidence_register', []),
                'capability_term_harvest': processed_posts[0].get('structured_data', {}).get('capability_term_harvest', []),
                'diff_matrix': processed_posts[0].get('structured_data', {}).get('diff_matrix', []),
                'feature_inventory': processed_posts[0].get('structured_data', {}).get('feature_inventory', []),
                'problem_solution_map': processed_posts[0].get('structured_data', {}).get('problem_solution_map', [])
            }
            
            markdown_content = create_competitive_intelligence_markdown(parsed_data)
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"competitive_intelligence_markdown_{timestamp}.md"
            
            return filename, markdown_content
            
        except ImportError as e:
            print(f"⚠️ Markdown generation not available: {e}")
            print("⚠️ Falling back to legacy HTML report")
            return create_legacy_html_report(processed_posts, report_id, timestamp, report_date)
    else:
        print("⚠️ Using create_legacy_html_report")
        return create_legacy_html_report(processed_posts, report_id, timestamp, report_date)

def create_legacy_html_report(processed_posts, report_id, timestamp, report_date):
    """
    Create legacy HTML content for non-competitive intelligence data
    """
    # Count successful analyses
    successful_posts = [p for p in processed_posts if p['structured_data']]
    failed_posts = [p for p in processed_posts if not p['structured_data']]
    
    # Generate executive overview
    executive_overview = generate_executive_overview(successful_posts)
    
    # Start building HTML
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chrome Enterprise Intelligence Report - {report_date}</title>
    <style>
        {get_enhanced_competitive_css()}
    </style>
</head>
<body>
    <div class="container">
        <header class="report-header">
            <div class="header-content">
                <h1>🔍 Microsoft Edge Competitive Intelligence</h1>
                <p class="subtitle">Chrome Enterprise Blog Monitoring Report</p>
                <div class="report-meta">
                    <span class="report-id">Report ID: {report_id}</span>
                    <span class="report-date">Generated: {timestamp}</span>
                </div>
            </div>
        </header>

        <section class="executive-summary">
            <h2>📊 Executive Summary</h2>
            <div class="summary-stats">
                <div class="stat-card">
                    <div class="stat-number">{len(successful_posts)}</div>
                    <div class="stat-label">Posts Analyzed</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{len([p for p in successful_posts if p['structured_data'] and p['structured_data'].get('priority_level') == 'High'])}</div>
                    <div class="stat-label">High Priority</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{len(failed_posts)}</div>
                    <div class="stat-label">Analysis Failures</div>
                </div>
            </div>
            {executive_overview}
        </section>

        <section class="detailed-analysis">
            <h2>📰 Detailed Analysis</h2>
            {generate_detailed_posts_html(successful_posts)}
        </section>

        {generate_failure_section_html(failed_posts) if failed_posts else ''}

        <footer class="report-footer">
            <p>Generated by Microsoft Edge Competitive Intelligence System</p>
            <p>Automated Chrome Enterprise Blog Monitoring | {timestamp}</p>
            <p><small>Report ID: {report_id} | Source: Google Cloud Chrome Enterprise Blog</small></p>
        </footer>
    </div>

    <script>
        {get_interactive_js()}
    </script>
</body>
</html>"""
    
    return html_content

def generate_executive_overview(successful_posts):
    """Generate executive overview section from structured data"""
    if not successful_posts:
        return "<p>No successful analyses available for executive overview.</p>"
    
    # Collect key insights
    all_threats = []
    all_opportunities = []
    high_priority_count = 0
    
    for post in successful_posts:
        data = post.get('structured_data', {})
        if data:
            all_threats.extend(data.get('competitive_threats', []))
            all_opportunities.extend(data.get('opportunities', []))
            if data.get('priority_level') == 'High':
                high_priority_count += 1
    
    # Remove duplicates and take top items
    unique_threats = list(set(all_threats))[:3]
    unique_opportunities = list(set(all_opportunities))[:3]
    
    overview_html = f"""
    <div class="overview-content">
        <div class="key-insights">
            <h3>🎯 Key Strategic Insights</h3>
            <ul>
                <li><strong>High Priority Items:</strong> {high_priority_count} out of {len(successful_posts)} posts require immediate attention</li>
                <li><strong>Competitive Threats:</strong> {len(unique_threats)} distinct threats identified</li>
                <li><strong>Strategic Opportunities:</strong> {len(unique_opportunities)} opportunities discovered</li>
            </ul>
        </div>
        
        {"<div class='threat-summary'><h4>🚨 Top Competitive Threats</h4><ul>" + "".join([f"<li>{threat}</li>" for threat in unique_threats]) + "</ul></div>" if unique_threats else ""}
        
        {"<div class='opportunity-summary'><h4>💡 Strategic Opportunities</h4><ul>" + "".join([f"<li>{opp}</li>" for opp in unique_opportunities]) + "</ul></div>" if unique_opportunities else ""}
    </div>
    """
    
    return overview_html

def generate_detailed_posts_html(successful_posts):
    """Generate detailed analysis section for each post"""
    if not successful_posts:
        return "<p>No successful analyses to display.</p>"
    
    posts_html = ""
    
    for post in successful_posts:
        data = post.get('structured_data', {})
        if not data:
            continue
            
        priority_class = f"priority-{data.get('priority_level', 'medium').lower()}"
        
        posts_html += f"""
        <article class="post-analysis {priority_class}">
            <header class="post-header">
                <h3 class="post-title">
                    <span class="post-number">#{post['post_number']}</span>
                    {post['title']}
                    <span class="priority-badge priority-{data.get('priority_level', 'medium').lower()}">{data.get('priority_level', 'Medium')}</span>
                </h3>
                <div class="post-meta">
                    <span><strong>Author:</strong> {post['author']}</span>
                    <span><strong>Published:</strong> {post['publish_date']}</span>
                    <span><strong>URL:</strong> <a href="{post['url']}" target="_blank">View Original</a></span>
                </div>
            </header>
            
            <div class="analysis-content">
                <section class="executive-summary-section">
                    <h4>📋 Executive Summary</h4>
                    <p>{data.get('executive_summary', 'No summary available')}</p>
                </section>
                
                {"<section class='technologies-section'><h4>🔧 Key Technologies</h4>" + generate_technologies_table(data.get('key_technologies', [])) + "</section>" if data.get('key_technologies') else ""}
                
                <section class="impact-section">
                    <h4>💼 Business Impact</h4>
                    <p>{data.get('business_impact', 'No business impact analysis available')}</p>
                </section>
                
                {"<section class='threats-section'><h4>🚨 Competitive Threats</h4><ul>" + "".join([f"<li>{threat}</li>" for threat in data.get('competitive_threats', [])]) + "</ul></section>" if data.get('competitive_threats') else ""}
                
                {"<section class='opportunities-section'><h4>💡 Opportunities</h4><ul>" + "".join([f"<li>{opp}</li>" for opp in data.get('opportunities', [])]) + "</ul></section>" if data.get('opportunities') else ""}
                
                {"<section class='recommendations-section'><h4>📝 Recommendations</h4><ul>" + "".join([f"<li>{rec}</li>" for rec in data.get('recommendations', [])]) + "</ul></section>" if data.get('recommendations') else ""}
                
                {"<section class='metrics-section'><h4>📊 Key Metrics</h4>" + generate_metrics_table(data.get('key_metrics', [])) + "</section>" if data.get('key_metrics') else ""}
            </div>
        </article>
        """
    
    return posts_html

def generate_technologies_table(technologies):
    """Generate HTML table for technologies"""
    if not technologies:
        return "<p>No technologies identified.</p>"
    
    table_html = """
    <table class="technologies-table">
        <thead>
            <tr>
                <th>Technology</th>
                <th>Description</th>
                <th>Business Impact</th>
            </tr>
        </thead>
        <tbody>
    """
    
    for tech in technologies:
        table_html += f"""
            <tr>
                <td><strong>{tech.get('name', 'Unknown')}</strong></td>
                <td>{tech.get('description', 'No description')}</td>
                <td>{tech.get('impact', 'No impact analysis')}</td>
            </tr>
        """
    
    table_html += "</tbody></table>"
    return table_html

def generate_metrics_table(metrics):
    """Generate HTML table for key metrics"""
    if not metrics:
        return "<p>No metrics available.</p>"
    
    table_html = """
    <table class="metrics-table">
        <thead>
            <tr>
                <th>Metric</th>
                <th>Value</th>
                <th>Significance</th>
            </tr>
        </thead>
        <tbody>
    """
    
    for metric in metrics:
        table_html += f"""
            <tr>
                <td><strong>{metric.get('metric', 'Unknown')}</strong></td>
                <td>{metric.get('value', 'No value')}</td>
                <td>{metric.get('significance', 'No significance noted')}</td>
            </tr>
        """
    
    table_html += "</tbody></table>"
    return table_html

def generate_failure_section_html(failed_posts):
    """Generate section for failed analyses"""
    if not failed_posts:
        return ""
    
    failure_html = """
    <section class="analysis-failures">
        <h2>⚠️ Analysis Failures</h2>
        <p>The following posts could not be processed for structured analysis:</p>
        <ul class="failure-list">
    """
    
    for post in failed_posts:
        failure_html += f"""
            <li>
                <strong>{post['title']}</strong>
                <span class="failure-meta">Author: {post['author']} | <a href="{post['url']}" target="_blank">View Original</a></span>
                <p class="raw-analysis">{post.get('ai_analysis', 'No analysis available')[:200]}...</p>
            </li>
        """
    
    failure_html += "</ul></section>"
    return failure_html

def get_professional_css():
    """Return professional CSS styling for HTML reports"""
    return """
        /* Reset and Base Styles */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f8f9fa;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }

        /* Header Styles */
        .report-header {
            background: linear-gradient(135deg, #0078d4, #106ebe);
            color: white;
            padding: 40px 30px;
            text-align: center;
        }

        .report-header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            font-weight: 300;
        }

        .subtitle {
            font-size: 1.2em;
            opacity: 0.9;
            margin-bottom: 20px;
        }

        .report-meta {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid rgba(255,255,255,0.3);
            font-size: 0.9em;
        }

        /* Executive Summary */
        .executive-summary {
            padding: 40px 30px;
            background: #f8f9fa;
            border-bottom: 3px solid #0078d4;
        }

        .summary-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }

        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 4px solid #0078d4;
        }

        .stat-number {
            font-size: 2.5em;
            font-weight: bold;
            color: #0078d4;
        }

        .stat-label {
            color: #666;
            text-transform: uppercase;
            font-size: 0.8em;
            letter-spacing: 1px;
        }

        /* Section Styles */
        section {
            padding: 30px;
        }

        h2 {
            color: #0078d4;
            font-size: 1.8em;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e1e5e9;
        }

        h3 {
            color: #0078d4;
            font-size: 1.4em;
            margin: 20px 0 10px 0;
        }

        h4 {
            color: #333;
            font-size: 1.1em;
            margin: 15px 0 8px 0;
            font-weight: 600;
        }

        /* Post Analysis Cards */
        .post-analysis {
            background: white;
            margin: 20px 0;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow: hidden;
        }

        .post-header {
            padding: 20px;
            background: #f8f9fa;
            border-left: 5px solid #0078d4;
        }

        .post-title {
            display: flex;
            align-items: center;
            gap: 15px;
            font-size: 1.3em;
            margin-bottom: 10px;
        }

        .post-number {
            background: #0078d4;
            color: white;
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 0.8em;
        }

        .priority-badge {
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.7em;
            text-transform: uppercase;
            font-weight: bold;
            margin-left: auto;
        }

        .priority-high {
            background: #dc3545;
            color: white;
        }

        .priority-medium {
            background: #ffc107;
            color: #333;
        }

        .priority-low {
            background: #28a745;
            color: white;
        }

        .post-meta {
            display: flex;
            gap: 20px;
            font-size: 0.9em;
            color: #666;
            flex-wrap: wrap;
        }

        .post-meta a {
            color: #0078d4;
            text-decoration: none;
        }

        .post-meta a:hover {
            text-decoration: underline;
        }

        /* Analysis Content */
        .analysis-content {
            padding: 20px;
        }

        .analysis-content section {
            margin: 20px 0;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 5px;
            border-left: 3px solid #0078d4;
        }

        /* Tables */
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            background: white;
            border-radius: 5px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }

        th, td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #e1e5e9;
        }

        th {
            background: #0078d4;
            color: white;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.8em;
            letter-spacing: 1px;
        }

        tr:hover {
            background: #f8f9fa;
        }

        /* Lists */
        ul {
            list-style: none;
            padding: 0;
        }

        li {
            padding: 8px 0;
            padding-left: 20px;
            position: relative;
        }

        li:before {
            content: "→";
            position: absolute;
            left: 0;
            color: #0078d4;
            font-weight: bold;
        }

        /* Overview Content */
        .overview-content {
            display: grid;
            grid-template-columns: 1fr;
            gap: 20px;
        }

        .key-insights {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .threat-summary, .opportunity-summary {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .threat-summary {
            border-left: 4px solid #dc3545;
        }

        .opportunity-summary {
            border-left: 4px solid #28a745;
        }

        /* Analysis Failures */
        .analysis-failures {
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 5px;
            padding: 20px;
            margin: 20px 0;
        }

        .failure-list li {
            background: white;
            margin: 10px 0;
            padding: 15px;
            border-radius: 5px;
            border-left: 4px solid #ffc107;
        }

        .failure-meta {
            display: block;
            font-size: 0.9em;
            color: #666;
            margin: 5px 0;
        }

        .raw-analysis {
            background: #f8f9fa;
            padding: 10px;
            border-radius: 3px;
            font-size: 0.9em;
            margin-top: 10px;
            font-family: monospace;
        }

        /* Footer */
        .report-footer {
            background: #333;
            color: white;
            padding: 30px;
            text-align: center;
        }

        .report-footer p {
            margin: 5px 0;
        }

        .report-footer small {
            opacity: 0.7;
        }

        /* Responsive Design */
        @media (max-width: 768px) {
            .container {
                margin: 0;
                box-shadow: none;
            }

            .report-header {
                padding: 20px 15px;
            }

            .report-header h1 {
                font-size: 2em;
            }

            .report-meta {
                flex-direction: column;
                gap: 10px;
            }

            section {
                padding: 20px 15px;
            }

            .summary-stats {
                grid-template-columns: 1fr;
            }

            .post-meta {
                flex-direction: column;
                gap: 10px;
            }

            table {
                font-size: 0.8em;
            }

            th, td {
                padding: 8px 10px;
            }
        }

        /* Print Styles */
        @media print {
            body {
                background: white;
            }

            .container {
                box-shadow: none;
                max-width: none;
            }

            .report-header {
                background: #0078d4 !important;
                color: white !important;
            }

            .post-analysis {
                break-inside: avoid;
                page-break-inside: avoid;
            }

            a {
                color: #0078d4 !important;
            }
        }

        /* Animation */
        .post-analysis {
            opacity: 0;
            animation: slideInUp 0.5s ease forwards;
        }

        .post-analysis:nth-child(1) { animation-delay: 0.1s; }
        .post-analysis:nth-child(2) { animation-delay: 0.2s; }
        .post-analysis:nth-child(3) { animation-delay: 0.3s; }

        @keyframes slideInUp {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
    """

def get_enhanced_competitive_css():
    """Return enhanced CSS styling for competitive intelligence HTML reports"""
    return """
        /* Reset and Base Styles */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f8f9fa;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }
        /* Header Styles */
        .report-header {
            background: linear-gradient(135deg, #0078d4, #106ebe);
            color: white;
            padding: 40px 30px;
            text-align: center;
        }
        .report-title {
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 10px;
        }
        .report-subtitle {
            font-size: 1.2rem;
            opacity: 0.9;
        }
        
        /* Navigation Tabs */
        .nav-tabs {
            display: flex;
            background: #f1f3f4;
            border-bottom: 3px solid #0078d4;
            padding: 0 30px;
        }
        .nav-tab {
            padding: 15px 25px;
            background: none;
            border: none;
            font-size: 1rem;
            font-weight: 500;
            cursor: pointer;
            color: #666;
            transition: all 0.3s ease;
            border-bottom: 3px solid transparent;
        }
        .nav-tab.active {
            color: #0078d4;
            border-bottom-color: #0078d4;
            background: white;
        }
        .nav-tab:hover {
            background: #e8f3ff;
            color: #0078d4;
        }
        
        /* Tab Content */
        .tab-content {
            display: none;
            padding: 30px;
        }
        .tab-content.active {
            display: block;
        }
        
        /* Evidence Navigator */
        .evidence-section {
            margin-bottom: 40px;
        }
        .evidence-filters {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .filter-btn {
            padding: 8px 16px;
            border: 2px solid #e1e5e9;
            background: white;
            color: #666;
            border-radius: 20px;
            cursor: pointer;
            font-size: 0.9rem;
            transition: all 0.3s ease;
        }
        .filter-btn.active, .filter-btn:hover {
            background: #0078d4;
            color: white;
            border-color: #0078d4;
        }
        .evidence-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .evidence-card {
            border: 1px solid #e1e5e9;
            border-radius: 8px;
            padding: 20px;
            background: white;
            transition: all 0.3s ease;
        }
        .evidence-card:hover {
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            transform: translateY(-2px);
        }
        .evidence-id {
            font-weight: bold;
            color: #0078d4;
            font-size: 0.9rem;
            margin-bottom: 8px;
        }
        .evidence-product {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 0.8rem;
            font-weight: 500;
            margin-bottom: 10px;
        }
        .evidence-product.chrome {
            background: #e8f0fe;
            color: #1967d2;
        }
        .evidence-product.edge {
            background: #e1f5fe;
            color: #0078d4;
        }
        .evidence-feature {
            font-weight: 600;
            margin-bottom: 8px;
            color: #333;
        }
        .evidence-quote {
            font-style: italic;
            color: #666;
            line-height: 1.5;
            border-left: 3px solid #0078d4;
            padding-left: 12px;
            margin: 10px 0;
        }
        .evidence-platforms {
            display: flex;
            gap: 6px;
            margin-top: 12px;
        }
        .platform-badge {
            padding: 3px 8px;
            border-radius: 10px;
            font-size: 0.75rem;
            font-weight: 500;
        }
        .platform-badge.desktop {
            background: #f3e5f5;
            color: #7b1fa2;
        }
        .platform-badge.ios {
            background: #e8f5e8;
            color: #2e7d32;
        }
        .platform-badge.android {
            background: #fff3e0;
            color: #f57c00;
        }
        
        /* Capability Matrix */
        .capability-matrix {
            overflow-x: auto;
            margin-bottom: 40px;
        }
        .parity-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }
        .parity-table th, .parity-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e1e5e9;
        }
        .parity-table th {
            background: #f8f9fa;
            font-weight: 600;
            color: #333;
            position: sticky;
            top: 0;
        }
        .parity-rating {
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 0.8rem;
            font-weight: 500;
        }
        .parity-rating.superior {
            background: #e8f5e8;
            color: #2e7d32;
        }
        .parity-rating.on-par {
            background: #fff3e0;
            color: #f57c00;
        }
        .parity-rating.inferior {
            background: #ffebee;
            color: #c62828;
        }
        .parity-rating.unknown {
            background: #f5f5f5;
            color: #666;
        }
        
        /* Gaps Dashboard */
        .gaps-dashboard {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 30px;
        }
        .gap-summary {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 20px;
        }
        .gap-count {
            text-align: center;
        }
        .gap-count .count {
            display: block;
            font-size: 2.5rem;
            font-weight: bold;
            color: #c62828;
        }
        .gap-count .label {
            color: #666;
            font-size: 0.9rem;
        }
        .platform-breakdown {
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
        }
        .platform-stat {
            text-align: center;
        }
        .platform-stat .number {
            display: block;
            font-size: 1.5rem;
            font-weight: bold;
            color: #0078d4;
        }
        .platform-stat .platform {
            color: #666;
            font-size: 0.8rem;
        }
        
        /* Gap Items */
        .gap-item {
            background: white;
            border-left: 4px solid #c62828;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 0 4px 4px 0;
        }
        .gap-platform {
            font-weight: bold;
            color: #c62828;
            font-size: 0.9rem;
            margin-bottom: 5px;
        }
        
        /* Feature Inventory */
        .feature-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .feature-card {
            border: 1px solid #e1e5e9;
            border-radius: 8px;
            padding: 20px;
            background: white;
        }
        .feature-name {
            font-weight: bold;
            color: #0078d4;
            margin-bottom: 8px;
        }
        .feature-purpose {
            color: #666;
            margin-bottom: 10px;
            font-size: 0.9rem;
        }
        .feature-quote {
            font-style: italic;
            color: #888;
            border-left: 3px solid #ddd;
            padding-left: 12px;
        }
        
        /* Search and Filter */
        .search-controls {
            display: flex;
            gap: 15px;
            margin-bottom: 25px;
            flex-wrap: wrap;
            align-items: center;
        }
        .search-input {
            flex: 1;
            min-width: 250px;
            padding: 10px 15px;
            border: 2px solid #e1e5e9;
            border-radius: 6px;
            font-size: 1rem;
        }
        .search-input:focus {
            outline: none;
            border-color: #0078d4;
        }
        
        /* Legacy support */
        .post-card, .analysis-content, .key-findings {
            margin-bottom: 20px;
            padding: 20px;
            background: white;
            border-radius: 8px;
            border: 1px solid #e1e5e9;
        }
        
        /* Responsive Design */
        @media (max-width: 768px) {
            .container {
                margin: 0;
                box-shadow: none;
            }
            .nav-tabs {
                padding: 0 15px;
                overflow-x: auto;
            }
            .tab-content {
                padding: 20px 15px;
            }
            .evidence-grid {
                grid-template-columns: 1fr;
            }
            .gap-summary {
                flex-direction: column;
                text-align: center;
            }
            .platform-breakdown {
                justify-content: center;
            }
        }
        
        /* Enhanced Table Styles */
        .enhanced-table, .parity-detailed-table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            font-size: 0.9rem;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .enhanced-table th, .parity-detailed-table th {
            background: #f8f9fa;
            font-weight: 600;
            padding: 12px;
            text-align: left;
            border-bottom: 2px solid #e1e5e9;
            position: sticky;
            top: 0;
        }
        .enhanced-table td, .parity-detailed-table td {
            padding: 12px;
            border-bottom: 1px solid #e1e5e9;
            vertical-align: top;
        }
        .enhanced-table tr:hover, .parity-detailed-table tr:hover {
            background: #f8f9fa;
        }
        
        /* Action Badges */
        .action-badge {
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.8rem;
            font-weight: 500;
            text-transform: capitalize;
        }
        .action-badge.match {
            background: #fff3e0;
            color: #f57c00;
        }
        .action-badge.defend {
            background: #e8f5e8;
            color: #2e7d32;
        }
        .action-badge.leapfrog {
            background: #e3f2fd;
            color: #1976d2;
        }
        .action-badge.deprioritize {
            background: #fce4ec;
            color: #c2185b;
        }
        
        /* UX Teardown Styles */
        .ux-teardown-section {
            margin: 20px 0;
        }
        .ux-flow-card {
            border: 1px solid #e1e5e9;
            border-radius: 8px;
            margin: 15px 0;
            background: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .ux-header {
            background: #f8f9fa;
            padding: 15px;
            border-bottom: 1px solid #e1e5e9;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .ux-header h4 {
            margin: 0;
            color: #0078d4;
        }
        .ux-flow-details {
            padding: 20px;
        }
        .ux-step {
            display: flex;
            margin-bottom: 10px;
            align-items: flex-start;
        }
        .step-label {
            font-weight: 600;
            min-width: 140px;
            color: #666;
        }
        .step-value {
            flex: 1;
            color: #333;
        }
        .ux-notes {
            margin: 15px 0;
            padding: 10px;
            background: #f8f9fa;
            border-radius: 4px;
            font-style: italic;
        }
        
        /* Problem-Solution Map Styles */
        .problem-solution-section {
            margin: 20px 0;
        }
        .category-section {
            margin: 25px 0;
        }
        .category-title {
            color: #0078d4;
            border-bottom: 2px solid #0078d4;
            padding-bottom: 5px;
            margin-bottom: 15px;
        }
        .problem-solution-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .problem-solution-card {
            border: 1px solid #e1e5e9;
            border-radius: 8px;
            background: white;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .problem-header {
            background: #f8f9fa;
            padding: 15px;
            border-bottom: 1px solid #e1e5e9;
        }
        .problem-header h5 {
            margin: 0;
            color: #c62828;
            font-size: 1.1rem;
        }
        .solution-details {
            padding: 15px;
        }
        .solution-details > div {
            margin-bottom: 10px;
        }
        .solution-feature {
            color: #1976d2;
        }
        .pain-point {
            color: #f57c00;
        }
        .value-prop {
            color: #2e7d32;
        }
        
        /* Feature Parity Platform Tabs */
        .parity-platform-tabs {
            display: flex;
            background: #f1f3f4;
            border-radius: 8px 8px 0 0;
            margin: 20px 0 0 0;
        }
        .parity-tab {
            padding: 12px 20px;
            background: none;
            border: none;
            font-size: 0.9rem;
            font-weight: 500;
            cursor: pointer;
            color: #666;
            transition: all 0.3s ease;
            border-radius: 8px 8px 0 0;
        }
        .parity-tab.active {
            color: #0078d4;
            background: white;
            border-bottom: 2px solid #0078d4;
        }
        .parity-tab:hover {
            background: #e8f3ff;
            color: #0078d4;
        }
        .parity-platform-content {
            display: none;
            background: white;
            border: 1px solid #e1e5e9;
            border-radius: 0 0 8px 8px;
            padding: 20px;
        }
        .parity-platform-content.active {
            display: block;
        }
        .parity-table-wrapper {
            overflow-x: auto;
            margin-top: 15px;
        }
        .delta-analysis {
            max-width: 200px;
            word-wrap: break-word;
        }
        
        /* CSV Table Wrappers */
        .csv-table-wrapper {
            overflow-x: auto;
            margin: 20px 0;
        }
        .section-description {
            color: #666;
            font-style: italic;
            margin-bottom: 20px;
        }
        
        /* Evidence References */
        .evidence-refs {
            font-size: 0.8rem;
            color: #666;
            font-family: monospace;
        }
        
        /* Gap Analysis Styles */
        .gaps-overview {
            margin-bottom: 30px;
        }
        .gaps-summary {
            display: flex;
            justify-content: center;
            margin-bottom: 20px;
        }
        .platform-gap-section {
            margin-bottom: 30px;
        }
        .platform-gap-title {
            color: #0078d4;
            font-size: 1.3rem;
            margin-bottom: 15px;
            padding-bottom: 5px;
            border-bottom: 2px solid #e1e5e9;
        }
        .gaps-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
        }
        .gap-card {
            background: white;
            border: 1px solid #e1e5e9;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: box-shadow 0.2s ease;
        }
        .gap-card:hover {
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .gap-header {
            background: #f8f9fa;
            padding: 12px 16px;
            display: flex;
            align-items: center;
            gap: 10px;
            border-bottom: 1px solid #e1e5e9;
        }
        .gap-number {
            background: #0078d4;
            color: white;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 0.8rem;
            font-weight: bold;
        }
        .gap-platform {
            background: #6c757d;
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.8rem;
            font-weight: 500;
        }
        .evidence-badge {
            background: #28a745;
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.8rem;
            cursor: help;
        }
        .gap-content {
            padding: 16px;
        }
        .edge-capability, .chrome-advantage {
            margin-bottom: 12px;
        }
        .edge-capability strong {
            color: #dc3545;
        }
        .chrome-advantage strong {
            color: #28a745;
        }
        .gap-content p {
            margin-top: 5px;
            color: #666;
            line-height: 1.4;
        }
        
        /* Utility Classes */
        .text-center { text-align: center; }
        .mb-20 { margin-bottom: 20px; }
        .mb-30 { margin-bottom: 30px; }
        .hidden { display: none; }
    """

def get_interactive_js():
    """Return JavaScript for interactive features"""
    return """
        // Initialize interactive features when DOM is loaded
        document.addEventListener('DOMContentLoaded', function() {
            // Add search functionality
            addSearchCapability();
            
            // Add collapsible sections
            addCollapsibleSections();
            
            // Add table sorting
            addTableSorting();
            
            // Add print functionality
            addPrintButton();
            
            // Add scroll-to-top button
            addScrollToTop();
        });

        function addSearchCapability() {
            // Create search input
            const searchHTML = `
                <div id="search-container" style="padding: 20px; background: #f8f9fa; border-bottom: 1px solid #e1e5e9;">
                    <input type="text" id="search-input" placeholder="Search reports..." 
                           style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-size: 16px;">
                </div>
            `;
            
            const header = document.querySelector('.report-header');
            header.insertAdjacentHTML('afterend', searchHTML);
            
            // Add search functionality
            const searchInput = document.getElementById('search-input');
            searchInput.addEventListener('input', function() {
                const searchTerm = this.value.toLowerCase();
                const posts = document.querySelectorAll('.post-analysis');
                
                posts.forEach(post => {
                    const text = post.textContent.toLowerCase();
                    if (text.includes(searchTerm) || searchTerm === '') {
                        post.style.display = 'block';
                    } else {
                        post.style.display = 'none';
                    }
                });
            });
        }

        function addCollapsibleSections() {
            // Make analysis content sections collapsible
            const sections = document.querySelectorAll('.analysis-content section');
            
            sections.forEach(section => {
                const header = section.querySelector('h4');
                if (header) {
                    header.style.cursor = 'pointer';
                    header.innerHTML += ' <span style="float: right; font-size: 0.8em; color: #666;">▼</span>';
                    
                    header.addEventListener('click', function() {
                        const content = Array.from(section.children).slice(1);
                        const arrow = header.querySelector('span');
                        
                        content.forEach(element => {
                            if (element.style.display === 'none') {
                                element.style.display = 'block';
                                arrow.textContent = '▼';
                            } else {
                                element.style.display = 'none';
                                arrow.textContent = '▶';
                            }
                        });
                    });
                }
            });
        }

        function addTableSorting() {
            // Add sorting to table headers
            const tables = document.querySelectorAll('table');
            
            tables.forEach(table => {
                const headers = table.querySelectorAll('th');
                headers.forEach((header, index) => {
                    header.style.cursor = 'pointer';
                    header.innerHTML += ' <span style="font-size: 0.8em; opacity: 0.7;">⇅</span>';
                    
                    header.addEventListener('click', function() {
                        sortTable(table, index);
                    });
                });
            });
        }

        function sortTable(table, columnIndex) {
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            
            rows.sort((a, b) => {
                const aText = a.cells[columnIndex].textContent.trim();
                const bText = b.cells[columnIndex].textContent.trim();
                return aText.localeCompare(bText);
            });
            
            rows.forEach(row => tbody.appendChild(row));
        }

        function addPrintButton() {
            // Add print button to header
            const printButton = `
                <button onclick="window.print()" 
                        style="position: fixed; top: 20px; right: 20px; z-index: 1000; 
                               padding: 10px 20px; background: #0078d4; color: white; 
                               border: none; border-radius: 5px; cursor: pointer; 
                               box-shadow: 0 2px 5px rgba(0,0,0,0.2);">
                    📄 Print Report
                </button>
            `;
            document.body.insertAdjacentHTML('beforeend', printButton);
        }

        function addScrollToTop() {
            // Add scroll to top button
            const scrollButton = `
                <button id="scroll-top" onclick="scrollToTop()" 
                        style="position: fixed; bottom: 20px; right: 20px; z-index: 1000; 
                               padding: 15px; background: #0078d4; color: white; 
                               border: none; border-radius: 50%; cursor: pointer; 
                               box-shadow: 0 2px 5px rgba(0,0,0,0.2); display: none;">
                    ↑
                </button>
            `;
            document.body.insertAdjacentHTML('beforeend', scrollButton);
            
            // Show/hide scroll button based on scroll position
            window.addEventListener('scroll', function() {
                const scrollButton = document.getElementById('scroll-top');
                if (window.pageYOffset > 300) {
                    scrollButton.style.display = 'block';
                } else {
                    scrollButton.style.display = 'none';
                }
            });
        }

        function scrollToTop() {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }

        // Add keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            // Ctrl/Cmd + F for search
            if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
                e.preventDefault();
                const searchInput = document.getElementById('search-input');
                if (searchInput) {
                    searchInput.focus();
                    searchInput.select();
                }
            }
            
            // Ctrl/Cmd + P for print
            if ((e.ctrlKey || e.metaKey) && e.key === 'p') {
                e.preventDefault();
                window.print();
            }
        });
    """

def sanitize_html_content(content):
    """
    Sanitize HTML content to prevent XSS and ensure safety
    
    Args:
        content (str): Raw HTML content
        
    Returns:
        str: Sanitized HTML content
    """
    if not content:
        return ""
    
    import html
    import re
    
    # Basic HTML escaping for any user-generated content
    # Since our content comes from AI, we need to be careful
    
    # Escape any potential script tags
    content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.IGNORECASE | re.DOTALL)
    
    # Remove any javascript: URLs
    content = re.sub(r'javascript:', '', content, flags=re.IGNORECASE)
    
    # Remove any on* event handlers
    content = re.sub(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', '', content, flags=re.IGNORECASE)
    
    # Escape any potentially dangerous characters in text content
    # but preserve our generated HTML structure
    
    return content

def validate_html_structure(html_content):
    """
    Validate HTML structure and ensure it's well-formed
    
    Args:
        html_content (str): HTML content to validate
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not html_content:
        return False, "Empty HTML content"
    
    try:
        from bs4 import BeautifulSoup
        
        # Parse with BeautifulSoup to check for well-formed HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Check for required elements
        required_elements = ['html', 'head', 'body', 'title']
        for element in required_elements:
            if not soup.find(element):
                return False, f"Missing required element: {element}"
        
        # Check for basic structure
        # Note: Enhanced reports use different structure with Tailwind CSS
        if soup.find('div', class_='container') or soup.find('div', class_='max-w-7xl'):
            # Valid structure found
            pass
        else:
            return False, "Missing main container element"
        
        # Check for CSS (either inline styles or Tailwind CDN)
        has_css = (soup.find('style') or 
                  soup.find('script', src=lambda x: x and 'tailwindcss' in x))
        if not has_css:
            return False, "Missing CSS styling"
        
        # Check for JavaScript functionality
        has_js = (soup.find('script', string=lambda x: x and ('showTab' in x or 'function' in x)) or
                 soup.find('script') and len(soup.find_all('script')) > 1)
        if not has_js:
            return False, "Missing JavaScript functionality"
        
        return True, "HTML structure is valid"
        
    except Exception as e:
        return False, f"HTML parsing error: {str(e)}"

def validate_report_data(processed_posts):
    """
    Validate that report data is complete and properly structured
    
    Args:
        processed_posts (list): List of processed post data
        
    Returns:
        tuple: (is_valid, warnings)
    """
    if not processed_posts:
        return False, ["No posts provided for report generation"]
    
    warnings = []
    valid_posts = 0
    
    for i, post in enumerate(processed_posts, 1):
        # Check required fields
        required_fields = ['title', 'author', 'url', 'ai_analysis']
        for field in required_fields:
            if not post.get(field):
                warnings.append(f"Post {i}: Missing {field}")
        
        # Check structured data quality
        structured_data = post.get('structured_data')
        if structured_data:
            valid_posts += 1
            
            # Check for empty or missing key sections
            if not structured_data.get('executive_summary'):
                warnings.append(f"Post {i}: Missing executive summary")
            
            if not structured_data.get('business_impact'):
                warnings.append(f"Post {i}: Missing business impact analysis")
            
            if not structured_data.get('priority_level'):
                warnings.append(f"Post {i}: Missing priority level")
            
        else:
            warnings.append(f"Post {i}: No structured data available")
    
    # Overall validation
    if valid_posts == 0:
        return False, warnings + ["No posts have valid structured data"]
    
    if valid_posts < len(processed_posts) * 0.5:
        warnings.append(f"Only {valid_posts}/{len(processed_posts)} posts have structured data (less than 50%)")
    
    return True, warnings

def save_html_report_to_file(filename, html_content, reports_dir="reports"):
    """
    Save HTML report to file system with proper error handling
    
    Args:
        filename (str): Name of the file to save
        html_content (str): HTML content to save
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
        
        # Validate HTML before saving
        is_valid, validation_error = validate_html_structure(html_content)
        if not is_valid:
            return False, None, f"HTML validation failed: {validation_error}"
        
        # Sanitize content before saving
        sanitized_content = sanitize_html_content(html_content)
        
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
    
    # Plain text email content
    text_content = f"""🚨 CHROME ENTERPRISE INTELLIGENCE ALERT

📊 {len(analyzed_posts)} New Posts Detected | {timestamp}

EXECUTIVE SUMMARIES:
{''.join([f"• {post.get('title', 'Unknown')[:60]}...\n  → {post.get('email_summary', 'No summary available')}\n" for post in analyzed_posts])}

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
                color: white; 
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

def publish_report_and_get_url(html_file_path, report_id):
    """
    Publish HTML report and return the public URL
    
    Args:
        html_file_path (str): Path to the HTML report file
        report_id (str): Unique report identifier
        
    Returns:
        tuple: (success, report_url, error_message)
    """
    try:
        # Try to import and use GitHub Pages publisher
        from report_publisher import (
            get_github_config,
            setup_github_pages_repo,
            publish_report_to_github_pages,
            generate_report_url
        )
        
        # Get GitHub configuration
        github_config = get_github_config()
        if not github_config:
            # Fallback: return local file URL
            local_url = f"file://{os.path.abspath(html_file_path)}"
            print(f"⚠️ GitHub Pages not configured, using local URL: {local_url}")
            return True, local_url, "GitHub Pages not configured - using local file"
        
        # Set up GitHub Pages repository
        setup_success = setup_github_pages_repo(github_config)
        if not setup_success:
            local_url = f"file://{os.path.abspath(html_file_path)}"
            return False, local_url, "Failed to set up GitHub Pages repository"
        
        # Publish report
        success, report_url, error = publish_report_to_github_pages(
            html_file_path, report_id, github_config
        )
        
        if success:
            print(f"✅ Report published to GitHub Pages: {report_url}")
            return True, report_url, None
        else:
            # Fallback to local URL
            local_url = f"file://{os.path.abspath(html_file_path)}"
            print(f"⚠️ GitHub Pages publishing failed, using local URL: {local_url}")
            return False, local_url, error
        
    except ImportError:
        # report_publisher.py not available
        local_url = f"file://{os.path.abspath(html_file_path)}"
        print(f"⚠️ Report publisher not available, using local URL: {local_url}")
        return True, local_url, "Report publisher module not available"
    except Exception as e:
        error_logger.log_error(e, "publish_report_and_get_url", {"html_file_path": html_file_path, "report_id": report_id})
        print(f"⚠️ Publishing error: {e}")
        print("🔄 Using GitHub publishing fallback...")
        
        # Use GitHub publishing fallback strategy
        success, fallback_url, fallback_message = FallbackStrategies.github_publishing_fallback(html_file_path, report_id, e)
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
        'content': blog_post.get('content', 'No content available')[:4000]  # Limit content length
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

def get_default_ai_prompts():
    """
    Get a collection of predefined AI analysis prompts for different use cases
    
    Returns:
        dict: Collection of named prompts for different analysis styles
    """
    return {
        'comprehensive': """
        Analyze this Google Cloud blog post and provide a comprehensive summary for IT professionals and developers.

        Focus on:
        1. **Key Technologies & Features**: What specific Google Cloud products, features, or technologies are discussed?
        2. **Business Impact**: How does this announcement or information affect businesses using Google Cloud?
        3. **Technical Details**: Important technical specifications, capabilities, or changes mentioned
        4. **Target Audience**: Who should care about this - developers, IT admins, business leaders, etc.?
        5. **Action Items**: Any specific steps readers should take or deadlines to be aware of
        6. **Strategic Significance**: How does this fit into Google Cloud's broader strategy or market positioning?

        Keep the analysis professional, actionable, and under 400 words. Focus on practical implications rather than marketing language.
        """,
        
        'executive_summary': """
        Create an executive summary of this Google Cloud blog post for business leaders.

        Provide:
        1. **Business Value**: How does this impact our organization's technology strategy?
        2. **Competitive Advantage**: What competitive benefits or risks does this present?
        3. **Investment Implications**: Are there cost considerations or ROI opportunities?
        4. **Timeline**: Any important dates, deadlines, or availability information
        5. **Recommendation**: Should we take action, investigate further, or monitor?

        Keep it concise (under 200 words) and focus on strategic business implications.
        """,
        
        'technical_deep_dive': """
        Provide a technical analysis of this Google Cloud blog post for engineers and architects.

        Cover:
        1. **Technical Architecture**: How do the discussed technologies work?
        2. **Integration Points**: How does this integrate with existing Google Cloud services?
        3. **Implementation Considerations**: What should teams consider when adopting this?
        4. **Performance & Scale**: Any performance, scalability, or reliability implications?
        5. **Migration Path**: How might existing users migrate to or adopt this technology?
        6. **Best Practices**: Any recommended approaches or patterns mentioned?

        Include technical details but keep under 500 words. Focus on actionable engineering insights.
        """,
        
        'security_focus': """
        Analyze this Google Cloud blog post from a cybersecurity and compliance perspective.

        Examine:
        1. **Security Features**: What security capabilities or improvements are discussed?
        2. **Compliance Impact**: How does this affect regulatory compliance (GDPR, HIPAA, SOC, etc.)?
        3. **Risk Assessment**: Does this introduce new risks or mitigate existing ones?
        4. **Access Controls**: Any changes to authentication, authorization, or access management?
        5. **Data Protection**: How does this impact data privacy, encryption, or data residency?
        6. **Security Operations**: Impact on monitoring, incident response, or security tooling?

        Keep the analysis focused on security implications under 300 words.
        """,
        
        'brief_digest': """
        Create a brief digest of this Google Cloud blog post for busy professionals.

        Summarize in bullet points:
        • **What's New**: Main announcement or update in one sentence
        • **Who It Affects**: Target audience and use cases
        • **Key Benefit**: Primary value proposition
        • **Next Steps**: What readers should do (if anything)
        • **Learn More**: Where to find additional information

        Keep it under 100 words and make it scannable for quick consumption.
        """
    }

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

def send_blog_notification(analyzed_posts, notification_type="new_posts"):
    """
    Send email notification with blog analysis results
    
    Args:
        analyzed_posts (list[dict]): List of analyzed blog posts with AI analysis
        notification_type (str): Type of notification ('new_posts', 'test', 'digest')
        
    Returns:
        dict: Email sending result with status and details
            - success (bool): Whether email was sent successfully
            - message (str): Status message
            - email_sent_at (str): Timestamp of email sending
            - posts_count (int): Number of posts included
            - email_preview (str): Preview of email content
            
    Notes:
        - Uses environment variables for email configuration
        - Supports both HTML and plain text email formats
        - Includes comprehensive error handling
        - Creates professional competitive intelligence reports
    """
    if not analyzed_posts:
        return {
            'success': False,
            'message': 'No analyzed posts provided for email notification',
            'email_sent_at': datetime.now().isoformat(),
            'posts_count': 0,
            'email_preview': None
        }
    
    try:
        # Get email configuration from environment variables
        smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        sender_email = os.getenv('EMAIL_USERNAME')
        sender_password = os.getenv('EMAIL_PASSWORD')
        recipient_email = os.getenv('EMAIL_TO')
        
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
                'email_preview': None
            }
        
        print(f"📧 Preparing email notification for {len(analyzed_posts)} analyzed posts...")
        
        # Create email subject based on notification type
        if notification_type == "test":
            subject = "🧪 Test: Microsoft Edge Competitive Intelligence Report"
        elif notification_type == "digest":
            subject = f"📊 Weekly Chrome Enterprise Digest - {len(analyzed_posts)} Posts"
        else:
            subject = f"🚨 New Chrome Enterprise Updates - {len(analyzed_posts)} Posts Detected"
        
        # Generate email content
        email_body_html, email_body_text = create_email_content(analyzed_posts, notification_type)
        
        # Send email using enhanced function
        success = send_enhanced_email(
            subject=subject,
            html_body=email_body_html,
            text_body=email_body_text,
            recipient_email=recipient_email,
            sender_email=sender_email,
            sender_password=sender_password,
            smtp_server=smtp_server,
            smtp_port=smtp_port
        )
        
        if success:
            print(f"✅ Email notification sent successfully to {recipient_email}")
            return {
                'success': True,
                'message': f'Email sent successfully to {recipient_email}',
                'email_sent_at': datetime.now().isoformat(),
                'posts_count': len(analyzed_posts),
                'email_preview': email_body_text[:300] + '...' if len(email_body_text) > 300 else email_body_text
            }
        else:
            return {
                'success': False,
                'message': 'Failed to send email - check SMTP configuration and credentials',
                'email_sent_at': datetime.now().isoformat(),
                'posts_count': len(analyzed_posts),
                'email_preview': email_body_text[:300] + '...' if len(email_body_text) > 300 else email_body_text
            }
            
    except Exception as e:
        error_msg = f"Email notification failed: {str(e)}"
        print(f"✗ {error_msg}")
        return {
            'success': False,
            'message': error_msg,
            'email_sent_at': datetime.now().isoformat(),
            'posts_count': len(analyzed_posts),
            'email_preview': None
        }

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
    Convert AI analysis text with markdown-style formatting to proper HTML
    
    Args:
        analysis_text (str): Analysis text with markdown tables and formatting
        
    Returns:
        str: HTML formatted analysis with proper tables and styling
    """
    if not analysis_text:
        return ""
    
    import re
    
    lines = analysis_text.split('\n')
    html_parts = []
    i = 0
    max_iterations = len(lines) * 2  # Safety mechanism to prevent infinite loops
    iteration_count = 0
    
    while i < len(lines) and iteration_count < max_iterations:
        iteration_count += 1
        line = lines[i].strip()
        
        if not line:
            html_parts.append('<br>')
            i += 1
            continue
        
        # Handle markdown-style headers (# ## ### etc.)
        if line.startswith('#'):
            # Count the number of # symbols to determine header level
            hash_count = 0
            for char in line:
                if char == '#':
                    hash_count += 1
                else:
                    break
            
            # Extract header text (remove # symbols and strip whitespace)
            header_text = line[hash_count:].strip()
            
            # Convert to appropriate HTML header (limit to h1-h6)
            header_level = min(hash_count, 6)
            html_parts.append(f'<h{header_level}>{header_text}</h{header_level}>')
            i += 1
            continue
        
        # Handle numbered lists first (consecutive numbered items)
        if re.match(r'^\d+\.\s+', line):
            # Check if this is part of a numbered list (look ahead)
            is_numbered_list = False
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if re.match(r'^\d+\.\s+', next_line) or not next_line:
                    is_numbered_list = True
            
            if is_numbered_list:
                numbered_lines = []
                
                # Collect consecutive numbered items
                while i < len(lines):
                    current_line = lines[i].strip()
                    if re.match(r'^\d+\.\s+', current_line):
                        # Clean up numbered item
                        clean_line = re.sub(r'^\d+\.\s+', '', current_line)
                        numbered_lines.append(clean_line)
                        i += 1
                    elif not current_line:  # Empty line continues the list
                        i += 1
                    else:
                        break
                
                if numbered_lines:
                    html_parts.append('<ol>')
                    for item in numbered_lines:
                        html_parts.append(f'<li>{item}</li>')
                    html_parts.append('</ol>')
                continue
            else:
                # Single numbered item - treat as header
                header_text = re.sub(r'^\d+\.\s+', '', line)
                html_parts.append(f'<h3>{header_text}</h3>')
                i += 1
                continue
            
        # Handle **Header** style headers
        if line.startswith('**') and line.endswith('**'):
            header_text = line.strip('*').strip()
            html_parts.append(f'<h3>{header_text}</h3>')
            i += 1
            continue
        
        # Handle table detection (lines with | separators)
        if '|' in line or '│' in line:
            # Start of a table
            table_lines = []
            
            # Collect all table lines
            while i < len(lines):
                current_line = lines[i].strip()
                if '|' in current_line or '│' in current_line:
                    # Convert | to │ for consistency
                    current_line = current_line.replace('|', '│')
                    table_lines.append(current_line)
                    i += 1
                else:
                    break
            
            # Convert table to HTML
            if table_lines:
                html_table = convert_table_to_html(table_lines)
                html_parts.append(html_table)
            continue
        
        # Handle bullet points
        if line.startswith('•') or line.startswith('-') or line.startswith('*'):
            bullet_lines = []
            
            # Collect consecutive bullet points
            while i < len(lines):
                current_line = lines[i].strip()
                if current_line.startswith('•') or current_line.startswith('-') or current_line.startswith('*'):
                    # Clean up bullet point
                    clean_line = re.sub(r'^[•\-\*]\s*', '', current_line)
                    bullet_lines.append(clean_line)
                    i += 1
                elif not current_line:  # Empty line continues the list
                    i += 1
                else:
                    break
            
            if bullet_lines:
                html_parts.append('<ul>')
                for bullet in bullet_lines:
                    html_parts.append(f'<li>{bullet}</li>')
                html_parts.append('</ul>')
            continue
        
        # Regular paragraph
        if line:
            # Handle bold text **text**
            line = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line)
            # Handle links [text](url) - basic implementation
            line = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank">\1</a>', line)
            html_parts.append(f'<p>{line}</p>')
        
        i += 1
    
    # Safety check for infinite loops
    if iteration_count >= max_iterations:
        print(f"⚠️ Warning: HTML conversion reached iteration limit ({max_iterations}), may have truncated content")
        html_parts.append('<p><em>[Content may be truncated due to processing limits]</em></p>')
    
    return '\n'.join(html_parts)

def convert_table_to_html(table_lines):
    """
    Convert markdown-style table lines to HTML table
    
    Args:
        table_lines (list): List of table row strings with │ separators
        
    Returns:
        str: HTML table
    """
    if not table_lines:
        return ""
    
    html_parts = ['<table>']
    
    for i, line in enumerate(table_lines):
        if not line.strip():
            continue
            
        # Split by │ and clean up cells
        cells = [cell.strip() for cell in line.split('│') if cell.strip()]
        
        if not cells:
            continue
        
        # Skip separator lines (lines with mostly dashes)
        if all(cell.replace('-', '').replace(':', '').strip() == '' for cell in cells):
            continue
        
        # First non-separator line is header
        if i == 0 or (i == 1 and all(cell.replace('-', '').replace(':', '').strip() == '' for cell in table_lines[0].split('│'))):
            html_parts.append('<thead><tr>')
            for cell in cells:
                # Handle bold text in headers
                cell = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', cell)
                html_parts.append(f'<th>{cell}</th>')
            html_parts.append('</tr></thead><tbody>')
        else:
            html_parts.append('<tr>')
            for j, cell in enumerate(cells):
                # Handle bold text and links in cells
                cell = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', cell)
                cell = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank">\1</a>', cell)
                
                html_parts.append(f'<td>{cell}</td>')
            html_parts.append('</tr>')
    
    html_parts.append('</tbody></table>')
    
    return '\n'.join(html_parts)

def create_email_content(analyzed_posts, notification_type="new_posts"):
    """
    Create both HTML and plain text email content for competitive intelligence reports
    with proper table and markdown formatting
    
    Args:
        analyzed_posts (list[dict]): List of analyzed blog posts
        notification_type (str): Type of notification for content customization
        
    Returns:
        tuple: (html_content, text_content)
            - html_content (str): Professional HTML email content with proper tables
            - text_content (str): Plain text email content
    """
    # Generate timestamp
    timestamp = datetime.now().strftime('%B %d, %Y at %I:%M %p')
    
    # Count successful analyses
    successful_analyses = [post for post in analyzed_posts if post.get('analysis_success', False)]
    failed_analyses = [post for post in analyzed_posts if not post.get('analysis_success', False)]
    
    # Create email introduction based on notification type
    if notification_type == "test":
        intro_text = "This is a test email from your Microsoft Edge Competitive Intelligence system."
        intro_html = "<p><strong>This is a test email from your Microsoft Edge Competitive Intelligence system.</strong></p>"
    else:
        intro_text = f"New Chrome Enterprise blog posts have been detected and analyzed for competitive intelligence."
        intro_html = f"<p>New Chrome Enterprise blog posts have been detected and analyzed for competitive intelligence.</p>"
    
    # Start building content
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 1200px; margin: 0 auto; }}
            .header {{ background: linear-gradient(135deg, #0078d4, #106ebe); color: white; padding: 20px; text-align: center; }}
            .summary {{ background: #f8f9fa; padding: 15px; margin: 20px 0; border-left: 4px solid #0078d4; }}
            .post {{ background: white; margin: 20px 0; padding: 20px; border: 1px solid #e1e5e9; border-radius: 8px; }}
            .post-title {{ color: #0078d4; font-size: 1.2em; font-weight: bold; margin-bottom: 10px; }}
            .post-meta {{ color: #666; font-size: 0.9em; margin-bottom: 15px; }}
            .analysis {{ font-size: 0.95em; line-height: 1.5; }}
            .footer {{ background: #f8f9fa; padding: 15px; text-align: center; font-size: 0.8em; color: #666; }}
            
            /* Table Styling */
            table {{ 
                border-collapse: collapse; 
                width: 100%; 
                margin: 15px 0; 
                font-size: 0.9em;
                background: white;
            }}
            th, td {{ 
                border: 1px solid #ddd; 
                padding: 12px 8px; 
                text-align: left; 
                vertical-align: top;
                word-wrap: break-word;
            }}
            th {{ 
                background-color: #0078d4; 
                color: white; 
                font-weight: bold;
                text-align: center;
            }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
            tr:hover {{ background-color: #f5f5f5; }}
            
            /* Section Headers */
            h1, h2, h3, h4 {{ color: #0078d4; margin-top: 20px; margin-bottom: 10px; }}
            h3 {{ border-bottom: 2px solid #0078d4; padding-bottom: 5px; }}
            
            /* Bullet points */
            ul {{ margin: 10px 0; padding-left: 20px; }}
            li {{ margin: 5px 0; }}
            
            /* Code and links */
            code {{ background: #f1f1f1; padding: 2px 4px; border-radius: 3px; }}
            a {{ color: #0078d4; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🔍 Microsoft Edge Competitive Intelligence</h1>
            <p>Chrome Enterprise Blog Monitoring Report</p>
        </div>
        
        <div class="summary">
            <h2>📊 Report Summary</h2>
            {intro_html}
            <ul>
                <li><strong>Posts Analyzed:</strong> {len(successful_analyses)}</li>
                <li><strong>Analysis Failures:</strong> {len(failed_analyses)}</li>
                <li><strong>Generated:</strong> {timestamp}</li>
                <li><strong>Source:</strong> Google Cloud Chrome Enterprise Blog</li>
            </ul>
        </div>
    """
    
    text_content = f"""
MICROSOFT EDGE COMPETITIVE INTELLIGENCE REPORT
==============================================

{intro_text}

REPORT SUMMARY:
- Posts Analyzed: {len(successful_analyses)}
- Analysis Failures: {len(failed_analyses)}
- Generated: {timestamp}
- Source: Google Cloud Chrome Enterprise Blog

"""
    
    # Include all successful analyses
    posts_to_include = successful_analyses
    
    for i, post in enumerate(posts_to_include, 1):
        title = post.get('title', 'Unknown Title')
        author = post.get('author', 'Unknown Author')
        url = post.get('url', '')
        analysis = post.get('ai_analysis', 'No analysis available')
        
        # Convert analysis to HTML with proper table and formatting
        analysis_html = convert_analysis_to_html(analysis)
        
        # HTML version
        html_content += f"""
        <div class="post">
            <div class="post-title">📰 Analysis #{i}: {title}</div>
            <div class="post-meta">
                <strong>Author:</strong> {author} |
                <strong>URL:</strong> <a href="{url}" target="_blank">View Original Post</a>
            </div>
            <div class="analysis">{analysis_html}</div>
        </div>
        """
        
        # Text version
        text_content += f"""
ANALYSIS #{i}: {title}
{'=' * (len(title) + 15)}

Author: {author}
URL: {url}

{analysis}

"""
    
    # Add failed analyses if any
    if failed_analyses:
        html_content += """
        <div class="summary">
            <h2>⚠️ Analysis Failures</h2>
            <p>The following posts could not be analyzed:</p>
            <ul>
        """
        
        text_content += "\nANALYSIS FAILURES:\n" + "=" * 20 + "\n"
        
        for post in failed_analyses:
            title = post.get('title', 'Unknown Title')
            error = post.get('analysis_error', 'Unknown error')
            
            html_content += f"<li><strong>{title}</strong> - {error}</li>"
            text_content += f"- {title}: {error}\n"
        
        html_content += "</ul></div>"
    
    # Close HTML
    html_content += f"""
        <div class="footer">
            <p>Generated by Microsoft Edge Competitive Intelligence System</p>
            <p>Automated Chrome Enterprise Blog Monitoring | {timestamp}</p>
        </div>
    </body>
    </html>
    """
    
    text_content += f"""
---
Generated by Microsoft Edge Competitive Intelligence System
Automated Chrome Enterprise Blog Monitoring | {timestamp}
"""
    
    return html_content, text_content

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
