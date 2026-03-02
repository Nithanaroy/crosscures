#!/usr/bin/env python3
"""Search for text patterns across all tables in a DuckDB database."""

import duckdb
import argparse
from pathlib import Path
from typing import Dict
import pandas as pd


# Default configuration
DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "patient_data.duckdb"


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Search for text patterns across all tables in DuckDB.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "search_term",
        type=str,
        help="Text pattern to search for (case-insensitive)"
    )
    parser.add_argument(
        "--db-path", "-d",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to DuckDB database file"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=10,
        help="Maximum results to return per table/column"
    )
    parser.add_argument(
        "--table", "-t",
        type=str,
        help="Limit search to a specific table"
    )
    parser.add_argument(
        "--show-all-columns",
        action="store_true",
        help="Show all columns in results (default: only relevant columns)"
    )
    parser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Perform case-sensitive search"
    )
    return parser.parse_args()


def get_searchable_columns(conn, table_filter=None):
    """Get all text columns from the database."""
    query = """
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'main'
        AND data_type IN ('VARCHAR', 'TEXT')
    """
    
    if table_filter:
        query += f" AND table_name = '{table_filter}'"
    
    query += " ORDER BY table_name, column_name"
    
    return conn.execute(query).fetchall()


def search_all_tables(
    conn, 
    search_term: str, 
    limit_per_table: int = 10,
    table_filter: str = None,
    show_all_columns: bool = False,
    case_sensitive: bool = False
) -> Dict[str, pd.DataFrame]:
    """Search for a text pattern across all tables in the database.
    
    Args:
        conn: DuckDB connection
        search_term: Text pattern to search for
        limit_per_table: Maximum results per table/column combination
        table_filter: Optional table name to restrict search
        show_all_columns: If True, show all columns; if False, show only matched column
        case_sensitive: If True, use LIKE; if False, use ILIKE
        
    Returns:
        Dictionary mapping "table.column" to DataFrame of results
    """
    print(f"[INFO] Searching for: '{search_term}'")
    print(f"[INFO] Case-sensitive: {case_sensitive}")
    
    # Get all searchable columns
    tables_info = get_searchable_columns(conn, table_filter)
    print(f"[INFO] Searching {len(tables_info)} text columns...")
    print()
    
    results = {}
    total_matches = 0
    total_columns = len(tables_info)
    
    like_operator = "LIKE" if case_sensitive else "ILIKE"
    
    for idx, (table_name, column_name, data_type) in enumerate(tables_info, 1):
        # Show progress
        print(f"\r[PROGRESS] Searching {idx}/{total_columns}: {table_name}.{column_name}...", end='', flush=True)
        
        # Build the query
        if show_all_columns:
            select_clause = "*"
        else:
            select_clause = f"{column_name}"
        
        query = f"""
            SELECT '{table_name}' as source_table, 
                   '{column_name}' as source_column,
                   {select_clause}
            FROM {table_name}
            WHERE {column_name} {like_operator} '%{search_term}%'
            LIMIT {limit_per_table}
        """
        
        try:
            df = conn.execute(query).df()
            if not df.empty:
                key = f"{table_name}.{column_name}"
                results[key] = df
                total_matches += len(df)
                
                # Clear progress line and print results
                print(f"\r{' ' * 100}\r", end='')  # Clear the progress line
                print(f"[MATCH] {key} ({len(df)} results)")
                print("-" * 80)
                print(df.to_string(index=False))
                print()
                
        except Exception as e:
            # Clear progress line and print warning
            print(f"\r{' ' * 100}\r", end='')  # Clear the progress line
            print(f"[WARN] Skipped {table_name}.{column_name}: {e}")
    
    # Clear the final progress line
    print(f"\r{' ' * 100}\r", end='')
    
    return results, total_matches


def main():
    """Main entry point."""
    args = parse_args()
    
    # Validate database path
    if not args.db_path.exists():
        print(f"[ERROR] Database not found: {args.db_path}")
        return 1
    
    # Connect to database
    print(f"[INFO] Connecting to: {args.db_path}")
    conn = duckdb.connect(str(args.db_path), read_only=True)
    
    try:
        # Perform search
        results, total_matches = search_all_tables(
            conn=conn,
            search_term=args.search_term,
            limit_per_table=args.limit,
            table_filter=args.table,
            show_all_columns=args.show_all_columns,
            case_sensitive=args.case_sensitive
        )
        
        # Summary
        print("=" * 80)
        print(f"[SUMMARY] Found {total_matches} total matches across {len(results)} table/column combinations")
        
        if results:
            print()
            print("Matches by location:")
            for key, df in results.items():
                print(f"  - {key}: {len(df)} results")
        else:
            print(f"[INFO] No matches found for '{args.search_term}'")
        
    finally:
        conn.close()
    
    return 0


if __name__ == "__main__":
    exit(main())
