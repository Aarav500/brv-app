#!/usr/bin/env python
"""
Admin CLI for BRV Applicant Management System

This script provides a command-line interface for administrative tasks:
- User management (add, remove, update roles)
- Database status check
- Storage usage monitoring

Usage:
    python admin_cli.py [command] [options]

Commands:
    user add <email> <role>     - Add a new user
    user remove <email>         - Remove a user
    user list                   - List all users
    user update-role <email> <new_role> - Update a user's role
    
    db status                   - Check database status
    db storage                  - Check storage usage
    db update-storage           - Update storage usage information
    
    help                        - Show this help message
"""

import os
import sys
import argparse
import getpass
from datetime import datetime

# Import from db.py
from db import (
    init_db,
    get_user_by_email,
    create_user,
    delete_user,
    update_user_role,
    get_all_users,
    update_storage_usage,
    get_db_config,
    test_connection,
    monitor_database_usage
)

def setup_argparse():
    """Set up argument parser"""
    parser = argparse.ArgumentParser(description='Admin CLI for BRV Applicant Management System')
    
    # Create subparsers for different command groups
    subparsers = parser.add_subparsers(dest='command_group', help='Command group')
    
    # User commands
    user_parser = subparsers.add_parser('user', help='User management commands')
    user_subparsers = user_parser.add_subparsers(dest='user_command', help='User command')
    
    # user add
    add_parser = user_subparsers.add_parser('add', help='Add a new user')
    add_parser.add_argument('email', help='User email')
    add_parser.add_argument('role', help='User role (receptionist, interviewer, ceo)')
    
    # user remove
    remove_parser = user_subparsers.add_parser('remove', help='Remove a user')
    remove_parser.add_argument('email', help='User email')
    
    # user list
    user_subparsers.add_parser('list', help='List all users')
    
    # user update-role
    update_role_parser = user_subparsers.add_parser('update-role', help='Update a user\'s role')
    update_role_parser.add_argument('email', help='User email')
    update_role_parser.add_argument('new_role', help='New role (receptionist, interviewer, ceo)')
    
    # Database commands
    db_parser = subparsers.add_parser('db', help='Database management commands')
    db_subparsers = db_parser.add_subparsers(dest='db_command', help='Database command')
    
    # db status
    db_subparsers.add_parser('status', help='Check database status')
    
    # db storage
    db_subparsers.add_parser('storage', help='Check storage usage')
    
    # db update-storage
    db_subparsers.add_parser('update-storage', help='Update storage usage information')
    
    # Help command
    subparsers.add_parser('help', help='Show help message')
    
    return parser

def handle_user_add(args):
    """Handle user add command"""
    email = args.email
    role = args.role.lower()
    
    # Validate role
    valid_roles = ['receptionist', 'interviewer', 'ceo']
    if role not in valid_roles:
        print(f"❌ Invalid role: {role}")
        print(f"Valid roles are: {', '.join(valid_roles)}")
        return
    
    # Check if user already exists
    existing_user = get_user_by_email(email)
    if existing_user:
        print(f"❌ User with email {email} already exists")
        return
    
    # Get password
    password = getpass.getpass("Enter password for new user: ")
    password_confirm = getpass.getpass("Confirm password: ")
    
    if password != password_confirm:
        print("❌ Passwords do not match")
        return
    
    # Create user
    success, user_id, message = create_user(email, email, password, role)
    
    if success:
        print(f"✅ User added successfully: {email} ({role})")
    else:
        print(f"❌ Failed to add user: {message}")

def handle_user_remove(args):
    """Handle user remove command"""
    email = args.email
    
    # Check if user exists
    user = get_user_by_email(email)
    if not user:
        print(f"❌ User with email {email} not found")
        return
    
    # Confirm deletion
    confirm = input(f"Are you sure you want to remove user {email}? (y/n): ")
    if confirm.lower() != 'y':
        print("Operation cancelled")
        return
    
    # Delete user
    success, message = delete_user(user['user_id'])
    
    if success:
        print(f"✅ User removed successfully: {email}")
    else:
        print(f"❌ Failed to remove user: {message}")

def handle_user_list(args):
    """Handle user list command"""
    users = get_all_users()
    
    if not users:
        print("No users found")
        return
    
    print(f"\nFound {len(users)} users:\n")
    print(f"{'Email':<30} {'Role':<15} {'Last Password Change':<25}")
    print("-" * 70)
    
    for user in users:
        email = user.get('email', 'N/A')
        role = user.get('role', 'N/A')
        last_password_change = user.get('last_password_change', 'Never')
        
        print(f"{email:<30} {role:<15} {last_password_change:<25}")

def handle_user_update_role(args):
    """Handle user update-role command"""
    email = args.email
    new_role = args.new_role.lower()
    
    # Validate role
    valid_roles = ['receptionist', 'interviewer', 'ceo']
    if new_role not in valid_roles:
        print(f"❌ Invalid role: {new_role}")
        print(f"Valid roles are: {', '.join(valid_roles)}")
        return
    
    # Check if user exists
    user = get_user_by_email(email)
    if not user:
        print(f"❌ User with email {email} not found")
        return
    
    # Update role
    success, message = update_user_role(user['user_id'], new_role)
    
    if success:
        print(f"✅ User role updated successfully: {email} → {new_role}")
    else:
        print(f"❌ Failed to update user role: {message}")

def handle_db_status(args):
    """Handle db status command"""
    print("\n🔄 Checking database status...")
    
    # Initialize database connection
    init_db()
    
    # Test connection
    if test_connection():
        print("✅ Database connection successful")
        
        # Get database configuration
        config = get_db_config()
        
        print(f"\nCurrent Database Configuration:")
        print(f"  Current Write DB: {config['current_write_db']}")
        print(f"  Available Databases: {', '.join(config['databases'])}")
    else:
        print("❌ Database connection failed")

def handle_db_storage(args):
    """Handle db storage command"""
    print("\n🔄 Checking storage usage...")
    
    # Initialize database connection
    init_db()
    
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
        print("Run 'admin_cli.py db update-storage' to update storage usage information")

def handle_db_update_storage(args):
    """Handle db update-storage command"""
    print("\n🔄 Updating storage usage information...")
    
    # Initialize database connection
    init_db()
    
    # Update storage usage
    if update_storage_usage():
        print("✅ Storage usage information updated successfully")
        
        # Check if auto-scaling is needed
        threshold_reached, db_name = monitor_database_usage()
        
        if threshold_reached:
            print(f"⚠️ Database {db_name} has reached the storage threshold")
            print("Auto-scaling may be triggered on the next check")
    else:
        print("❌ Failed to update storage usage information")

def main():
    """Main function"""
    parser = setup_argparse()
    args = parser.parse_args()
    
    # Initialize database connection
    init_db()
    
    # Handle commands
    if args.command_group == 'user':
        if args.user_command == 'add':
            handle_user_add(args)
        elif args.user_command == 'remove':
            handle_user_remove(args)
        elif args.user_command == 'list':
            handle_user_list(args)
        elif args.user_command == 'update-role':
            handle_user_update_role(args)
        else:
            parser.print_help()
    elif args.command_group == 'db':
        if args.db_command == 'status':
            handle_db_status(args)
        elif args.db_command == 'storage':
            handle_db_storage(args)
        elif args.db_command == 'update-storage':
            handle_db_update_storage(args)
        else:
            parser.print_help()
    elif args.command_group == 'help' or args.command_group is None:
        parser.print_help()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()