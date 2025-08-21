# Test Data for Competitive Analysis Parser

This directory contains external test data files for validating the competitive analysis parser functionality. All test data is kept separate from source code to ensure no hardcoded samples in production code.

## Files

### `sample_ai_analysis_chrome_ios.txt`
- **Description**: Complete AI analysis sample covering Chrome iOS competitive intelligence
- **Source**: Real AI analysis output from production system
- **Sections**: Contains all 11 analysis sections with mixed formats (CSV, JSON, Markdown)
- **Evidence Items**: 16 evidence items (E1-E16)
- **Purpose**: Primary test case for validating 100% data extraction capability

## Test Data Format

The test data follows the standardized AI analysis format with these sections:
1. Edge Competitive Gaps
2. Strategic Actions (CSV)
3. Feature Parity Chart (Multi-platform CSV)
4. UX Delta Teardown (CSV)
5. Edge Advantage Highlights
6. Executive Summary
7. Evidence Register (JSON)
8. Capability Term Harvest (JSON)
9. Diff Matrix (JSON)
10. Feature Inventory (JSON)
11. Problem–Solution Map (CSV)

## Usage

These files are used by the test suite to validate:
- Parser extraction accuracy (target: 100% vs legacy ~40%)
- Evidence item count (target: 16+ vs legacy 4-6)
- Section parsing completeness
- Error handling and fallback behavior
- Performance benchmarking

## Adding New Test Data

When adding new test files:
1. Use descriptive filenames: `sample_ai_analysis_[topic]_[platform].txt`
2. Ensure complete 11-section format
3. Include diverse evidence counts and formats
4. Document source and purpose in this README
5. Update test suite to include new files

## Security Note

All test data is sanitized and contains no sensitive information. URLs and quotes are from public documentation sources only.