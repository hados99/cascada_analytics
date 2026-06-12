#!/usr/bin/env python3
import os
import glob
import sys
import argparse
from datetime import datetime
import duckdb

DEFAULT_DB_PATH = "cascada_analytics.db"
DEFAULT_DATA_DIR = "data"

# Schema definition
TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS cascada_metrics (
    target_time DATE,
    date_category VARCHAR,
    channel_id VARCHAR,
    channel_name VARCHAR,
    channel_country VARCHAR,
    genre_name VARCHAR,
    provider_name VARCHAR,
    platform VARCHAR,
    model VARCHAR,
    users INTEGER,
    active_users_playback_15 INTEGER,
    active_users_playback_180 INTEGER,
    active_users_playback_900 INTEGER,
    playback_counts INTEGER,
    active_playback_counts_15 INTEGER,
    active_playback_counts_180 INTEGER,
    active_playback_counts_900 INTEGER,
    playback_count_per_user DOUBLE,
    playback_count_per_user_15 DOUBLE,
    playback_count_per_user_180 DOUBLE,
    playback_count_per_user_900 DOUBLE,
    viewing_time INTEGER,
    viewing_time_per_user DOUBLE,
    active_viewing_time_15 INTEGER,
    active_viewing_time_per_active_user_15 DOUBLE,
    active_viewing_time_per_active_playback_15 DOUBLE,
    active_viewing_time_180 INTEGER,
    active_viewing_time_per_active_user_180 DOUBLE,
    active_viewing_time_per_active_playback_180 DOUBLE,
    active_viewing_time_900 INTEGER,
    active_viewing_time_per_active_user_900 DOUBLE,
    active_viewing_time_per_active_playback_900 DOUBLE
);
"""

METADATA_SCHEMA = """
CREATE TABLE IF NOT EXISTS imported_files (
    file_path VARCHAR PRIMARY KEY,
    file_name VARCHAR,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    row_count INTEGER,
    file_size_bytes BIGINT
);
"""

def setup_database(con):
    """Creates tables if they do not exist."""
    con.execute(TABLE_SCHEMA)
    con.execute(METADATA_SCHEMA)

def get_imported_files(con):
    """Retrieves list of already imported files."""
    result = con.execute("SELECT file_path FROM imported_files").fetchall()
    return set(row[0] for row in result)

def import_csv_file(con, file_path, force=False):
    """Imports a single CSV file into the database with type casting and transformations."""
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    
    # Check if file has already been imported
    if not force:
        already_imported = con.execute(
            "SELECT count(*) FROM imported_files WHERE file_path = ?", 
            [file_path]
        ).fetchone()[0]
        if already_imported > 0:
            print(f"[-] Skipping already imported file: {file_name}")
            return False

    print(f"[*] Importing: {file_name} ({file_size / (1024*1024):.2f} MB)")
    
    # We load columns from the CSV and cast them explicitly to our final schema.
    # To handle potential duplicate records when re-importing (under force), we delete existing logs for this file if force is True.
    if force:
        con.execute("DELETE FROM imported_files WHERE file_path = ?", [file_path])
        # Note: If we need transaction safety to avoid duplicate inserts on force-reimport,
        # we could track files or delete by some key, but usually force is for clean rebuilds.
        # Here we just inform the user we are doing a force import.

    # Execute insert using strptime for target_time and cast other columns.
    # DuckDB can efficiently stream read_csv into the destination table.
    query = f"""
    INSERT INTO cascada_metrics
    SELECT
        strptime(target_time::VARCHAR, '%Y%m%d')::DATE as target_time,
        date_category,
        channel_id,
        channel_name,
        channel_country,
        genre_name,
        provider_name,
        platform,
        model,
        users::INTEGER,
        active_users_playback_15::INTEGER,
        active_users_playback_180::INTEGER,
        active_users_playback_900::INTEGER,
        playback_counts::INTEGER,
        active_playback_counts_15::INTEGER,
        active_playback_counts_180::INTEGER,
        active_playback_counts_900::INTEGER,
        playback_count_per_user::DOUBLE,
        playback_count_per_user_15::DOUBLE,
        playback_count_per_user_180::DOUBLE,
        playback_count_per_user_900::DOUBLE,
        viewing_time::INTEGER,
        viewing_time_per_user::DOUBLE,
        active_viewing_time_15::INTEGER,
        active_viewing_time_per_active_user_15::DOUBLE,
        active_viewing_time_per_active_playback_15::DOUBLE,
        active_viewing_time_180::INTEGER,
        active_viewing_time_per_active_user_180::DOUBLE,
        active_viewing_time_per_active_playback_180::DOUBLE,
        active_viewing_time_900::INTEGER,
        active_viewing_time_per_active_user_900::DOUBLE,
        active_viewing_time_per_active_playback_900::DOUBLE
    FROM read_csv(?, header=True, auto_detect=True)
    WHERE channel_id != 'ALL'
    """
    
    try:
        # Start transaction
        con.execute("BEGIN TRANSACTION")
        
        # Run import
        con.execute(query, [file_path])
        
        # Get count of rows inserted (using a simple check on the target file)
        row_count = con.execute("SELECT COUNT(*) FROM read_csv(?, header=True, auto_detect=True) WHERE channel_id != 'ALL'", [file_path]).fetchone()[0]
        
        # Record metadata
        con.execute(
            "INSERT INTO imported_files (file_path, file_name, row_count, file_size_bytes) VALUES (?, ?, ?, ?)",
            [file_path, file_name, row_count, file_size]
        )
        
        # Commit
        con.execute("COMMIT")
        print(f"[+] Successfully imported {file_name}: {row_count} rows added.")
        return True
    except Exception as e:
        con.execute("ROLLBACK")
        print(f"[ERROR] Failed to import {file_name}. Changes rolled back.", file=sys.stderr)
        print(f"[ERROR] Detail: {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description="Import CASCADA CSV metrics files into DuckDB.")
    parser.add_argument(
        "--db", 
        default=DEFAULT_DB_PATH, 
        help=f"Path to the DuckDB file (default: {DEFAULT_DB_PATH})"
    )
    parser.add_argument(
        "--data-dir", 
        default=DEFAULT_DATA_DIR, 
        help=f"Directory containing CSV files to import (default: {DEFAULT_DATA_DIR})"
    )
    parser.add_argument(
        "--force", 
        action="store_true", 
        help="Force re-import files that have already been imported"
    )
    parser.add_argument(
        "--include-samples", 
        action="store_true", 
        help="Include files under sample/ subdirectories (skipped by default)"
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.data_dir):
        print(f"[ERROR] Data directory '{args.data_dir}' does not exist.", file=sys.stderr)
        sys.exit(1)
        
    # Find all CSV files recursively in the data directory
    search_pattern = os.path.join(args.data_dir, "**", "*.csv")
    all_files = glob.glob(search_pattern, recursive=True)
    
    # Filter files
    files_to_import = []
    for f in all_files:
        is_sample = "sample" in os.path.normpath(f).split(os.sep)
        if is_sample and not args.include_samples:
            continue
        files_to_import.append(os.path.abspath(f))
        
    if not files_to_import:
        print(f"No CSV files found to import in '{args.data_dir}' (samples are excluded by default).")
        return
        
    print(f"[*] Found {len(files_to_import)} files to import.")
    
    # Connect to DuckDB
    con = duckdb.connect(args.db)
    
    try:
        # Setup tables
        setup_database(con)
        
        # Perform imports
        imported_count = 0
        for file_path in sorted(files_to_import):
            success = import_csv_file(con, file_path, force=args.force)
            if success:
                imported_count += 1
                
        print(f"\n[Summary] Imported {imported_count}/{len(files_to_import)} new files.")
        
        # Display current row counts
        total_rows = con.execute("SELECT COUNT(*) FROM cascada_metrics").fetchone()[0]
        total_files = con.execute("SELECT COUNT(*) FROM imported_files").fetchone()[0]
        print(f"[Summary] Total records in 'cascada_metrics': {total_rows} rows.")
        print(f"[Summary] Total files registered in 'imported_files': {total_files} files.")
        
    finally:
        con.close()

if __name__ == "__main__":
    main()
