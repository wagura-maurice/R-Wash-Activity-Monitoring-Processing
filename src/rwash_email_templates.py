#!/usr/bin/env python3
"""R-WASH Activity Monitoring Email Templates.

This module provides professional email templates for the R-WASH Activity Monitoring
project, matching the visual style of the wardwatch2027 project with UNICEF branding.

Templates follow modern email development best practices:
- Table-based layout for maximum email client compatibility
- Inline CSS for consistent rendering
- Responsive design for mobile devices
- Professional UNICEF branding and contact information
"""

from typing import Dict, List, Optional


def create_rwash_activity_report_html(
    report_data: Dict,
    timestamp: str = ""
) -> str:
    """Create a professional HTML email for R-WASH Activity Monitoring Reports.
    
    This template matches the visual style of the wardwatch2027 project with:
    - Primary green color (#1a5f3f) from the wardwatch2027 theme
    - Accent gold color (#d4a574) for highlights
    - Navy color (#1f2a44) for footer sections
    - UNICEF logo integration
    - Professional contact information
    
    Args:
        report_data: Dictionary containing report statistics and information
        timestamp: When the report was generated (default: current time)
    
    Returns:
        Complete HTML email body as string
    """
    
    # Extract data with defaults
    download_status = report_data.get('download_status', 'Success')
    download_stats = report_data.get('download_stats', {})
    conversion_status = report_data.get('conversion_status', 'Success')
    conversion_stats = report_data.get('conversion_stats', {})
    upload_status = report_data.get('upload_status', 'Success')
    upload_stats = report_data.get('upload_stats', {})
    
    if not timestamp:
        from datetime import datetime
        timestamp = datetime.now().strftime("%B %d, %Y at %H:%M:%S UTC")
    
    # Determine status badge color
    status_colors = {
        'Success': '#1a5f3f',
        'Partial': '#d4a574',
        'Failure': '#dc3545',
        'Warning': '#f57c00'
    }
    
    overall_status = 'Success'  # Default, could be calculated from individual statuses
    status_color = status_colors.get(overall_status, '#1a5f3f')
    
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>R-WASH Activity Monitoring Report</title>
    <!--[if mso]>
    <noscript>
        <xml>
            <o:OfficeDocumentSettings>
                <o:PixelsPerInch>96</o:PixelsPerInch>
            </o:OfficeDocumentSettings>
        </xml>
    </noscript>
    <![endif]-->
    <style>
        body, table, td, a {{ -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }}
        table, td {{ mso-table-lspace: 0pt; mso-table-rspace: 0pt; }}
        img {{ -ms-interpolation-mode: bicubic; border: 0; height: auto; line-height: 100%; outline: none; text-decoration: none; }}
        table {{ border-collapse: collapse !important; }}
        body {{ height: 100% !important; margin: 0 !important; padding: 0 !important; width: 100% !important; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif; -webkit-font-smoothing: antialiased; }}
        
        @media screen and (max-width: 600px) {{
            .email-container {{ width: 100% !important; }}
            .fluid-img {{ width: 100% !important; max-width: 100% !important; height: auto !important; }}
            .stack-column {{ display: block !important; width: 100% !important; max-width: 100% !important; direction: ltr !important; }}
            .mobile-padding {{ padding-left: 20px !important; padding-right: 20px !important; }}
            .mobile-center {{ text-align: center !important; }}
            .mobile-full {{ width: 100% !important; }}
            .mobile-hide {{ display: none !important; }}
        }}
        
        a {{ color: #1a5f3f; text-decoration: underline; }}
        a:hover {{ color: #134a30; text-decoration: none; }}
    </style>
</head>
<body style="margin: 0; padding: 0; background-color: #f8f9fa; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;">
    
    <div style="display: none; max-height: 0; overflow: hidden;">
        R-WASH Activity Monitoring Report - Your daily update on water, sanitation, and hygiene activities
    </div>
    
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f8f9fa;">
        <tr>
            <td style="padding: 40px 20px;">
                
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" class="email-container" align="center" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.07);">
                    
                    <!-- Header with Logo -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #1a5f3f 0%, #134a30 100%); padding: 30px 40px; text-align: center;">
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                <tr>
                                    <td style="text-align: center;">
                                        <img src="https://rwash.odiousodds.xyz/img/Logo_of_UNICEF_(cropped).svg" alt="UNICEF Logo" width="180" style="display: block; max-width: 180px; height: auto; margin: 0 auto;">
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding-top: 20px; text-align: center;">
                                        <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 600; letter-spacing: 0.5px;">
                                            R-WASH Activity Monitoring
                                        </h1>
                                        <p style="margin: 8px 0 0 0; color: #d4a574; font-size: 14px; font-weight: 500;">
                                            Daily Processing Report
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Status Banner -->
                    <tr>
                        <td style="background-color: #2d8a5a; padding: 15px 40px; text-align: center;">
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                <tr>
                                    <td style="text-align: center;">
                                        <span style="display: inline-block; background-color: #ffffff; color: {status_color}; padding: 8px 20px; border-radius: 20px; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px;">
                                            ✓ {overall_status}
                                        </span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Content Section -->
                    <tr>
                        <td style="padding: 40px 40px 30px 40px;">
                            
                            <!-- Greeting -->
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                <tr>
                                    <td>
                                        <p style="margin: 0 0 20px 0; color: #3c4043; font-size: 16px; line-height: 1.6;">
                                            Dear R-WASH Team,
                                        </p>
                                        <p style="margin: 0 0 20px 0; color: #3c4043; font-size: 16px; line-height: 1.6;">
                                            The R-WASH Activity Monitoring system has completed its daily processing cycle. Below is a comprehensive report of today's activities, including image downloads, conversions, and uploads.
                                        </p>
                                    </td>
                                </tr>
                            </table>
                            
                            <!-- Download Summary -->
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin-top: 30px;">
                                <tr>
                                    <td style="background-color: #f8f9fa; border-left: 4px solid #1a5f3f; padding: 25px; border-radius: 4px;">
                                        <h2 style="margin: 0 0 20px 0; color: #1a5f3f; font-size: 18px; font-weight: 600;">
                                            📊 Image Download Summary
                                        </h2>
                                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                            <tr>
                                                <td style="padding-bottom: 12px; color: #3c4043; font-size: 14px;">
                                                    <strong>Script:</strong> <span style="font-family: 'Courier New', monospace; background-color: #e8eaed; padding: 2px 8px; border-radius: 3px; font-size: 13px;">006-download_images.py</span>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding-bottom: 12px; color: #3c4043; font-size: 14px;">
                                                    <strong>Status:</strong> <span style="color: #1a5f3f; font-weight: 500;">{download_status}</span>
                                                </td>
                                            </tr>
                                            {_format_stats_list(download_stats)}
                                        </table>
                                    </td>
                                </tr>
                            </table>
                            
                            <!-- Image Processing Section -->
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin-top: 30px;">
                                <tr>
                                    <td style="background-color: #f8f9fa; border-left: 4px solid #d4a574; padding: 25px; border-radius: 4px;">
                                        <h2 style="margin: 0 0 20px 0; color: #1a5f3f; font-size: 18px; font-weight: 600;">
                                            🖼️ Image Processing Summary
                                        </h2>
                                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                            <tr>
                                                <td style="padding-bottom: 12px; color: #3c4043; font-size: 14px;">
                                                    <strong>Script:</strong> <span style="font-family: 'Courier New', monospace; background-color: #e8eaed; padding: 2px 8px; border-radius: 3px; font-size: 13px;">007-convert_nonstandard_images.py</span>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding-bottom: 12px; color: #3c4043; font-size: 14px;">
                                                    <strong>Status:</strong> <span style="color: #1a5f3f; font-weight: 500;">{conversion_status}</span>
                                                </td>
                                            </tr>
                                            {_format_stats_list(conversion_stats)}
                                        </table>
                                    </td>
                                </tr>
                            </table>
                            
                            <!-- Upload Section -->
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin-top: 30px;">
                                <tr>
                                    <td style="background-color: #f8f9fa; border-left: 4px solid #1f2a44; padding: 25px; border-radius: 4px;">
                                        <h2 style="margin: 0 0 20px 0; color: #1a5f3f; font-size: 18px; font-weight: 600;">
                                            📤 FTP Upload Summary
                                        </h2>
                                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                            <tr>
                                                <td style="padding-bottom: 12px; color: #3c4043; font-size: 14px;">
                                                    <strong>Script:</strong> <span style="font-family: 'Courier New', monospace; background-color: #e8eaed; padding: 2px 8px; border-radius: 3px; font-size: 13px;">008-upload_sync_images.py</span>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding-bottom: 12px; color: #3c4043; font-size: 14px;">
                                                    <strong>Status:</strong> <span style="color: #1a5f3f; font-weight: 500;">{upload_status}</span>
                                                </td>
                                            </tr>
                                            {_format_stats_list(upload_stats)}
                                        </table>
                                    </td>
                                </tr>
                            </table>
                            
                            <!-- Processing Time -->
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin-top: 30px;">
                                <tr>
                                    <td style="background-color: #1f2a44; padding: 20px; border-radius: 4px; text-align: center;">
                                        <p style="margin: 0; color: #ffffff; font-size: 14px; font-weight: 500;">
                                            Processing completed on <strong>{timestamp}</strong>
                                        </p>
                                    </td>
                                </tr>
                            </table>
                            
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f8f9fa; padding: 40px 40px 20px 40px; border-top: 1px solid #e8eaed;">
                            
                            <!-- Contact Information -->
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                <tr>
                                    <td style="text-align: center; padding-bottom: 30px;">
                                        <h3 style="margin: 0 0 20px 0; color: #1a5f3f; font-size: 16px; font-weight: 600;">
                                            Contact Information
                                        </h3>
                                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" align="center">
                                            <tr>
                                                <td style="padding-bottom: 12px; color: #3c4043; font-size: 14px;">
                                                    <strong>Phone:</strong> <a href="tel:+254725275610" style="color: #1a5f3f; text-decoration: none;">+254 725 275610</a>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding-bottom: 12px; color: #3c4043; font-size: 14px;">
                                                    <strong>Email:</strong> <a href="mailto:md@globeconcs.com" style="color: #1a5f3f; text-decoration: none;">md@globeconcs.com</a>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>
                            
                            <!-- UNICEF Branding -->
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                <tr>
                                    <td style="text-align: center; padding-bottom: 20px;">
                                        <p style="margin: 0 0 10px 0; color: #5f6368; font-size: 12px; line-height: 1.5;">
                                            This report is generated by the R-WASH Activity Monitoring System, implemented in partnership with UNICEF.
                                        </p>
                                    </td>
                                </tr>
                            </table>
                            
                            <!-- Copyright -->
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                <tr>
                                    <td style="text-align: center; padding-top: 20px; border-top: 1px solid #e8eaed;">
                                        <p style="margin: 0; color: #5f6368; font-size: 11px; line-height: 1.5;">
                                            © 2026 R-WASH Activity Monitoring. All rights reserved.<br>
                                            Running on Ubuntu VPS • Scheduled: Daily at 00:00:00 UTC
                                        </p>
                                    </td>
                                </tr>
                            </table>
                            
                        </td>
                    </tr>
                    
                </table>
                
            </td>
        </tr>
    </table>
    
</body>
</html>
"""
    
    return html


def _format_stats_list(stats: Dict) -> str:
    """Format statistics dictionary into HTML table rows.
    
    Args:
        stats: Dictionary of statistic key-value pairs
    
    Returns:
        HTML string with formatted table rows
    """
    rows = []
    for key, value in stats.items():
        if isinstance(value, dict):
            # Handle nested dictionaries
            for nested_key, nested_value in value.items():
                rows.append(f"""
                                            <tr>
                                                <td style="padding-bottom: 12px; color: #3c4043; font-size: 14px;">
                                                    <strong>{nested_key}:</strong> {nested_value}
                                                </td>
                                            </tr>""")
        else:
            rows.append(f"""
                                            <tr>
                                                <td style="padding-bottom: 12px; color: #3c4043; font-size: 14px;">
                                                    <strong>{key}:</strong> {value}
                                                </td>
                                            </tr>""")
    
    # Remove padding from last row
    if rows:
        rows[-1] = rows[-1].replace('padding-bottom: 12px;', 'padding-bottom: 0;')
    
    return ''.join(rows)


def create_rwash_activity_report_email(
    report_data: Dict,
    to_email: str = "wagura465@gmail.com",
    cc_email: str = "victor@globeconcs.com",
    from_email: str = "noreply@rwash-monitoring.com",
    from_name: str = "R-WASH Monitoring System"
) -> Dict:
    """Create a complete email message with R-WASH Activity Monitoring template.
    
    Args:
        report_data: Dictionary containing report statistics
        to_email: Primary recipient email address
        cc_email: CC recipient email address
        from_email: Sender email address
        from_name: Sender name
    
    Returns:
        Dictionary with email components (subject, from, to, cc, html_body)
    """
    from datetime import datetime
    
    timestamp = datetime.now().strftime("%B %d, %Y at %H:%M:%S UTC")
    
    # Determine overall status
    statuses = [
        report_data.get('download_status', 'Success'),
        report_data.get('conversion_status', 'Success'),
        report_data.get('upload_status', 'Success')
    ]
    
    if any('Failure' in s for s in statuses):
        overall_status = 'Failure'
    elif any('Partial' in s or 'Warning' in s for s in statuses):
        overall_status = 'Partial'
    else:
        overall_status = 'Success'
    
    subject = f"[{overall_status.upper()}] R-WASH Activity Monitoring Report - {timestamp}"
    
    html_body = create_rwash_activity_report_html(report_data, timestamp)
    
    return {
        'subject': subject,
        'from_email': from_email,
        'from_name': from_name,
        'to_email': to_email,
        'cc_email': cc_email,
        'html_body': html_body
    }


# Example usage
if __name__ == "__main__":
    # Sample report data
    sample_report = {
        'download_status': 'Success',
        'download_stats': {
            'Projects Processed': 9,
            'Total Submissions': 1234,
            'New Downloads': 45,
            'Reused Existing': 847,
            'Failed Downloads': 0
        },
        'conversion_status': 'Success',
        'conversion_stats': {
            'Files Converted': 13,
            'Orientation Corrections': 1756,
            'Cache Hits': 0
        },
        'upload_status': 'Success',
        'upload_stats': {
            'FTP Server': 'ftp.rwash.net:21',
            'Files Uploaded': 45,
            'Files Skipped': 1716,
            'Failed Uploads': 0
        }
    }
    
    # Generate email
    email = create_rwash_activity_report_email(sample_report)
    
    # Save to file for testing
    with open('/tmp/rwash_activity_report_email.html', 'w') as f:
        f.write(email['html_body'])
    
    print("R-WASH Activity Monitoring email template generated!")
    print(f"Subject: {email['subject']}")
    print(f"To: {email['to_email']}")
    print(f"CC: {email['cc_email']}")
    print(f"HTML saved to: /tmp/rwash_activity_report_email.html")