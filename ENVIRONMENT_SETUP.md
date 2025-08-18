# Environment Configuration Setup

This document provides comprehensive guidance for setting up the environment variables needed for the Microsoft Edge Competitive Intelligence system.

## Required Configuration

### 1. AI Configuration (Required)

```bash
# Google Gemini API Key (Required for AI analysis)
GEMINI_API_KEY=your_gemini_api_key_here

# Optional: Custom AI model (default: gemini-2.5-flash)
GEMINI_MODEL=gemini-2.5-flash

# Optional: Custom AI analysis prompt
CUSTOM_AI_PROMPT="Your custom prompt here..."
```

**Setup Instructions:**
1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Copy the key to `GEMINI_API_KEY`

### 2. Email Configuration (Required for notifications)

```bash
# Gmail SMTP Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587

# Gmail Account Credentials
EMAIL_USERNAME=your-email@gmail.com
EMAIL_PASSWORD=your_app_password_here
EMAIL_TO=recipient@example.com
```

**Setup Instructions:**
1. Enable 2-Factor Authentication on your Gmail account
2. Go to [Google Account App Passwords](https://myaccount.google.com/apppasswords)
3. Generate an "App Password" for "Mail"
4. Use the 16-character app password (no spaces) in `EMAIL_PASSWORD`

### 3. GitHub Configuration (Required for hosted reports)

```bash
# GitHub Personal Access Token
GITHUB_TOKEN=ghp_your_token_here

# GitHub Repository (format: username/repo-name)
GITHUB_REPO=yourusername/your-repo-name

# Optional: Custom base URL (auto-generated if not provided)
REPORTS_BASE_URL=https://yourusername.github.io/your-repo-name
```

**Setup Instructions:**
1. Go to [GitHub Personal Access Tokens](https://github.com/settings/tokens)
2. Click "Generate new token (classic)"
3. Select the following scopes:
   - `repo` (Full control of private repositories)
   - `workflow` (Update GitHub Action workflows)
4. Create the token and copy it to `GITHUB_TOKEN`
5. Create or use an existing repository for hosting reports
6. Enable GitHub Pages in repository settings

## Optional Configuration

### Report Management

```bash
# Report retention settings
MAX_REPORTS_TO_KEEP=30
REPORTS_CLEANUP_DAYS=30
ENABLE_REPORT_CLEANUP=true
```

### Monitoring Behavior

```bash
# Notification type (new_posts, test, force_analysis)
NOTIFICATION_TYPE=new_posts

# Force analysis of all posts (not just new ones)
FORCE_ANALYSIS=false
```

### Blog Monitoring

```bash
# Optional: Custom blog URL to monitor
BLOG_URL=https://cloud.google.com/blog/

# Optional: Check interval in hours
CHECK_INTERVAL_HOURS=6
```

## Configuration Validation

To check if your configuration is correct, run:

```bash
uv run python report_config.py
```

This will show:
- ✅ AI Configured
- ✅ Email Configured  
- ✅ GitHub Configured
- ✅ System Ready

Or use the production pipeline:

```bash
uv run python production_pipeline.py --config-check
```

## Minimum Required Configuration

For basic functionality, you need:

1. **AI Configuration**: `GEMINI_API_KEY`
2. **Either Email OR GitHub**: 
   - Email: `EMAIL_USERNAME`, `EMAIL_PASSWORD`, `EMAIL_TO`
   - GitHub: `GITHUB_TOKEN`, `GITHUB_REPO`

## Security Best Practices

1. **Never commit .env files** to version control
2. **Use app passwords** for Gmail (not your regular password)
3. **Limit GitHub token permissions** to only required scopes
4. **Regularly rotate API keys** and tokens
5. **Use environment-specific configurations** for different deployments

## Troubleshooting

### Common Issues

1. **AI not working**: Check `GEMINI_API_KEY` is valid and has quota
2. **Email not sending**: Verify app password and 2FA is enabled
3. **GitHub publishing fails**: Check token permissions and repository access
4. **Reports not accessible**: Verify GitHub Pages is enabled in repository settings

### Debug Commands

```bash
# Check system status
uv run python production_pipeline.py --config-check

# Test configuration components
uv run python report_config.py

# Run integration tests
uv run python test_phase2_integration.py
```

## Production Deployment

For production environments:

1. Use secure secret management (e.g., GitHub Secrets, Azure Key Vault)
2. Set up automated workflows with GitHub Actions
3. Configure monitoring and alerting
4. Enable automatic cleanup to manage storage
5. Set up backup procedures for critical reports

## GitHub Actions Integration

If using GitHub Actions, set these as repository secrets:

- `GEMINI_API_KEY`
- `EMAIL_USERNAME`
- `EMAIL_PASSWORD`
- `EMAIL_TO`
- `GITHUB_TOKEN` (automatically available as `${{ secrets.GITHUB_TOKEN }}`)

The workflow will automatically use these secrets for production monitoring.