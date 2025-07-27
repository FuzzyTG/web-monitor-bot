#!/usr/bin/env python3
"""
Test script to verify markdown header conversion
"""

from monitor import convert_analysis_to_html

def test_header_conversion():
    """Test various header formats"""
    print("Testing markdown header conversion...")
    
    test_content = """
# Main Title
## Executive Summary
### Technical Details
#### Implementation Notes

**Bold Header**

1. Numbered Header

Regular paragraph text.

## 2. Problem-Solution Map (Chrome view)

Another paragraph.
"""
    
    print("Input content:")
    print("-" * 50)
    print(test_content)
    print("-" * 50)
    
    html_output = convert_analysis_to_html(test_content)
    
    print("\nHTML output:")
    print("-" * 50)
    print(html_output)
    print("-" * 50)
    
    # Check for expected conversions
    expected_conversions = [
        ('<h1>Main Title</h1>', '# Main Title'),
        ('<h2>Executive Summary</h2>', '## Executive Summary'),
        ('<h3>Technical Details</h3>', '### Technical Details'),
        ('<h4>Implementation Notes</h4>', '#### Implementation Notes'),
        ('<h3>Bold Header</h3>', '**Bold Header**'),
        ('<h3>Numbered Header</h3>', '1. Numbered Header'),
        ('<h2>2. Problem-Solution Map (Chrome view)</h2>', '## 2. Problem-Solution Map (Chrome view)'),
    ]
    
    print("\nVerification:")
    print("-" * 50)
    all_passed = True
    for expected_html, original_markdown in expected_conversions:
        if expected_html in html_output:
            print(f"✅ '{original_markdown}' → '{expected_html}'")
        else:
            print(f"❌ '{original_markdown}' → Expected '{expected_html}' but not found")
            all_passed = False
    
    if all_passed:
        print("\n🎉 All header conversions working correctly!")
    else:
        print("\n❌ Some header conversions failed")
    
    return all_passed

if __name__ == "__main__":
    test_header_conversion()
