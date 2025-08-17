import sqlite3
import spacy
import requests
from typing import List, Dict, Optional
from dataclasses import dataclass
import re
import sys
import os

# Add the database directory to the path to import enhance_time_periods
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'database'))
from enhance_time_periods import extract_book_time_period

@dataclass
class LocationMention:
    location_id: int
    location_name: str
    latitude: float
    longitude: float
    mentioned_as: str
    context: str
    text_position: int
    confidence: float

class DatabaseGazetteer:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
    
    def connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
    
    def close(self):
        if self.conn:
            self.conn.close()
    
    def find_location(self, entity_text: str) -> Optional[Dict]:
        """Find a location in the gazetteer database."""
        if not self.conn:
            self.connect()
        
        # Try exact match first
        self.cursor.execute('''
            SELECT id, name, latitude, longitude 
            FROM locations 
            WHERE LOWER(name) = LOWER(?)
        ''', (entity_text,))
        
        result = self.cursor.fetchone()
        if result:
            return self._row_to_dict(result)
        
        # Try partial match
        self.cursor.execute('''
            SELECT id, name, latitude, longitude 
            FROM locations 
            WHERE LOWER(name) LIKE LOWER(?)
            LIMIT 1
        ''', (f'%{entity_text}%',))
        
        result = self.cursor.fetchone()
        if result:
            return self._row_to_dict(result)
        
        return None
    
    def _row_to_dict(self, row) -> Dict:
        return {
            'id': row[0],
            'name': row[1],
            'latitude': row[2],
            'longitude': row[3]
        }

