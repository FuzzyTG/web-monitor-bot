#!/usr/bin/env python3

import sys
import os
from datetime import datetime
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def create_competitive_intelligence_markdown(processed_posts, aggregated_data, reports_dir, report_date):
    """
    Create comprehensive competitive intelligence report in Markdown format
    Based on the complete 11-section structure from user's working template
    
    Args:
        processed_posts (list): Posts with structured data
        aggregated_data (dict): Aggregated analysis data
        reports_dir (str): Reports directory 
        report_date (str): Date in YYYY-MM-DD format
        
    Returns:
        str: Complete Markdown content
    """
    
    # Extract data from aggregated_data
    gaps = aggregated_data.get('edge_competitive_gaps', [])
    strategic_actions = aggregated_data.get('strategic_actions', [])
    evidence_base = aggregated_data.get('evidence_base', [])
    executive_summary = aggregated_data.get('executive_summary', 'No executive summary available.')
    edge_advantages = aggregated_data.get('edge_advantages', [])
    capability_terms = aggregated_data.get('capability_term_harvest', [])
    feature_inventory = aggregated_data.get('feature_inventory', [])
    ux_analysis = aggregated_data.get('ux_competitive_analysis', [])
    feature_parity = aggregated_data.get('feature_parity_analysis', {})
    diff_matrix = aggregated_data.get('diff_matrix', [])
    problem_solution = aggregated_data.get('problem_solution_map', [])
    
    # Generate header
    markdown_content = f"""---
title: "Chrome vs Edge — Competitive Intelligence Brief"
date: {datetime.now().strftime('%Y-%m-%d')}
layout: default
---

# Chrome vs Edge — Competitive Intelligence Brief

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')} • **Audience:** PM/Engineering • **Status:** Draft

---

## 6) Executive Summary

{executive_summary}

---

## 1) Edge Competitive Gaps

"""
    
    # Add competitive gaps
    if gaps:
        for gap in gaps:
            markdown_content += f"* {gap}\n"
    else:
        markdown_content += "* No competitive gaps identified.\n"
    
    markdown_content += "\n---\n\n## 2) Strategic Actions\n\n"
    
    # Add strategic actions table
    if strategic_actions:
        markdown_content += """| Chrome Feature | Platform | Edge Action (Defend\|Match\|Leapfrog\|Deprioritize) | Rationale (<=20 words) | Evidence IDs |
|---|---|---|---|---|
"""
        for action in strategic_actions:
            evidence_links = ""
            if action.get('evidence_ids'):
                evidence_links = ', '.join([f'[{eid}](#{eid.lower()})' for eid in action['evidence_ids']])
            
            chrome_feature = action.get('chrome_feature', 'Unknown')
            platform = action.get('platform', 'Unknown') 
            edge_action = action.get('edge_action', 'Unknown')
            rationale = action.get('rationale', 'No rationale provided')
            
            markdown_content += f"| {chrome_feature} | {platform} | {edge_action} | {rationale} | {evidence_links} |\n"
    else:
        markdown_content += "No strategic actions available.\n"
    
    markdown_content += "\n---\n\n"
    
    # Add feature parity charts for each platform
    if feature_parity:
        for platform, features in feature_parity.items():
            if not features:
                continue
                
            platform_title = platform.title()
            markdown_content += f"## 3) Feature Parity Chart — {platform_title}\n\n"
            
            markdown_content += """| Chrome Feature | Chrome DeliveryMode | Chrome AdminPlane | Chrome Granularity | Chrome RedirectSupport | Edge Capability | Edge DeliveryMode | Edge AdminPlane | Edge Granularity | Edge RedirectSupport | Delta & Rationale | Parity Rating | Evidence IDs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
"""
            
            for feature in features:
                evidence_links = ""
                if feature.get('evidence_ids'):
                    evidence_links = ', '.join([f'[{eid}](#{eid.lower()})' for eid in feature['evidence_ids']])
                
                row = [
                    feature.get('chrome_feature', 'Unknown'),
                    feature.get('chrome_delivery_mode', 'Unknown'),
                    feature.get('chrome_admin_plane', 'Unknown'),
                    feature.get('chrome_granularity', 'Unknown'),
                    feature.get('chrome_redirect_support', 'Unknown'),
                    feature.get('edge_capability', 'Unknown'),
                    feature.get('edge_delivery_mode', 'Unknown'),
                    feature.get('edge_admin_plane', 'Unknown'),
                    feature.get('edge_granularity', 'Unknown'),
                    feature.get('edge_redirect_support', 'Unknown'),
                    feature.get('delta_rationale', 'No rationale provided'),
                    feature.get('parity_rating', 'Unknown'),
                    evidence_links
                ]
                
                markdown_content += f"| {' | '.join(row)} |\n"
            
            markdown_content += "\n---\n\n"
    else:
        markdown_content += "## 3) Feature Parity Chart\n\nNo feature parity data available.\n\n---\n\n"
    
    # Add UX Delta Teardown
    markdown_content += "## 4) UX Delta Teardown\n\n"
    
    if ux_analysis:
        markdown_content += """| Feature | Platform | Entry Trigger | Block/Switch Mechanism | Data/Account Boundary | Admin/Policy Controls | Redirect Path | Recovery Path | Notes | Evidence IDs |
|---|---|---|---|---|---|---|---|---|---|
"""
        
        for ux in ux_analysis:
            evidence_links = ""
            if ux.get('evidence_ids'):
                evidence_links = ', '.join([f'[{eid}](#{eid.lower()})' for eid in ux['evidence_ids']])
            
            row = [
                ux.get('feature', 'Unknown'),
                ux.get('platform', 'Unknown'),
                ux.get('entry_trigger', 'Unknown'),
                ux.get('block_switch_mechanism', 'Unknown'),
                ux.get('data_account_boundary', 'Unknown'),
                ux.get('admin_policy_controls', 'Unknown'),
                ux.get('redirect_path', 'Unknown'),
                ux.get('recovery_path', 'Unknown'),
                ux.get('notes', 'Unknown'),
                evidence_links
            ]
            
            markdown_content += f"| {' | '.join(row)} |\n"
    else:
        markdown_content += "No UX teardown data available.\n"
    
    markdown_content += "\n---\n\n## 5) Edge Advantage Highlights\n\n"
    
    # Add Edge advantages
    if edge_advantages:
        for advantage in edge_advantages:
            markdown_content += f"* {advantage}\n"
    else:
        markdown_content += "* No Edge advantages identified.\n"
    
    markdown_content += "\n---\n\n## 7) Evidence Register\n\n"
    
    # Add evidence cards
    if evidence_base:
        for evidence in evidence_base:
            evidence_id = evidence.get('id', 'N/A')
            product = evidence.get('product', 'Unknown')
            feature = evidence.get('feature', 'Unknown Feature')
            platforms = ', '.join(evidence.get('platforms', ['Unknown']))
            quote = evidence.get('quote', evidence.get('content', 'No quote available'))
            source_url = evidence.get('url', evidence.get('source', '#'))
            
            markdown_content += f"""### {evidence_id}

**{product}** • **{feature}** • `{platforms}`

> "{quote}"

[Source]({source_url})

"""
    else:
        markdown_content += "No evidence available.\n"
    
    markdown_content += "\n---\n\n## 8) Capability Term Harvest\n\n"
    
    # Add capability terms table
    if capability_terms:
        markdown_content += """| Term | Class | Feature Name | Platforms (in sentence) | Quote | Evidence |
|---|---|---|---|---|---|
"""
        
        for term in capability_terms:
            platforms_str = ', '.join(term.get('platforms_in_sentence', ['Unknown']))
            evidence_id = term.get('evidence_id', 'N/A')
            evidence_link = f'[{evidence_id}](#{evidence_id.lower()})' if evidence_id != 'N/A' else 'N/A'
            
            row = [
                term.get('term', 'Unknown'),
                term.get('class', 'Unknown'),
                term.get('feature_name', 'Unknown'),
                platforms_str,
                term.get('quote', 'No quote available'),
                evidence_link
            ]
            
            markdown_content += f"| {' | '.join(row)} |\n"
    else:
        markdown_content += "No capability terms available.\n"
    
    markdown_content += "\n---\n\n## 9) Diff Matrix\n\n"
    
    # Add diff matrix table
    if diff_matrix:
        markdown_content += """| Class | Term | Platform | Chrome Feature | Edge Status | Required Edge Phrase | Evidence IDs | Reason |
|---|---|---|---|---|---|---|---|
"""
        
        for diff in diff_matrix:
            evidence_links = ""
            if diff.get('evidence_ids'):
                evidence_links = ', '.join([f'[{eid}](#{eid.lower()})' for eid in diff['evidence_ids']])
            
            row = [
                diff.get('class', 'Unknown'),
                diff.get('term', 'Unknown'),
                diff.get('platform', 'Unknown'),
                diff.get('chrome_feature', 'Unknown'),
                diff.get('edge_status', 'Unknown'),
                diff.get('required_edge_phrase', 'Unknown'),
                evidence_links,
                diff.get('reason', 'No reason provided')
            ]
            
            markdown_content += f"| {' | '.join(row)} |\n"
    else:
        markdown_content += "No diff matrix data available.\n"
    
    markdown_content += "\n---\n\n## 10) Feature Inventory\n\n"
    
    # Add feature inventory table
    if feature_inventory:
        markdown_content += """| Name | Purpose | Direct Quote (≤40w) | Platforms in Source |
|---|---|---|---|
"""
        
        for feature in feature_inventory:
            platforms_str = ', '.join(feature.get('platforms_in_source', ['Unknown']))
            
            row = [
                feature.get('name', 'Unknown'),
                feature.get('one_line_purpose', 'Unknown purpose'),
                feature.get('direct_quote', 'No quote available'),
                platforms_str
            ]
            
            markdown_content += f"| {' | '.join(row)} |\n"
    else:
        markdown_content += "No feature inventory available.\n"
    
    markdown_content += "\n---\n\n## 11) Problem–Solution Map (Chrome view)\n\n"
    
    # Add problem-solution mapping table
    if problem_solution:
        markdown_content += """| Problem | Category | Chrome Feature | Pain Point Addressed | Value Proposition | Evidence IDs |
|---|---|---|---|---|---|
"""
        
        for ps in problem_solution:
            evidence_links = ""
            if ps.get('evidence_ids'):
                evidence_links = ', '.join([f'[{eid}](#{eid.lower()})' for eid in ps['evidence_ids']])
            
            row = [
                ps.get('problem', 'Unknown'),
                ps.get('category', 'Unknown'),
                ps.get('chrome_feature', 'Unknown'),
                ps.get('pain_point_addressed', 'Unknown'),
                ps.get('value_proposition', 'Unknown'),
                evidence_links
            ]
            
            markdown_content += f"| {' | '.join(row)} |\n"
    else:
        markdown_content += "No problem-solution mapping data available.\n"
    
    markdown_content += "\n---\n\n**Built for rapid competitive readouts. Evidence IDs link to sources above.**\n"
    
    return markdown_content

