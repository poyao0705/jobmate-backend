"""
Database Mode Switcher
Switches between SQLite (dev) and PostgreSQL (production) databases.

Usage:
    python switch_db.py sqlite    # Switch to SQLite
    python switch_db.py postgres  # Switch to PostgreSQL
"""

import sys
import os
from pathlib import Path


def switch_database(mode: str):
    """Switch database mode in .env file."""
    if mode not in ["sqlite", "postgres"]:
        print("❌ Error: Mode must be either 'sqlite' or 'postgres'")
        print("Usage: python switch_db.py [sqlite|postgres]")
        sys.exit(1)
    
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ Error: .env file not found")
        sys.exit(1)
    
    # Read the current .env file
    with open(env_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    # Update the database mode lines
    updated = False
    for i, line in enumerate(lines):
        if line.startswith("DATABASE_MODE="):
            lines[i] = f"DATABASE_MODE={mode}\n"
            updated = True
            print(f"✅ Updated DATABASE_MODE={mode}")
        elif line.startswith("DATABASE_ENV="):
            lines[i] = f"DATABASE_ENV={mode}\n"
            print(f"✅ Updated DATABASE_ENV={mode}")
    
    if not updated:
        print("⚠️  Warning: DATABASE_MODE not found in .env file")
        sys.exit(1)
    
    # Write back to .env file
    with open(env_file, "w", encoding="utf-8") as f:
        f.writelines(lines)
    
    # Show which database will be used
    if mode == "sqlite":
        db_path = "instance/efficientai.db"
        print(f"\n🗄️  Database switched to SQLite")
        print(f"   Location: {db_path}")
        print(f"   {'✅ Exists' if Path(db_path).exists() else '⚠️  File not found - will be created on first run'}")
    else:
        print(f"\n🗄️  Database switched to PostgreSQL")
        print(f"   Host: RDS AWS (jobmate-db.chqwg28o0e4b.ap-southeast-2.rds.amazonaws.com)")
        print(f"   ⚠️  Make sure the PostgreSQL server is accessible")
    
    print("\n💡 Restart your application for changes to take effect")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python switch_db.py [sqlite|postgres]")
        print("\nExamples:")
        print("  python switch_db.py sqlite    # Switch to SQLite (local dev)")
        print("  python switch_db.py postgres  # Switch to PostgreSQL (AWS RDS)")
        sys.exit(1)
    
    mode = sys.argv[1].lower()
    switch_database(mode)
