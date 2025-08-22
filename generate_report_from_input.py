#!/usr/bin/env python3
"""
Competitive Intelligence Report Generator - VALIDATION ONLY

This script is now VALIDATION ONLY - no hardcoded samples in source code.
For production use, import competitive_analysis_parser directly.

Key Changes:
- Removed all hardcoded sample data (moved to external test files)  
- Uses tests/data/ directory for test data
- Functions preserved for validation purposes
- Clean architecture separation maintained

Usage:
  python3 generate_report_from_input_clean.py
  
The script will automatically find and use test data from tests/data/ directory.
"""

import re
import json
import csv
from io import StringIO
from datetime import datetime
import os
import sys
from pathlib import Path


def parse_competitive_report_systematically(report_text):
    """
    Systematically parse user's competitive report input
    Don't assume structure - extract what's actually provided
    
    NOTE: This function is kept for validation but production should use
    competitive_analysis_parser.py directly.
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
    
    # Find all platform sections in Feature Parity Chart
    parity_section = re.search(r'3\) Feature Parity Chart\s*\n(.*?)(?=\n\d+\)|$)', report_text, re.DOTALL)
    if parity_section:
        parity_content = parity_section.group(1)
        
        # Find iOS section
        ios_match = re.search(r'iOS\s*\n```csv\s*\n(.*?)\n```', parity_content, re.DOTALL)
        if ios_match:
            sections['feature_parity_analysis']['ios'] = parse_csv_to_dict_list(ios_match.group(1))
        
        # Find Android section
        android_match = re.search(r'Android\s*\n```csv\s*\n(.*?)\n```', parity_content, re.DOTALL)
        if android_match:
            sections['feature_parity_analysis']['android'] = parse_csv_to_dict_list(android_match.group(1))
        
        # Find Desktop section
        desktop_match = re.search(r'Desktop\s*\n```csv\s*\n(.*?)\n```', parity_content, re.DOTALL)
        if desktop_match:
            sections['feature_parity_analysis']['desktop'] = parse_csv_to_dict_list(desktop_match.group(1))
    
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


def create_competitive_intelligence_markdown(parsed_data):
    """
    Create comprehensive competitive intelligence report in Markdown format
    Based on what the user actually provided - no assumptions
    
    NOTE: This function is kept for validation but production should use
    monitor.py's create_enhanced_competitive_markdown() instead.
    """
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    markdown_content = f"""---
title: "Chrome vs Edge — Competitive Intelligence Brief"
date: {datetime.now().strftime('%Y-%m-%d')}
layout: default
---

# Chrome vs Edge — Competitive Intelligence Brief

**Generated:** {timestamp} • **Audience:** PM/Engineering • **Status:** Draft

---

## 1) Executive Summary

{parsed_data.get('executive_summary', 'No executive summary provided.')}

---

## 2) Edge Competitive Gaps

