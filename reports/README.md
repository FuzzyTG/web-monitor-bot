# Reports Directory

This directory contains generated Markdown reports for the Microsoft Edge Competitive Intelligence system.

## Structure

```
reports/
├── README.md              # This file
├── generated/             # Generated Markdown reports (auto-created)
│   ├── chrome_enterprise_report_20240315_1a2b3c.md
│   ├── chrome_enterprise_report_20240316_4d5e6f.md
│   └── ...
└── templates/             # Report templates (optional - used for custom configurations)
    └── report_config.json # Report configuration
```

## Generated Reports

- **Naming Convention**: `chrome_enterprise_report_{YYYYMMDD_HHMMSS}_{hash}.md`
- **Content**: Professional Markdown reports with structured competitive intelligence data
- **Retention**: Reports are automatically cleaned up after 30 days (configurable)

## Features

Each generated report includes:
- ✅ Executive summary with key insights
- ✅ Edge competitive gaps analysis
- ✅ Strategic actions recommendations  
- ✅ Feature parity charts by platform
- ✅ UX Delta teardown analysis
- ✅ Evidence register with source links
- ✅ Capability term harvest
- ✅ Feature inventory
- ✅ Clean Markdown formatting for easy reading

## Usage

Reports are automatically generated during the production monitoring pipeline and can be:
- Viewed locally with any Markdown reader
- Published to GitHub Pages for web access
- Converted to HTML/PDF using standard Markdown tools
- Shared via direct URLs
- Easily parsed programmatically

## Security

- Plain text Markdown format with no executable content
- No external dependencies required
- Safe for sharing across platforms
- No sensitive data embedded in URLs