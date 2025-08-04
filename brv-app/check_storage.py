#!/usr/bin/env python
"""
Storage Check Script for BRV Applicant Management System

This script checks the storage usage of the Oracle database and updates
the storage usage information in the database configuration file.

It can be run periodically as a scheduled task or cron job:
- Windows: Use Task Scheduler
- Linux/macOS: Use cron

Example cron entry (run every 6 hours):
0 */6 * * * cd /path/to/BRV1 && python check_storage.py

Usage:
    python check_storage.py [--monitor]

Options:
    --monitor    Monitor storage usage and trigger auto-scaling if needed
"""

import os
import sys
import argparse
from datetime import datetime

# Import from db.py
from db import (
    init_db,
    update_storage_usage,
    monitor_database_usage,
    get_db_config
)

def print_storage_usage():
    """Print the current storage usage"""
    # Get database configuration
    config = get_db_config()
    
    if "storage_usage" in config:
        print("\nStorage Usage:")
        for db, usage in config["storage_usage"].items():
            used_gb = usage.get("used_gb", 0)
            total_gb = usage.get("total_gb", 0)
            used_percent = (used_gb / total_gb) * 100 if total_gb > 0 else 0
            
            print(f"  {db}: {used_gb:.2f} GB / {total_gb} GB ({used_percent:.1f}%)")
            
            if usage.get("last_checked"):
                print(f"    Last Checked: {usage['last_checked']}")
    else:
        print("❌ No storage usage information available")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Storage Check Script for BRV Applicant Management System')
    parser.add_argument('--monitor', action='store_true', help='Monitor storage usage and trigger auto-scaling if needed')
    args = parser.parse_args()
    
    print(f"🔄 Running storage check at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Initialize database connection
    init_db()
    
    # Update storage usage
    print("🔄 Updating storage usage information...")
    if update_storage_usage():
        print("✅ Storage usage information updated successfully")
        
        # Print storage usage
        print_storage_usage()
        
        # Monitor storage usage if requested
        if args.monitor:
            print("\n🔄 Monitoring storage usage...")
            threshold_reached, db_name = monitor_database_usage()
            
            if threshold_reached:
                print(f"⚠️ Database {db_name} has reached the storage threshold")
                print("Auto-scaling may be triggered on the next check")
            else:
                print("✅ All databases are below the storage threshold")
    else:
        print("❌ Failed to update storage usage information")

if __name__ == "__main__":
    main()