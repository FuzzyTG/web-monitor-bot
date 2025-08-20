# Microsoft Edge Competitive Intelligence Reports

Welcome to the automated competitive intelligence monitoring system for Microsoft Edge.

## Latest Reports

{% for post in site.posts %}
- [{{ post.title }}]({{ post.url }}) - {{ post.date | date: "%B %d, %Y" }}
{% endfor %}

## Available Reports

- [Chrome Enterprise Report - August 19, 2025 20:23](./chrome_enterprise_report_20250819_202357_e6c57f.md)
- [Chrome Enterprise Report - August 19, 2025 23:17](./chrome_enterprise_report_20250819_231705_70cecb.md)

## About

This site automatically monitors Google Chrome Enterprise blog posts and generates competitive intelligence reports comparing Chrome features with Microsoft Edge capabilities.

### Report Contents

Each report includes:
- ✅ Executive summary with key insights
- ✅ Edge competitive gaps analysis  
- ✅ Strategic actions recommendations
- ✅ Feature parity charts by platform
- ✅ UX Delta teardown analysis
- ✅ Evidence register with source links

### System Information

- **Monitoring Target**: [Google Chrome Enterprise Blog](https://cloud.google.com/blog/products/chrome-enterprise/)
- **Update Frequency**: Daily at 9 AM UTC
- **Report Format**: Markdown
- **Retention Policy**: 30 days

---

*Last updated: {{ site.time | date: "%B %d, %Y at %I:%M %p UTC" }}*

*🤖 Automated monitoring system powered by Claude Code*