class BookProcessor:
    def __init__(self, gazetteer: DatabaseGazetteer):
        self.gazetteer = gazetteer
        self.nlp = None
        self.load_nlp_model()
    
    def load_nlp_model(self) -> bool:
        """Load spaCy NLP model for named entity recognition."""
        try:
            self.nlp = spacy.load("en_core_web_sm")
            print("spaCy model loaded successfully")
            return True
        except OSError as e:
            print(f"Error loading spaCy model: {e}")
            print("Please install with: python -m spacy download en_core_web_sm")
            return False
    
    def download_book(self, url: str) -> Optional[str]:
        """Download book text from URL."""
        try:
            print(f"Downloading book from {url}...")
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Error downloading book: {e}")
            return None
    
    def extract_book_title(self, text: str) -> str:
        """Extract the actual book title from Gutenberg text."""
        try:
            # First, try to find "Title:" pattern which is standard in Gutenberg books
            title_marker = "Title:"
            if title_marker in text:
                title_index = text.index(title_marker)
                # Look for the title on the same line or next few lines
                title_section = text[title_index:title_index + 500]
                lines = title_section.split('\n')
                
                for i, line in enumerate(lines):
                    line = line.strip()
                    if line.startswith(title_marker):
                        # Title is on the same line as "Title:"
                        title = line[len(title_marker):].strip()
                        if title and len(title) > 3:
                            print(f"Extracted title from 'Title:' marker: {title}")
                            return title
                    elif i > 0 and line and not line.startswith('***') and not line.startswith('Produced by'):
                        # Title is on the next line after "Title:"
                        title = line.replace('_', '').replace('*', '').strip()
                        if len(title) > 3 and len(title) < 200:
                            print(f"Extracted title from line after 'Title:' marker: {title}")
                            return title
            
            # Fallback: Look for the title after the START marker
            start_marker = "*** START OF THE PROJECT GUTENBERG EBOOK"
            if start_marker in text:
                start_index = text.index(start_marker)
                title_section = text[start_index:start_index + 2000]  # Look in first 2000 chars after start
                
                # Try to find the title in different formats
                lines = title_section.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('***') and not line.startswith('Produced by'):
                        # Clean up the line and return as title
                        title = line.replace('_', '').replace('*', '').strip()
                        if len(title) > 5 and len(title) < 200:  # Reasonable title length
                            print(f"Fallback title from START marker: {title}")
                            return title
                
                # Final fallback: return the first non-empty line after start marker
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('***') and not line.startswith('Produced by'):
                        title = line.replace('_', '').replace('*', '').strip()
                        if len(title) > 3:
                            print(f"Final fallback title: {title}")
                            return title
        except Exception as e:
            print(f"Error extracting title: {e}")
        
        # If all else fails, return a generic title
        print("Could not extract title, using generic name")
        return "Unknown Book"
    
    def extract_book_description(self, text: str) -> str:
        """Extract book description or summary from Gutenberg text."""
        try:
            # Look for description patterns in Gutenberg text
            desc_patterns = [
                r'Summary:\s*(.+?)(?:\n\n|\n[A-Z]|$)',  # Summary: description
                r'Description:\s*(.+?)(?:\n\n|\n[A-Z]|$)',  # Description: description
                r'About\s+this\s+book:\s*(.+?)(?:\n\n|\n[A-Z]|$)',  # About this book: description
                r'Introduction:\s*(.+?)(?:\n\n|\n[A-Z]|$)',  # Introduction: description
            ]
            
            for pattern in desc_patterns:
                match = re.search(pattern, text[:5000], re.IGNORECASE | re.DOTALL)  # Search first 5000 chars
                if match:
                    description = match.group(1).strip()
                    if len(description) > 20 and len(description) < 500:  # Reasonable description length
                        print(f"Extracted description: {description[:100]}...")
                        return description
            
            # Fallback: use first paragraph that might be descriptive
            lines = text.split('\n')
            for i, line in enumerate(lines[:50]):  # Check first 50 lines
                line = line.strip()
                if (len(line) > 50 and len(line) < 300 and 
                    not line.startswith('The Project Gutenberg') and
                    not line.startswith('Title:') and
                    not line.startswith('Author:') and
                    not line.startswith('Release Date:') and
                    not line.isupper() and
                    not line.isdigit() and
                    line.endswith('.') and
                    i > 5):  # Skip first few lines (usually metadata)
                    print(f"Fallback description: {line[:100]}...")
                    return line
                    
        except Exception as e:
            print(f"Error extracting description: {e}")
        
        return ""
    
    def clean_gutenberg_text(self, text: str) -> str:
        """Remove Project Gutenberg headers and footers."""
        start_marker = "*** START OF THE PROJECT GUTENBERG EBOOK"
        end_marker = "*** END OF THE PROJECT GUTENBERG EBOOK"
        
        try:
            start_index = text.index(start_marker)
            text_after_start = text[start_index + len(start_marker):]
            end_index = text_after_start.index(end_marker)
            clean_text = text_after_start[:end_index].strip()
            print(f"Cleaned text: {len(clean_text):,} characters")
            return clean_text
        except ValueError:
            print("Warning: Gutenberg markers not found. Using full text.")
            return text
    
    def extract_locations_with_context(self, text: str, context_window: int = 100) -> List[LocationMention]:
        """
        Extract location mentions with surrounding context.
        Returns list of LocationMention objects ready for database storage.
        """
        if not self.nlp:
            print("NLP model not loaded!")
            return []
        
        print(f"Extracting locations from {len(text):,} characters...")
        
        # Process text in chunks to avoid memory issues
        chunk_size = 500000
        all_mentions = []
        
        for chunk_start in range(0, len(text), chunk_size):
            chunk_end = min(chunk_start + chunk_size, len(text))
            chunk = text[chunk_start:chunk_end]
            
            print(f"Processing chunk {chunk_start//chunk_size + 1} (chars {chunk_start:,}-{chunk_end:,})...")
            
            doc = self.nlp(chunk)
            
            for ent in doc.ents:
                # Focus on location-related entities
                if ent.label_ in ['GPE', 'LOC', 'FAC']:  # Countries, cities, locations, facilities
                    location_data = self.gazetteer.find_location(ent.text)
                    
                    if location_data:
                        # Calculate context window
                        context_start = max(0, ent.start_char - context_window)
                        context_end = min(len(chunk), ent.end_char + context_window)
                        context = chunk[context_start:context_end].strip()
                        
                        # Calculate confidence based on entity type and text length
                        confidence = self._calculate_confidence(ent, location_data)
                        
                        mention = LocationMention(
                            location_id=location_data['id'],
                            location_name=location_data['name'],
                            latitude=location_data['latitude'],
                            longitude=location_data['longitude'],
                            mentioned_as=ent.text,
                            context=context,
                            text_position=chunk_start + ent.start_char,
                            confidence=confidence
                        )
                        
                        all_mentions.append(mention)
        
        print(f"Extracted {len(all_mentions)} location mentions")
        return all_mentions
    
    def _calculate_confidence(self, entity, location_data: Dict) -> float:
        """Calculate confidence score for a location match."""
        base_confidence = 0.5
        
        # Boost for longer entity text (more specific)
        if len(entity.text) > 3:
            base_confidence += 0.2
        
        # Boost for exact name match
        if entity.text.lower() == location_data['name'].lower():
            base_confidence += 0.3
        
        return min(base_confidence, 1.0)

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
    
    def connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
    
    def close(self):
        if self.conn:
            self.conn.close()
    
    def store_book(self, title: str, url: str, description: str = "") -> int:
        """Store a book and return its ID."""
        if not self.conn:
            self.connect()
        
        # Check if book already exists
        self.cursor.execute('SELECT id FROM books WHERE title = ?', (title,))
        existing = self.cursor.fetchone()
        
        if existing:
            book_id = existing[0]
            print(f"Book already exists: {title} (ID: {book_id})")
            return book_id
        
        # Insert new book
        self.cursor.execute('''
            INSERT INTO books (title, url, description) 
            VALUES (?, ?, ?)
        ''', (title, url, description))
        
        book_id = self.cursor.lastrowid
        
        # Extract and update time periods for the newly stored book
        try:
            time_info = extract_book_time_period(title, description)
            if time_info['start_year'] and time_info['end_year']:
                self.cursor.execute('''
                    UPDATE books 
                    SET 
                        historical_start_year = ?,
                        historical_end_year = ?,
                        time_period_description = ?,
                        period_status = ?
                    WHERE id = ?
                ''', (
                    time_info['start_year'],
                    time_info['end_year'],
                    time_info['description'],
                    time_info['period_status']
                ))
                self.conn.commit()
                print(f"✓ Extracted time period: {time_info['start_year']}-{time_info['end_year']} ({time_info['confidence']} confidence)")
            else:
                # Mark book as having unknown time period
                self.cursor.execute('''
                    UPDATE books 
                    SET 
                        period_status = ?,
                        time_period_description = ?
                    WHERE id = ?
                ''', (
                    time_info['period_status'],
                    time_info['description']
                ))
                self.conn.commit()
                print(f"⚠️  No time period found - marked as {time_info['period_status']}")
        except Exception as e:
            print(f"⚠️  Time period extraction failed: {e}")
        
        print(f"Stored new book: {title} (ID: {book_id})")
        return book_id
    
    def store_mentions(self, book_id: int, mentions: List[LocationMention]):
        """Store location mentions for a book."""
        if not self.conn:
            self.connect()
        
        # Clear existing mentions for this book to avoid duplicates
        self.cursor.execute('DELETE FROM mentions WHERE book_id = ?', (book_id,))
        print(f"Cleared existing mentions for book ID {book_id}")
        
        for mention in mentions:
            self.cursor.execute('''
                INSERT INTO mentions (
                    book_id, location_id, text_position, context
                ) VALUES (?, ?, ?, ?)
            ''', (
                book_id, mention.location_id, mention.text_position, mention.context
            ))
        
        self.conn.commit()
        print(f"Stored {len(mentions)} mentions for book ID {book_id}")

