# Cron Job Configuration for Ubuntu VPS

This document describes the cron job configuration for automated daily execution of the R-WASH Activity Monitoring image pipeline on Ubuntu VPS.

## Overview

The image pipeline (scripts 006, 007, 008) runs automatically every day at midnight (00:00:00 UTC) to process the previous 24 hours of data from ODK Central. Email notifications are sent to the team upon completion of each stage.

## Cron Job Entry

### Full Pipeline (Daily at Midnight UTC)

```bash
0 0 * * * cd /home/wagura-maurice/Documents/WASH\ 2026/R-Wash-Activity-Monitoring-Processing && python3 src/006-download_images.py && python3 src/007-convert_nonstandard_images.py && python3 src/008-upload_sync_images.py
```

### Breakdown

| Component | Description |
|-----------|-------------|
| `0 0 * * *` | Schedule: minute 0, hour 0, every day, every month, every day of week (midnight daily) |
| `cd /home/wagura-maurice/Documents/WASH\ 2026/R-Wash-Activity-Monitoring-Processing` | Change to project directory (note escaped space in path) |
| `python3 src/006-download_images.py` | Download images from ODK Central |
| `&&` | Only run next command if previous succeeded |
| `python3 src/007-convert_nonstandard_images.py` | Convert non-standard image formats to JPG |
| `&&` | Only run next command if previous succeeded |
| `python3 src/008-upload_sync_images.py` | Upload processed images to FTPS server |

## Setup Instructions

### 1. Edit Crontab

```bash
crontab -e
```

### 2. Add the Cron Entry

Copy and paste the cron job entry above into your crontab file.

### 3. Save and Exit

- If using `nano`: Press `Ctrl+X`, then `Y`, then `Enter`
- If using `vim`: Press `Esc`, type `:wq`, then `Enter`

### 4. Verify Cron Job

```bash
# List current cron jobs
crontab -l

# Check cron service status
sudo systemctl status cron

# View cron logs
sudo tail -f /var/log/syslog | grep CRON
```

## Environment Variables

The cron job relies on environment variables set in the `.env` file. Since cron runs with a minimal environment, ensure:

1. **.env file exists** in the project root
2. **Email configuration** is set up in `.env`:
   ```env
   MAIL_MAILER=smtp
   MAIL_HOST=your_smtp_host.com
   MAIL_PORT=2525
   MAIL_USERNAME=your_smtp_username
   MAIL_PASSWORD=your_smtp_password
   MAIL_TO=recipient@example.com
   MAIL_CC=cc_recipient@example.com
   ```

3. **Python dependencies** are installed in the system Python or use a virtual environment

### Using Virtual Environment (Recommended)

If using a virtual environment, modify the cron entry:

```bash
0 0 * * * cd /home/wagura-maurice/Documents/WASH\ 2026/R-Wash-Activity-Monitoring-Processing && /path/to/venv/bin/python3 src/006-download_images.py && /path/to/venv/bin/python3 src/007-convert_nonstandard_images.py && /path/to/venv/bin/python3 src/008-upload_sync_images.py
```

Or activate the virtual environment in the cron job:

```bash
0 0 * * * cd /home/wagura-maurice/Documents/WASH\ 2026/R-Wash-Activity-Monitoring-Processing && source venv/bin/activate && python3 src/006-download_images.py && python3 src/007-convert_nonstandard_images.py && python3 src/008-upload_sync_images.py
```

## Email Notifications

Each script sends an email notification upon completion with:

- **Professional R-WASH branding** with UNICEF logo
- **Status indicators**: Success (green), Partial (gold), Failure (red)
- **Processing statistics**: Files downloaded, converted, uploaded, skipped, failed
- **Contact information**: Phone and email in footer
- **Recipients**: Primary (wagura465@gmail.com) and CC (victor@globeconcs.com)

### Email Subjects

Subject lines use professional formatting (no file extensions, numbers, or underscores):

- `[SUCCESS] R-WASH Processing: Download Images`
- `[SUCCESS] R-WASH Processing: Convert Nonstandard Images`
- `[SUCCESS] R-WASH Processing: Upload Sync Images`

## Alternative Schedules

### Different Time

Run at a different time (e.g., 2:00 AM UTC):

