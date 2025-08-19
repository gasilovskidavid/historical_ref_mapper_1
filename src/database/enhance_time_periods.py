import sqlite3
import re
from datetime import datetime

def enhance_database_with_time_periods():
    """Enhance the database schema to include time period analysis."""
    conn = sqlite3.connect('history_map.db')
    cursor = conn.cursor()
    
    print("Enhancing database with time period analysis...")
    
    # 1. Add time period columns to books table
    cursor.execute("""
        ALTER TABLE books ADD COLUMN publication_year INTEGER
    """)
    
    cursor.execute("""
        ALTER TABLE books ADD COLUMN historical_start_year INTEGER
    """)
    
    cursor.execute("""
        ALTER TABLE books ADD COLUMN historical_end_year INTEGER
    """)
    
    cursor.execute("""
        ALTER TABLE books ADD COLUMN time_period_description TEXT
    """)
    
    # 2. Add time period columns to locations table
    cursor.execute("""
        ALTER TABLE locations ADD COLUMN first_mentioned_year INTEGER
    """)
    
    cursor.execute("""
        ALTER TABLE locations ADD COLUMN period_of_significance TEXT
    """)
    
    # 3. Add time period columns to mentions table
    cursor.execute("""
        ALTER TABLE mentions ADD COLUMN estimated_year INTEGER
    """)
    
    cursor.execute("""
        ALTER TABLE mentions ADD COLUMN time_context TEXT
    """)
    
    # 4. Create new time_periods table for reference
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS time_periods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            start_year INTEGER,
            end_year INTEGER,
            description TEXT,
            region TEXT
        )
    """)
    
    # 5. Insert common historical periods
    periods = [
        ("Early Middle Ages", 500, 1000, "Migration period, Carolingian Empire", "Europe"),
        ("High Middle Ages", 1000, 1300, "Crusades, rise of cities, Gothic architecture", "Europe"),
        ("Late Middle Ages", 1300, 1500, "Black Death, Hundred Years War, Renaissance begins", "Europe"),
        ("Early Modern Period", 1500, 1800, "Age of Discovery, Reformation, Enlightenment", "Europe"),
        ("Roman Empire", -27, 476, "Classical Roman civilization", "Mediterranean"),
        ("Byzantine Empire", 330, 1453, "Eastern Roman Empire", "Eastern Mediterranean"),
        ("Islamic Golden Age", 750, 1258, "Abbasid Caliphate, scientific advances", "Middle East"),
        ("Viking Age", 793, 1066, "Norse exploration and raids", "Northern Europe"),
        ("Crusader States", 1098, 1291, "Christian kingdoms in the Levant", "Middle East"),
        ("Holy Roman Empire", 800, 1806, "Medieval and early modern German empire", "Central Europe")
    ]
    
    cursor.executemany("""
        INSERT OR IGNORE INTO time_periods (name, start_year, end_year, description, region)
        VALUES (?, ?, ?, ?, ?)
    """, periods)
    
    # 6. Update existing book with time period information
    cursor.execute("""
        UPDATE books 
        SET 
            publication_year = 1895,
            historical_start_year = 918,
            historical_end_year = 1273,
            time_period_description = 'High Middle Ages: Holy Roman Empire and Papacy conflicts'
        WHERE title = 'The Empire and the Papacy, 918-1273'
    """)
    
    # 7. Create indexes for time-based queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_books_publication_year ON books(publication_year)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_books_historical_start ON books(historical_start_year)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_books_historical_end ON books(historical_end_year)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_mentions_estimated_year ON mentions(estimated_year)")
    
    conn.commit()
    conn.close()
    print("Database enhanced with time period analysis!")

def extract_time_periods_from_text(text):
    """Extract time periods and dates from text content."""
    time_patterns = {
        'year': r'\b(1[0-9]{3}|2[0-9]{3})\b',  # Years 1000-2999
        'century': r'\b(\d{1,2})(?:st|nd|rd|th)\s+century\b',  # 1st century, 2nd century, etc.
        'era': r'\b(BCE?|AD|CE)\b',  # Before Christ, Anno Domini, Common Era
        'dynasty': r'\b(?:House of|Dynasty of|reign of)\s+([A-Z][a-z]+)\b',
        'period': r'\b(?:during|in|the)\s+([A-Z][a-z]+\s+(?:period|era|age))\b'
    }
    
    extracted_times = {}
    
    for time_type, pattern in time_patterns.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            extracted_times[time_type] = list(set(matches))
    
    return extracted_times

def analyze_mentions_with_time_context():
    """Analyze existing mentions to add time context."""
    conn = sqlite3.connect('history_map.db')
    cursor = conn.cursor()
    
    print("Analyzing mentions for time context...")
    
    # Get all mentions with their context
    cursor.execute("""
        SELECT m.id, m.context, m.text_position, b.historical_start_year, b.historical_end_year
        FROM mentions m
        JOIN books b ON m.book_id = b.id
        WHERE m.time_context IS NULL
    """)
    
    mentions = cursor.fetchall()
    
    for mention in mentions:
        mention_id, context, position, start_year, end_year = mention
        
        # Extract time information from context
        time_info = extract_time_periods_from_text(context)
        
        # Estimate year based on position in text and book's time range
        if start_year and end_year:
            # Simple linear interpolation based on position in text
            # This is a rough estimate - could be improved with more sophisticated analysis
            estimated_year = start_year + int((position / 1000000) * (end_year - start_year))
        else:
            estimated_year = None
        
        # Create time context description
        time_context_parts = []
        if time_info.get('year'):
            time_context_parts.append(f"Years mentioned: {', '.join(time_info['year'])}")
        if time_info.get('century'):
            time_context_parts.append(f"Centuries: {', '.join(time_info['century'])}")
        if time_info.get('period'):
            time_context_parts.append(f"Periods: {', '.join(time_info['period'])}")
        
        time_context = "; ".join(time_context_parts) if time_context_parts else "No specific time mentioned"
        
        # Update the mention with time information
        cursor.execute("""
            UPDATE mentions 
            SET estimated_year = ?, time_context = ?
            WHERE id = ?
        """, (estimated_year, time_context, mention_id))
    
    conn.commit()
    conn.close()
    print("Time context analysis complete!")

if __name__ == "__main__":
    enhance_database_with_time_periods()
    analyze_mentions_with_time_context()
    print("\n🎉 Time period analysis system ready!")
    print("\nNew capabilities:")
    print("- Book publication and historical coverage dates")
    print("- Location time periods and significance")
    print("- Mention-specific time context and estimated years")
    print("- Historical period reference table")
    print("- Time-based querying and filtering")

