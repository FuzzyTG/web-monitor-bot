#!/usr/bin/env python3

import re
import json
import csv
from io import StringIO
from datetime import datetime

def parse_competitive_report_systematically(report_text):
    """
    Systematically parse user's competitive report input
    Don't assume structure - extract what's actually provided
    """
    
    sections = {}
    
    # Extract Executive Summary
    exec_summary_match = re.search(r'6\) Executive Summary\s*\n(.*?)(?=\n\d+\)|$)', report_text, re.DOTALL)
    if exec_summary_match:
        sections['executive_summary'] = exec_summary_match.group(1).strip()
    
    # Extract Edge Competitive Gaps
    gaps_match = re.search(r'1\) Edge Competitive Gaps\s*\n(.*?)(?=\n\d+\)|$)', report_text, re.DOTALL)
    if gaps_match:
        gaps_text = gaps_match.group(1).strip()
        # Extract bullet points
        gaps = re.findall(r'\* (.+)', gaps_text)
        sections['edge_competitive_gaps'] = gaps
    
    # Extract Strategic Actions CSV
    strategic_match = re.search(r'2\) Strategic Actions\s*\n```csv\s*\n(.*?)\n```', report_text, re.DOTALL)
    if strategic_match:
        csv_content = strategic_match.group(1)
        sections['strategic_actions'] = parse_csv_to_dict_list(csv_content)
    
    # Extract Feature Parity Charts (multiple platforms)
    sections['feature_parity_analysis'] = {}
    
    # Find all platform sections
    parity_sections = re.findall(r'(\w+)\s*\n```csv\s*\n(.*?)\n```', report_text, re.DOTALL)
    for platform, csv_content in parity_sections:
        if platform.lower() in ['ios', 'android', 'desktop']:
            sections['feature_parity_analysis'][platform.lower()] = parse_csv_to_dict_list(csv_content)
    
    # Extract UX Delta Teardown CSV
    ux_match = re.search(r'4\) UX Delta Teardown\s*\n```csv\s*\n(.*?)\n```', report_text, re.DOTALL)
    if ux_match:
        csv_content = ux_match.group(1)
        sections['ux_competitive_analysis'] = parse_csv_to_dict_list(csv_content)
    
    # Extract Edge Advantage Highlights
    advantages_match = re.search(r'5\) Edge Advantage Highlights\s*\n(.*?)(?=\n\d+\)|$)', report_text, re.DOTALL)
    if advantages_match:
        advantages_text = advantages_match.group(1).strip()
        advantages = re.findall(r'\* (.+)', advantages_text)
        sections['edge_advantages'] = advantages
    
    # Extract Evidence Register JSON
    evidence_match = re.search(r'7\) Evidence Register\s*\n```json\s*\n(.*?)\n```', report_text, re.DOTALL)
    if evidence_match:
        try:
            evidence_json = json.loads(evidence_match.group(1))
            sections['evidence_base'] = evidence_json
        except json.JSONDecodeError:
            sections['evidence_base'] = []
    
    # Extract Capability Term Harvest JSON
    capability_match = re.search(r'8\) Capability Term Harvest\s*\n```json\s*\n(.*?)\n```', report_text, re.DOTALL)
    if capability_match:
        try:
            capability_json = json.loads(capability_match.group(1))
            sections['capability_term_harvest'] = capability_json
        except json.JSONDecodeError:
            sections['capability_term_harvest'] = []
    
    # Extract Diff Matrix JSON
    diff_match = re.search(r'9\) Diff Matrix\s*\n```json\s*\n(.*?)\n```', report_text, re.DOTALL)
    if diff_match:
        try:
            diff_json = json.loads(diff_match.group(1))
            sections['diff_matrix'] = diff_json
        except json.JSONDecodeError:
            sections['diff_matrix'] = []
    
    # Extract Feature Inventory JSON
    inventory_match = re.search(r'10\) Feature Inventory\s*\n```json\s*\n(.*?)\n```', report_text, re.DOTALL)
    if inventory_match:
        try:
            inventory_json = json.loads(inventory_match.group(1))
            sections['feature_inventory'] = inventory_json
        except json.JSONDecodeError:
            sections['feature_inventory'] = []
    
    # Extract Problem-Solution Map CSV
    problem_match = re.search(r'11\) Problem–Solution Map.*?\n```csv\s*\n(.*?)\n```', report_text, re.DOTALL)
    if problem_match:
        csv_content = problem_match.group(1)
        sections['problem_solution_map'] = parse_csv_to_dict_list(csv_content)
    
    return sections

