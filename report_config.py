#!/usr/bin/env python3
"""
Report Configuration and URL Management
Centralized configuration for report generation and URL management
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class ReportConfig:
    """Centralized configuration for report system"""
    
    def __init__(self):
        self.load_config()
    
    def load_config(self):
        """Load configuration from environment and config files"""
        
        # Email configuration
        self.email_config = {
            'username': os.getenv('EMAIL_USERNAME'),
            'password': os.getenv('EMAIL_PASSWORD'),
            'to': os.getenv('EMAIL_TO'),
            'smtp_server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
            'smtp_port': int(os.getenv('SMTP_PORT', '587')),
        }
        
        # GitHub configuration
        self.github_config = {
            'token': os.getenv('GITHUB_TOKEN'),
            'repo': os.getenv('GITHUB_REPO'),
            'base_url': os.getenv('REPORTS_BASE_URL'),
        }
        
        # Auto-generate GitHub Pages URL if not provided
        if self.github_config['repo'] and not self.github_config['base_url']:
            username, repo_name = self.github_config['repo'].split('/')
            self.github_config['base_url'] = f"https://{username}.github.io/{repo_name}"
        
        # AI configuration
        self.ai_config = {
            'gemini_api_key': os.getenv('GEMINI_API_KEY'),
            'custom_prompt': os.getenv('CUSTOM_AI_PROMPT'),
            'model_name': os.getenv('GEMINI_MODEL', 'gemini-2.5-flash'),
        }
        
        # Report settings
        self.report_config = {
            'max_reports_to_keep': int(os.getenv('MAX_REPORTS_TO_KEEP', '30')),
            'reports_cleanup_days': int(os.getenv('REPORTS_CLEANUP_DAYS', '30')),
            'enable_auto_cleanup': os.getenv('ENABLE_REPORT_CLEANUP', 'true').lower() == 'true',
            'notification_type': os.getenv('NOTIFICATION_TYPE', 'new_posts'),
        }
        
        # Load report template config if available
        try:
            config_file = 'reports/templates/report_config.json'
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    template_config = json.load(f)
                    self.template_config = template_config
            else:
                self.template_config = self.get_default_template_config()
        except Exception:
            self.template_config = self.get_default_template_config()
    
    def get_default_template_config(self):
        """Get default template configuration"""
        return {
            "report_settings": {
                "max_posts_per_report": 10,
                "include_failed_analyses": True,
                "interactive_features": True,
                "print_optimized": True,
                "mobile_responsive": True
            },
            "styling": {
                "primary_color": "#0078d4",
                "secondary_color": "#106ebe",
                "accent_color": "#e1e5e9",
                "font_family": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                "brand_name": "Microsoft Edge Competitive Intelligence"
            },
            "content": {
                "show_executive_summary": True,
                "show_detailed_analysis": True,
                "show_statistics": True,
                "collapsible_sections": True,
                "search_functionality": True
            },
            "export_options": {
                "include_css_inline": True,
                "include_js_inline": True,
                "self_contained": True,
                "minify_output": False
            },
            "cleanup": {
                "auto_cleanup_enabled": True,
                "retention_days": 30,
                "cleanup_schedule": "daily"
            }
        }
    
    def is_email_configured(self) -> bool:
        """Check if email is properly configured"""
        required_fields = ['username', 'password', 'to']
        return all(self.email_config.get(field) for field in required_fields)
    
    def is_github_configured(self) -> bool:
        """Check if GitHub Pages is properly configured"""
        required_fields = ['token', 'repo']
        return all(self.github_config.get(field) for field in required_fields)
    
    def is_ai_configured(self) -> bool:
        """Check if AI is properly configured"""
        return bool(self.ai_config.get('gemini_api_key'))
    
    def get_missing_config(self) -> List[str]:
        """Get list of missing configuration items"""
        missing = []
        
        if not self.is_ai_configured():
            missing.append("GEMINI_API_KEY")
        
        if not self.is_email_configured():
            email_missing = [f"EMAIL_{field.upper()}" for field in ['username', 'password', 'to'] 
                           if not self.email_config.get(field)]
            missing.extend(email_missing)
        
        if not self.is_github_configured():
            github_missing = [f"GITHUB_{field.upper()}" for field in ['token', 'repo'] 
                            if not self.github_config.get(field)]
            missing.extend(github_missing)
        
        return missing
    
    def get_config_status(self) -> Dict[str, Any]:
        """Get comprehensive configuration status"""
        return {
            'email_configured': self.is_email_configured(),
            'github_configured': self.is_github_configured(),
            'ai_configured': self.is_ai_configured(),
            'missing_config': self.get_missing_config(),
            'github_pages_url': self.github_config.get('base_url'),
            'reports_cleanup_enabled': self.report_config['enable_auto_cleanup'],
        }

class URLManager:
    """Manage report URLs and access patterns"""
    
    def __init__(self, config: ReportConfig):
        self.config = config
    
    def generate_report_url(self, report_id: str) -> str:
        """Generate URL for a specific report"""
        base_url = self.config.github_config.get('base_url')
        if not base_url:
            return f"file://./reports/generated/chrome_enterprise_report_{report_id}.html"
        
        return f"{base_url}/reports/chrome_enterprise_report_{report_id}.html"
    
    def generate_index_url(self) -> str:
        """Generate URL for the reports index page"""
        base_url = self.config.github_config.get('base_url')
        if not base_url:
            return "file://./reports/index.html"
        
        return base_url
    
    def get_local_report_path(self, report_id: str) -> str:
        """Get local file path for a report"""
        return f"reports/generated/chrome_enterprise_report_{report_id}.html"
    
    def get_shareable_urls(self, report_id: str) -> Dict[str, str]:
        """Get all shareable URLs for a report"""
        return {
            'web_url': self.generate_report_url(report_id),
            'index_url': self.generate_index_url(),
            'local_path': self.get_local_report_path(report_id),
            'raw_github_url': self.generate_raw_github_url(report_id) if self.config.is_github_configured() else None
        }
    
    def generate_raw_github_url(self, report_id: str) -> Optional[str]:
        """Generate raw GitHub URL for direct file access"""
        if not self.config.github_config.get('repo'):
            return None
        
        repo = self.config.github_config['repo']
        return f"https://raw.githubusercontent.com/{repo}/gh-pages/reports/chrome_enterprise_report_{report_id}.html"
    
    def validate_url_accessibility(self, url: str) -> bool:
        """Validate if a URL is accessible (basic check)"""
        try:
            import requests
            response = requests.head(url, timeout=10)
            return response.status_code == 200
        except Exception:
            return False

class ReportMetadata:
    """Manage report metadata and tracking"""
    
    def __init__(self):
        self.metadata_file = 'reports/report_metadata.json'
    
    def load_metadata(self) -> List[Dict]:
        """Load existing report metadata"""
        try:
            if os.path.exists(self.metadata_file):
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️ Failed to load metadata: {e}")
        return []
    
    def save_metadata(self, metadata: List[Dict]):
        """Save report metadata"""
        try:
            os.makedirs(os.path.dirname(self.metadata_file), exist_ok=True)
            with open(self.metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            print(f"⚠️ Failed to save metadata: {e}")
    
    def add_report(self, report_id: str, report_data: Dict):
        """Add new report to metadata"""
        metadata = self.load_metadata()
        
        new_report = {
            'id': report_id,
            'created_at': datetime.now().isoformat(),
            'posts_count': report_data.get('posts_count', 0),
            'high_priority_count': report_data.get('high_priority_count', 0),
            'analysis_success_count': report_data.get('analysis_success_count', 0),
            'file_size_bytes': report_data.get('file_size_bytes', 0),
            'urls': report_data.get('urls', {}),
            'email_sent': report_data.get('email_sent', False),
            'email_sent_at': report_data.get('email_sent_at'),
        }
        
        metadata.insert(0, new_report)  # Add to beginning
        
        # Keep only recent reports
        metadata = metadata[:100]  # Keep last 100 reports
        
        self.save_metadata(metadata)
        return new_report
    
    def get_recent_reports(self, days: int = 30) -> List[Dict]:
        """Get reports from the last N days"""
        metadata = self.load_metadata()
        cutoff_date = datetime.now() - timedelta(days=days)
        
        recent = []
        for report in metadata:
            try:
                report_date = datetime.fromisoformat(report['created_at'])
                if report_date >= cutoff_date:
                    recent.append(report)
            except Exception:
                continue
        
        return recent
    
    def get_report_stats(self) -> Dict[str, Any]:
        """Get comprehensive report statistics"""
        metadata = self.load_metadata()
        
        if not metadata:
            return {
                'total_reports': 0,
                'reports_this_week': 0,
                'reports_this_month': 0,
                'total_posts_analyzed': 0,
                'avg_posts_per_report': 0,
            }
        
        now = datetime.now()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        week_count = 0
        month_count = 0
        total_posts = 0
        
        for report in metadata:
            try:
                report_date = datetime.fromisoformat(report['created_at'])
                if report_date >= week_ago:
                    week_count += 1
                if report_date >= month_ago:
                    month_count += 1
                total_posts += report.get('posts_count', 0)
            except Exception:
                continue
        
        return {
            'total_reports': len(metadata),
            'reports_this_week': week_count,
            'reports_this_month': month_count,
            'total_posts_analyzed': total_posts,
            'avg_posts_per_report': total_posts / len(metadata) if metadata else 0,
            'latest_report': metadata[0] if metadata else None,
        }

def get_system_status() -> Dict[str, Any]:
    """Get comprehensive system status"""
    config = ReportConfig()
    url_manager = URLManager(config)
    metadata_manager = ReportMetadata()
    
    return {
        'timestamp': datetime.now().isoformat(),
        'config_status': config.get_config_status(),
        'report_stats': metadata_manager.get_report_stats(),
        'github_pages_url': url_manager.generate_index_url(),
        'system_ready': all([
            config.is_ai_configured(),
            config.is_email_configured() or config.is_github_configured()  # At least one output method
        ])
    }

if __name__ == "__main__":
    print("🔧 Report Configuration and URL Management")
    print("=" * 50)
    
    # Test configuration
    config = ReportConfig()
    status = get_system_status()
    
    print(f"✅ System Status:")
    print(f"   AI Configured: {status['config_status']['ai_configured']}")
    print(f"   Email Configured: {status['config_status']['email_configured']}")
    print(f"   GitHub Configured: {status['config_status']['github_configured']}")
    print(f"   System Ready: {status['system_ready']}")
    
    if status['config_status']['missing_config']:
        print(f"⚠️ Missing Configuration:")
        for item in status['config_status']['missing_config']:
            print(f"   - {item}")
    
    print(f"📊 Report Statistics:")
    stats = status['report_stats']
    print(f"   Total Reports: {stats['total_reports']}")
    print(f"   This Week: {stats['reports_this_week']}")
    print(f"   This Month: {stats['reports_this_month']}")
    
    if status['config_status']['github_pages_url']:
        print(f"🌐 GitHub Pages: {status['config_status']['github_pages_url']}")
    
    # Test URL generation
    url_manager = URLManager(config)
    test_urls = url_manager.get_shareable_urls("test_20240101_123456")
    print(f"🔗 Sample URLs:")
    for url_type, url in test_urls.items():
        if url:
            print(f"   {url_type}: {url}")