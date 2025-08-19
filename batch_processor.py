#!/usr/bin/env python3
"""
Simple Batch Book Processor
Processes discovered books from the JSON file in batches of 10
"""

import json
import sqlite3
import os
import time
import sys
import argparse
from typing import List, Dict

# Add src/processing to path for the process_book function
sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'processing'))

def load_discovery_results(filename: str) -> List[Dict]:
    """Load discovered books from JSON file."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f" Loaded {len(data['books'])} discovered books from {filename}")
        return data['books']
    except Exception as e:
        print(f" Error loading discovery results: {e}")
        return []

def get_processed_book_urls(db_path: str) -> set:
    """Get URLs of already processed books from database."""
    processed_urls = set()
    
    try:
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT url FROM books')
            rows = cursor.fetchall()
            processed_urls = {row[0] for row in rows}
            conn.close()
            print(f" Found {len(processed_urls)} already processed books in database")
        else:
            print(" No existing database found - all books are new")
    except Exception as e:
        print(f" Error getting processed books: {e}")
    
    return processed_urls

def filter_new_books(books: List[Dict], processed_urls: set) -> List[Dict]:
    """Filter out already processed books and non-English books, then sort by popularity."""
    print("Filtering out already processed books and non-English books...")
    
    # Filter out already processed books
    new_books = [book for book in books if book['text_url'] not in processed_urls]
    print(f" Found {len(new_books)} new books after removing processed ones")
    
    # Filter to only English books
    english_books = []
    for book in new_books:
        title = book['title'].lower()
        
        # Skip books with obvious non-English indicators
        if any(indicator in title for indicator in [
            '(german)', '(french)', '(spanish)', '(italian)', '(russian)', 
            '(dutch)', '(portuguese)', '(swedish)', '(norwegian)', '(danish)',
            '(polish)', '(czech)', '(hungarian)', '(romanian)', '(bulgarian)',
            '(greek)', '(turkish)', '(arabic)', '(chinese)', '(japanese)',
            '(korean)', '(hindi)', '(persian)', '(hebrew)', '(latin)'
        ]):
            continue
        
        # Skip books with non-English characters in title (basic heuristic)
        if any(char in title for char in ['ä', 'ö', 'ü', 'ß', 'é', 'è', 'à', 'ñ', 'ç']):
            continue
            
        english_books.append(book)
    
    print(f" Found {len(english_books)} English books to process")
    
    # Sort by download count (popularity)
    english_books.sort(key=lambda x: x['download_count'], reverse=True)
    
    return english_books

def process_books_in_batches(books: List[Dict], batch_size: int = 10, non_interactive: bool = False):
    """Process books in batches of specified size."""
    total_books = len(books)
    total_batches = (total_books + batch_size - 1) // batch_size
    
    print(f" Processing {total_books} books in {total_batches} batches of {batch_size}")
    print("=" * 80)
    
    successful = 0
    failed = 0
    
    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, total_books)
        batch_books = books[start_idx:end_idx]
        
        print(f"\n Processing Batch {batch_num + 1}/{total_batches}")
        print(f" Books {start_idx + 1}-{end_idx} of {total_books}")
        print("=" * 80)
        
        batch_successful = 0
        batch_failed = 0
        
        for i, book in enumerate(batch_books, 1):
            print(f"\n Processing book {start_idx + i}/{total_books}: {book['title']}")
            print(f" Author: {book['author']}")
            print(f" Downloads: {book['download_count']:,}")
            print(f" Text URL: {book['text_url']}")
            
            try:
                # Import and use the process_book function
                from extract_locations_updated import process_book
                
                success = process_book(book['text_url'])
                if success:
                    batch_successful += 1
                    successful += 1
                    print(f" Successfully processed: {book['title']}")
                else:
                    batch_failed += 1
                    failed += 1
                    print(f" Failed to process: {book['title']}")
            except Exception as e:
                batch_failed += 1
                failed += 1
                print(f" Error processing {book['title']}: {e}")
            
            # Small delay between books to be respectful to servers
            time.sleep(2)
        
        print(f"\n Batch {batch_num + 1} Complete:")
        print(f"    Successful: {batch_successful}")
        print(f"    Failed: {batch_failed}")
        
        # Save progress after each batch
        save_batch_progress(books, successful, failed, batch_num + 1, total_batches)
        
        # Ask user if they want to continue to next batch (skip in non-interactive mode)
        if batch_num < total_batches - 1 and not non_interactive:
            print(f"\n⏸  Batch {batch_num + 1} complete. Continue to next batch? (y/n)")
            try:
                user_input = input("Enter 'y' to continue or 'n' to stop: ").lower().strip()
                if user_input != 'y':
                    print("⏹  Processing stopped by user")
                    break
            except KeyboardInterrupt:
                print("\n⏹  Processing interrupted by user")
                break
        
        print(" Continuing to next batch...")
        time.sleep(3)
    
    print(f"\n ALL BATCHES COMPLETE!")
    print(f" Final Results:")
    print(f"    Total Successful: {successful}")
    print(f"    Total Failed: {failed}")
    print(f"    Total Processed: {successful + failed}")
    
    return successful, failed

def save_batch_progress(books: List[Dict], successful: int, failed: int, current_batch: int, total_batches: int):
    """Save batch processing progress to a JSON file."""
    results = {
        'processing_date': time.strftime('%Y-%m-%d %H:%M:%S'),
        'total_books': len(books),
        'successful_books': successful,
        'failed_books': failed,
        'current_batch': current_batch,
        'total_batches': total_batches,
        'progress_percentage': round((current_batch / total_batches) * 100, 2)
    }
    
    filename = f"batch_progress_{time.strftime('%Y%m%d_%H%M%S')}.json"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f" Batch progress saved to: {filename}")
    except Exception as e:
        print(f" Error saving progress: {e}")

def main():
    """Main execution function."""
    print("Simple Batch Book Processor")
    print("=" * 60)

    # Parse CLI arguments
    parser = argparse.ArgumentParser(description="Process discovered Gutenberg books in batches")
    parser.add_argument("-y", "--yes", action="store_true", help="Run non-interactively and process all batches")
    parser.add_argument("--batch-size", type=int, default=10, help="Number of books per batch (default: 10)")
    args = parser.parse_args()
    
    # Find the most recent discovery results file
    discovery_files = [f for f in os.listdir('.') if f.startswith('discovery_results_') and f.endswith('.json')]
    
    if not discovery_files:
        print(" No discovery results files found!")
        print("Please run the discovery script first.")
        return
    
    # Use the most recent discovery file
    discovery_file = sorted(discovery_files)[-1]
    print(f" Using discovery results from: {discovery_file}")
    
    # Load discovered books
    books = load_discovery_results(discovery_file)
    
    if not books:
        print(" No books loaded. Exiting.")
        return
    
    # Get already processed books
    processed_urls = get_processed_book_urls('history_map.db')
    
    # Filter new books
    new_books = filter_new_books(books, processed_urls)
    
    if not new_books:
        print(" All discovered books have already been processed!")
        return
    
    # Show summary
    print(f"\n Ready to process {len(new_books)} English books")
    print(f" Top 5 books by popularity:")
    for i, book in enumerate(new_books[:5], 1):
        print(f"  {i}. {book['title']} ({book['download_count']:,} downloads)")
    
    # Show filtering summary
    total_discovered = len(books)
    total_new = len([book for book in books if book['text_url'] not in processed_urls])
    total_english = len(new_books)
    
    print(f"\n Filtering Summary:")
    print(f"    Total discovered: {total_discovered}")
    print(f"    New (not processed): {total_new}")
    print(f"    English books: {total_english}")
    print(f"    Filtered out: {total_new - total_english} non-English books")
    
    # Confirm before starting (skip in non-interactive mode)
    print(f"\n  This will process {len(new_books)} English books in batches of {args.batch_size}")
    print("   This may take a very long time depending on the number of books.")
    
    if not args.yes:
        try:
            user_input = input("\nContinue with processing? (y/n): ").lower().strip()
            if user_input != 'y':
                print("⏹  Processing cancelled by user")
                return
        except KeyboardInterrupt:
            print("\n⏹  Processing cancelled by user")
            return
    
    # Start processing
    try:
        successful, failed = process_books_in_batches(new_books, batch_size=args.batch_size, non_interactive=args.yes)
        
        print(f"\n Processing complete!")
        print(f" Successfully processed: {successful} books")
        print(f" Failed: {failed} books")
        
    except KeyboardInterrupt:
        print("\n⏹  Processing interrupted by user")
    except Exception as e:
        print(f"\n Error during processing: {e}")

if __name__ == "__main__":
    main()