def parse_csv_to_dict_list(csv_content):
    """Convert CSV content to list of dictionaries"""
    try:
        reader = csv.DictReader(StringIO(csv_content))
        return [dict(row) for row in reader]
    except Exception as e:
        print(f"Error parsing CSV: {e}")
        return []

def validate_report_structure(parsed_data):
    """
    Validate that we have the expected SECTIONS (not specific counts)
    This is structure validation, not content validation
    """
    required_sections = [
        'executive_summary',
        'edge_competitive_gaps', 
        'strategic_actions',
        'feature_parity_analysis',
        'ux_competitive_analysis',
        'edge_advantages',
        'evidence_base',
        'capability_term_harvest',
        'diff_matrix',
        'feature_inventory',
        'problem_solution_map'
    ]
    
    missing_sections = []
    for section in required_sections:
        if section not in parsed_data or not parsed_data[section]:
            missing_sections.append(section)
    
    if missing_sections:
        print(f"⚠️ Missing sections: {missing_sections}")
    else:
        print("✅ All required sections found")
    
    return len(missing_sections) == 0

def verify_input_output_consistency(original_input, parsed_data):
    """
    Check that we didn't lose data during parsing
    This is data consistency validation
    """
    consistency_report = {
        'platforms_found': list(parsed_data.get('feature_parity_analysis', {}).keys()),
        'evidence_count': len(parsed_data.get('evidence_base', [])),
        'strategic_actions_count': len(parsed_data.get('strategic_actions', [])),
        'gaps_count': len(parsed_data.get('edge_competitive_gaps', [])),
        'capability_terms_count': len(parsed_data.get('capability_term_harvest', []))
    }
    
    print("📊 Data Consistency Report:")
    for key, value in consistency_report.items():
        print(f"   {key}: {value}")
    
    return consistency_report

