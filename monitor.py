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
            raise ValueError(f"Failed to fetch Chrome Enterprise blog page: {e}")
    
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
        print(f"Error extracting blog posts: {e}")
        import traceback
        traceback.print_exc()
        return []
        
        print(f"Successfully extracted {len(unique_posts)} unique blog posts")
        return unique_posts
        
    except Exception as e:
        print(f"Error in extract_blog_posts: {e}")
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
        model = genai.GenerativeModel('gemini-2.5-flash')
        
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
        
        response = model.generate_content(prompt)
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
        model = genai.GenerativeModel('gemini-2.5-flash')
        
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
        response = model.generate_content(formatted_prompt)
        
        if not response or not response.text:
            error_msg = "Gemini API returned empty response"
            print(f"✗ {error_msg}")
            return create_failed_analysis_result(blog_post, error_msg)
        
        # Create enhanced blog post with AI analysis
        analyzed_post = blog_post.copy()
        analyzed_post.update({
            'ai_analysis': response.text.strip(),
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
        error_msg = f"AI analysis failed: {str(e)}"
        print(f"✗ {error_msg}")
        return create_failed_analysis_result(blog_post, error_msg)

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
    
    if len(prompt) > 5000:
        return False, "Prompt must be less than 5000 characters (too long may exceed API limits)"
    
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
        # Format the template with blog data
        formatted_prompt = f"""
        {prompt_template}

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
