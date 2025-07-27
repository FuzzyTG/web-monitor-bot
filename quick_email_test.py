#!/usr/bin/env python3
"""
Quick test: Mock data → Email formatting → Send
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

def send_test_email():
    """Send a test email with formatted tables and highlights"""
    
    # Mock HTML content with tables and highlights
    html_content = """
    <html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; }
            table { border-collapse: collapse; width: 100%; margin: 20px 0; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
            .defend { color: #d73027; font-weight: bold; }
            .match { color: #fc8d59; font-weight: bold; }
            .leapfrog { color: #4575b4; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>🔍 Chrome Enterprise Competitive Intelligence Brief</h1>
        
        <h2>Executive Summary</h2>
        <p>Chrome Enterprise announces <strong>work-personal profile separation</strong> for iOS users. 
        <strong>Key impact:</strong> Direct competition with Microsoft Edge container technology.</p>
        
        <h2>Strategic Response</h2>
        <table>
            <tr>
                <th>Feature</th>
                <th>Chrome Enterprise</th>
                <th>Microsoft Edge</th>
                <th>Action Required</th>
            </tr>
            <tr>
                <td>iOS Work-Personal Separation</td>
                <td>✅ Available</td>
                <td>❌ Missing</td>
                <td class="defend">DEFEND</td>
            </tr>
            <tr>
                <td>Mobile Security</td>
                <td>Enhanced</td>
                <td>Standard</td>
                <td class="match">MATCH</td>
            </tr>
            <tr>
                <td>Enterprise Integration</td>
                <td>Google Workspace</td>
                <td>Microsoft 365</td>
                <td class="leapfrog">LEAPFROG</td>
            </tr>
        </table>
        
        <h2>Recommended Actions</h2>
        <p><strong>Priority:</strong> HIGH</p>
        <ul>
            <li><span class="defend">DEFEND:</span> Accelerate iOS enterprise features</li>
            <li><span class="match">MATCH:</span> Develop mobile security parity</li>
            <li><span class="leapfrog">LEAPFROG:</span> Leverage M365 advantages</li>
        </ul>
        
        <p><em>Analysis generated on July 26, 2025</em></p>
    </body>
    </html>
    """
    
    # Email setup
    sender_email = os.getenv('EMAIL_USERNAME')
    sender_password = os.getenv('EMAIL_PASSWORD')
    recipient_email = os.getenv('EMAIL_TO', 'alexyuan@microsoft.com')
    
    # Create message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = '[TEST] Chrome Enterprise Competitive Brief - Email Formatting Test'
    msg['From'] = sender_email
    msg['To'] = recipient_email
    
    # Attach HTML content
    html_part = MIMEText(html_content, 'html')
    msg.attach(html_part)
    
    # Send email
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        print("✅ Test email sent successfully!")
        print(f"📧 Check {recipient_email} for formatted email")
        return True
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False

if __name__ == "__main__":
    print("📧 Sending test email with tables and highlights...")
    send_test_email()
