#!/usr/bin/env python3
"""
Report Publisher - GitHub Pages Integration
Handles publishing Markdown reports to GitHub Pages for web access
"""

import os
import subprocess
import json
from datetime import datetime, timedelta
from typing import Optional, Tuple, List
import tempfile
import shutil

def get_github_config():
    """
    Get GitHub configuration from environment variables
    
    Returns:
        dict: GitHub configuration or None if incomplete
    """
    github_token = os.getenv('GITHUB_TOKEN')
    github_repo = os.getenv('GITHUB_REPO')  # Format: username/repo-name
    reports_base_url = os.getenv('REPORTS_BASE_URL')  # Base URL for hosted reports
    
    if not github_token:
        print("⚠️ GITHUB_TOKEN environment variable not set")
        return None
    
    if not github_repo:
        print("⚠️ GITHUB_REPO environment variable not set (format: username/repo-name)")
        return None
    
    # Generate base URL if not provided
    if not reports_base_url:
        username, repo_name = github_repo.split('/')
        reports_base_url = f"https://{username.lower()}.github.io/{repo_name}"
    
    return {
        'token': github_token,
        'repo': github_repo,
        'base_url': reports_base_url,
        'username': github_repo.split('/')[0],
        'repo_name': github_repo.split('/')[1]
    }

def setup_github_pages_repo(github_config):
    """
    Set up GitHub Pages repository for report hosting
    
    Args:
        github_config (dict): GitHub configuration
        
    Returns:
        bool: True if setup successful, False otherwise
    """
    try:
        repo_url = f"https://{github_config['token']}@github.com/{github_config['repo']}.git"
        
        # Check if repo exists locally
        if os.path.exists('.git'):
            print("✅ Git repository already exists")
            return True
        
        # Clone or initialize repository
        try:
            print(f"📥 Cloning repository {github_config['repo']}...")
            subprocess.run(['git', 'clone', repo_url, '.'], check=True, capture_output=True)
            print("✅ Repository cloned successfully")
        except subprocess.CalledProcessError:
            print("📝 Initializing new git repository...")
            subprocess.run(['git', 'init'], check=True)
            subprocess.run(['git', 'remote', 'add', 'origin', repo_url], check=True)
            print("✅ Git repository initialized")
        
        # Configure git user (use GitHub token user)
        subprocess.run(['git', 'config', 'user.name', 'Competitive Intelligence Bot'], check=True)
        subprocess.run(['git', 'config', 'user.email', 'ci-bot@microsoft.com'], check=True)
        
        # Check if gh-pages branch exists
        try:
            subprocess.run(['git', 'checkout', 'gh-pages'], check=True, capture_output=True)
            print("✅ Switched to gh-pages branch")
        except subprocess.CalledProcessError:
            print("📝 Creating gh-pages branch...")
            subprocess.run(['git', 'checkout', '--orphan', 'gh-pages'], check=True)
            subprocess.run(['git', 'rm', '-rf', '.'], check=True, capture_output=True)
            
            # Create initial index.html
            create_initial_index_page(github_config)
            
            subprocess.run(['git', 'add', '.'], check=True)
            subprocess.run(['git', 'commit', '-m', 'Initial gh-pages setup'], check=True)
            subprocess.run(['git', 'push', '-u', 'origin', 'gh-pages'], check=True)
            print("✅ gh-pages branch created and pushed")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Git operation failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Repository setup failed: {e}")
        return False

