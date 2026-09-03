# R-WASH Activity Monitoring Email Template Guide

## Overview

This guide documents the professional email template system for R-WASH Activity Monitoring Reports. The templates are designed to match the visual style of the wardwatch2027 project while incorporating UNICEF branding and contact information.

## Design Specifications

### Visual Style Reference
The template matches the visual design from `/var/www/html/wardwatch2027`:
- **Primary Green**: `#1a5f3f` (from wardwatch2027 theme)
- **Primary Dark**: `#134a30` 
- **Accent Gold**: `#d4a574` (for highlights and secondary elements)
- **Navy**: `#1f2a44` (for footer and technical sections)
- **Background**: `#f8f9fa` (light gray for readability)

### Branding Elements
- **UNICEF Logo**: `https://rwash.odiousodds.xyz/img/Logo_of_UNICEF_(cropped).svg`
- **Professional typography**: System fonts for maximum compatibility
- **Color-coded status indicators**: Green (success), Gold (partial), Red (failure)

### Contact Information
- **Phone**: +254 725 275610
- **Email**: md@globeconcs.com
- **Organization**: R-WASH Activity Monitoring System (UNICEF Partnership)

## Template Files

### 1. HTML Template
**Location**: `src/rwash_activity_report_email_template.html`

A standalone HTML file that can be opened in a browser for previewing. This is useful for:
- Visual testing and design review
- Client presentations
- Template customization

### 2. Python Template Module
**Location**: `src/rwash_email_templates.py`

A Python module that provides:
- `create_rwash_activity_report_html()` - Generate HTML email body
- `create_rwash_activity_report_email()` - Create complete email message
- Dynamic data insertion
- Status-based color coding
- Professional formatting

## Usage Examples

### Basic Usage

```python
from rwash_email_templates import create_rwash_activity_report_email

# Prepare report data
report_data = {
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
email = create_rwash_activity_report_email(
    report_data,
    to_email="wagura465@gmail.com",
    cc_email="victor@globeconcs.com"
)

# Access email components
subject = email['subject']
html_body = email['html_body']
from_email = email['from_email']
```

### Integration with Email Notifier

To integrate with the existing email notification system:

```python
from email_notifier import send_email_notification
from rwash_email_templates import create_rwash_activity_report_email

# Generate R-WASH formatted email
email = create_rwash_activity_report_email(report_data)

# Send using existing email infrastructure
config = load_email_config()
# Use the custom HTML body instead of default template
```

### Custom Data Structure

The template accepts flexible data structures:

```python
# Simple key-value pairs
stats = {
    'Projects Processed': 9,
    'Total Submissions': 1234
}

# Nested dictionaries (automatically flattened)
stats = {
    'By Country': {
        'Ethiopia': 456,
        'Somalia': 389,
        'Sudan': 389
    }
}
```

## Template Features

### 1. Responsive Design
- Mobile-first approach with breakpoints at 600px
- Fluid images that scale appropriately
- Stackable columns for mobile devices
- Touch-friendly spacing

### 2. Email Client Compatibility
- Table-based layout for maximum compatibility
- Inline CSS for consistent rendering
- MSO conditional comments for Outlook support
- Fallback styles for older clients

### 3. Status-Based Styling
- Automatic color coding based on status
- Success (green), Partial (gold), Failure (red)
- Clear visual indicators for quick scanning
- Professional gradient headers

### 4. Professional Sections
- **Header**: UNICEF logo with gradient background
- **Status Banner**: Prominent status indicator
- **Processing Summary**: Three distinct sections for each script
- **Contact Information**: Professional footer with contact details
- **Branding**: UNICEF partnership acknowledgment

## Customization Guide

### Changing Colors

Edit the color variables in the template:

```python
# In rwash_email_templates.py
status_colors = {
    'Success': '#1a5f3f',  # Primary green
    'Partial': '#d4a574',  # Accent gold
    'Failure': '#dc3545',  # Error red
    'Warning': '#f57c00'   # Warning orange
}
```

