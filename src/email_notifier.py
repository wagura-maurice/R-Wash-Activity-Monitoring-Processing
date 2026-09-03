#!/usr/bin/env python3
"""Email notification module for R-WASH Activity Monitoring processing scripts.

This module provides functionality to send email notifications for the various
processing scripts in the R-WASH Activity Monitoring pipeline.
"""

import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Dict, List, Optional


def load_email_config():
    """Load email configuration from environment variables."""
    return {
        'host': os.getenv('MAIL_HOST', 'localhost'),
        'port': int(os.getenv('MAIL_PORT', 25)),
        'username': os.getenv('MAIL_USERNAME', ''),
        'password': os.getenv('MAIL_PASSWORD', ''),
        'to_email': os.getenv('MAIL_TO', ''),
        'cc_email': os.getenv('MAIL_CC', ''),
        'from_email': os.getenv('MAIL_FROM', 'noreply@rwash-monitoring.com'),
        'from_name': os.getenv('MAIL_FROM_NAME', 'R-WASH Monitoring System'),
    }


def format_script_name_for_subject(script_name: str) -> str:
    """Format script name for email subject line.
    
    Converts script names like "007-convert_nonstandard_images.py" to 
    "Convert Nonstandard Images" by:
    - Removing .py extension
    - Removing leading numbers (e.g., 007, 008)
    - Removing underscores
    - Converting to title case
    
    Args:
        script_name: Script filename (e.g., "007-convert_nonstandard_images.py")
    
    Returns:
        Formatted name for subject (e.g., "Convert Nonstandard Images")
    """
    # Remove .py extension
    name = script_name.replace('.py', '')
    
    # Remove leading numbers (e.g., "007-", "008-")
    import re
    name = re.sub(r'^\d+-', '', name)
    
    # Replace underscores with spaces
    name = name.replace('_', ' ')
    
    # Convert to title case
    name = name.title()
    
    return name


