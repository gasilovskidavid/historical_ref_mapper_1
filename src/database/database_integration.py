import json
import spacy
import requests
import sqlite3 
import os
from typing import Optional, Union
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Database Configuration ---
def get_database_type() -> str:
    """Determine which database to use based on environment variables."""
    if os.getenv('DB_TYPE') == 'postgresql':
        return 'postgresql'
    return 'sqlite'  # Default fallback

def get_db_connection():
    """Get database connection based on configuration."""
    db_type = get_database_type()
    
    if db_type == 'postgresql':
        return get_postgresql_connection()
    else:
        return get_sqlite_connection()

def get_sqlite_connection():
    """Get SQLite connection (existing functionality)."""
    conn = sqlite3.connect('history_map.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_postgresql_connection():
    """Get PostgreSQL connection."""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT', 5432),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD')
        )
        return conn
    except ImportError:
        print("Warning: psycopg2 not installed, falling back to SQLite")
        return get_sqlite_connection()
    except Exception as e:
        print(f"Warning: PostgreSQL connection failed ({e}), falling back to SQLite")
        return get_sqlite_connection()

# --- Database Functions ---
def setup_database(db_file):
    """Creates the database and tables if they don't exist."""
    db_type = get_database_type()
    
    if db_type == 'postgresql':
        setup_postgresql_database()
    else:
        setup_sqlite_database(db_file)

def setup_sqlite_database(db_file):
    """Setup SQLite database (existing functionality)."""
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Create the books table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL UNIQUE,
        url TEXT
    )''')
    
    # Create the locations table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL
    )''')
    
    # Create the mentions linking table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS mentions (
        book_id INTEGER,
        location_id INTEGER,
        text_position INTEGER,
        context TEXT,
        FOREIGN KEY (book_id) REFERENCES books (id),
        FOREIGN KEY (location_id) REFERENCES locations (id),
        PRIMARY KEY (book_id, location_id)
    )''')
    
    conn.commit()
    conn.close()
    print(f"SQLite database '{db_file}' is set up.")

def setup_postgresql_database():
    """Setup PostgreSQL database."""
    try:
        conn = get_postgresql_connection()
        cursor = conn.cursor()
        
        # Create the books table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id SERIAL PRIMARY KEY,
            title VARCHAR(500) NOT NULL UNIQUE,
            url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Create the locations table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS locations (
            id SERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL UNIQUE,
            latitude DOUBLE PRECISION NOT NULL,
            longitude DOUBLE PRECISION NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Create the mentions linking table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS mentions (
            id SERIAL PRIMARY KEY,
            book_id INTEGER,
            location_id INTEGER,
            text_position INTEGER,
            context TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (book_id) REFERENCES books (id),
            FOREIGN KEY (location_id) REFERENCES locations (id)
        )''')
        
        # Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_books_title ON books(title)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_locations_name ON locations(name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_mentions_book_id ON mentions(book_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_mentions_location_id ON mentions(location_id)')
        
        conn.commit()
        cursor.close()
        conn.close()
        print("PostgreSQL database is set up.")
        
    except Exception as e:
        print(f"Warning: PostgreSQL setup failed ({e}), falling back to SQLite")
        setup_sqlite_database('history_map.db')

def save_results_to_db(db_file, book_title, book_url, found_locations):
    """Saves the analysis results to the database."""
    db_type = get_database_type()
    
    if db_type == 'postgresql':
        save_results_to_postgresql(book_title, book_url, found_locations)
    else:
        save_results_to_sqlite(db_file, book_title, book_url, found_locations)

def save_results_to_sqlite(db_file, book_title, book_url, found_locations):
    """Save results to SQLite (existing functionality)."""
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # 1. Add the book and get its ID
    cursor.execute("INSERT OR IGNORE INTO books (title, url) VALUES (?, ?)", (book_title, book_url))
    cursor.execute("SELECT id FROM books WHERE title = ?", (book_title,))
    book_id = cursor.fetchone()[0]
    
    # 2. Add the locations and the mentions with context
    total_mentions = 0
    for name, data in found_locations.items():
        # Add the location and get its ID
        cursor.execute("INSERT OR IGNORE INTO locations (name, latitude, longitude) VALUES (?, ?, ?)",
                       (name, data['lat'], data['lon']))
        cursor.execute("SELECT id FROM locations WHERE name = ?", (name,))
        location_id = cursor.fetchone()[0]
        
        # Add each mention with its context
        for mention in data['mentions']:
            cursor.execute("INSERT OR IGNORE INTO mentions (book_id, location_id, text_position, context) VALUES (?, ?, ?, ?)",
                           (book_id, location_id, mention['position'], mention['context']))
            total_mentions += 1

    conn.commit()
    conn.close()
    print(f"Successfully saved {total_mentions} mentions for '{book_title}' to SQLite database.")

