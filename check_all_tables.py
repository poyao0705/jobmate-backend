"""
Compare all PostgreSQL tables with FastAPI models to find schema mismatches.
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect

load_dotenv()

uri = os.getenv("DATABASE_PROD")
engine = create_engine(uri)

print("=" * 80)
print("PostgreSQL Schema Report - ALL TABLES")
print("=" * 80)

with engine.connect() as conn:
    # First, get all table names from the database
    result = conn.execute(text("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name
    """))
    
    all_tables = [row[0] for row in result]
    
    print(f"\nFound {len(all_tables)} tables in database\n")
    
    for table_name in all_tables:
        # Get row count
        row_count_result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        row_count = row_count_result.scalar()
        
        print(f"\n✓ Table: {table_name} ({row_count:,} rows)")
        print("-" * 80)
        
        # Get columns
        result = conn.execute(text(f"""
            SELECT column_name, data_type, character_maximum_length, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position
        """))
        
        for row in result:
            nullable = "NULL" if row.is_nullable == "YES" else "NOT NULL"
            max_len = f"({row.character_maximum_length})" if row.character_maximum_length else ""
            default = f" DEFAULT {row.column_default}" if row.column_default else ""
            print(f"  {row.column_name:30} {row.data_type}{max_len:15} {nullable:10}{default}")

print("\n" + "=" * 80)