```bash
0 2 * * * cd /home/wagura-maurice/Documents/WASH\ 2026/R-Wash-Activity-Monitoring-Processing && python3 src/006-download_images.py && python3 src/007-convert_nonstandard_images.py && python3 src/008-upload_sync_images.py
```

### Multiple Times Per Day

Run every 6 hours:

```bash
0 */6 * * * cd /home/wagura-maurice/Documents/WASH\ 2026/R-Wash-Activity-Monitoring-Processing && python3 src/006-download_images.py && python3 src/007-convert_nonstandard_images.py && python3 src/008-upload_sync_images.py
```

### Weekdays Only

Run only on weekdays at midnight:

```bash
0 0 * * 1-5 cd /home/wagura-maurice/Documents/WASH\ 2026/R-Wash-Activity-Monitoring-Processing && python3 src/006-download_images.py && python3 src/007-convert_nonstandard_images.py && python3 src/008-upload_sync_images.py
```

## Logging and Monitoring

### Cron Logs

View cron execution logs:

```bash
# View recent cron logs
sudo tail -f /var/log/syslog | grep CRON

# Search for specific script
sudo grep "006-download_images" /var/log/syslog
```

### Script Output

By default, cron sends any script output (stdout/stderr) to the cron owner's email. To capture output to log files:

```bash
0 0 * * * cd /home/wagura-maurice/Documents/WASH\ 2026/R-Wash-Activity-Monitoring-Processing && python3 src/006-download_images.py >> /var/log/rwash-download.log 2>&1 && python3 src/007-convert_nonstandard_images.py >> /var/log/rwash-convert.log 2>&1 && python3 src/008-upload_sync_images.py >> /var/log/rwash-upload.log 2>&1
```

### Create Log Directory

```bash
sudo mkdir -p /var/log/rwash
sudo chown $USER:$USER /var/log/rwash
```

## Troubleshooting

### Cron Job Not Running

1. **Check cron service**:
   ```bash
   sudo systemctl status cron
   ```

2. **Verify cron syntax**:
   ```bash
   crontab -l
   ```

3. **Check system logs**:
   ```bash
   sudo tail -f /var/log/syslog | grep CRON
   ```

4. **Test command manually**:
   ```bash
   cd /home/wagura-maurice/Documents/WASH\ 2026/R-Wash-Activity-Monitoring-Processing
   python3 src/006-download_images.py
   ```

### Environment Issues

Cron runs with a minimal environment. Common issues:

1. **Python not found**: Use full path to Python executable
2. **Missing dependencies**: Ensure all packages are installed in the Python environment used by cron
3. **.env file not loaded**: Scripts should load .env from project root (they do this automatically)
4. **Path issues**: Use absolute paths or change directory before running scripts

### Email Notifications Not Received

1. **Check .env configuration**: Verify MAIL_* variables are set correctly
2. **Test email manually**: Run scripts manually to verify email sending
3. **Check SMTP server**: Ensure SMTP server is accessible from VPS
4. **Check spam folder**: Emails may be filtered as spam

## Security Considerations

1. **Protect .env file**: Ensure .env is not readable by other users:
   ```bash
   chmod 600 /home/wagura-maurice/Documents/WASH\ 2026/R-Wash-Activity-Monitoring-Processing/.env
   ```

2. **Limit cron access**: Only allow necessary users to edit crontab

3. **Review logs regularly**: Check for errors or suspicious activity

4. **Use virtual environment**: Isolate dependencies and prevent conflicts

## Maintenance

### Update Cron Job

To modify the cron job:

1. Edit crontab: `crontab -e`
2. Make changes
3. Save and exit

### Disable Cron Job Temporarily

Comment out the cron entry by adding `#` at the beginning:

```bash
# 0 0 * * * cd /home/wagura-maurice/Documents/WASH\ 2026/R-Wash-Activity-Monitoring-Processing && python3 src/006-download_images.py && python3 src/007-convert_nonstandard_images.py && python3 src/008-upload_sync_images.py
```

### Remove Cron Job

```bash
crontab -e
# Delete the unwanted entry
# Save and exit
```

Or remove all cron jobs:
```bash
crontab -r
```

## References

- [Cron Wikipedia](https://en.wikipedia.org/wiki/Cron)
- [Crontab Guru](https://crontab.guru/) - Cron schedule editor
- [Ubuntu Cron Documentation](https://help.ubuntu.com/community/CronHowto)