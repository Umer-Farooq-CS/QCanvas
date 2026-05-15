import sys
import os
import argparse
from sqlalchemy import text, inspect as sa_inspect, create_engine

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config.database import SessionLocal, engine


def print_table(title, headers, rows):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")
    if not rows:
        print("  No records found.")
        return

    # Convert all values to string, truncate long values
    str_rows = []
    for row in rows:
        str_row = []
        for val in row:
            s = str(val) if val is not None else "NULL"
            if len(s) > 50:
                s = s[:47] + "..."
            str_row.append(s)
        str_rows.append(str_row)
    
    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in str_rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(val))
    
    # Create format string
    fmt = " | ".join([f"{{:<{w}}}" for w in widths])
    
    # Print header
    separator = "-" * (sum(widths) + 3 * (len(widths) - 1))
    print(separator)
    print(fmt.format(*headers))
    print(separator)
    
    # Print rows
    for row in str_rows:
        print(fmt.format(*row))
    print(separator)
    print(f"  Total: {len(rows)} records shown\n")


def get_all_tables():
    """Dynamically discover all tables in the database."""
    inspector = sa_inspect(engine)
    return sorted(inspector.get_table_names())


def get_table_columns(table_name):
    """Get column names for a table."""
    inspector = sa_inspect(engine)
    columns = inspector.get_columns(table_name)
    return [col["name"] for col in columns]


def show_table_data(table_name, limit=15):
    """Show data from a specific table using raw SQL."""
    db = SessionLocal()
    try:
        columns = get_table_columns(table_name)
        
        # Count total
        count_result = db.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
        total = count_result.scalar()
        
        # Fetch rows
        result = db.execute(text(f'SELECT * FROM "{table_name}" ORDER BY 1 DESC LIMIT :lim'), {"lim": limit})
        rows = [list(row) for row in result]
        
        title = f"{table_name.upper()} ({total} total, showing {min(total, limit)})"
        print_table(title, columns, rows)
        
    except Exception as e:
        print(f"\n⚠ Error reading table '{table_name}': {e}")
    finally:
        db.close()


def show_summary():
    """Show a summary of all tables with record counts."""
    db = SessionLocal()
    tables = get_all_tables()
    
    print(f"\nUsage: python show_db_data.py [table_name|all] [--limit N]")
    print(f"Available tables: {', '.join(tables)}")
    print("Use 'all' to show data from every table.\n")
    print("--- Summary ---")
    
    for table in tables:
        try:
            count_result = db.execute(text(f'SELECT COUNT(*) FROM "{table}"'))
            count = count_result.scalar()
            print(f"  {table:<25} {count:>6} records")
        except Exception as e:
            print(f"  {table:<25}    ⚠ error: {e}")
    
    db.close()


def show_file_content(file_id):
    """Show content of a specific file by ID."""
    db = SessionLocal()
    try:
        result = db.execute(text('SELECT id, filename, content FROM files WHERE id = :fid'), {"fid": file_id})
        row = result.fetchone()
        if row:
            print(f"\n=== Content of File ID {row[0]} ({row[1]}) ===")
            print("-" * 50)
            print(row[2])
            print("-" * 50)
        else:
            print(f"File with ID {file_id} not found.")
    except Exception as e:
        print(f"Error fetching file: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect ALL database tables dynamically")
    parser.add_argument("table", nargs="?", help="Table name, 'all' for everything, or 'view_content'")
    parser.add_argument("extra_arg", nargs="?", help="File ID if using view_content")
    parser.add_argument("--limit", type=int, default=15, help="Number of records to show per table")
    
    args = parser.parse_args()
    
    if args.table == "view_content":
        if not args.extra_arg:
            print("Usage: python show_db_data.py view_content <file_id>")
        else:
            show_file_content(args.extra_arg)
    elif args.table == "all":
        tables = get_all_tables()
        for table in tables:
            show_table_data(table, args.limit)
    elif args.table:
        all_tables = get_all_tables()
        if args.table not in all_tables:
            print(f"Error: Table '{args.table}' not found.")
            print(f"Available tables: {', '.join(all_tables)}")
        else:
            show_table_data(args.table, args.limit)
    else:
        show_summary()
