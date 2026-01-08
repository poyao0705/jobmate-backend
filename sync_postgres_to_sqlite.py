"""
Sync data from PostgreSQL to SQLite database.
Imports all data from production PostgreSQL to local SQLite for development.
"""
import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect, MetaData, Table
from sqlalchemy.exc import OperationalError

load_dotenv()

# Database connections
POSTGRES_URI = os.getenv("DATABASE_PROD")
SQLITE_URI = os.getenv("DATABASE_DEV", "sqlite:///instance/efficientai.db")

# Tables to skip (sensitive user data)
SKIP_TABLES = {
    'alembic_version',  # Migration version, not data
    'sync_metadata'     # Our own tracking table
}

# Tables to always sync (can add more as needed)
PRIORITY_TABLES = [
    'user_profiles',
    'resumes', 
    'job_listings',
    'skills',
    'skill_gap_reports',
    'chats',
    'chat_messages',
    'processing_runs',
    'job_collections',
    'learning_items',
    'report_learning_items',
    'skill_aliases',
    'skill_gap_statuses',
    'preloaded_contexts',
    'tasks',
    'goals',
    'notes',
    'messages',
    'users',
    'user_settings',
    'memberships'
]


def create_sync_metadata_table(sqlite_engine):
    """Create metadata tracking table in SQLite."""
    with sqlite_engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS sync_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                last_sync_at TIMESTAMP,
                records_synced INTEGER,
                sync_mode TEXT
            )
        """))
        conn.commit()


def get_last_sync_time(sqlite_engine, table_name):
    """Get the last sync timestamp for a table."""
    try:
        with sqlite_engine.connect() as conn:
            result = conn.execute(text("""
                SELECT last_sync_at FROM sync_metadata 
                WHERE table_name = :table_name
                ORDER BY last_sync_at DESC LIMIT 1
            """), {"table_name": table_name})
            row = result.first()
            return row[0] if row else None
    except:
        return None


def update_sync_metadata(sqlite_engine, table_name, records_synced, sync_mode):
    """Update sync metadata after successful sync."""
    with sqlite_engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO sync_metadata (table_name, last_sync_at, records_synced, sync_mode)
            VALUES (:table_name, :sync_time, :records, :mode)
        """), {
            "table_name": table_name,
            "sync_time": datetime.now(),
            "records": records_synced,
            "mode": sync_mode
        })
        conn.commit()