def create_initial_index_page(github_config):
    """
    Create initial index page for GitHub Pages
    
    Args:
        github_config (dict): GitHub configuration
    """
    index_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Microsoft Edge Competitive Intelligence Reports</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f8f9fa;
        }}
        .header {{
            background: linear-gradient(135deg, #0078d4, #106ebe);
            color: white;
            padding: 40px 20px;
            text-align: center;
            border-radius: 8px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }}
        .subtitle {{
            opacity: 0.9;
            margin: 10px 0 0 0;
        }}
        .content {{
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .reports-list {{
            margin-top: 30px;
        }}
        .no-reports {{
            text-align: center;
            color: #666;
            font-style: italic;
            padding: 40px;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            color: #666;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 Microsoft Edge Competitive Intelligence</h1>
        <p class="subtitle">Chrome Enterprise Blog Monitoring Reports</p>
    </div>
    
    <div class="content">
        <h2>📊 Intelligence Reports</h2>
        <p>This site hosts competitive intelligence reports generated by the Microsoft Edge team's automated Chrome Enterprise blog monitoring system.</p>
        
        <div class="reports-list">
            <div class="no-reports">
                📄 No reports published yet.<br>
                Reports will appear here automatically when new Chrome Enterprise posts are detected and analyzed.
            </div>
        </div>
    </div>
    
    <div class="footer">
        <p>Generated by Microsoft Edge Competitive Intelligence System</p>
        <p>Last updated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
    </div>
    
    <script>
        // Auto-refresh every 5 minutes
        setTimeout(() => {{
            window.location.reload();
        }}, 300000);
    </script>
</body>
</html>"""
    
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(index_content)

def publish_report_to_github_pages(markdown_file_path, report_id, github_config):
    """
    Publish Markdown report to GitHub Pages
    
    Args:
        markdown_file_path (str): Path to the Markdown report file
        report_id (str): Unique report identifier
        github_config (dict): GitHub configuration
        
    Returns:
        tuple: (success, report_url, error_message)
    """
    try:
        if not os.path.exists(markdown_file_path):
            return False, None, f"Report file not found: {markdown_file_path}"
        
        # Ensure we're on gh-pages branch
        try:
            subprocess.run(['git', 'checkout', 'gh-pages'], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            return False, None, "Failed to checkout gh-pages branch"
        
        # Create reports directory if it doesn't exist
        reports_dir = 'reports'
        os.makedirs(reports_dir, exist_ok=True)
        
        # Copy report file to GitHub Pages directory
        report_filename = f"chrome_enterprise_report_{report_id}.md"
        github_report_path = os.path.join(reports_dir, report_filename)
        
        shutil.copy2(markdown_file_path, github_report_path)
        print(f"📄 Copied report to {github_report_path}")
        
        # Update index page with new report
        update_index_page_with_report(report_id, github_config)
        
        # Add and commit changes
        subprocess.run(['git', 'add', '.'], check=True)
        commit_message = f"Add intelligence report {report_id}\n\n🤖 Generated with Claude Code\n\nCo-Authored-By: Claude <noreply@anthropic.com>"
        subprocess.run(['git', 'commit', '-m', commit_message], check=True)
        
        # Push to GitHub
        subprocess.run(['git', 'push', 'origin', 'gh-pages'], check=True)
        
        # Generate report URL
        report_url = f"{github_config['base_url']}/reports/{report_filename}"
        
        print(f"✅ Report published successfully!")
        print(f"📄 Report URL: {report_url}")
        
        return True, report_url, None
        
    except subprocess.CalledProcessError as e:
        return False, None, f"Git operation failed: {e}"
    except Exception as e:
        return False, None, f"Publishing failed: {str(e)}"

def update_index_page_with_report(report_id, github_config):
    """
    Update the index page to include the new report
    
    Args:
        report_id (str): Report identifier
        github_config (dict): GitHub configuration
    """
    try:
        # Load existing reports list
        reports_file = 'reports.json'
        if os.path.exists(reports_file):
            with open(reports_file, 'r') as f:
                reports = json.load(f)
        else:
            reports = []
        
        # Add new report
        new_report = {
            'id': report_id,
            'filename': f"chrome_enterprise_report_{report_id}.md",
            'url': f"{github_config['base_url']}/reports/chrome_enterprise_report_{report_id}.md",
            'published_at': datetime.now().isoformat(),
            'title': f"Intelligence Report {report_id}"
        }
        
        reports.insert(0, new_report)  # Add to beginning
        
        # Keep only last 30 reports
        reports = reports[:30]
        
        # Save updated reports list
        with open(reports_file, 'w') as f:
            json.dump(reports, f, indent=2)
        
        # Generate updated index page
        generate_updated_index_page(reports, github_config)
        
    except Exception as e:
        print(f"⚠️ Failed to update index page: {e}")

def generate_updated_index_page(reports, github_config):
    """
    Generate updated index page with reports list
    
    Args:
        reports (list): List of report metadata
        github_config (dict): GitHub configuration
    """
    if not reports:
        reports_html = '<div class="no-reports">📄 No reports published yet.</div>'
    else:
        reports_html = '<div class="reports-grid">'
        for report in reports:
            published_date = datetime.fromisoformat(report['published_at']).strftime('%B %d, %Y at %I:%M %p')
            reports_html += f'''
            <div class="report-card">
                <h3><a href="{report['url']}" target="_blank">{report['title']}</a></h3>
                <p class="report-date">📅 {published_date}</p>
                <p class="report-actions">
                    <a href="{report['url']}" target="_blank" class="view-button">View Report</a>
                </p>
            </div>
            '''
        reports_html += '</div>'
    
    index_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Microsoft Edge Competitive Intelligence Reports</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f8f9fa;
        }}
        .header {{
            background: linear-gradient(135deg, #0078d4, #106ebe);
            color: white;
            padding: 40px 20px;
            text-align: center;
            border-radius: 8px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }}
        .subtitle {{
            opacity: 0.9;
            margin: 10px 0 0 0;
        }}
        .content {{
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .reports-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }}
        .report-card {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #0078d4;
        }}
        .report-card h3 {{
            margin: 0 0 10px 0;
            color: #0078d4;
        }}
        .report-card a {{
            color: #0078d4;
            text-decoration: none;
        }}
        .report-card a:hover {{
            text-decoration: underline;
        }}
        .report-date {{
            color: #666;
            font-size: 0.9em;
            margin: 5px 0;
        }}
        .view-button {{
            background: #0078d4;
            color: white;
            padding: 8px 16px;
            border-radius: 4px;
            text-decoration: none;
            font-size: 0.9em;
        }}
        .view-button:hover {{
            background: #106ebe;
            text-decoration: none;
        }}
        .no-reports {{
            text-align: center;
            color: #666;
            font-style: italic;
            padding: 40px;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            color: #666;
            font-size: 0.9em;
        }}
        .stats {{
            display: flex;
            justify-content: center;
            gap: 30px;
            margin: 20px 0;
        }}
        .stat {{
            text-align: center;
        }}
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            color: #0078d4;
        }}
        .stat-label {{
            font-size: 0.8em;
            color: #666;
            text-transform: uppercase;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 Microsoft Edge Competitive Intelligence</h1>
        <p class="subtitle">Chrome Enterprise Blog Monitoring Reports</p>
    </div>
    
    <div class="content">
        <h2>📊 Intelligence Reports</h2>
        <p>Automated competitive intelligence reports analyzing Chrome Enterprise blog posts for strategic insights and competitive threats.</p>
        
        <div class="stats">
            <div class="stat">
                <div class="stat-number">{len(reports)}</div>
                <div class="stat-label">Total Reports</div>
            </div>
            <div class="stat">
                <div class="stat-number">{len([r for r in reports if datetime.fromisoformat(r['published_at']) > datetime.now() - timedelta(days=7)])}</div>
                <div class="stat-label">This Week</div>
            </div>
            <div class="stat">
                <div class="stat-number">{len([r for r in reports if datetime.fromisoformat(r['published_at']) > datetime.now() - timedelta(days=30)])}</div>
                <div class="stat-label">This Month</div>
            </div>
        </div>
        
        <div class="reports-list">
            {reports_html}
        </div>
    </div>
    
    <div class="footer">
        <p><strong>Microsoft Edge Competitive Intelligence System</strong></p>
        <p>Automated Chrome Enterprise Blog Monitoring</p>
        <p>Last updated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
    </div>
</body>
</html>"""
    
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(index_content)

def generate_report_url(report_id, github_config=None):
    """
    Generate URL for a published report
    
    Args:
        report_id (str): Report identifier
        github_config (dict, optional): GitHub configuration
        
    Returns:
        str: Report URL or None if config unavailable
    """
    if not github_config:
        github_config = get_github_config()
        if not github_config:
            return None
    
    return f"{github_config['base_url']}/chrome_enterprise_report_{report_id}.html"

def cleanup_old_reports(max_age_days=30):
    """
    Clean up old reports from GitHub Pages
    
    Args:
        max_age_days (int): Maximum age of reports to keep
        
    Returns:
        tuple: (success, cleanup_count, error_message)
    """
    try:
        github_config = get_github_config()
        if not github_config:
            return False, 0, "GitHub configuration not available"
        
        # Ensure we're on gh-pages branch
        subprocess.run(['git', 'checkout', 'gh-pages'], check=True, capture_output=True)
        
        reports_dir = 'reports'
        if not os.path.exists(reports_dir):
            return True, 0, None
        
        # Load reports metadata
        reports_file = 'reports.json'
        if not os.path.exists(reports_file):
            return True, 0, None
        
        with open(reports_file, 'r') as f:
            reports = json.load(f)
        
        # Find old reports
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        old_reports = [r for r in reports if datetime.fromisoformat(r['published_at']) < cutoff_date]
        
        cleanup_count = 0
        for report in old_reports:
            report_path = os.path.join(reports_dir, report['filename'])
            if os.path.exists(report_path):
                os.remove(report_path)
                cleanup_count += 1
                print(f"🗑️ Removed old report: {report['filename']}")
        
        # Update reports list
        updated_reports = [r for r in reports if datetime.fromisoformat(r['published_at']) >= cutoff_date]
        
        with open(reports_file, 'w') as f:
            json.dump(updated_reports, f, indent=2)
        
        # Update index page
        generate_updated_index_page(updated_reports, github_config)
        
        if cleanup_count > 0:
            # Commit cleanup
            subprocess.run(['git', 'add', '.'], check=True)
            subprocess.run(['git', 'commit', '-m', f'Cleanup {cleanup_count} old reports'], check=True)
            subprocess.run(['git', 'push', 'origin', 'gh-pages'], check=True)
        
        return True, cleanup_count, None
        
    except Exception as e:
        return False, 0, f"Cleanup failed: {str(e)}"

if __name__ == "__main__":
    print("🚀 Report Publisher - GitHub Pages Integration")
    print("=" * 50)
    
    # Test GitHub configuration
    config = get_github_config()
    if config:
        print(f"✅ GitHub config loaded:")
        print(f"   Repository: {config['repo']}")
        print(f"   Base URL: {config['base_url']}")
    else:
        print("❌ GitHub configuration incomplete")
        print("Required environment variables:")
        print("   GITHUB_TOKEN=<your-github-token>")
        print("   GITHUB_REPO=<username/repo-name>")
        print("   REPORTS_BASE_URL=<optional-custom-url>")