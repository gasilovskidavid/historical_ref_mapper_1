#!/usr/bin/env python3
"""
Batch processor for European History books from Project Gutenberg
Uses the fast in-memory gazetteer for efficient location extraction
"""

import requests
from bs4 import BeautifulSoup
import time
import json
import sqlite3
import os
import sys
from typing import List, Dict, Optional
from dataclasses import dataclass
import re

# Add the processing directory to the path to import the fast extractor
sys.path.append(os.path.dirname(__file__))
from extract_locations_fast import FastLocationExtractor, LocationMention

# Add the database directory to the path to import periodization and database functions
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'database'))
from enhance_time_periods import extract_time_periods_from_text
from database_integration import get_db_connection, get_database_type

@dataclass
class BookInfo:
    title: str
    author: str
    url: str
    gutenberg_id: str
    release_date: str = ""  # New field for release date

class EuropeanHistoryBatchProcessor:
    def __init__(self, db_path: str = 'history_map.db'):
        self.db_path = db_path
        self.extractor = None
        self.books_processed = 0
        self.total_locations = 0
        self.db_type = get_database_type()
        
    def initialize_extractor(self):
        """Initialize the fast location extractor."""
        print("Initializing fast location extractor...")
        self.extractor = FastLocationExtractor()
        
        if not self.extractor.gazetteer or not self.extractor.nlp:
            print("Failed to initialize extractor!")
            return False
            
        print(f"Extractor ready with {len(self.extractor.gazetteer):,} European locations")
        return True
    
    def scrape_european_history_books(self) -> List[BookInfo]:
        """Scrape all books from the European History category across all pages."""
        base_url = "https://www.gutenberg.org/ebooks/bookshelf/658"
        print(f"Scraping European History books from: {base_url}")
        
        all_books = []
        page_num = 1
        
        while True:
            # Construct page URL
            if page_num == 1:
                page_url = base_url
            else:
                page_url = f"{base_url}?start_index={(page_num-1)*25 + 1}"
            
            print(f"\nScraping page {page_num}...")
            
            try:
                response = requests.get(page_url, timeout=30)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for book entries in the category page
                book_entries = soup.find_all(['li', 'div'], class_=lambda x: x and 'book' in x.lower())
                
                if not book_entries:
                    # Fallback: look for any elements containing book links
                    book_entries = soup.find_all(['li', 'div', 'p'])
                
                print(f"Scanning page {page_num} for book links...")
                
                page_books = 0
                
                for entry in book_entries:
                    # Look for links that contain book IDs
                    links = entry.find_all('a', href=True)
                    
                    for link in links:
                        href = link.get('href', '')
                        
                        # Check if it's a book link (contains /ebooks/ followed by numbers)
                        if '/ebooks/' in href and any(char.isdigit() for char in href):
                            # Extract Gutenberg ID
                            parts = href.split('/')
                            if len(parts) >= 3 and parts[-1].isdigit():
                                gutenberg_id = parts[-1]
                                
                                # No need to parse titles from HTML anymore - we'll get them from text files
                                
                                # Create book info with minimal data from category page
                                # We'll get the real title and release date from the text file later
                                book = BookInfo(
                                    title="",  # Will be extracted from text file
                                    author="",  # Empty string for author
                                    url=f"https://www.gutenberg.org/cache/epub/{gutenberg_id}/pg{gutenberg_id}.txt",
                                    gutenberg_id=gutenberg_id,
                                    release_date=""  # Will be extracted from text file
                                )
                                
                                # Avoid duplicates across all pages
                                if not any(b.gutenberg_id == gutenberg_id for b in all_books):
                                    all_books.append(book)
                                    page_books += 1
                                    print(f"  Found book ID: {gutenberg_id}")
                
                print(f"Page {page_num}: Found {page_books} new books")
                
                # Check if this page had any books
                if page_books == 0:
                    print(f"No more books found on page {page_num}. Stopping pagination.")
                    break
                
                # Check if there's a next page link
                next_page_link = soup.find('a', string=lambda x: x and 'next' in x.lower())
                if not next_page_link:
                    print("No next page link found. Reached end of category.")
                    break
                
                page_num += 1
                
                # Small delay between pages to be respectful
                time.sleep(2)
                
            except Exception as e:
                print(f"Error scraping page {page_num}: {e}")
                break
        
        print(f"\nSuccessfully parsed {len(all_books)} total books from all pages of European History category")
        return all_books
    
    def extract_book_metadata_from_text(self, book: BookInfo) -> tuple[str, str]:
        """Extract title and release date from the book's text file."""
        try:
            print(f"  Extracting metadata from text file for book {book.gutenberg_id}...")
            
            # Download the text file
            response = requests.get(book.url, timeout=30)
            response.raise_for_status()
            text_content = response.text
            
            # Extract title (look for "Title:" marker)
            title = ""
            title_match = re.search(r'Title:\s*(.+?)(?:\r?\n|$)', text_content, re.IGNORECASE)
            if title_match:
                title = title_match.group(1).strip()
                print(f"    Extracted title: {title}")
            else:
                print(f"    No title found in text file")
                title = f"Unknown Title (ID: {book.gutenberg_id})"
            
            # Extract release date (look for "Release date:" marker)
            release_date = ""
            release_match = re.search(r'Release date:\s*(.+?)(?:\r?\n|$)', text_content, re.IGNORECASE)
            if release_match:
                release_date = release_match.group(1).strip()
                print(f"    Extracted release date: {release_date}")
            else:
                print(f"    No release date found in text file")
                release_date = "Unknown"
            
            return title, release_date
            
        except Exception as e:
            print(f"    Error extracting metadata: {e}")
            return f"Error extracting title (ID: {book.gutenberg_id})", "Error"
    
    def setup_database(self):
        """Set up database tables if they don't exist."""
        if self.db_type == 'postgresql':
            self.setup_postgresql_database()
        else:
            self.setup_sqlite_database()
    
    def setup_sqlite_database(self):
        """Set up SQLite database tables (existing functionality)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if books table exists and what columns it has
        cursor.execute("PRAGMA table_info(books)")
        existing_columns = [col[1] for col in cursor.fetchall()]
        
        if not existing_columns:
            # Create books table if it doesn't exist
            cursor.execute('''
                CREATE TABLE books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    author TEXT,
                    gutenberg_url TEXT UNIQUE,
                    url TEXT,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        elif 'gutenberg_url' not in existing_columns:
            # Add gutenberg_url column if it doesn't exist
            cursor.execute('ALTER TABLE books ADD COLUMN gutenberg_url TEXT UNIQUE')
        
        # Check if locations table exists
        cursor.execute("PRAGMA table_info(locations)")
        locations_columns = [col[1] for col in cursor.fetchall()]
        
        if not locations_columns:
            # Create locations table if it doesn't exist
            cursor.execute('''
                CREATE TABLE locations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    country_code TEXT,
                    population INTEGER
                )
            ''')
        elif 'country_code' not in locations_columns:
            # Add missing columns if they don't exist
            cursor.execute('ALTER TABLE locations ADD COLUMN country_code TEXT')
            cursor.execute('ALTER TABLE locations ADD COLUMN population INTEGER')
        
        # Check if mentions table exists
        cursor.execute("PRAGMA table_info(mentions)")
        mentions_columns = [col[1] for col in cursor.fetchall()]
        
        if not mentions_columns:
            # Create mentions table if it doesn't exist
            cursor.execute('''
                CREATE TABLE mentions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER,
                    location_id INTEGER,
                    text_position INTEGER,
                    context TEXT,
                    estimated_year INTEGER,
                    time_context TEXT,
                    FOREIGN KEY (book_id) REFERENCES books (id),
                    FOREIGN KEY (location_id) REFERENCES locations (id)
                )
            ''')
        elif 'time_context' not in mentions_columns:
            # Add time_context column if it doesn't exist
            cursor.execute('ALTER TABLE mentions ADD COLUMN time_context TEXT')
        
        # Check if books table has time period columns
        if 'historical_start_year' not in existing_columns:
            cursor.execute('ALTER TABLE books ADD COLUMN historical_start_year INTEGER')
        if 'historical_end_year' not in existing_columns:
            cursor.execute('ALTER TABLE books ADD COLUMN historical_end_year INTEGER')
        if 'time_period_description' not in existing_columns:
            cursor.execute('ALTER TABLE books ADD COLUMN time_period_description TEXT')
        
        # Check if books table has release_date column
        if 'release_date' not in existing_columns:
            cursor.execute('ALTER TABLE books ADD COLUMN release_date TEXT')
        
        conn.commit()
        conn.close()
        print("SQLite database setup completed")
    
    def setup_postgresql_database(self):
        """Set up PostgreSQL database tables."""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Check if books table exists and what columns it has
            cursor.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'books'
            """)
            existing_columns = [col[0] for col in cursor.fetchall()]
            
            if not existing_columns:
                # Create books table if it doesn't exist
                cursor.execute('''
                    CREATE TABLE books (
                        id SERIAL PRIMARY KEY,
                        title VARCHAR(500) NOT NULL,
                        author VARCHAR(200),
                        gutenberg_url TEXT UNIQUE,
                        url TEXT,
                        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        release_date DATE,
                        historical_start_year INTEGER,
                        historical_end_year INTEGER,
                        time_period_description TEXT
                    )
                ''')
            
            # Check if locations table exists
            cursor.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'locations'
            """)
            locations_columns = [col[0] for col in cursor.fetchall()]
            
            if not locations_columns:
                # Create locations table if it doesn't exist
                cursor.execute('''
                    CREATE TABLE locations (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(200) NOT NULL UNIQUE,
                        latitude DOUBLE PRECISION NOT NULL,
                        longitude DOUBLE PRECISION NOT NULL,
                        country_code VARCHAR(10),
                        population INTEGER
                    )
                ''')
            
            # Check if mentions table exists
            cursor.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'mentions'
            """)
            mentions_columns = [col[0] for col in cursor.fetchall()]
            
            if not mentions_columns:
                # Create mentions table if it doesn't exist
                cursor.execute('''
                    CREATE TABLE mentions (
                        id SERIAL PRIMARY KEY,
                        book_id INTEGER,
                        location_id INTEGER,
                        text_position INTEGER,
                        context TEXT,
                        estimated_year INTEGER,
                        time_context TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (book_id) REFERENCES books (id),
                        FOREIGN KEY (location_id) REFERENCES locations (id)
                    )
                ''')
            
            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_books_title ON books(title)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_books_gutenberg_url ON books(gutenberg_url)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_locations_name ON locations(name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_mentions_book_id ON mentions(book_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_mentions_location_id ON mentions(location_id)')
            
            conn.commit()
            cursor.close()
            conn.close()
            print("PostgreSQL database setup completed")
            
        except Exception as e:
            print(f"Warning: PostgreSQL setup failed ({e}), falling back to SQLite")
            self.db_type = 'sqlite'
            self.setup_sqlite_database()
    
    def save_book_to_db(self, book: BookInfo, location_mentions: List[LocationMention]) -> int:
        """Save book and location mentions to database using normalized schema."""
        if self.db_type == 'postgresql':
            return self.save_book_to_postgresql(book, location_mentions)
        else:
            return self.save_book_to_sqlite(book, location_mentions)
    
    def save_book_to_sqlite(self, book: BookInfo, location_mentions: List[LocationMention]) -> int:
        """Save book to SQLite database (existing functionality)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Extract time periods from book title and description (not full text)
            title_and_desc = f"{book.title} {book.author or ''}"
            print(f"  DEBUG: Title being processed for year extraction: '{title_and_desc}'")
            time_periods = extract_time_periods_from_text(title_and_desc)
            print(f"  DEBUG: Raw time periods extracted: {time_periods}")
            
            # Convert the time info to the expected format (same as archive system)
            historical_start_year = None
            historical_end_year = None
            time_period_description = "No specific time period found"
            
            if time_periods.get('year'):
                years = [int(y) for y in time_periods['year'] if y.isdigit()]
                if years:
                    historical_start_year = min(years)
                    historical_end_year = max(years)
                    time_period_description = f"Years mentioned: {', '.join(time_periods['year'])}"
                    print(f"  DEBUG: Years found: {years}, Range: {historical_start_year}-{historical_end_year}")
            
            if time_periods.get('century'):
                centuries = time_periods['century']
                time_period_description += f"; Centuries: {', '.join(centuries)}"
            
            if time_periods.get('period'):
                periods = time_periods['period']
                time_period_description += f"; Periods: {', '.join(periods)}"
            
            if time_periods:
                print(f"  Extracted time periods from title: {time_periods}")
                if historical_start_year and historical_end_year:
                    print(f"  Historical range: {historical_start_year} - {historical_end_year}")
                else:
                    print(f"  No clear historical range extracted")
            else:
                print(f"   DEBUG: No time periods found at all")
            
            # Insert book with time period information
            cursor.execute('''
                INSERT OR REPLACE INTO books (
                    title, author, gutenberg_url, url, 
                    historical_start_year, historical_end_year, time_period_description, release_date
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                book.title, book.author or "", 
                f"https://www.gutenberg.org/ebooks/{book.gutenberg_id}", 
                book.url,
                historical_start_year, historical_end_year, time_period_description, book.release_date
            ))
            
            book_id = cursor.lastrowid
            
            # Process each location mention
            for mention in location_mentions:
                # First, ensure the location exists in the locations table
                cursor.execute('''
                    INSERT OR IGNORE INTO locations (name, latitude, longitude, country_code, population)
                    VALUES (?, ?, ?, ?, ?)
                ''', (mention.location_name, mention.latitude, mention.longitude, mention.country_code, mention.population))
                
                # Get the location ID
                cursor.execute('SELECT id FROM locations WHERE name = ?', (mention.location_name,))
                location_id = cursor.fetchone()[0]
                
                # Extract time context from the mention context
                mention_time_info = extract_time_periods_from_text(mention.context)
                estimated_year = None
                time_context = ""
                
                if mention_time_info.get('year'):
                    years = [int(y) for y in mention_time_info['year'] if y.isdigit()]
                    if years:
                        estimated_year = years[0]  # Use first year mentioned in context
                        time_context = f"Years: {', '.join(mention_time_info['year'])}"
                
                if mention_time_info.get('century'):
                    if not time_context:
                        time_context = f"Centuries: {', '.join(mention_time_info['century'])}"
                    else:
                        time_context += f"; Centuries: {', '.join(mention_time_info['century'])}"
                
                # Insert the mention with time context
                cursor.execute('''
                    INSERT INTO mentions (book_id, location_id, text_position, context, estimated_year, time_context)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (book_id, location_id, mention.text_position, mention.context, estimated_year, time_context))
            
            conn.commit()
            print(f"  ✅ Saved {len(location_mentions)} location mentions to SQLite database")
            if time_periods:
                print(f"   Time periods saved: {time_period_description}")
            return book_id
            
        except Exception as e:
            print(f"   Error saving to SQLite database: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()
    
    def save_book_to_postgresql(self, book: BookInfo, location_mentions: List[LocationMention]) -> int:
        """Save book to PostgreSQL database."""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Extract time periods from book title and description (not full text)
            title_and_desc = f"{book.title} {book.author or ''}"
            print(f"  DEBUG: Title being processed for year extraction: '{title_and_desc}'")
            time_periods = extract_time_periods_from_text(title_and_desc)
            print(f"  DEBUG: Raw time periods extracted: {time_periods}")
            
            # Convert the time info to the expected format (same as archive system)
            historical_start_year = None
            historical_end_year = None
            time_period_description = "No specific time period found"
            
            if time_periods.get('year'):
                years = [int(y) for y in time_periods['year'] if y.isdigit()]
                if years:
                    historical_start_year = min(years)
                    historical_end_year = max(years)
                    time_period_description = f"Years mentioned: {', '.join(time_periods['year'])}"
                    print(f"  DEBUG: Years found: {years}, Range: {historical_start_year}-{historical_end_year}")
            
            if time_periods.get('century'):
                centuries = time_periods['century']
                time_period_description += f"; Centuries: {', '.join(centuries)}"
            
            if time_periods.get('period'):
                periods = time_periods['period']
                time_period_description += f"; Periods: {', '.join(periods)}"
            
            if time_periods:
                print(f"  Extracted time periods from title: {time_periods}")
                if historical_start_year and historical_end_year:
                    print(f"  Historical range: {historical_start_year} - {historical_end_year}")
                else:
                    print(f"  No clear historical range extracted")
            else:
                print(f"   DEBUG: No time periods found at all")
            
            # Insert book with time period information
            cursor.execute('''
                INSERT INTO books (
                    title, author, gutenberg_url, url, 
                    historical_start_year, historical_end_year, time_period_description, release_date
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (gutenberg_url) DO UPDATE SET
                    title = EXCLUDED.title,
                    author = EXCLUDED.author,
                    url = EXCLUDED.url,
                    historical_start_year = EXCLUDED.historical_start_year,
                    historical_end_year = EXCLUDED.historical_end_year,
                    time_period_description = EXCLUDED.time_period_description,
                    release_date = EXCLUDED.release_date
                RETURNING id
            ''', (
                book.title, book.author or "", 
                f"https://www.gutenberg.org/ebooks/{book.gutenberg_id}", 
                book.url,
                historical_start_year, historical_end_year, time_period_description, book.release_date
            ))
            
            result = cursor.fetchone()
            if result:
                book_id = result[0]
            else:
                # Book was already there, get its ID
                cursor.execute('SELECT id FROM books WHERE gutenberg_url = %s', 
                             (f"https://www.gutenberg.org/ebooks/{book.gutenberg_id}",))
                book_id = cursor.fetchone()[0]
            
            # Process each location mention
            for mention in location_mentions:
                # First, ensure the location exists in the locations table
                cursor.execute('''
                    INSERT INTO locations (name, latitude, longitude, country_code, population)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (name) DO NOTHING
                ''', (mention.location_name, mention.latitude, mention.longitude, mention.country_code, mention.population))
                
                # Get the location ID
                cursor.execute('SELECT id FROM locations WHERE name = %s', (mention.location_name,))
                result = cursor.fetchone()
                if result:
                    location_id = result[0]
                else:
                    # Location was already there, get its ID
                    cursor.execute('SELECT id FROM locations WHERE name = %s', (mention.location_name,))
                    location_id = cursor.fetchone()[0]
                
                # Extract time context from the mention context
                mention_time_info = extract_time_periods_from_text(mention.context)
                estimated_year = None
                time_context = ""
                
                if mention_time_info.get('year'):
                    years = [int(y) for y in mention_time_info['year'] if y.isdigit()]
                    if years:
                        estimated_year = years[0]  # Use first year mentioned in context
                        time_context = f"Years: {', '.join(mention_time_info['year'])}"
                
                if mention_time_info.get('century'):
                    if not time_context:
                        time_context = f"Centuries: {', '.join(mention_time_info['century'])}"
                    else:
                        time_context += f"; Centuries: {', '.join(mention_time_info['century'])}"
                
                # Insert the mention with time context
                cursor.execute('''
                    INSERT INTO mentions (book_id, location_id, text_position, context, estimated_year, time_context)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                ''', (book_id, location_id, mention.text_position, mention.context, estimated_year, time_context))
            
            conn.commit()
            print(f"  ✅ Saved {len(location_mentions)} location mentions to PostgreSQL database")
            if time_periods:
                print(f"   Time periods saved: {time_period_description}")
            return book_id
            
        except Exception as e:
            print(f"   Error saving to PostgreSQL database: {e}")
            if conn:
                conn.rollback()
            return None
        finally:
            if conn:
                cursor.close()
                conn.close()
    
    def process_book(self, book: BookInfo) -> bool:
        """Process a single book and extract locations."""
        try:
            print(f"\n📚 Processing: {book.gutenberg_id}")
            print(f"   Gutenberg ID: {book.gutenberg_id}")
            print(f"   URL: {book.url}")
            
            # First, extract title and release date from the text file
            title, release_date = self.extract_book_metadata_from_text(book)
            book.title = title
            book.release_date = release_date
            
            print(f"   Title: {book.title}")
            print(f"   Release Date: {book.release_date}")
            
            # Download and process book
            location_mentions = self.extractor.process_book(book.url)
            
            if location_mentions is not None:
                # Save to database with time period information from title/description
                book_id = self.save_book_to_db(book, location_mentions)
                if book_id:
                    self.total_locations += len(location_mentions)
                    print(f"   Book processed successfully - {len(location_mentions)} locations saved")
                    return True
                else:
                    print(f"   Failed to save to database")
                    return False
            else:
                print(f"   Book processing failed")
                return False
                
        except Exception as e:
            print(f"   Error processing book: {e}")
            return False
    
    def process_books_in_batches(self, books: List[BookInfo], batch_size: int = 10):
        """Process books in batches."""
        total_books = len(books)
        print(f"\n Starting batch processing of {total_books} books in batches of {batch_size}")
        
        for batch_num in range(0, total_books, batch_size):
            batch_end = min(batch_num + batch_size, total_books)
            batch_books = books[batch_num:batch_end]
            
            print(f"\n Processing batch {batch_num//batch_size + 1} (books {batch_num + 1}-{batch_end})")
            print("=" * 60)
            
            batch_success = 0
            batch_locations = 0
            
            for book in batch_books:
                success = self.process_book(book)
                if success:
                    batch_success += 1
                
                # Small delay between books to be respectful
                time.sleep(1)
            
            print(f"\n Batch {batch_num//batch_size + 1} complete:")
            print(f"   Books processed: {batch_success}/{len(batch_books)}")
            
            self.books_processed += batch_success
            
            # Progress update
            progress = (batch_end / total_books) * 100
            print(f"   Overall progress: {progress:.1f}% ({self.books_processed}/{total_books})")
            
            # Continue automatically to next batch
            if batch_end < total_books:
                print(f"\n⏭ Continuing to next batch automatically...")
                time.sleep(2)  # Brief pause to show progress
    
    def run(self):
        """Main processing pipeline."""
        print("=== European History Books Batch Processor ===")
        print("Using fast in-memory gazetteer for location extraction")
        print("=" * 60)
        
        # Initialize extractor
        if not self.initialize_extractor():
            return
        
        # Setup database
        self.setup_database()
        
        # Scrape books
        books = self.scrape_european_history_books()
        if not books:
            print("No books found. Exiting.")
            return
        
        # Show books found
        print(f"\n Found {len(books)} European History books:")
        for i, book in enumerate(books[:10], 1):  # Show first 10
            print(f"   {i}. {book.title}")
        if len(books) > 10:
            print(f"   ... and {len(books) - 10} more")
        
        # Start processing
        self.process_books_in_batches(books)
        
        # Final summary
        print(f"\n🎉 Batch processing complete!")
        print(f"   Total books processed: {self.books_processed}")
        print(f"   Total locations found: {self.total_locations}")

def main():
    """Main function."""
    processor = EuropeanHistoryBatchProcessor()
    processor.run()

if __name__ == "__main__":
    main()