# Test with user's comprehensive data
user_analysis_data = {
    "edge_competitive_gaps": [
        "iOS: Edge lacks redirect support in URL filtering parity vs Chrome URL Filtering with Redirect on iOS. [Evidence: E3]"
    ],
    
    "strategic_actions": [
        {
            "chrome_feature": "URL Filtering with Redirect on iOS",
            "platform": "iOS", 
            "edge_action": "Match",
            "rationale": "Due to Redirect/redirect them to their managed Chrome browser gap on iOS. Add redirect option to URL blocklist policy.",
            "evidence_ids": ["E3"]
        }
    ],
    
    "feature_parity_analysis": {
        "ios": [
            {
                "chrome_feature": "URL Filtering with Redirect on iOS",
                "chrome_delivery_mode": "Native-Browser",
                "chrome_admin_plane": "Chrome-Cloud-Management", 
                "chrome_granularity": "Domain",
                "chrome_redirect_support": "Yes",
                "edge_capability": "URL Filtering [https://learn.microsoft.com/en-us/mem/intune/apps/app-configuration-microsoft-edge-ios]",
                "edge_delivery_mode": "Native-Browser",
                "edge_admin_plane": "Intune/Defender",
                "edge_granularity": "Domain",
                "edge_redirect_support": "No",
                "delta_rationale": "Chrome's native filtering includes redirect on block; Edge's does not. AdminPlanes differ.",
                "parity_rating": "Inferior",
                "evidence_ids": ["E2", "E3", "E16"]
            },
            {
                "chrome_feature": "Personal and Work Separation on iOS",
                "chrome_delivery_mode": "Native-Browser",
                "chrome_admin_plane": "Chrome-Cloud-Management",
                "chrome_granularity": "Unknown",
                "chrome_redirect_support": "No",
                "edge_capability": "Managed Browser with Dual Identity [https://learn.microsoft.com/en-us/mem/intune/apps/manage-microsoft-edge]",
                "edge_delivery_mode": "Native-Browser", 
                "edge_admin_plane": "Intune/Defender",
                "edge_granularity": "Unknown",
                "edge_redirect_support": "Yes",
                "delta_rationale": "Both browsers offer native profile separation. Edge can force links into the work profile.",
                "parity_rating": "On Par",
                "evidence_ids": ["E1", "E6"]
            },
            {
                "chrome_feature": "DLP Controls for Profiles",
                "chrome_delivery_mode": "Native-Browser",
                "chrome_admin_plane": "Chrome-Cloud-Management",
                "chrome_granularity": "Unknown",
                "chrome_redirect_support": "No",
                "edge_capability": "App Protection Policies [https://learn.microsoft.com/en-us/mem/intune/apps/app-protection-policy-settings-ios]",
                "edge_delivery_mode": "Native-Browser",
                "edge_admin_plane": "Intune/Defender",
                "edge_granularity": "Unknown",
                "edge_redirect_support": "No",
                "delta_rationale": "Both products support copy/paste restriction between profiles via their respective management planes.",
                "parity_rating": "On Par",
                "evidence_ids": ["E4", "E8"]
            },
            {
                "chrome_feature": "Enhanced Threat Protection",
                "chrome_delivery_mode": "Native-Browser",
                "chrome_admin_plane": "Product-Native",
                "chrome_granularity": "Page-Element",
                "chrome_redirect_support": "No",
                "edge_capability": "Microsoft Defender SmartScreen [https://learn.microsoft.com/en-us/deployedge/microsoft-edge-mobile-security]",
                "edge_delivery_mode": "Native-Browser",
                "edge_admin_plane": "Product-Native",
                "edge_granularity": "Page-Element",
                "edge_redirect_support": "No",
                "delta_rationale": "Both browsers provide native, real-time phishing and malware protection (Safe Browsing vs. SmartScreen).",
                "parity_rating": "On Par",
                "evidence_ids": ["E5", "E9"]
            }
        ],
        "android": [
            {
                "chrome_feature": "Personal and Work Separation on iOS",
                "chrome_delivery_mode": "Unknown",
                "chrome_admin_plane": "Unknown",
                "chrome_granularity": "Unknown",
                "chrome_redirect_support": "Unknown",
                "edge_capability": "Managed Browser with Dual Identity [https://learn.microsoft.com/en-us/mem/intune/apps/manage-microsoft-edge]",
                "edge_delivery_mode": "Native-Browser", 
                "edge_admin_plane": "Intune/Defender",
                "edge_granularity": "Unknown",
                "edge_redirect_support": "Yes",
                "delta_rationale": "Primary source is silent on Chrome for this feature on Android. Edge supports it.",
                "parity_rating": "Unknown",
                "evidence_ids": ["E1", "E6"]
            },
            {
                "chrome_feature": "URL Filtering with Redirect on iOS",
                "chrome_delivery_mode": "Unknown",
                "chrome_admin_plane": "Unknown",
                "chrome_granularity": "Unknown",
                "chrome_redirect_support": "Unknown",
                "edge_capability": "URL Filtering [https://learn.microsoft.com/en-us/mem/intune/apps/app-configuration-microsoft-edge-android]",
                "edge_delivery_mode": "Native-Browser",
                "edge_admin_plane": "Intune/Defender",
                "edge_granularity": "Domain",
                "edge_redirect_support": "No",
                "delta_rationale": "Primary source is silent on Chrome for this feature on Android. Edge supports native filtering.",
                "parity_rating": "Unknown",
                "evidence_ids": ["E2", "E3", "E15"]
            },
            {
                "chrome_feature": "DLP Controls for Profiles",
                "chrome_delivery_mode": "Unknown",
                "chrome_admin_plane": "Unknown",
                "chrome_granularity": "Unknown",
                "chrome_redirect_support": "Unknown",
                "edge_capability": "App Protection Policies [https://learn.microsoft.com/en-us/mem/intune/apps/app-protection-policy-settings-android]",
                "edge_delivery_mode": "Native-Browser",
                "edge_admin_plane": "Intune/Defender",
                "edge_granularity": "Unknown",
                "edge_redirect_support": "No",
                "delta_rationale": "Primary source is silent on Chrome for this feature on Android. Edge supports it.",
                "parity_rating": "Unknown",
                "evidence_ids": ["E4", "E8"]
            },
            {
                "chrome_feature": "Enhanced Threat Protection",
                "chrome_delivery_mode": "Native-Browser",
                "chrome_admin_plane": "Product-Native",
                "chrome_granularity": "Page-Element",
                "chrome_redirect_support": "No",
                "edge_capability": "Microsoft Defender SmartScreen [https://learn.microsoft.com/en-us/deployedge/microsoft-edge-mobile-security]",
                "edge_delivery_mode": "Native-Browser",
                "edge_admin_plane": "Product-Native",
                "edge_granularity": "Page-Element",
                "edge_redirect_support": "No",
                "delta_rationale": "Both browsers provide native, real-time phishing and malware protection (Safe Browsing vs. SmartScreen).",
                "parity_rating": "On Par",
                "evidence_ids": ["E5", "E9"]
            }
        ],
        "desktop": [
            {
                "chrome_feature": "Personal and Work Separation on iOS",
                "chrome_delivery_mode": "Unknown",
                "chrome_admin_plane": "Unknown",
                "chrome_granularity": "Unknown",
                "chrome_redirect_support": "Unknown",
                "edge_capability": "Edge for Business Profiles [https://learn.microsoft.com/en-us/deployedge/microsoft-edge-for-business]",
                "edge_delivery_mode": "Native-Browser",
                "edge_admin_plane": "Intune/Defender",
                "edge_granularity": "Unknown",
                "edge_redirect_support": "No",
                "delta_rationale": "Primary source is silent on Chrome for this feature on Desktop. Edge supports it.",
                "parity_rating": "Unknown",
                "evidence_ids": ["E1", "E12"]
            },
            {
                "chrome_feature": "URL Filtering with Redirect on iOS",
                "chrome_delivery_mode": "Unknown",
                "chrome_admin_plane": "Unknown",
                "chrome_granularity": "Unknown",
                "chrome_redirect_support": "Unknown",
                "edge_capability": "URL Filtering Policies [https://learn.microsoft.com/en-us/deployedge/microsoft-edge-policies#urlallowlist]",
                "edge_delivery_mode": "Native-Browser",
                "edge_admin_plane": "Intune/Defender",
                "edge_granularity": "Domain",
                "edge_redirect_support": "No",
                "delta_rationale": "Primary source is silent on Chrome for this feature on Desktop. Edge supports native filtering.",
                "parity_rating": "Unknown",
                "evidence_ids": ["E2", "E3", "E14"]
            },
            {
                "chrome_feature": "DLP Controls for Profiles",
                "chrome_delivery_mode": "Unknown",
                "chrome_admin_plane": "Unknown",
                "chrome_granularity": "Unknown",
                "chrome_redirect_support": "Unknown",
                "edge_capability": "Microsoft Purview Endpoint DLP [https://learn.microsoft.com/en-us/purview/endpoint-dlp-learn-about]",
                "edge_delivery_mode": "External-Dependency",
                "edge_admin_plane": "Intune/Defender",
                "edge_granularity": "Pattern",
                "edge_redirect_support": "No",
                "delta_rationale": "Primary source is silent on Chrome for this feature on Desktop. Edge supports it via Endpoint DLP.",
                "parity_rating": "Unknown",
                "evidence_ids": ["E4"]
            },
            {
                "chrome_feature": "Enhanced Threat Protection",
                "chrome_delivery_mode": "Unknown",
                "chrome_admin_plane": "Unknown",
                "chrome_granularity": "Unknown",
                "chrome_redirect_support": "Unknown",
                "edge_capability": "Microsoft Defender SmartScreen [https://learn.microsoft.com/en-us/deployedge/microsoft-edge-security-smartscreen]",
                "edge_delivery_mode": "Native-Browser",
                "edge_admin_plane": "Product-Native",
                "edge_granularity": "Page-Element",
                "edge_redirect_support": "No",
                "delta_rationale": "Primary source is silent on Chrome for this feature on Desktop. Edge supports it.",
                "parity_rating": "Unknown",
                "evidence_ids": ["E5", "E9"]
            }
        ]
    },
    
    "ux_competitive_analysis": [
        {
            "feature": "URL Filtering with Redirect on iOS",
            "platform": "iOS",
            "entry_trigger": "User navigates to a URL on the admin-configured blocklist.",
            "block_switch_mechanism": "Chrome: Page blocked, automatic redirect. Edge: Page blocked, no redirect.",
            "data_account_boundary": "N/A",
            "admin_policy_controls": "Chrome: Google Admin console. Edge: Intune App Configuration Policy.",
            "redirect_path": "Chrome: To managed browser/safe site. Edge: N/A.",
            "recovery_path": "User must manually navigate away from blocked page.",
            "notes": "Chrome combines block and redirect; Edge policies are separate.",
            "evidence_ids": ["E2", "E3", "E16"]
        }
    ],
    
    "edge_advantages": [
        "Desktop: Edge offers category-based web content filtering via Microsoft Defender for Endpoint. [Evidence: E11]",
        "All: Edge security is deeply integrated with the Microsoft 365 Defender and Intune stack. [Evidence: E9,E11]", 
        "Desktop: Edge for Business provides a dedicated work browser with rich management capabilities. [Evidence: E12]",
        "Android: Edge provides native URL allow/block list capabilities via App Configuration Policies. [Evidence: E15]",
        "iOS: Edge provides native URL allow/block list capabilities via App Configuration Policies. [Evidence: E16]"
    ],
    
    "executive_summary": "Google has announced Chrome for iOS now supports work/personal profile separation, achieving parity with existing Edge capabilities. The primary competitive gap identified is Chrome's ability to redirect users from a blocked URL as part of its native filtering policy, a feature Edge currently lacks on iOS. Other announced features like DLP and threat protection are on par. We should prioritize matching the redirect capability within our URL filtering policy to close this user experience gap.",
    
    "evidence_base": [
        {
            "id": "E1",
            "product": "Chrome",
            "feature": "ManagedProfile on iOS",
            "platforms": ["iOS"],
            "url": "https://cloud.google.com/blog/products/chrome-enterprise/chrome-brings-personal-and-work-separation-to-ios-users-and-more-enterprise-protections-to-mobile",
            "quote": "we're excited to announce that users can now separate their personal and work data in Chrome on iOS."
        },
        {
            "id": "E2", 
            "product": "Chrome",
            "feature": "UrlFiltering on iOS",
            "platforms": ["iOS"],
            "url": "https://cloud.google.com/blog/products/chrome-enterprise/chrome-brings-personal-and-work-separation-to-ios-users-and-more-enterprise-protections-to-mobile",
            "quote": "Admins can configure URL allow and block lists to prevent users from navigating to malicious sites or to ensure users can only access sites from their corporate list."
        },
        {
            "id": "E3",
            "product": "Chrome", 
            "feature": "Redirect from Blocked URL",
            "platforms": ["iOS"],
            "url": "https://cloud.google.com/blog/products/chrome-enterprise/chrome-brings-personal-and-work-separation-to-ios-users-and-more-enterprise-protections-to-mobile",
            "quote": "...or redirect them to their managed Chrome browser to ensure corporate data remains secure."
        },
        {
            "id": "E4",
            "product": "Chrome",
            "feature": "DLP on iOS",
            "platforms": ["iOS"],
            "url": "https://cloud.google.com/blog/products/chrome-enterprise/chrome-brings-personal-and-work-separation-to-ios-users-and-more-enterprise-protections-to-mobile",
            "quote": "...preventing data leakage through copy and paste between their personal and work accounts."
        },
        {
            "id": "E5",
            "product": "Chrome",
            "feature": "ThreatProtection on Mobile",
            "platforms": ["iOS", "Android"],
            "url": "https://cloud.google.com/blog/products/chrome-enterprise/chrome-brings-personal-and-work-separation-to-ios-users-and-more-enterprise-protections-to-mobile",
            "quote": "Enhanced Safe Browsing on mobile provides our strongest protection against phishing and malware by checking URLs in real time..."
        },
        {
            "id": "E6",
            "product": "Edge",
            "feature": "ManagedBrowser on Mobile",
            "platforms": ["iOS", "Android"],
            "url": "https://learn.microsoft.com/en-us/mem/intune/apps/manage-microsoft-edge",
            "quote": "Microsoft Edge for iOS and Android supports app settings that allow...administrators to customize the experience... This feature works with any Unified Endpoint Management (UEM) provider."
        },
        {
            "id": "E8",
            "product": "Edge",
            "feature": "DLP on Mobile",
            "platforms": ["iOS", "Android"],
            "url": "https://learn.microsoft.com/en-us/mem/intune/apps/app-protection-policy-settings-ios",
            "quote": "Prevent 'Save As'... Prevent 'Copy/Paste'... These settings allow you to configure data transfer policies for your organization."
        },
        {
            "id": "E9",
            "product": "Edge",
            "feature": "ThreatProtection",
            "platforms": ["iOS", "Android", "Desktop"],
            "url": "https://learn.microsoft.com/en-us/deployedge/microsoft-edge-mobile-security",
            "quote": "Microsoft Edge for mobile uses Microsoft Defender SmartScreen to protect users from phishing and malware sites and to help protect them from downloading potentially malicious files."
        },
        {
            "id": "E11",
            "product": "Edge",
            "feature": "UrlFiltering (Category-based)",
            "platforms": ["Desktop"],
            "url": "https://learn.microsoft.com/en-us/microsoft-365/security/defender-endpoint/web-content-filtering",
            "quote": "Web content filtering is part of Web protection in Microsoft Defender for Endpoint. It enables your organization to track and regulate access to websites based on their content categories."
        },
        {
            "id": "E12",
            "product": "Edge",
            "feature": "ManagedBrowser on Desktop",
            "platforms": ["Desktop"],
            "url": "https://learn.microsoft.com/en-us/deployedge/microsoft-edge-for-business",
            "quote": "Microsoft Edge for Business is a dedicated Edge experience built for work that enables admins in organizations to give their users a productive and secure work browser across managed and unmanaged devices."
        },
        {
            "id": "E15",
            "product": "Edge",
            "feature": "UrlFiltering on Android",
            "platforms": ["Android"],
            "url": "https://learn.microsoft.com/en-us/mem/intune/apps/app-configuration-microsoft-edge-android",
            "quote": "You can configure specific app configuration settings for Microsoft Edge. Microsoft Edge for Android has the following supported configuration settings: Allowed and blocked URLs."
        },
        {
            "id": "E14",
            "product": "Edge",
            "feature": "UrlFiltering on Desktop",
            "platforms": ["Desktop"],
            "url": "https://learn.microsoft.com/en-us/deployedge/microsoft-edge-policies#urlallowlist",
            "quote": "You can use this policy to specify which URLs are allowed and can be accessed. Configure a list of URLs that are allowed. Users can't access URLs that aren't in this list."
        },
        {
            "id": "E16",
            "product": "Edge",
            "feature": "UrlFiltering on iOS",
            "platforms": ["iOS"],
            "url": "https://learn.microsoft.com/en-us/mem/intune/apps/app-configuration-microsoft-edge-ios",
            "quote": "You can configure specific app configuration settings for Microsoft Edge. Microsoft Edge for iOS has the following supported configuration settings: Allowed and blocked URLs."
        }
    ],
    
    "capability_term_harvest": [
        {
            "term": "personal and work separation",
            "class": "ManagedProfile",
            "feature_name": "Personal and work separation on iOS",
            "platforms_in_sentence": ["iOS"],
            "quote": "we're excited to announce that users can now separate their personal and work data in Chrome on iOS.",
            "evidence_id": "E1"
        },
        {
            "term": "URL allow and block lists", 
            "class": "UrlFiltering",
            "feature_name": "URL filtering with allow and block lists",
            "platforms_in_sentence": ["Unknown"],
            "quote": "Admins can configure URL allow and block lists to prevent users from navigating to malicious sites or to ensure users can only access sites from their corporate list.",
            "evidence_id": "E2"
        },
        {
            "term": "redirect them to their managed Chrome browser",
            "class": "Redirect", 
            "feature_name": "Redirect from blocked URL",
            "platforms_in_sentence": ["Unknown"],
            "quote": "...or redirect them to their managed Chrome browser to ensure corporate data remains secure.",
            "evidence_id": "E3"
        },
        {
            "term": "preventing data leakage through copy and paste",
            "class": "DLP",
            "feature_name": "DLP via copy and paste prevention",
            "platforms_in_sentence": ["Unknown"],
            "quote": "...preventing data leakage through copy and paste between their personal and work accounts.",
            "evidence_id": "E4"
        },
        {
            "term": "protection against phishing and malware",
            "class": "ThreatProtection",
            "feature_name": "Threat protection against phishing and malware",
            "platforms_in_sentence": ["iOS", "Android"],
            "quote": "Enhanced Safe Browsing on mobile provides our strongest protection against phishing and malware by checking URLs in real time...",
            "evidence_id": "E5"
        }
    ],
    
    "diff_matrix": [
        {
            "class": "Redirect",
            "term": "redirect them to their managed Chrome browser",
            "platform": "iOS",
            "chrome_feature": "Redirect from blocked URL",
            "edge_status": "No in-app evidence",
            "required_edge_phrase": "redirect",
            "evidence_ids": ["E3"],
            "reason": "Chrome has Native-Browser Redirect as part of URL filtering; no Edge doc for same integrated capability on platform."
        }
    ],
    
    "feature_inventory": [
        {
            "name": "Personal and Work Separation on iOS",
            "one_line_purpose": "Allows users to maintain separate accounts, cookies, and data for personal and work browsing within a single app.",
            "direct_quote": "we're excited to announce that users can now separate their personal and work data in Chrome on iOS.",
            "platforms_in_source": ["iOS"]
        },
        {
            "name": "URL Filtering with Redirect on iOS",
            "one_line_purpose": "Enables administrators to block or allow specific URLs and automatically redirect users from blocked sites.",
            "direct_quote": "Admins can configure URL allow and block lists to prevent users from navigating to malicious sites...or redirect them to their managed Chrome browser...",
            "platforms_in_source": ["iOS"]
        },
        {
            "name": "DLP Controls for Profiles",
            "one_line_purpose": "Prevents data exfiltration by restricting copy and paste actions between work and personal profiles.",
            "direct_quote": "...preventing data leakage through copy and paste between their personal and work accounts.",
            "platforms_in_source": ["iOS"]
        },
        {
            "name": "Enhanced Threat Protection",
            "one_line_purpose": "Provides real-time protection against phishing, malware, and other web-based threats on mobile devices.",
            "direct_quote": "Enhanced Safe Browsing on mobile provides our strongest protection against phishing and malware by checking URLs in real time...",
            "platforms_in_source": ["iOS", "Android"]
        }
    ],
    
    "problem_solution_map": [
        {
            "problem": "Data commingling on personal devices",
            "category": "Data Security",
            "chrome_feature": "Personal and Work Separation on iOS",
            "pain_point_addressed": "Risk of corporate data leaking into personal apps or accounts on iOS.",
            "value_proposition": "Securely enable BYOD by isolating work data within the managed browser.",
            "evidence_ids": ["E1"]
        },
        {
            "problem": "Access to malicious or unapproved websites",
            "category": "Security & Compliance",
            "chrome_feature": "URL Filtering with Redirect on iOS",
            "pain_point_addressed": "Users may visit harmful sites or non-compliant web applications.",
            "value_proposition": "Enforce corporate web access policies and improve security posture.",
            "evidence_ids": ["E2", "E3"]
        },
        {
            "problem": "Accidental or malicious data exfiltration",
            "category": "Data Security",
            "chrome_feature": "DLP Controls for Profiles",
            "pain_point_addressed": "Users copying sensitive corporate information into personal applications.",
            "value_proposition": "Prevent data loss by enforcing boundaries between work and personal data.",
            "evidence_ids": ["E4"]
        },
        {
            "problem": "Mobile users exposed to web threats",
            "category": "Threat Management",
            "chrome_feature": "Enhanced Threat Protection",
            "pain_point_addressed": "Employees are increasingly targeted by phishing and malware on mobile devices.",
            "value_proposition": "Protect users and corporate data from web-based attacks on any device.",
            "evidence_ids": ["E5"]
        }
    ]
}

