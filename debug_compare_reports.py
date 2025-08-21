#!/usr/bin/env python3
"""
Debug Report Comparison Tool
Compares raw AI response with final report to identify parsing issues
"""

import json
import re
import os
from datetime import datetime
from typing import Dict, List, Any, Tuple


class ReportComparison:
    def __init__(self):
        self.raw_response = None
        self.parsed_sections = None
        self.evidence_base = None
        self.final_report = None
        self.comparison_results = {}
    
    def load_debug_files(self) -> bool:
        """Load all debug files created during report generation"""
        try:
            # Load raw AI response
            if os.path.exists('debug_ai_response.txt'):
                with open('debug_ai_response.txt', 'r', encoding='utf-8') as f:
                    self.raw_response = f.read()
                print(f"✅ Loaded raw AI response ({len(self.raw_response)} chars)")
            else:
                print("❌ debug_ai_response.txt not found")
                return False
            
            # Load parsed sections
            if os.path.exists('debug_parsed_sections.json'):
                with open('debug_parsed_sections.json', 'r', encoding='utf-8') as f:
                    self.parsed_sections = json.load(f)
                print(f"✅ Loaded parsed sections ({len(self.parsed_sections)} sections)")
            else:
                print("❌ debug_parsed_sections.json not found")
                return False
            
            # Load evidence base
            if os.path.exists('debug_evidence_base.json'):
                with open('debug_evidence_base.json', 'r', encoding='utf-8') as f:
                    self.evidence_base = json.load(f)
                print(f"✅ Loaded evidence base ({len(self.evidence_base)} items)")
            else:
                print("❌ debug_evidence_base.json not found")
                return False
            
            # Load final report
            if os.path.exists('debug_final_report.md'):
                with open('debug_final_report.md', 'r', encoding='utf-8') as f:
                    self.final_report = f.read()
                print(f"✅ Loaded final report ({len(self.final_report)} chars)")
            else:
                print("❌ debug_final_report.md not found")
                return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error loading debug files: {e}")
            return False
    
    def extract_ai_evidence_register(self) -> List[Dict]:
        """Extract evidence register from raw AI response"""
        if not self.raw_response:
            return []
        
        try:
            # Find Evidence Register JSON section
            evidence_match = re.search(r'7\) Evidence Register\s*\n```json\s*\n(.*?)\n```', self.raw_response, re.DOTALL)
            if evidence_match:
                evidence_json = json.loads(evidence_match.group(1))
                return evidence_json
        except Exception as e:
            print(f"⚠️ Failed to extract AI evidence register: {e}")
        
        return []
    
    def extract_ai_strategic_actions(self) -> List[Dict]:
        """Extract strategic actions from raw AI response"""
        if not self.raw_response:
            return []
        
        try:
            # Find Strategic Actions CSV section
            actions_match = re.search(r'2\) Strategic Actions\s*\n```csv\s*\n(.*?)\n```', self.raw_response, re.DOTALL)
            if actions_match:
                csv_content = actions_match.group(1)
                # Simple CSV parsing
                lines = csv_content.strip().split('\n')
                if len(lines) < 2:
                    return []
                
                headers = [h.strip() for h in lines[0].split(',')]
                actions = []
                for line in lines[1:]:
                    values = [v.strip().strip('"') for v in line.split(',')]
                    if len(values) >= len(headers):
                        action = dict(zip(headers, values))
                        actions.append(action)
                
                return actions
        except Exception as e:
            print(f"⚠️ Failed to extract AI strategic actions: {e}")
        
        return []
    
    def extract_final_evidence_items(self) -> List[Dict]:
        """Extract evidence items from final markdown report"""
        if not self.final_report:
            return []
        
        evidence_items = []
        
        # Find all evidence entries (### E1, ### E2, etc.)
        evidence_pattern = r'### (E\d+)\n\n(.*?)(?=\n---\n|\n### |\Z)'
        matches = re.findall(evidence_pattern, self.final_report, re.DOTALL)
        
        for match in matches:
            evidence_id, content = match
            
            # Parse the content to determine format
            if '**Source:**' in content:
                # Parser-generated format
                source_match = re.search(r'\*\*Source:\*\* (.+?) •', content)
                context_match = re.search(r'\*\*Context:\*\* (.+?)(?:\n|$)', content)
                platform_match = re.search(r'\*\*Platform:\*\* (.+?)(?:\n|$)', content)
                
                evidence_items.append({
                    'id': evidence_id,
                    'format': 'parser_generated',
                    'source': source_match.group(1) if source_match else 'Unknown',
                    'context': context_match.group(1) if context_match else 'Unknown',
                    'platform': platform_match.group(1) if platform_match else None
                })
            else:
                # AI JSON format
                product_match = re.search(r'\*\*(.+?)\*\* • \*\*(.+?)\*\*', content)
                platforms_match = re.search(r'`(.+?)`', content)
                quote_match = re.search(r'> (.+?)(?:\n|$)', content, re.DOTALL)
                source_match = re.search(r'\[Source\]\((.+?)\)', content)
                
                evidence_items.append({
                    'id': evidence_id,
                    'format': 'ai_json',
                    'product': product_match.group(1) if product_match else 'Unknown',
                    'feature': product_match.group(2) if product_match else 'Unknown',
                    'platforms': platforms_match.group(1) if platforms_match else '',
                    'quote': quote_match.group(1).strip() if quote_match else '',
                    'source_url': source_match.group(1) if source_match else ''
                })
        
        return evidence_items
    
    def extract_final_strategic_actions(self) -> List[Dict]:
        """Extract strategic actions from final markdown report"""
        if not self.final_report:
            return []
        
        # Find Strategic Actions table
        table_match = re.search(r'## 3\) Strategic Actions.*?\n\n(.*?)(?=\n---|\n## |\Z)', self.final_report, re.DOTALL)
        if not table_match:
            return []
        
        table_content = table_match.group(1)
        lines = [line.strip() for line in table_content.split('\n') if line.strip()]
        
        # Find table rows (skip header and separator)
        data_lines = [line for line in lines if line.startswith('|') and '---' not in line][1:]  # Skip header
        
        actions = []
        for line in data_lines:
            cells = [cell.strip() for cell in line.split('|')[1:-1]]  # Remove empty first/last
            if len(cells) >= 5:
                actions.append({
                    'Chrome Feature': cells[0],
                    'Platform': cells[1], 
                    'Edge Action': cells[2],
                    'Rationale': cells[3],
                    'Evidence IDs': cells[4]
                })
        
        return actions
    
    def compare_evidence_registers(self) -> Dict:
        """Compare AI evidence register with final evidence register"""
        ai_evidence = self.extract_ai_evidence_register()
        final_evidence = self.extract_final_evidence_items()
        
        # Count by format
        ai_json_format = [e for e in final_evidence if e.get('format') == 'ai_json']
        parser_generated = [e for e in final_evidence if e.get('format') == 'parser_generated']
        
        # Find duplicates
        ai_ids = set(item.get('id') for item in ai_evidence)
        final_ids = [item.get('id') for item in final_evidence]
        duplicate_ids = [id for id in final_ids if final_ids.count(id) > 1]
        
        # Missing/extra evidence
        missing_in_final = ai_ids - set(final_ids)
        extra_in_final = set(final_ids) - ai_ids
        
        return {
            'ai_evidence_count': len(ai_evidence),
            'final_evidence_count': len(final_evidence),
            'ai_json_format_count': len(ai_json_format),
            'parser_generated_count': len(parser_generated),
            'duplicate_ids': duplicate_ids,
            'missing_in_final': list(missing_in_final),
            'extra_in_final': list(extra_in_final),
            'ai_evidence_ids': list(ai_ids),
            'final_evidence_ids': final_ids
        }
    
    def compare_strategic_actions(self) -> Dict:
        """Compare AI strategic actions with final strategic actions"""
        ai_actions = self.extract_ai_strategic_actions()
        final_actions = self.extract_final_strategic_actions()
        
        # Check for missing Edge Actions
        ai_edge_actions = [action.get('Edge Action (Defend|Match|Leapfrog|Deprioritize)', '') for action in ai_actions]
        final_edge_actions = [action.get('Edge Action', '') for action in final_actions]
        
        empty_final_actions = sum(1 for action in final_edge_actions if not action.strip())
        
        return {
            'ai_actions_count': len(ai_actions),
            'final_actions_count': len(final_actions),
            'ai_edge_actions': ai_edge_actions,
            'final_edge_actions': final_edge_actions,
            'empty_final_actions': empty_final_actions,
            'ai_actions': ai_actions,
            'final_actions': final_actions
        }
    
    def run_full_comparison(self) -> Dict:
        """Run complete comparison analysis"""
        print("🔍 Running comprehensive comparison analysis...")
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'evidence_comparison': self.compare_evidence_registers(),
            'strategic_actions_comparison': self.compare_strategic_actions()
        }
        
        # Add summary
        evidence_comp = results['evidence_comparison']
        actions_comp = results['strategic_actions_comparison']
        
        results['summary'] = {
            'evidence_duplication_detected': len(evidence_comp['duplicate_ids']) > 0,
            'evidence_count_mismatch': evidence_comp['ai_evidence_count'] != evidence_comp['ai_json_format_count'],
            'strategic_actions_missing': actions_comp['empty_final_actions'] > 0,
            'parser_generated_evidence': evidence_comp['parser_generated_count'] > 0
        }
        
        return results
    
    def generate_comparison_report(self, results: Dict) -> str:
        """Generate human-readable comparison report"""
        report = f"""# Debug Report Comparison Analysis

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary

"""
        
        summary = results['summary']
        if summary['evidence_duplication_detected']:
            report += "❌ **Evidence Duplication Detected**\n"
        if summary['evidence_count_mismatch']:
            report += "❌ **Evidence Count Mismatch**\n"
        if summary['strategic_actions_missing']:
            report += "❌ **Strategic Actions Missing**\n"
        if summary['parser_generated_evidence']:
            report += "❌ **Parser-Generated Evidence Found**\n"
        
        if not any(summary.values()):
            report += "✅ **No Issues Detected**\n"
        
        report += f"""
## Evidence Register Analysis

**AI Generated Evidence:** {results['evidence_comparison']['ai_evidence_count']} items
**Final Report Evidence:** {results['evidence_comparison']['final_evidence_count']} items
**AI JSON Format:** {results['evidence_comparison']['ai_json_format_count']} items
**Parser Generated:** {results['evidence_comparison']['parser_generated_count']} items

"""
        
        if results['evidence_comparison']['duplicate_ids']:
            report += f"**Duplicate IDs:** {', '.join(results['evidence_comparison']['duplicate_ids'])}\n"
        
        if results['evidence_comparison']['missing_in_final']:
            report += f"**Missing in Final:** {', '.join(results['evidence_comparison']['missing_in_final'])}\n"
        
        if results['evidence_comparison']['extra_in_final']:
            report += f"**Extra in Final:** {', '.join(results['evidence_comparison']['extra_in_final'])}\n"
        
        report += f"""
## Strategic Actions Analysis

**AI Actions:** {results['strategic_actions_comparison']['ai_actions_count']}
**Final Actions:** {results['strategic_actions_comparison']['final_actions_count']}
**Empty Final Actions:** {results['strategic_actions_comparison']['empty_final_actions']}

**AI Edge Actions:** {results['strategic_actions_comparison']['ai_edge_actions']}
**Final Edge Actions:** {results['strategic_actions_comparison']['final_edge_actions']}

"""
        
        if results['strategic_actions_comparison']['empty_final_actions'] > 0:
            report += "⚠️ **Issue:** Strategic Actions table has empty Edge Action cells\n\n"
        
        return report