def create_html_email_template(
    script_name: str,
    status: str,
    summary: Dict,
    timestamp: str,
    details: Optional[str] = None
) -> str:
    """Create a professional R-WASH branded HTML email template with UNICEF logo.
    
    Args:
        script_name: Name of the script that ran
        status: Status of the run (success/failure/partial)
        summary: Summary statistics from the script run
        timestamp: When the script ran
        details: Optional detailed information about the run
    
    Returns:
        HTML formatted email body
    """
    
    # R-WASH Brand Colors (matching wardwatch2027 style)
    status_colors = {
        'success': '#1a5f3f',  # primary green
        'failure': '#dc3545',  # red  
        'partial': '#d4a574',  # accent gold
        'warning': '#f57c00',  # warning orange
    }
    
    status_color = status_colors.get(status.lower(), '#1a5f3f')
    
    # Build summary items HTML
    summary_items = ""
    for key, value in summary.items():
        if isinstance(value, dict):
            # Handle nested dictionaries
            nested_items = ""
            for nested_key, nested_value in value.items():
                nested_items += f"<li><strong>{nested_key}:</strong> {nested_value}</li>"
            summary_items += f"""
            <div class="summary-group">
                <strong>{key.replace('_', ' ').title()}:</strong>
                <ul>{nested_items}</ul>
            </div>
            """
        else:
            summary_items += f"<li><strong>{key.replace('_', ' ').title()}:</strong> {value}</li>"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f8f9fa;
            }}
            .container {{
                background-color: #ffffff;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 4px 6px rgba(0,0,0,0.07);
            }}
            .header {{
                background: linear-gradient(135deg, #1a5f3f 0%, #134a30 100%);
                color: white;
                padding: 30px 40px;
                text-align: center;
            }}
            .header img {{
                max-width: 180px;
                height: auto;
                margin: 0 auto 20px auto;
                display: block;
            }}
            .header h1 {{
                margin: 0 0 8px 0;
                font-size: 24px;
                font-weight: 600;
                letter-spacing: 0.5px;
            }}
            .header p {{
                margin: 0;
                color: #d4a574;
                font-size: 14px;
                font-weight: 500;
            }}
            .status-banner {{
                background-color: #2d8a5a;
                padding: 15px 40px;
                text-align: center;
            }}
            .status-badge {{
                display: inline-block;
                background-color: #ffffff;
                color: {status_color};
                padding: 8px 20px;
                border-radius: 20px;
                font-size: 13px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            .content {{
                padding: 40px 40px 30px 40px;
            }}
            .greeting {{
                color: #3c4043;
                font-size: 16px;
                line-height: 1.6;
                margin-bottom: 20px;
            }}
            .timestamp {{
                background-color: #1f2a44;
                color: #ffffff;
                padding: 20px;
                border-radius: 4px;
                text-align: center;
                margin-top: 30px;
                font-size: 14px;
                font-weight: 500;
            }}
            .summary {{
                background-color: #f8f9fa;
                border-left: 4px solid {status_color};
                padding: 25px;
                margin: 30px 0;
                border-radius: 4px;
            }}
            .summary h3 {{
                margin-top: 0;
                margin-bottom: 20px;
                color: #1a5f3f;
                font-size: 18px;
                font-weight: 600;
            }}
            .summary ul {{
                margin-bottom: 0;
                padding-left: 20px;
            }}
            .summary li {{
                margin-bottom: 12px;
                color: #3c4043;
                font-size: 14px;
            }}
            .summary-group {{
                margin-bottom: 10px;
            }}
            .details {{
                margin-top: 20px;
            }}
            .details h3 {{
                color: #1a5f3f;
                font-size: 18px;
                font-weight: 600;
                border-bottom: 2px solid #e9ecef;
                padding-bottom: 10px;
            }}
            .details pre {{
                background-color: #f8f9fa;
                padding: 15px;
                border-radius: 4px;
                overflow-x: auto;
                font-size: 12px;
                border: 1px solid #dee2e6;
            }}
            .footer {{
                background-color: #f8f9fa;
                padding: 40px 40px 20px 40px;
                border-top: 1px solid #e8eaed;
            }}
            .contact-section {{
                text-align: center;
                padding-bottom: 30px;
            }}
            .contact-section h3 {{
                margin: 0 0 20px 0;
                color: #1a5f3f;
                font-size: 16px;
                font-weight: 600;
            }}
            .contact-section p {{
                margin: 0 0 12px 0;
                color: #3c4043;
                font-size: 14px;
            }}
            .contact-section a {{
                color: #1a5f3f;
                text-decoration: none;
            }}
            .branding {{
                text-align: center;
                padding-bottom: 20px;
            }}
            .branding p {{
                margin: 0 0 10px 0;
                color: #5f6368;
                font-size: 12px;
                line-height: 1.5;
            }}
            .copyright {{
                text-align: center;
                padding-top: 20px;
                border-top: 1px solid #e8eaed;
            }}
            .copyright p {{
                margin: 0;
                color: #5f6368;
                font-size: 11px;
                line-height: 1.5;
            }}
            .script-name {{
                font-family: 'Courier New', monospace;
                background-color: #e8eaed;
                padding: 2px 8px;
                border-radius: 3px;
                font-size: 13px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <!-- Header with UNICEF Logo -->
            <div class="header">
                <img src="https://rwash.odiousodds.xyz/img/Logo_of_UNICEF_(cropped).svg" alt="UNICEF Logo">
                <h1>R-WASH Activity Monitoring</h1>
                <p>Daily Processing Report</p>
            </div>
            
            <!-- Status Banner -->
            <div class="status-banner">
                <span class="status-badge">✓ {status.title()}</span>
            </div>
            
            <div class="content">
                <p class="greeting">Dear R-WASH Team,</p>
                <p class="greeting">The R-WASH Activity Monitoring system has completed its daily processing cycle. Below is a comprehensive report of today's activities.</p>
                
                <div class="summary">
                    <h3>📊 Processing Summary</h3>
                    <ul>
                        <li><strong>Script:</strong> <span class="script-name">{script_name}</span></li>
                        <li><strong>Status:</strong> <span style="color: {status_color}; font-weight: 500;">{status.title()}</span></li>
                        {summary_items}
                    </ul>
                </div>
                
                {f'<div class="details"><h3>📋 Detailed Information</h3><pre>{details}</pre></div>' if details else ''}
                
                <div class="timestamp">
                    Processing completed on <strong>{timestamp}</strong>
                </div>
            </div>
            
            <!-- Footer with Contact Information -->
            <div class="footer">
                <div class="contact-section">
                    <h3>Contact Information</h3>
                    <p><strong>Phone:</strong> <a href="tel:+254725275610">+254 725 275610</a></p>
                    <p><strong>Email:</strong> <a href="mailto:md@globeconcs.com">md@globeconcs.com</a></p>
                </div>
                
                <div class="branding">
                    <p>This report is generated by the R-WASH Activity Monitoring System, implemented in partnership with UNICEF.</p>
                </div>
                
                <div class="copyright">
                    <p>© 2026 R-WASH Activity Monitoring. All rights reserved.<br>
                    Running on Ubuntu VPS • Scheduled: Daily at 00:00:00 UTC</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html


def send_email_notification(
    script_name: str,
    status: str,
    summary: Dict,
    details: Optional[str] = None,
    config: Optional[Dict] = None
) -> bool:
    """Send an email notification about script execution.
    
    Args:
        script_name: Name of the script that ran
        status: Status of the run (success/failure/partial/warning)
        summary: Summary statistics from the script run
        details: Optional detailed information about the run
        config: Optional email configuration (will load from env if not provided)
    
    Returns:
        True if email was sent successfully, False otherwise
    """
    
    if config is None:
        config = load_email_config()
    
    # Check if email configuration is available
    if not config['to_email']:
        print("WARNING: No recipient email configured. Skipping email notification.", flush=True)
        return False
    
    if not config['host']:
        print("WARNING: No SMTP host configured. Skipping email notification.", flush=True)
        return False
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    # Format script name for subject line (remove .py, numbers, underscores, convert to title case)
    formatted_name = format_script_name_for_subject(script_name)
    
    # Create email message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"[{status.upper()}] R-WASH Processing: {formatted_name}"
    msg['From'] = formataddr((config['from_name'], config['from_email']))
    msg['To'] = config['to_email']
    
    if config['cc_email']:
        msg['Cc'] = config['cc_email']
    
    # Create HTML body
    html_body = create_html_email_template(script_name, status, summary, timestamp, details)
    
    # Attach HTML body
    html_part = MIMEText(html_body, 'html')
    msg.attach(html_part)
    
    # Send email
    try:
        if config['username'] and config['password']:
            # Use authentication
            with smtplib.SMTP(config['host'], config['port']) as server:
                server.starttls()  # Secure the connection
                server.login(config['username'], config['password'])
                
                # Combine To and CC for sending
                recipients = [config['to_email']]
                if config['cc_email']:
                    recipients.append(config['cc_email'])
                
                server.send_message(msg)
        else:
            # Send without authentication
            with smtplib.SMTP(config['host'], config['port']) as server:
                recipients = [config['to_email']]
                if config['cc_email']:
                    recipients.append(config['cc_email'])
                
                server.send_message(msg)
        
        print(f"Email notification sent to {config['to_email']}", flush=True)
        if config['cc_email']:
            print(f"Email notification CC'd to {config['cc_email']}", flush=True)
        
        return True
        
    except Exception as exc:
        print(f"Failed to send email notification: {exc}", flush=True)
        return False


def send_success_email(script_name: str, summary: Dict, details: Optional[str] = None) -> bool:
    """Send a success email notification."""
    return send_email_notification(script_name, "success", summary, details)


def send_failure_email(script_name: str, summary: Dict, error_message: str) -> bool:
    """Send a failure email notification."""
    return send_email_notification(script_name, "failure", summary, error_message)


def send_warning_email(script_name: str, summary: Dict, warning_message: str) -> bool:
    """Send a warning email notification."""
    return send_email_notification(script_name, "warning", summary, warning_message)


def send_partial_success_email(script_name: str, summary: Dict, details: Optional[str] = None) -> bool:
    """Send a partial success email notification."""
    return send_email_notification(script_name, "partial", summary, details)