# Mock post structure
mock_post = {
    'url': 'https://cloud.google.com/blog/products/chrome-enterprise/chrome-brings-personal-and-work-separation-to-ios-users-and-more-enterprise-protections-to-mobile',
    'title': 'Chrome brings personal and work separation to iOS users and more enterprise protections to mobile',
    'content': 'Chrome Enterprise mobile security and management features for iOS',
    'published_date': datetime.now().strftime('%Y-%m-%d'),
    'summary': 'Chrome for iOS adds work/personal separation, URL filtering with redirect, DLP controls, and enhanced threat protection',
    'structured_data': user_analysis_data
}

print("Generating comprehensive Markdown report with all 11 sections...")

try:
    # Generate the Markdown report
    markdown_content = create_competitive_intelligence_markdown(
        [mock_post], 
        user_analysis_data,
        "reports",
        datetime.now().strftime('%Y-%m-%d')
    )
    
    # Save to file
    report_filename = f"reports/competitive_intelligence_markdown_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    os.makedirs("reports", exist_ok=True)
    
    with open(report_filename, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    
    print(f"✅ Markdown report generated successfully!")
    print(f"📁 Report saved to: {report_filename}")
    print("\n🔍 This report includes ALL 11 sections:")
    print("   ✅ 1) Edge Competitive Gaps")
    print("   ✅ 2) Strategic Actions") 
    print("   ✅ 3) Feature Parity Charts (iOS, Android, Desktop)")
    print("   ✅ 4) UX Delta Teardown")
    print("   ✅ 5) Edge Advantage Highlights")
    print("   ✅ 6) Executive Summary")
    print("   ✅ 7) Evidence Register (12 evidence items)")
    print("   ✅ 8) Capability Term Harvest")
    print("   ✅ 9) Diff Matrix")
    print("   ✅ 10) Feature Inventory")
    print("   ✅ 11) Problem-Solution Map")
    print("\n📊 Data completeness:")
    print(f"   • {len(user_analysis_data.get('evidence_base', []))} evidence items")
    print(f"   • {len(user_analysis_data.get('capability_term_harvest', []))} capability terms")
    print(f"   • {len(user_analysis_data.get('feature_inventory', []))} feature inventory items")
    print(f"   • {len(user_analysis_data.get('problem_solution_map', []))} problem-solution mappings")
    
except Exception as e:
    print(f"❌ Error generating report: {str(e)}")
    import traceback
    traceback.print_exc()