def main():
    """Main comparison analysis function"""
    print("🔍 DEBUG REPORT COMPARISON ANALYSIS")
    print("=" * 50)
    
    comparator = ReportComparison()
    
    # Load debug files
    if not comparator.load_debug_files():
        print("❌ Failed to load debug files. Run with --save-debug first.")
        return False
    
    # Run comparison
    results = comparator.run_full_comparison()
    
    # Generate report
    report_content = comparator.generate_comparison_report(results)
    
    # Save comparison report
    try:
        with open('debug_comparison_report.md', 'w', encoding='utf-8') as f:
            f.write(report_content)
        print(f"✅ Comparison report saved to debug_comparison_report.md")
        
        # Also save detailed JSON results
        with open('debug_comparison_results.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"✅ Detailed results saved to debug_comparison_results.json")
        
    except Exception as e:
        print(f"❌ Failed to save comparison report: {e}")
        return False
    
    # Print summary to console
    print("\n📊 COMPARISON SUMMARY")
    print("=" * 30)
    
    evidence_comp = results['evidence_comparison']
    actions_comp = results['strategic_actions_comparison']
    
    print(f"Evidence: AI={evidence_comp['ai_evidence_count']}, Final={evidence_comp['final_evidence_count']}")
    print(f"Formats: AI JSON={evidence_comp['ai_json_format_count']}, Parser={evidence_comp['parser_generated_count']}")
    print(f"Duplicates: {len(evidence_comp['duplicate_ids'])} IDs")
    print(f"Strategic Actions: AI={actions_comp['ai_actions_count']}, Final={actions_comp['final_actions_count']}")
    print(f"Empty Actions: {actions_comp['empty_final_actions']}")
    
    return True


if __name__ == "__main__":
    main()