"""
Export all SQLite database data to a readable text file.
"""
import os
import json
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect

load_dotenv()

SQLITE_URI = os.getenv("DATABASE_DEV", "sqlite:///instance/efficientai.db")
OUTPUT_FILE = f"exports/sqlite_data_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

def format_value(value):
    """Format value for display."""
    if value is None:
        return "NULL"
    if isinstance(value, str) and len(value) > 100:
        return value[:100] + "..."
    if isinstance(value, (dict, list)):
        return json.dumps(value)[:100] + "..."
    return str(value)


def export_sqlite_to_txt():
    """Export SQLite data to text file."""
    print("="*60)
    print("SQLite Data Export to Text File")
    print("="*60)
    print(f"Database: {SQLITE_URI}")
    print(f"Output: {OUTPUT_FILE}")
    print()
    
    # Ensure exports directory exists
    os.makedirs("exports", exist_ok=True)
    
    # Connect to SQLite
    engine = create_engine(SQLITE_URI)
    inspector = inspect(engine)
    
    # Get all tables
    tables = inspector.get_table_names()
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        # Write header
        f.write("="*80 + "\n")
        f.write("SQLite Database Export\n")
        f.write(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Database: {SQLITE_URI}\n")
        f.write(f"Total Tables: {len(tables)}\n")
        f.write("="*80 + "\n\n")
        
        total_records = 0
        
        with engine.connect() as conn:
            for table_name in sorted(tables):
                # Get row count
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                row_count = result.scalar()
                total_records += row_count
                
                f.write("\n" + "="*80 + "\n")
                f.write(f"TABLE: {table_name} ({row_count:,} rows)\n")
                f.write("="*80 + "\n\n")
                
                print(f"Exporting {table_name} ({row_count:,} rows)...")
                
                if row_count == 0:
                    f.write("  (empty table)\n")
                    continue
                
                # Get columns
                columns = inspector.get_columns(table_name)
                column_names = [col['name'] for col in columns]
                
                # Write column headers
                f.write("Columns: " + ", ".join(column_names) + "\n")
                f.write("-"*80 + "\n\n")
                
                # Get all data (limit display for large tables)
                limit = 100 if row_count > 100 else row_count
                result = conn.execute(text(f"SELECT * FROM {table_name} LIMIT {limit}"))
                
                # Write rows
                for idx, row in enumerate(result, 1):
                    f.write(f"Row {idx}:\n")
                    for col_name, value in zip(column_names, row):
                        formatted_value = format_value(value)
                        f.write(f"  {col_name:30} = {formatted_value}\n")
                    f.write("\n")
                
                if row_count > limit:
                    f.write(f"... {row_count - limit:,} more rows not shown ...\n\n")
        
        # Write summary
        f.write("\n" + "="*80 + "\n")
        f.write("EXPORT SUMMARY\n")
        f.write("="*80 + "\n")
        f.write(f"Total Tables: {len(tables)}\n")
        f.write(f"Total Records: {total_records:,}\n")
        f.write(f"Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*80 + "\n")
    
    print()
    print("="*60)
    print("Export Complete!")
    print("="*60)
    print(f"File: {OUTPUT_FILE}")
    print(f"Tables: {len(tables)}")
    print(f"Records: {total_records:,}")
    print("="*60)


if __name__ == "__main__":
    export_sqlite_to_txt()
