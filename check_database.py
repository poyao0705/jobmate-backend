"""
Quick script to check which database is being used.
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

# Get database URI
mode = os.getenv("DATABASE_MODE", "sqlite")
if mode == "postgres":
    uri = os.getenv("DATABASE_PROD")
else:
    uri = os.getenv("DATABASE_DEV", "sqlite:///instance/efficientai.db")

print("=" * 60)
print("Database Configuration Check")
print("=" * 60)
print(f"DATABASE_MODE: {mode}")
print(f"Database URI: {uri}")
print()

# Try to connect
try:
    engine = create_engine(uri)
    with engine.connect() as conn:
        # Get database type and version
        if "postgresql" in uri:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            print("✓ Connected to PostgreSQL")
            print(f"Version: {version.split(',')[0]}")
            
            # Get current database name
            result = conn.execute(text("SELECT current_database()"))
            db_name = result.scalar()
            print(f"Database: {db_name}")
            
            # Get table count
            result = conn.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            table_count = result.scalar()
            print(f"Tables: {table_count}")
            
        else:
            result = conn.execute(text("SELECT sqlite_version()"))
            version = result.scalar()
            print("✓ Connected to SQLite")
            print(f"Version: {version}")
            
            # Get table count
            result = conn.execute(text("""
                SELECT COUNT(*) 
                FROM sqlite_master 
                WHERE type='table'
            """))
            table_count = result.scalar()
            print(f"Tables: {table_count}")
    
    print()
    print("=" * 60)
    print("Connection successful!")
    print("=" * 60)
    
except Exception as e:
    print()
    print("=" * 60)
    print("✗ Connection failed!")
    print("=" * 60)
    print(f"Error: {e}")