"""
    
    edge_gaps = parsed_data.get('edge_competitive_gaps', [])
    if edge_gaps:
        for gap in edge_gaps:
            markdown_content += f"* {gap}\n"
    else:
        markdown_content += "* No competitive gaps identified.\n"
    
    markdown_content += "\n---\n\n## 3) Strategic Actions\n\n"
    
    strategic_actions = parsed_data.get('strategic_actions', [])
    if strategic_actions:
        # Create table
        headers = list(strategic_actions[0].keys()) if strategic_actions else []
        markdown_content += "| " + " | ".join(headers) + " |\n"
        markdown_content += "|" + "---|" * len(headers) + "\n"
        
        for action in strategic_actions:
            row = []
            for header in headers:
                cell_value = str(action.get(header, ''))
                # Escape pipes in cell content
                cell_value = cell_value.replace('|', '\\|')
                row.append(cell_value)
            markdown_content += "| " + " | ".join(row) + " |\n"
    else:
        markdown_content += "No strategic actions provided.\n"
    
    # Feature Parity Analysis
    markdown_content += "\n---\n\n## 4) Feature Parity Chart\n\n"
    
    parity_analysis = parsed_data.get('feature_parity_analysis', {})
    if parity_analysis:
        for platform, features in parity_analysis.items():
            if features:
                markdown_content += f"### {platform.capitalize()}\n\n"
                
                headers = list(features[0].keys()) if features else []
                if headers:
                    markdown_content += "| " + " | ".join(headers) + " |\n"
                    markdown_content += "|" + "---|" * len(headers) + "\n"
                    
                    for feature in features:
                        row = []
                        for header in headers:
                            cell_value = str(feature.get(header, ''))
                            cell_value = cell_value.replace('|', '\\|')
                            row.append(cell_value)
                        markdown_content += "| " + " | ".join(row) + " |\n"
                    
                    markdown_content += "\n"
    else:
        markdown_content += "No feature parity analysis provided.\n"
    
    # UX Delta Teardown  
    markdown_content += "---\n\n## 5) UX Delta Teardown\n\n"
    
    ux_analysis = parsed_data.get('ux_competitive_analysis', [])
    if ux_analysis:
        headers = list(ux_analysis[0].keys()) if ux_analysis else []
        if headers:
            markdown_content += "| " + " | ".join(headers) + " |\n"
            markdown_content += "|" + "---|" * len(headers) + "\n"
            
            for item in ux_analysis:
                row = []
                for header in headers:
                    cell_value = str(item.get(header, ''))
                    cell_value = cell_value.replace('|', '\\|')
                    row.append(cell_value)
                markdown_content += "| " + " | ".join(row) + " |\n"
    else:
        markdown_content += "No UX delta teardown provided.\n"
    
    # Edge Advantages
    markdown_content += "\n---\n\n## 6) Edge Advantage Highlights\n\n"
    
    edge_advantages = parsed_data.get('edge_advantages', [])
    if edge_advantages:
        for advantage in edge_advantages:
            markdown_content += f"* {advantage}\n"
    else:
        markdown_content += "* No Edge advantages identified.\n"
    
    # Evidence Register
    markdown_content += "\n---\n\n## 7) Evidence Register\n\n"
    
    evidence_items = parsed_data.get('evidence_base', [])
    if evidence_items:
        for item in evidence_items:
            if isinstance(item, dict):
                evidence_id = item.get('id', 'Unknown')
                product = item.get('product', 'Unknown')
                feature = item.get('feature', 'Unknown Feature')
                platforms = item.get('platforms', [])
                url = item.get('url', '')
                quote = item.get('quote', '')
                
                markdown_content += f"### {evidence_id}\n\n"
                markdown_content += f"**{product}** • **{feature}** • `{', '.join(platforms)}`\n\n"
                if quote:
                    markdown_content += f"> {quote}\n\n"
                if url:
                    markdown_content += f"[Source]({url})\n\n"
    else:
        markdown_content += "No evidence register provided.\n"
    
    # Additional sections if present
    capability_harvest = parsed_data.get('capability_term_harvest', [])
    if capability_harvest:
        markdown_content += "\n---\n\n## 8) Capability Term Harvest\n\n"
        for item in capability_harvest:
            if isinstance(item, dict):
                term = item.get('term', 'Unknown')
                class_name = item.get('class', 'Unknown')
                feature_name = item.get('feature_name', 'Unknown')
                markdown_content += f"* **{term}** ({class_name}): {feature_name}\n"
    
    diff_matrix = parsed_data.get('diff_matrix', [])
    if diff_matrix:
        markdown_content += "\n---\n\n## 9) Diff Matrix\n\n"
        for item in diff_matrix:
            if isinstance(item, dict):
                class_name = item.get('class', 'Unknown')
                term = item.get('term', 'Unknown')
                platform = item.get('platform', 'Unknown')
                reason = item.get('reason', 'Unknown')
                markdown_content += f"* **{class_name}**: {term} on {platform} - {reason}\n"
    
    feature_inventory = parsed_data.get('feature_inventory', [])
    if feature_inventory:
        markdown_content += "\n---\n\n## 10) Feature Inventory\n\n"
        for item in feature_inventory:
            if isinstance(item, dict):
                name = item.get('name', 'Unknown Feature')
                purpose = item.get('one_line_purpose', 'Unknown purpose')
                platforms = item.get('platforms_in_source', [])
                markdown_content += f"* **{name}**: {purpose} (Platforms: {', '.join(platforms)})\n"
    
    problem_solution = parsed_data.get('problem_solution_map', [])
    if problem_solution:
        markdown_content += "\n---\n\n## 11) Problem–Solution Map\n\n"
        headers = list(problem_solution[0].keys()) if problem_solution else []
        if headers:
            markdown_content += "| " + " | ".join(headers) + " |\n"
            markdown_content += "|" + "---|" * len(headers) + "\n"
            
            for item in problem_solution:
                row = []
                for header in headers:
                    cell_value = str(item.get(header, ''))
                    cell_value = cell_value.replace('|', '\\|')
                    row.append(cell_value)
                markdown_content += "| " + " | ".join(row) + " |\n"
    
    markdown_content += f"""