def save_results_to_postgresql(book_title, book_url, found_locations):
    """Save results to PostgreSQL."""
    try:
        conn = get_postgresql_connection()
        cursor = conn.cursor()
        
        # 1. Add the book and get its ID
        cursor.execute("INSERT INTO books (title, url) VALUES (%s, %s) ON CONFLICT (title) DO NOTHING", (book_title, book_url))
        cursor.execute("SELECT id FROM books WHERE title = %s", (book_title,))
        result = cursor.fetchone()
        if result:
            book_id = result[0]
        else:
            # Book was already there, get its ID
            cursor.execute("SELECT id FROM books WHERE title = %s", (book_title,))
            book_id = cursor.fetchone()[0]
        
        # 2. Add the locations and the mentions with context
        total_mentions = 0
        for name, data in found_locations.items():
            # Add the location and get its ID
            cursor.execute("INSERT INTO locations (name, latitude, longitude) VALUES (%s, %s, %s) ON CONFLICT (name) DO NOTHING",
                           (name, data['lat'], data['lon']))
            cursor.execute("SELECT id FROM locations WHERE name = %s", (name,))
            result = cursor.fetchone()
            if result:
                location_id = result[0]
            else:
                # Location was already there, get its ID
                cursor.execute("SELECT id FROM locations WHERE name = %s", (name,))
                location_id = cursor.fetchone()[0]
            
            # Add each mention with its context
            cursor.execute("INSERT INTO mentions (book_id, location_id, text_position, context) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                           (book_id, location_id, mention['position'], mention['context']))
            total_mentions += 1

        conn.commit()
        cursor.close()
        conn.close()
        print(f"Successfully saved {total_mentions} mentions for '{book_title}' to PostgreSQL database.")
        
    except Exception as e:
        print(f"Warning: PostgreSQL save failed ({e}), falling back to SQLite")
        save_results_to_sqlite('history_map.db', book_title, book_url, found_locations)


# --- Data Processing Functions ---
def load_gazetteer_lookup(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return None

def get_book_text(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException:
        return None

def clean_gutenberg_text(text):
    start_marker = "*** START OF THE PROJECT GUTENBERG EBOOK"
    end_marker = "*** END OF THE PROJECT GUTENBERG EBOOK"
    try:
        start_index = text.index(start_marker)
        text_after_start = text[start_index + len(start_marker):]
        end_index = text_after_start.index(end_marker)
        return text_after_start[:end_index].strip()
    except ValueError:
        return text

def extract_entities(text):
    """Extracts potential named entities from the full text by processing in chunks."""
    nlp = spacy.load("en_core_web_sm")
    
    # Increase the maximum text length limit
    nlp.max_length = 2000000  
    
    print(f"Processing text of length {len(text):,} characters with spaCy...")
    
    # Process in chunks to avoid memory issues
    chunk_size = 500000  
    all_entities = set()
    
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i + chunk_size]
        print(f"Processing chunk {i//chunk_size + 1} (characters {i:,} to {min(i + chunk_size, len(text)):,})...")
        
        doc = nlp(chunk)
        chunk_entities = [ent.text.strip() for ent in doc.ents if len(ent.text.strip()) > 2]
        all_entities.update(chunk_entities)
    
    print(f"Extracted {len(all_entities)} unique entities from all chunks.")
    return list(all_entities)

def match_locations_with_context(text, entities, gazetteer_lookup):
    """Matches entities against gazetteer and captures text position and context."""
    found_locations = {}
    
    for ent in entities:
        lookup_key = ent.lower()
        if lookup_key in gazetteer_lookup:
            record = gazetteer_lookup[lookup_key]
            main_name = record['name']
            
            # Find the position of this entity in the text
            pos = text.find(ent)
            if pos != -1:
                # Extract context around the mention (100 characters before and after)
                start = max(0, pos - 100)
                end = min(len(text), pos + len(ent) + 100)
                context = text[start:end].replace('\n', ' ').strip()
                
                if main_name not in found_locations:
                    found_locations[main_name] = {
                        "lat": record['lat'], 
                        "lon": record['lon'],
                        "mentions": []
                    }
                
                found_locations[main_name]["mentions"].append({
                    "text": ent,
                    "position": pos,
                    "context": context
                })
    
    return found_locations

# --- Main Execution ---
if __name__ == "__main__":
    DB_FILE = 'history_map.db'
    GAZETTEER_LOOKUP_FILE = 'hre_gazetteer_lookup.json'
    
    # Step 1: Set up the database file and tables
    setup_database(DB_FILE)
    
    # Step 2: Load the gazetteer
    gazetteer = load_gazetteer_lookup(GAZETTEER_LOOKUP_FILE)
    if not gazetteer:
        print("Gazetteer lookup file not found. Please run 'preprocess_gazetteer.py' first.")
    else:
        # Step 3: Process the book
        BOOK_URL = "https://www.gutenberg.org/cache/epub/61419/pg61419.txt"
        BOOK_TITLE = "The Empire and the Papacy, 918-1273"  # Historical text about medieval Europe
        
        print(f"\nStarting analysis for '{BOOK_TITLE}'...")
        raw_text = get_book_text(BOOK_URL)
        
        if raw_text:
            book_text = clean_gutenberg_text(raw_text)
            entities_from_text = extract_entities(book_text)
            results = match_locations_with_context(book_text, entities_from_text, gazetteer)
            
            # Step 4: Save the results to the database
            if results:
                save_results_to_db(DB_FILE, BOOK_TITLE, BOOK_URL, results)
            else:
                print("No known locations found in the text.")