# Test with the user's original input
user_original_input = """
1) Edge Competitive Gaps
* iOS: Edge lacks redirect support in URL filtering parity vs Chrome URL Filtering with Redirect on iOS. [Evidence: E3]

2) Strategic Actions
```csv
Chrome Feature,Platform,Edge Action (Defend|Match|Leapfrog|Deprioritize),Rationale (<=20 words),Evidence IDs
URL Filtering with Redirect on iOS,iOS,Match,"Due to Redirect/redirect them to their managed Chrome browser gap on iOS. Add redirect option to URL blocklist policy.",E3
```

3) Feature Parity Chart
iOS
```csv
Chrome Feature,Chrome DeliveryMode,Chrome AdminPlane,Chrome Granularity,Chrome RedirectSupport,Edge Capability,Edge DeliveryMode,Edge AdminPlane,Edge Granularity,Edge RedirectSupport,Delta & Rationale,Parity Rating,Evidence IDs
URL Filtering with Redirect on iOS,Native-Browser,Chrome-Cloud-Management,Domain,Yes,URL Filtering [https://learn.microsoft.com/en-us/mem/intune/apps/app-configuration-microsoft-edge-ios],Native-Browser,Intune/Defender,Domain,No,Chrome's native filtering includes redirect on block; Edge's does not. AdminPlanes differ.,Inferior,"E2,E3,E16"
Personal and Work Separation on iOS,Native-Browser,Chrome-Cloud-Management,Unknown,No,Managed Browser with Dual Identity [https://learn.microsoft.com/en-us/mem/intune/apps/manage-microsoft-edge],Native-Browser,Intune/Defender,Unknown,Yes,Both browsers offer native profile separation. Edge can force links into the work profile.,On Par,"E1,E6"
DLP Controls for Profiles,Native-Browser,Chrome-Cloud-Management,Unknown,No,App Protection Policies [https://learn.microsoft.com/en-us/mem/intune/apps/app-protection-policy-settings-ios],Native-Browser,Intune/Defender,Unknown,No,Both products support copy/paste restriction between profiles via their respective management planes.,On Par,"E4,E8"
Enhanced Threat Protection,Native-Browser,Product-Native,Page-Element,No,Microsoft Defender SmartScreen [https://learn.microsoft.com/en-us/deployedge/microsoft-edge-mobile-security],Native-Browser,Product-Native,Page-Element,No,Both browsers provide native, real-time phishing and malware protection (Safe Browsing vs. SmartScreen).,On Par,"E5,E9"
```
Android
```csv
Chrome Feature,Chrome DeliveryMode,Chrome AdminPlane,Chrome Granularity,Chrome RedirectSupport,Edge Capability,Edge DeliveryMode,Edge AdminPlane,Edge Granularity,Edge RedirectSupport,Delta & Rationale,Parity Rating,Evidence IDs
Personal and Work Separation on iOS,Unknown,Unknown,Unknown,Unknown,Managed Browser with Dual Identity [https://learn.microsoft.com/en-us/mem/intune/apps/manage-microsoft-edge],Native-Browser,Intune/Defender,Unknown,Yes,Primary source is silent on Chrome for this feature on Android. Edge supports it.,Unknown,"E1,E6"
URL Filtering with Redirect on iOS,Unknown,Unknown,Unknown,Unknown,URL Filtering [https://learn.microsoft.com/en-us/mem/intune/apps/app-configuration-microsoft-edge-android],Native-Browser,Intune/Defender,Domain,No,Primary source is silent on Chrome for this feature on Android. Edge supports native filtering.,Unknown,"E2,E3,E15"
DLP Controls for Profiles,Unknown,Unknown,Unknown,Unknown,App Protection Policies [https://learn.microsoft.com/en-us/mem/intune/apps/app-protection-policy-settings-android],Native-Browser,Intune/Defender,Unknown,No,Primary source is silent on Chrome for this feature on Android. Edge supports it.,Unknown,"E4,E8"
Enhanced Threat Protection,Native-Browser,Product-Native,Page-Element,No,Microsoft Defender SmartScreen [https://learn.microsoft.com/en-us/deployedge/microsoft-edge-mobile-security],Native-Browser,Product-Native,Page-Element,No,Both browsers provide native, real-time phishing and malware protection (Safe Browsing vs. SmartScreen).,On Par,"E5,E9"
```
Desktop
```csv
Chrome Feature,Chrome DeliveryMode,Chrome AdminPlane,Chrome Granularity,Chrome RedirectSupport,Edge Capability,Edge DeliveryMode,Edge AdminPlane,Edge Granularity,Edge RedirectSupport,Delta & Rationale,Parity Rating,Evidence IDs
Personal and Work Separation on iOS,Unknown,Unknown,Unknown,Unknown,Edge for Business Profiles [https://learn.microsoft.com/en-us/deployedge/microsoft-edge-for-business],Native-Browser,Intune/Defender,Unknown,No,Primary source is silent on Chrome for this feature on Desktop. Edge supports it.,Unknown,"E1,E12"
URL Filtering with Redirect on iOS,Unknown,Unknown,Unknown,Unknown,URL Filtering Policies [https://learn.microsoft.com/en-us/deployedge/microsoft-edge-policies#urlallowlist],Native-Browser,Intune/Defender,Domain,No,Primary source is silent on Chrome for this feature on Desktop. Edge supports native filtering.,Unknown,"E2,E3,E14"
DLP Controls for Profiles,Unknown,Unknown,Unknown,Unknown,Microsoft Purview Endpoint DLP [https://learn.microsoft.com/en-us/purview/endpoint-dlp-learn-about],External-Dependency,Intune/Defender,Pattern,No,Primary source is silent on Chrome for this feature on Desktop. Edge supports it via Endpoint DLP.,Unknown,"E4"
Enhanced Threat Protection,Unknown,Unknown,Unknown,Unknown,Microsoft Defender SmartScreen [https://learn.microsoft.com/en-us/deployedge/microsoft-edge-security-smartscreen],Native-Browser,Product-Native,Page-Element,No,Primary source is silent on Chrome for this feature on Desktop. Edge supports it.,Unknown,"E5,E9"
```

6) Executive Summary
Google has announced Chrome for iOS now supports work/personal profile separation, achieving parity with existing Edge capabilities. The primary competitive gap identified is Chrome's ability to redirect users from a blocked URL as part of its native filtering policy, a feature Edge currently lacks on iOS. Other announced features like DLP and threat protection are on par. We should prioritize matching the redirect capability within our URL filtering policy to close this user experience gap.
"""

print("Testing systematic parser...")

# Parse the input systematically 
parsed_data = parse_competitive_report_systematically(user_original_input)

# Validate structure
structure_valid = validate_report_structure(parsed_data)

# Check consistency 
consistency_report = verify_input_output_consistency(user_original_input, parsed_data)

print(f"\n✅ Structure Valid: {structure_valid}")
print(f"📊 Parsed data keys: {list(parsed_data.keys())}")

# Show what we extracted for each platform
if 'feature_parity_analysis' in parsed_data:
    for platform, data in parsed_data['feature_parity_analysis'].items():
        print(f"   {platform}: {len(data)} rows")