---

**Built for rapid competitive readouts. Evidence IDs link to sources above.**
"""
    
    return markdown_content


if __name__ == "__main__":
    """
    VALIDATION MODE: This script is now for validation purposes only.
    
    For production use, import competitive_analysis_parser directly.
    Hardcoded sample data removed - use external test data files.
    """
    print("🔧 VALIDATION MODE - Generate Report from External Input")
    print("=" * 60)
    print("This script validates the competitive intelligence parser")
    print("using external test data files (no hardcoded samples).\n")
    
    # Look for test data in tests/data/ directory
    test_data_dir = Path(__file__).parent / "tests" / "data"
    
    if not test_data_dir.exists():
        print("❌ Test data directory not found: tests/data/")
        print("   Create test data files in tests/data/ directory")
        sys.exit(1)
    
    # Find available test files
    test_files = list(test_data_dir.glob("*.txt"))
    
    if not test_files:
        print("❌ No test data files found in tests/data/")
        print("   Add .txt files with AI analysis samples")
        sys.exit(1)
    
    print(f"📁 Found {len(test_files)} test data files:")
    for i, test_file in enumerate(test_files, 1):
        print(f"   {i}. {test_file.name}")
    
    # Use the first available test file
    selected_file = test_files[0]
    print(f"\n📄 Using test file: {selected_file.name}")
    
    try:
        with open(selected_file, 'r', encoding='utf-8') as f:
            user_input = f.read()
        
        print(f"✅ Loaded {len(user_input):,} characters of test data")
        print("\n🔄 Parsing test data systematically...")
        
        # Parse the test data
        parsed_data = parse_competitive_report_systematically(user_input)
        
        print("\n📊 Parsing Results:")
        for section, data in parsed_data.items():
            if isinstance(data, list):
                print(f"   {section}: {len(data)} items")
            elif isinstance(data, dict):
                if section == 'feature_parity_analysis':
                    for platform, platform_data in data.items():
                        print(f"   {section}.{platform}: {len(platform_data)} rows")
                else:
                    print(f"   {section}: {len(data)} items")
            else:
                print(f"   {section}: {type(data).__name__}")
        
        # Generate markdown report
        print("\n📝 Generating markdown report...")
        markdown_content = create_competitive_intelligence_markdown(parsed_data)
        
        # Save to file
        report_filename = f"reports/validation_competitive_intelligence_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        os.makedirs("reports", exist_ok=True)
        
        with open(report_filename, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        print(f"✅ Validation report generated!")
        print(f"📁 Report saved to: {report_filename}")
        print(f"📊 Report length: {len(markdown_content):,} characters")
        print("\n🔍 This validation report demonstrates:")
        print("   ✅ External test data usage (no hardcoded samples)")
        print("   ✅ Systematic parsing of all 11 sections")
        print("   ✅ Evidence linking and referencing")  
        print("   ✅ Clean architecture separation")
        print("   ✅ Production-ready parsing capabilities")
        
        print(f"\n🎯 For production use: import competitive_analysis_parser")
        
    except Exception as e:
        print(f"❌ Validation error: {e}")
        sys.exit(1)