### Modifying Contact Information

Update the contact section in the HTML template:

```html
<td style="padding-bottom: 12px; color: #3c4043; font-size: 14px;">
    <strong>Phone:</strong> <a href="tel:+254725275610">+254 725 275610</a>
</td>
<td style="padding-bottom: 12px; color: #3c4043; font-size: 14px;">
    <strong>Email:</strong> <a href="mailto:md@globeconcs.com">md@globeconcs.com</a>
</td>
```

### Adding Custom Sections

Add new sections by copying the existing section pattern:

```html
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin-top: 30px;">
    <tr>
        <td style="background-color: #f8f9fa; border-left: 4px solid #1a5f3f; padding: 25px; border-radius: 4px;">
            <h2 style="margin: 0 0 20px 0; color: #1a5f3f; font-size: 18px; font-weight: 600;">
                📋 Custom Section Title
            </h2>
            <!-- Your content here -->
        </td>
    </tr>
</table>
```

## Testing

### Preview in Browser
```bash
# Generate sample email
python3 src/rwash_email_templates.py

# Open in browser
open /tmp/rwash_activity_report_email.html
```

### Email Client Testing
Test across different email clients:
- Gmail
- Outlook
- Apple Mail
- Mobile clients (iOS Mail, Gmail app)
- Web-based clients

### Responsive Testing
Test on various screen sizes:
- Desktop (1200px+)
- Tablet (768px - 1024px)
- Mobile (320px - 767px)

## Best Practices

### 1. Data Validation
Always validate data before passing to template:
```python
def validate_report_data(data):
    required_keys = ['download_status', 'download_stats', 
                    'conversion_status', 'conversion_stats',
                    'upload_status', 'upload_stats']
    for key in required_keys:
        if key not in data:
            raise ValueError(f"Missing required key: {key}")
    return data
```

### 2. Error Handling
```python
try:
    email = create_rwash_activity_report_email(report_data)
except Exception as e:
    logger.error(f"Failed to generate email: {e}")
    # Fallback to simple text email
```

### 3. Performance
- Cache generated templates when possible
- Minimize data processing before template generation
- Use efficient data structures

### 4. Accessibility
- Use semantic HTML
- Include alt text for images
- Ensure sufficient color contrast
- Test with screen readers

## Integration with Existing Scripts

To replace the current email templates in the processing scripts:

1. **Import the new template module**:
```python
from rwash_email_templates import create_rwash_activity_report_email
```

2. **Collect data from all three scripts**:
```python
# In a wrapper script or modify each script to return data
download_data = get_download_summary()
conversion_data = get_conversion_summary()
upload_data = get_upload_summary()
```

3. **Generate unified report**:
```python
report_data = {
    'download_status': download_data['status'],
    'download_stats': download_data['stats'],
    'conversion_status': conversion_data['status'],
    'conversion_stats': conversion_data['stats'],
    'upload_status': upload_data['status'],
    'upload_stats': upload_data['stats']
}
```

4. **Send single comprehensive email**:
```python
email = create_rwash_activity_report_email(report_data)
send_email(email)
```

## File Locations

- **HTML Template**: `src/rwash_activity_report_email_template.html`
- **Python Module**: `src/rwash_email_templates.py`
- **Documentation**: `docs/RWASH_EMAIL_TEMPLATE_GUIDE.md`
- **Sample Output**: `/tmp/rwash_activity_report_email.html`

## Support

For issues or questions:
- **Technical Support**: md@globeconcs.com
- **Phone**: +254 725 275610
- **Project**: R-WASH Activity Monitoring System

## Version History

- **v1.0.0** (2026-09-03): Initial release with UNICEF branding and wardwatch2027 styling

---

**Note**: This template follows modern email development best practices and is designed for maximum compatibility across email clients while maintaining a professional appearance that aligns with the wardwatch2027 project's visual identity.