def convert_value_for_sqlite(value):
    """Convert PostgreSQL values to SQLite-compatible format."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def get_table_columns(engine, table_name):
    """Get column names for a table."""
    inspector = inspect(engine)
    columns = inspector.get_columns(table_name)
    return [col['name'] for col in columns]


def create_table_in_sqlite(postgres_engine, sqlite_engine, table_name):
    """Create table in SQLite matching PostgreSQL schema."""
    from sqlalchemy import Column, Integer, String, Text, Boolean, Float, Date, DateTime, JSON, BigInteger
    from sqlalchemy.schema import CreateTable
    
    # Drop existing table if it exists
    with sqlite_engine.connect() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
        conn.commit()
    
    # Get column info from PostgreSQL
    inspector = inspect(postgres_engine)
    columns_info = inspector.get_columns(table_name)
    pk_constraint = inspector.get_pk_constraint(table_name)
    
    # Map PostgreSQL types to SQLite types
    type_mapping = {
        'character varying': String,
        'varchar': String,
        'text': Text,
        'integer': Integer,
        'bigint': BigInteger,
        'boolean': Boolean,
        'double precision': Float,
        'real': Float,
        'date': Date,
        'timestamp without time zone': DateTime,
        'timestamp with time zone': DateTime,
        'json': Text,  # Store as text in SQLite
        'jsonb': Text,
    }
    
    # Build CREATE TABLE statement
    column_defs = []
    pk_columns = pk_constraint.get('constrained_columns', [])
    
    for col in columns_info:
        col_name = col['name']
        col_type = str(col['type']).lower()
        
        # Map the type
        sqlite_type = 'TEXT'
        for pg_type, sql_type in type_mapping.items():
            if pg_type in col_type:
                sqlite_type = sql_type.__name__.upper()
                break
        
        # Build column definition
        col_def = f"{col_name} {sqlite_type}"
        
        if col_name in pk_columns:
            col_def += " PRIMARY KEY"
            if sqlite_type == "INTEGER":
                col_def += " AUTOINCREMENT"
        
        if not col.get('nullable', True) and col_name not in pk_columns:
            col_def += " NOT NULL"
        
        column_defs.append(col_def)
    
    # Create table
    create_sql = f"CREATE TABLE {table_name} ({', '.join(column_defs)})"
    
    with sqlite_engine.connect() as conn:
        conn.execute(text(create_sql))
        conn.commit()
    
    print(f"  ✓ Created table structure in SQLite")


def sync_table(postgres_engine, sqlite_engine, table_name, mode='full'):
    """Sync a single table from PostgreSQL to SQLite."""
    print(f"\n{'='*60}")
    print(f"Syncing: {table_name}")
    print(f"{'='*60}")
    
    try:
        # Get columns
        columns = get_table_columns(postgres_engine, table_name)
        column_list = ", ".join(columns)
        
        # Fetch data from PostgreSQL
        with postgres_engine.connect() as pg_conn:
            result = pg_conn.execute(text(f"SELECT {column_list} FROM {table_name}"))
            rows = result.fetchall()
            total_rows = len(rows)
            
            if total_rows == 0:
                print(f"  ℹ No data to sync (table is empty)")
                return 0
            
            print(f"  Found {total_rows:,} rows in PostgreSQL")
        
        # Ensure table exists in SQLite
        inspector = inspect(sqlite_engine)
        if table_name not in inspector.get_table_names():
            print(f"  Creating table in SQLite...")
            create_table_in_sqlite(postgres_engine, sqlite_engine, table_name)
        else:
            # Drop and recreate to ensure schema matches
            print(f"  Recreating table with current schema...")
            create_table_in_sqlite(postgres_engine, sqlite_engine, table_name)
        
        # Insert data into SQLite
        with sqlite_engine.connect() as sqlite_conn:
            # No need to clear data since we recreated the table
            
            # Prepare parameterized insert
            placeholders = ", ".join([f":{col}" for col in columns])
            insert_sql = f"INSERT OR REPLACE INTO {table_name} ({column_list}) VALUES ({placeholders})"
            
            # Batch insert
            batch_size = 500
            synced_count = 0
            
            for i in range(0, total_rows, batch_size):
                batch = rows[i:i + batch_size]
                batch_data = []
                
                for row in batch:
                    row_dict = {}
                    for col_name, value in zip(columns, row):
                        row_dict[col_name] = convert_value_for_sqlite(value)
                    batch_data.append(row_dict)
                
                sqlite_conn.execute(text(insert_sql), batch_data)
                synced_count += len(batch)
                
                if synced_count % 1000 == 0 or synced_count == total_rows:
                    print(f"  Synced {synced_count:,}/{total_rows:,} rows...", end='\r')
            
            sqlite_conn.commit()
            print(f"\n  ✓ Successfully synced {synced_count:,} rows")
        
        # Update metadata
        update_sync_metadata(sqlite_engine, table_name, synced_count, mode)
        return synced_count
        
    except Exception as e:
        print(f"  ✗ Error syncing {table_name}: {str(e)}")
        return 0


def get_all_tables(postgres_engine):
    """Get all table names from PostgreSQL."""
    inspector = inspect(postgres_engine)
    return inspector.get_table_names()


def main():
    """Main sync process."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Sync PostgreSQL to SQLite')
    parser.add_argument('--tables', nargs='+', help='Specific tables to sync')
    parser.add_argument('--jobs-only', action='store_true', help='Sync only job_listings')
    parser.add_argument('--status', action='store_true', help='Show sync status')
    parser.add_argument('--full', action='store_true', help='Force full sync (clear existing data)')
    
    args = parser.parse_args()
    
    print("="*60)
    print("PostgreSQL → SQLite Sync Tool")
    print("="*60)
    print(f"PostgreSQL: {POSTGRES_URI.split('@')[1] if '@' in POSTGRES_URI else 'configured'}")
    print(f"SQLite: {SQLITE_URI}")
    print()
    
    # Connect to databases
    try:
        pg_engine = create_engine(POSTGRES_URI)
        sqlite_engine = create_engine(SQLITE_URI)
        
        # Test connections
        with pg_engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✓ Connected to PostgreSQL")
        
        with sqlite_engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✓ Connected to SQLite")
        
        print()
        
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        sys.exit(1)
    
    # Create metadata table
    create_sync_metadata_table(sqlite_engine)
    
    # Show status if requested
    if args.status:
        print("Sync Status:")
        print("-" * 60)
        with sqlite_engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name, last_sync_at, records_synced, sync_mode
                FROM sync_metadata
                ORDER BY last_sync_at DESC
            """))
            for row in result:
                print(f"{row[0]:30} {row[1]} ({row[2]:,} rows) [{row[3]}]")
        return
    
    # Determine which tables to sync
    if args.jobs_only:
        tables_to_sync = ['job_listings']
    elif args.tables:
        tables_to_sync = args.tables
    else:
        # Get all tables, prioritize the important ones
        all_tables = get_all_tables(pg_engine)
        tables_to_sync = [t for t in PRIORITY_TABLES if t in all_tables]
        
        # Add any remaining tables not in skip list
        for table in all_tables:
            if table not in tables_to_sync and table not in SKIP_TABLES:
                tables_to_sync.append(table)
    
    # Sync mode
    sync_mode = 'full' if args.full else 'full'  # Default to full for now
    
    # Sync each table
    total_synced = 0
    success_count = 0
    start_time = datetime.now()
    
    for table_name in tables_to_sync:
        if table_name in SKIP_TABLES:
            print(f"\nSkipping {table_name} (in skip list)")
            continue
        
        synced = sync_table(pg_engine, sqlite_engine, table_name, mode=sync_mode)
        if synced > 0:
            success_count += 1
            total_synced += synced
    
    # Summary
    duration = (datetime.now() - start_time).total_seconds()
    print("\n" + "="*60)
    print("Sync Complete!")
    print("="*60)
    print(f"Tables synced: {success_count}/{len(tables_to_sync)}")
    print(f"Total records: {total_synced:,}")
    print(f"Duration: {duration:.1f} seconds")
    print("="*60)


if __name__ == "__main__":
    main()
