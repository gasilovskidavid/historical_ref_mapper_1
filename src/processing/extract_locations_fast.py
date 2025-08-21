#!/usr/bin/env python3
"""
Fast location extraction using in-memory European gazetteer
This version loads the gazetteer once and uses direct lookups instead of database queries
"""

import json
import pickle
import spacy
import requests
from typing import List, Dict, Optional
from dataclasses import dataclass
import os
import sys

# Add the database directory to the path to import enhance_time_periods
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'database'))
from enhance_time_periods import extract_time_periods_from_text

@dataclass
class LocationMention:
    location_name: str
    latitude: float
    longitude: float
    mentioned_as: str
    context: str
    text_position: int
    confidence: float
    country_code: str
    population: int

class FastLocationExtractor:
    def __init__(self, gazetteer_path: str = 'data/gazetteer/european_cities_optimized.pkl'):
        self.gazetteer_path = gazetteer_path
        self.gazetteer = None
        self.nlp = None
        self.load_gazetteer()
        self.load_nlp_model()
    
    def load_gazetteer(self):
        """Load the European gazetteer into memory."""
        try:
            if not os.path.exists(self.gazetteer_path):
                print(f"Gazetteer not found at: {self.gazetteer_path}")
                print("Please run create_optimized_gazetteer.py first")
                return False
            
            print(f"Loading European gazetteer from: {self.gazetteer_path}")
            if self.gazetteer_path.endswith('.pkl'):
                with open(self.gazetteer_path, 'rb') as f:
                    self.gazetteer = pickle.load(f)
            else:
                with open(self.gazetteer_path, 'r', encoding='utf-8') as f:
                    self.gazetteer = json.load(f)
            
            print(f"Loaded {len(self.gazetteer):,} European locations into memory")
            return True
            
        except Exception as e:
            print(f"Error loading gazetteer: {e}")
            return False
    
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
    
    def find_location(self, entity_text: str) -> Optional[Dict]:
        """Find a location in the in-memory gazetteer."""
        if not self.gazetteer:
            return None
        
        # Direct dictionary lookup (much faster than database query)
        key = entity_text.lower()
        if key in self.gazetteer:
            return self.gazetteer[key]
        
        return None
    
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
        Extract location mentions with surrounding context using in-memory gazetteer.
        Returns list of LocationMention objects.
        """
        if not self.nlp or not self.gazetteer:
            print("NLP model or gazetteer not loaded!")
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
                    location_data = self.find_location(ent.text)
                    
                    if location_data:
                        # Calculate context window
                        context_start = max(0, ent.start_char - context_window)
                        context_end = min(len(chunk), ent.end_char + context_window)
                        context = chunk[context_start:context_end].strip()
                        
                        # Calculate confidence based on entity type and text length
                        confidence = self._calculate_confidence(ent, location_data)
                        
                        mention = LocationMention(
                            location_name=location_data['name'],
                            latitude=location_data['lat'],
                            longitude=location_data['lon'],
                            mentioned_as=ent.text,
                            context=context,
                            text_position=chunk_start + ent.start_char,
                            confidence=confidence,
                            country_code=location_data.get('country', ''),
                            population=location_data.get('pop', 0)
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
    
    def process_book(self, url: str) -> Optional[List[LocationMention]]:
        """Process a single book and extract locations."""
        try:
            # Download book
            raw_text = self.download_book(url)
            if not raw_text:
                return None
            
            # Extract title
            title = self.extract_book_title(raw_text)
            print(f"Processing: {title}")
            
            # Clean text
            clean_text = self.clean_gutenberg_text(raw_text)
            
            # Extract locations
            mentions = self.extract_locations_with_context(clean_text)
            
            if mentions:
                print(f"Found {len(mentions)} location mentions")
                return mentions
            else:
                print("No locations found")
                return []
                
        except Exception as e:
            print(f"Error processing book: {e}")
            return None

def main():
    """Test the fast location extractor."""
    print("Fast European Location Extractor Test")
    print("=" * 50)
    
    extractor = FastLocationExtractor()
    
    if not extractor.gazetteer or not extractor.nlp:
        print("Failed to initialize extractor")
        return
    
    # Test with a sample book
    test_url = "https://www.gutenberg.org/cache/epub/49266/pg49266.txt"
    print(f"\nTesting with: {test_url}")
    
    success = extractor.process_book(test_url)
    if success:
        print("Book processing completed successfully!")
    else:
        print("Book processing failed!")

if __name__ == "__main__":
    main()
