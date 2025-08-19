#!/usr/bin/env python3
"""
Automated Book Discovery and Processing
Discovers European history books from Gutenberg's category page
and processes them in batches of 10
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import sqlite3
import sys
import os
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.processing.extract_locations_updated import process_book

class GutenbergBookDiscoverer:
    def __init__(self, db_path: str = 'history_map.db'):
        self.db_path = db_path
        self.base_url = "https://www.gutenberg.org"
        self.category_url = "https://www.gutenberg.org/ebooks/bookshelf/658"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
    def discover_all_books(self) -> List[Dict]:
        """Discover all books from the European History category."""
        print("🔍 Discovering European history books from Gutenberg...")
        
        all_books = []
        page_num = 1
        
        while True:
            print(f"📄 Crawling page {page_num}...")
            
            if page_num == 1:
                url = self.category_url
            else:
                # Gutenberg uses start_index parameter for pagination
                start_index = (page_num - 1) * 25 + 1  # 25 items per page
                url = f"{self.category_url}?start_index={start_index}"
            
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract books from this page
                page_books = self.extract_books_from_page(soup)
                
                if not page_books:
                    print(f"📄 No more books found on page {page_num}")
                    break
                
                all_books.extend(page_books)
                print(f"📚 Found {len(page_books)} books on page {page_num}")
                
                # Check if there's a next page
                if not self.has_next_page(soup):
                    print("📄 No more pages to crawl")
                    break
                
                page_num += 1
                time.sleep(1)  # Be respectful to Gutenberg's servers
                
            except Exception as e:
                print(f"❌ Error crawling page {page_num}: {e}")
                break
        
        print(f"🎯 Total books discovered: {len(all_books)}")
        return all_books
    
    def extract_books_from_page(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract book information from a category page."""
        books = []
        
        # Look for book entries - Gutenberg uses <li class="booklink">
        book_entries = soup.find_all('li', class_='booklink')
        
        if not book_entries:
            print("⚠️ No book entries found with expected structure")
            return []
        
        print(f"📚 Found {len(book_entries)} book entries")
        
        for entry in book_entries:
            book_info = self.extract_book_info(entry)
            if book_info:
                books.append(book_info)
        
        return books
    
    def has_next_page(self, soup: BeautifulSoup) -> bool:
        """Check if there's a next page available."""
        # Gutenberg uses meta tags for pagination info
        start_index_elem = soup.find('meta', attrs={'name': 'startIndex'})
        total_results_elem = soup.find('meta', attrs={'name': 'totalResults'})
        items_per_page_elem = soup.find('meta', attrs={'name': 'itemsPerPage'})
        
        if start_index_elem and total_results_elem and items_per_page_elem:
            try:
                start_index = int(start_index_elem.get('content', '1'))
                total_results = int(total_results_elem.get('content', '0'))
                items_per_page = int(items_per_page_elem.get('content', '25'))
                
                # Check if there are more results
                return (start_index + items_per_page - 1) < total_results
            except ValueError:
                pass
        
        # Fallback: look for next page indicators
        next_links = soup.find_all('a', string=lambda x: x and 'next' in x.lower() if x else False)
        if next_links:
            return True
        
        return False
    
    def extract_book_info(self, entry) -> Optional[Dict]:
        """Extract individual book information from an entry."""
        try:
            # Look for title - Gutenberg uses <span class="title">
            title_elem = entry.find('span', class_='title')
            if not title_elem:
                return None
            
            title = title_elem.get_text(strip=True)
            if not title or len(title) < 5:
                return None
            
            # Look for author - Gutenberg uses <span class="subtitle">
            author = "Unknown"
            author_elem = entry.find('span', class_='subtitle')
            if author_elem:
                author = author_elem.get_text(strip=True)
            
            # Look for download count - Gutenberg uses <span class="extra">
            download_count = 0
            download_elem = entry.find('span', class_='extra')
            if download_elem:
                try:
                    download_text = download_elem.get_text(strip=True)
                    # Extract just the number from "8065 downloads"
                    download_count = int(''.join(filter(str.isdigit, download_text)))
                except:
                    pass
            
            # Look for book URL - Gutenberg uses <a class="link" href="/ebooks/ID">
            book_url = None
            link_elem = entry.find('a', class_='link')
            if link_elem and link_elem.get('href'):
                href = link_elem['href']
                if '/ebooks/' in href:
                    book_url = urljoin(self.base_url, href)
            
            # Get the actual text URL
            text_url = self.get_book_text_url(book_url) if book_url else None
            
            if text_url and self.is_historical_book(title, author):
                return {
                    'title': title,
                    'author': author,
                    'download_count': download_count,
                    'book_url': book_url,
                    'text_url': text_url
                }
        
        except Exception as e:
            print(f"⚠️ Error extracting book info: {e}")
        
        return None
    
    def get_book_text_url(self, book_url: str) -> Optional[str]:
        """Get the actual text URL for a book."""
        if not book_url:
            return None
        
        try:
            response = self.session.get(book_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for text download links
            text_links = soup.find_all('a', href=lambda x: x and '.txt' in x if x else False)
            
            for link in text_links:
                href = link['href']
                if '/cache/epub/' in href and href.endswith('.txt'):
                    return urljoin(self.base_url, href)
            
            # Fallback: look for any .txt link
            for link in text_links:
                href = link['href']
                if href.endswith('.txt'):
                    return urljoin(self.base_url, href)
                    
        except Exception as e:
            print(f"⚠️ Error getting text URL for {book_url}: {e}")
        
        return None
    
    def is_historical_book(self, title: str, author: str) -> bool:
        """Determine if a book is historical (not fiction)."""
        title_lower = title.lower()
        author_lower = author.lower()
        
        # Historical indicators
        historical_keywords = [
            'history', 'historical', 'chronicle', 'chronicles', 'memoirs', 'memoir',
            'documents', 'document', 'inquisition', 'revolution', 'war', 'wars',
            'empire', 'kingdom', 'dynasty', 'medieval', 'medieval', 'ancient',
            'antiquity', 'classical', 'renaissance', 'reformation', 'crusade',
            'papacy', 'church', 'religious', 'theology', 'philosophy', 'politics',
            'government', 'administration', 'law', 'legal', 'constitution',
            'diplomacy', 'treaty', 'peace', 'conflict', 'battle', 'siege',
            'conquest', 'exploration', 'discovery', 'colonization', 'trade',
            'economy', 'social', 'culture', 'art', 'architecture', 'literature'
        ]
        
        # Fiction indicators
        fiction_keywords = [
            'novel', 'romance', 'tale', 'story', 'legend', 'myth', 'fable',
            'adventure', 'fantasy', 'fiction', 'narrative', 'saga', 'epic',
            'poem', 'poetry', 'drama', 'play', 'theater', 'comedy', 'tragedy'
        ]
        
        # Check for historical keywords
        has_historical = any(keyword in title_lower for keyword in historical_keywords)
        
        # Check for fiction keywords
        has_fiction = any(keyword in title_lower for keyword in fiction_keywords)
        
        # Author-based filtering
        known_historians = [
            'gibbon', 'carlyle', 'lea', 'thompson', 'schiller', 'tacitus',
            'diaz', 'bourrienne', 'winsor', 'oman', 'fraser', 'campan'
        ]
        
        is_known_historian = any(historian in author_lower for historian in known_historians)
        
        # Prioritize historical content, avoid fiction
        if has_fiction and not has_historical:
            return False
        
        if has_historical or is_known_historian:
            return True
        
        # Default: include if no clear fiction indicators
        return not has_fiction
    
    def filter_and_sort_books(self, books: List[Dict]) -> List[Dict]:
        """Filter out already processed books and sort by popularity."""
        print("🔍 Filtering and sorting discovered books...")
        
        # Get already processed books
        processed_urls = self.get_processed_book_urls()
        
        # Filter out already processed books
        new_books = [book for book in books if book['text_url'] not in processed_urls]
        
        print(f"📚 Found {len(new_books)} new books to process")
        
        # Sort by download count (popularity)
        new_books.sort(key=lambda x: x['download_count'], reverse=True)
        
        return new_books
    
    def get_processed_book_urls(self) -> set:
        """Get URLs of already processed books from database."""
        processed_urls = set()
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT url FROM books')
            rows = cursor.fetchall()
            processed_urls = {row[0] for row in rows}
            conn.close()
        except Exception as e:
            print(f"⚠️ Error getting processed books: {e}")
        
        return processed_urls
    
    def process_books_in_batches(self, books: List[Dict], batch_size: int = 10):
        """Process books in batches of specified size."""
        total_books = len(books)
        total_batches = (total_books + batch_size - 1) // batch_size
        
        print(f"🚀 Processing {total_books} books in {total_batches} batches of {batch_size}")
        
        successful = 0
        failed = 0
        
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, total_books)
            batch_books = books[start_idx:end_idx]
            
            print(f"\n{'='*60}")
            print(f"📦 Processing Batch {batch_num + 1}/{total_batches}")
            print(f"📚 Books {start_idx + 1}-{end_idx} of {total_books}")
            print(f"{'='*60}")
            
            batch_successful = 0
            batch_failed = 0
            
            for i, book in enumerate(batch_books, 1):
                print(f"\n📖 Processing book {start_idx + i}/{total_books}: {book['title']}")
                print(f"👤 Author: {book['author']}")
                print(f"📊 Downloads: {book['download_count']:,}")
                print(f"🔗 URL: {book['text_url']}")
                
                try:
                    success = process_book(book['text_url'])
                    if success:
                        batch_successful += 1
                        successful += 1
                        print(f"✅ Successfully processed: {book['title']}")
                    else:
                        batch_failed += 1
                        failed += 1
                        print(f"❌ Failed to process: {book['title']}")
                except Exception as e:
                    batch_failed += 1
                    failed += 1
                    print(f"❌ Error processing {book['title']}: {e}")
                
                # Small delay between books
                time.sleep(2)
            
            print(f"\n📊 Batch {batch_num + 1} Complete:")
            print(f"   ✅ Successful: {batch_successful}")
            print(f"   ❌ Failed: {batch_failed}")
            
            # Save progress after each batch
            self.save_discovery_results(books, successful, failed)
            
            # Ask user if they want to continue to next batch
            if batch_num < total_batches - 1:
                print(f"\n⏸️  Batch {batch_num + 1} complete. Continue to next batch? (y/n)")
                # For now, auto-continue, but you can add user input here
                print("🔄 Auto-continuing to next batch...")
                time.sleep(3)
        
        print(f"\n🎉 ALL BATCHES COMPLETE!")
        print(f"📊 Final Results:")
        print(f"   ✅ Total Successful: {successful}")
        print(f"   ❌ Total Failed: {failed}")
        print(f"   📚 Total Processed: {successful + failed}")
        
        return successful, failed
    
    def save_discovery_results(self, books: List[Dict], successful: int, failed: int):
        """Save discovery results to a JSON file."""
        results = {
            'discovery_date': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_books_discovered': len(books),
            'successful_books': successful,
            'failed_books': failed,
            'books': books
        }
        
        filename = f"discovery_results_{time.strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"💾 Discovery results saved to: {filename}")
        except Exception as e:
            print(f"⚠️ Error saving results: {e}")

def main():
    """Main execution function."""
    print("🚀 Automated European History Book Discovery")
    print("=" * 60)
    
    discoverer = GutenbergBookDiscoverer()
    
    # Step 1: Discover all books
    all_books = discoverer.discover_all_books()
    
    if not all_books:
        print("❌ No books discovered. Exiting.")
        return
    
    # Step 2: Filter and sort
    new_books = discoverer.filter_and_sort_books(all_books)
    
    if not new_books:
        print("✅ All discovered books have already been processed!")
        return
    
    # Step 3: Process in batches
    print(f"\n🎯 Ready to process {len(new_books)} new books in batches of 10")
    print("Press Enter to continue or Ctrl+C to cancel...")
    
    try:
        input()
        successful, failed = discoverer.process_books_in_batches(new_books, batch_size=10)
        
        print(f"\n🎉 Discovery and processing complete!")
        print(f"📚 Successfully processed: {successful} books")
        print(f"❌ Failed: {failed} books")
        
    except KeyboardInterrupt:
        print("\n⏹️  Processing interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during processing: {e}")

if __name__ == "__main__":
    main()
