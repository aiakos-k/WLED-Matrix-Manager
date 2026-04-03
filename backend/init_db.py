#!/usr/bin/env python
"""
Database Initialization Script
Schnell & einfach: Löscht alte DB und erstellt alles neu aus Models
Ideal für Entwicklung und Testing
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask_module.app import app
from flask_module.db import db
from flask_module.models import User, Device, Scene, Frame, scene_device_association, UserRole

def init_database(delete_existing=False):
    """Initialize database with default data
    
    Args:
        delete_existing: If True, delete old DB before creating (ONLY for development)
                        If False, just add default data if missing (production/docker safe)
    """
    
    with app.app_context():
        print("\n" + "=" * 70)
        if delete_existing:
            print("🔧  DATABASE FULL RESET (Development Mode - WARNING!)")
        else:
            print("🔧  DATABASE INITIALIZATION (Safe Mode - Keep Existing Data)")
        print("=" * 70)
        
        # Step 1: Optionally delete old DB
        if delete_existing:
            db_path = Path(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
            if db_path.exists():
                print(f"\n1️⃣  Deleting old database: {db_path}")
                try:
                    db_path.unlink()
                    print("   ✅ Old database deleted")
                except Exception as e:
                    print(f"   ⚠️  Could not delete: {e}")
            else:
                print("\n1️⃣  No old database found (first run?)")
        else:
            print("\n1️⃣  Preserving existing database and data")
        
        # Step 2: Create all tables and add missing columns
        print("\n2️⃣  Creating tables from models and checking for missing columns...")
        try:
            # Create tables if they don't exist
            db.create_all()
            
            # Add missing columns to existing tables (for schema updates)
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            
            # Check User table for missing TOTP columns
            if 'user' in inspector.get_table_names():
                existing_columns = [col['name'] for col in inspector.get_columns('user')]
                
                if 'totp_secret' not in existing_columns:
                    print("   🔄 Adding missing column: user.totp_secret")
                    with db.engine.connect() as conn:
                        conn.execute(text('ALTER TABLE user ADD COLUMN totp_secret VARCHAR(32)'))
                        conn.commit()
                
                if 'totp_enabled' not in existing_columns:
                    print("   🔄 Adding missing column: user.totp_enabled")
                    with db.engine.connect() as conn:
                        conn.execute(text('ALTER TABLE user ADD COLUMN totp_enabled BOOLEAN DEFAULT 0 NOT NULL'))
                        conn.commit()
            
            print("   ✅ All tables and columns verified!")
        except Exception as e:
            print(f"   ❌ Error creating tables: {e}")
            return False
        
        # Step 3: Create default admin user
        print("\n3️⃣  Setting up default admin user...")
        try:
            admin = User.query.filter_by(username="admin").first()
            if not admin:
                admin = User(
                    username="admin",
                    email="admin@ledmatrix.local",
                    role=UserRole.ADMIN,
                    is_active=True
                )
                admin.set_password("admin123")  # Use password hashing
                db.session.add(admin)
                db.session.commit()
                print(f"   ✅ Admin user created (ID: {admin.id})")
                print(f"      Username: admin")
                print(f"      Password: admin123")
                print(f"      Email: admin@ledmatrix.local")
                print(f"      Role: ADMIN")
                print(f"      ⚠️  Change password after first login!")
            else:
                print(f"   ℹ️  Admin user already exists (ID: {admin.id})")
        except Exception as e:
            print(f"   ❌ Error creating admin: {e}")
            return False
        
        # Step 4: Verify tables
        print("\n4️⃣  Verifying database contents...")
        try:
            users = User.query.count()
            scenes = Scene.query.count()
            devices = Device.query.count()
            frames = Frame.query.count()
            
            print(f"   📊 Users: {users}")
            print(f"   📊 Scenes: {scenes}")
            print(f"   📊 Devices: {devices}")
            print(f"   📊 Frames: {frames}")
        except Exception as e:
            print(f"   ⚠️  Error verifying: {e}")
        
        print("\n" + "=" * 70)
        print("✅  DATABASE READY!")
        print("=" * 70)
        print("\n📝 Next steps:")
        print("   1. Start Flask server: flask run")
        print("   2. Access API at: http://localhost:5000/swagger-ui")
        print("   3. Create scenes & devices via UI/API")
        print("=" * 70 + "\n")
        
        return True

if __name__ == "__main__":
    # Default: Safe mode (don't delete data)
    # Use --reset flag to delete old database (dev only)
    delete_existing = "--reset" in sys.argv
    
    if delete_existing:
        print("\n⚠️  WARNING: --reset flag detected!")
        print("    This will DELETE the existing database!")
        response = input("    Type 'DELETE' to confirm: ").strip()
        if response != "DELETE":
            print("    Cancelled.")
            sys.exit(0)
    
    success = init_database(delete_existing=delete_existing)
    sys.exit(0 if success else 1)
