#!/usr/bin/env python3
"""
Batch Book Processing Script
Processes multiple books from a JSON configuration file
"""

import json
import sqlite3
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.processing.extract_locations_updated import process_book

def load_books_config(config_file: str = 'books_to_process.json'):
    """Load books configuration from JSON file."""
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            books = json.load(f)
        print(f"Loaded {len(books)} books from {config_file}")
        return books
    except Exception as e:
        print(f"Error loading books config: {e}")
        return []

def process_single_book(book_info: dict) -> tuple:
    """Process a single book and return success status and extracted title."""
    print(f"\nProcessing: {book_info.get('title', 'Unknown')}")
    print(f"URL: {book_info.get('url', 'No URL')}")
    
    # Check if book already exists in database
    conn = sqlite3.connect('history_map.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, title FROM books WHERE url = ?', (book_info['url'],))
    existing = cursor.fetchone()
    conn.close()
    
    if existing:
        book_id, existing_title = existing
        # Count existing mentions
        conn = sqlite3.connect('history_map.db')
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM mentions WHERE book_id = ?', (book_id,))
        mention_count = cursor.fetchone()[0]
        conn.close()
        
        print(f"Book already exists: {existing_title} (ID: {book_id})")
        print(f"📊 Has {mention_count} existing mentions - skipping")
        return True, existing_title, mention_count
    
    # Process new book
    success = process_book(book_info['url'])
    
    if success:
        # Get the extracted title from the database
        conn = sqlite3.connect('history_map.db')
        cursor = conn.cursor()
        cursor.execute('SELECT title FROM books ORDER BY id DESC LIMIT 1')
        result = cursor.fetchone()
        extracted_title = result[0] if result else "Unknown"
        conn.close()
        
        # Count mentions for this book
        conn = sqlite3.connect('history_map.db')
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM mentions WHERE book_id = (SELECT id FROM books ORDER BY id DESC LIMIT 1)')
        mention_count = cursor.fetchone()[0]
        conn.close()
        
        return True, extracted_title, mention_count
    else:
        return False, "Failed", 0

def batch_process_books(books: list, max_books: int = None):
    """Process multiple books in batch."""
    print("=== Batch Book Processing ===")
    
    if max_books:
        books = books[:max_books]
        print(f"Processing first {max_books} books")
    
    successful = 0
    failed = 0
    total_mentions = 0
    
    for i, book_info in enumerate(books, 1):
        print(f"\n{'='*60}")
        print(f"Processing book {i}/{len(books)}")
        print(f"URL: {book_info.get('url', 'No URL')}")
        print(f"JSON title (reference): {book_info.get('title', 'Unknown')}")
        print(f"{'='*60}")
        
        success, extracted_title, mention_count = process_single_book(book_info)
        
        if success:
            successful += 1
            total_mentions += mention_count
            print(f"Found {mention_count} location mentions")
        else:
            failed += 1
            print(f"Failed to process book")
    
    print(f"\n{'='*60}")
    print("BATCH PROCESSING COMPLETE")
    print(f"{'='*60}")
    print(f"Total books: {len(books)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total mentions extracted: {total_mentions:,}")
    
    if successful > 0:
        print(f"\nSuccessfully processed {successful} books!")
        print(f"Extracted {total_mentions:,} location mentions")
        print(f"All mentions stored in database with context")
        print(f"Ready to use in your web application!")
        
        # Show book details
        print(f"\n📖 Book Processing Details:")
        for i, book_info in enumerate(books[:successful], 1):
            print(f"  {book_info.get('title', 'Unknown')}")

def main():
    """Main execution function."""
    print("=== Batch Book Location Extraction ===")
    print("Using new comprehensive gazetteer database")
    
    # Load books configuration
    books = load_books_config()
    if not books:
        print("No books to process. Exiting.")
        return
    
    # Process books in batch
    batch_process_books(books)

if __name__ == "__main__":
    main()