def process_book(url: str, gazetteer_path: str = 'history_map.db') -> bool:
    """Process a single book from URL."""
    try:
        # Initialize components
        gazetteer = DatabaseGazetteer(gazetteer_path)
        processor = BookProcessor(gazetteer)
        db_manager = DatabaseManager(gazetteer_path)
        
        # Download and process book
        text = processor.download_book(url)
        if not text:
            return False
        
        # Extract title and description
        title = processor.extract_book_title(text)
        description = processor.extract_book_description(text)
        print(f"Extracted title: {title}")
        if description:
            print(f"Extracted description: {description[:100]}...")
        
        clean_text = processor.clean_gutenberg_text(text)
        
        # Extract locations
        mentions = processor.extract_locations_with_context(clean_text)
        print(f"Found {len(mentions)} location mentions")
        
        if mentions:
            # Store in database
            book_id = db_manager.store_book(title, url, description)
            db_manager.store_mentions(book_id, mentions)
            print(f"Stored {len(mentions)} mentions for book ID {book_id}")
            
            # Show sample mentions
            print(f"\nSample mentions from '{title}':")
            for i, mention in enumerate(mentions[:3], 1):
                print(f"  {i}. {mention.mentioned_as} -> {mention.location_name}")
                print(f"     Location: {mention.latitude}, {mention.longitude}")
                print(f"     Context: {mention.context[:100]}...")
                print()
        
        # Clean up
        gazetteer.close()
        db_manager.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error processing book: {e}")
        return False

if __name__ == "__main__":
    # Example usage
    url = "https://www.gutenberg.org/cache/epub/49266/pg49266.txt"
    success = process_book(url)
    if success:
        print("Book processing completed successfully!")
    else:
        print("Book processing failed!")
