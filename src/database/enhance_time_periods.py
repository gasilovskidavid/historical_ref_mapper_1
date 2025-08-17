import sqlite3
import re
from datetime import datetime

def enhance_database_with_time_periods():
    """Enhance the database schema to include time period analysis."""
    conn = sqlite3.connect('history_map.db')
    cursor = conn.cursor()
    
    print("Enhancing database with time period analysis...")
    
    # Helper function to safely add columns
    def add_column_if_not_exists(table, column, definition):
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            print(f"✓ Added column {table}.{column}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"ℹ️  Column {table}.{column} already exists")
            else:
                raise e
    
    # 1. Add time period columns to books table
    add_column_if_not_exists('books', 'publication_year', 'INTEGER')
    add_column_if_not_exists('books', 'historical_start_year', 'INTEGER')
    add_column_if_not_exists('books', 'historical_end_year', 'INTEGER')
    add_column_if_not_exists('books', 'time_period_description', 'TEXT')
    add_column_if_not_exists('books', 'description', 'TEXT')
    add_column_if_not_exists('books', 'period_status', 'TEXT DEFAULT "unknown"')
    
    # 2. Add time period columns to locations table
    add_column_if_not_exists('locations', 'first_mentioned_year', 'INTEGER')
    add_column_if_not_exists('locations', 'period_of_significance', 'TEXT')
    
    # 3. Add time period columns to mentions table
    add_column_if_not_exists('mentions', 'estimated_year', 'INTEGER')
    add_column_if_not_exists('mentions', 'time_context', 'TEXT')
    
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
    
    # 6. Update existing book with time period information (only if it exists)
    cursor.execute("SELECT COUNT(*) FROM books WHERE title = 'The Empire and the Papacy, 918-1273'")
    if cursor.fetchone()[0] > 0:
        cursor.execute("""
            UPDATE books 
            SET 
                publication_year = 1895,
                historical_start_year = 918,
                historical_end_year = 1273,
                time_period_description = 'High Middle Ages: Holy Roman Empire and Papacy conflicts'
            WHERE title = 'The Empire and the Papacy, 918-1273'
        """)
        print("✓ Updated existing book with time period information")
    
    # 7. Create indexes for time-based queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_books_publication_year ON books(publication_year)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_books_historical_start ON books(historical_start_year)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_books_historical_end ON books(historical_end_year)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_mentions_estimated_year ON mentions(estimated_year)")
    
    conn.commit()
    conn.close()
    print("Database enhanced with time period analysis!")

def extract_time_periods_from_text(text):
    """Extract time periods and dates from text content with enhanced parsing."""
    if not text:
        return {}
    
    text = text.strip()
    extracted_times = {}
    
    # 1. Extract year ranges (e.g., "918-1273", "500-1500", "c. 1000-1200")
    year_range_patterns = [
        r'\b(\d{3,4})\s*[-–—]\s*(\d{3,4})\b',  # 918-1273, 500-1500
        r'\bc\.?\s*(\d{3,4})\s*[-–—]\s*(\d{3,4})\b',  # c. 1000-1200, c.1000-1200
        r'\b(\d{3,4})\s*to\s*(\d{3,4})\b',  # 1000 to 1200
        r'\b(\d{3,4})\s*through\s*(\d{3,4})\b',  # 1000 through 1200
        r'\b(\d{3,4})\s*until\s*(\d{3,4})\b',  # 1000 until 1200
    ]
    
    for pattern in year_range_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            extracted_times['year_ranges'] = []
            for match in matches:
                start_year, end_year = int(match[0]), int(match[1])
                if 500 <= start_year <= 2000 and 500 <= end_year <= 2000:
                    extracted_times['year_ranges'].append({
                        'start': start_year,
                        'end': end_year,
                        'text': f"{start_year}-{end_year}"
                    })
            break  # Use first pattern that finds matches
    
    # 2. Extract single years (e.g., "in 1066", "during 1200", "year 1453")
    single_year_patterns = [
        r'\b(?:in|during|year|of)\s+(\d{3,4})\b',  # in 1066, during 1200, year 1453
        r'\b(\d{3,4})\s+(?:AD|CE)\b',  # 1066 AD, 1200 CE
        r'\b(\d{3,4})\s+(?:BC|BCE)\b',  # 500 BC, 500 BCE
        r'\b(?:the year)\s+(\d{3,4})\b',  # the year 1066
    ]
    
    single_years = []
    for pattern in single_year_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            year = int(match) if match.isdigit() else int(match[0]) if match[0].isdigit() else None
            if year and 500 <= year <= 2000:
                single_years.append(year)
    
    if single_years:
        extracted_times['single_years'] = list(set(single_years))
    
    # 3. Extract centuries (e.g., "12th century", "twelfth century", "XII century")
    century_patterns = [
        r'\b(\d{1,2})(?:st|nd|rd|th)\s+century\b',  # 12th century, 1st century
        r'\b(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)\s+century\b',  # the 12th century
        r'\b(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|eighteenth|nineteenth|twentieth)\s+century\b',  # twelfth century
        r'\b(?:I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII|XIII|XIV|XV|XVI|XVII|XVIII|XIX|XX)\s+century\b',  # XII century
    ]
    
    centuries = []
    for pattern in century_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if match.isdigit():
                century = int(match)
            else:
                # Convert word/roman numeral to century number
                century = convert_to_century_number(match)
            if century and 1 <= century <= 20:
                centuries.append(century)
    
    if centuries:
        extracted_times['centuries'] = list(set(centuries))
    
    # 4. Extract historical periods and eras
    period_patterns = [
        r'\b(?:during|in|the|of)\s+([A-Z][a-z]+\s+(?:period|era|age|epoch))\b',  # during the Medieval period
        r'\b(?:the\s+)?([A-Z][a-z]+\s+[A-Z][a-z]+\s+(?:period|era|age|epoch))\b',  # the Early Modern period
        r'\b(?:during|in|the)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)\b',  # during the Middle Ages
    ]
    
    periods = []
    for pattern in period_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            period = match.strip()
            if len(period) > 3:  # Filter out very short matches
                periods.append(period)
    
    if periods:
        extracted_times['periods'] = list(set(periods))
    
    # 5. Extract dynasty and reign information
    dynasty_patterns = [
        r'\b(?:House of|Dynasty of|reign of|rule of)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b',  # House of Tudor, Dynasty of Abbasid
        r'\b(?:under|during)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:dynasty|reign|rule)\b',  # under Ottoman dynasty
        r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:dynasty|reign|rule)\b',  # Tudor dynasty
    ]
    
    dynasties = []
    for pattern in dynasty_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            dynasty = match.strip()
            if len(dynasty) > 2:  # Filter out very short matches
                dynasties.append(dynasty)
    
    if dynasties:
        extracted_times['dynasties'] = list(set(dynasties))
    
    # 6. Extract era indicators
    era_patterns = [
        r'\b(BCE?|AD|CE|BC)\b',  # Before Christ, Anno Domini, Common Era
        r'\b(?:before|after)\s+(?:Christ|Common Era)\b',  # before Christ, after Common Era
    ]
    
    eras = []
    for pattern in era_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            era = match.strip()
            if era:
                eras.append(era)
    
    if eras:
        extracted_times['eras'] = list(set(eras))
    
    # 7. Extract approximate dates (e.g., "around 1000", "circa 1200")
    approx_patterns = [
        r'\b(?:around|about|circa|c\.?|approximately|roughly)\s+(\d{3,4})\b',  # around 1000, circa 1200
        r'\b(?:early|mid|late)\s+(\d{1,2})(?:st|nd|rd|th)\s+century\b',  # early 12th century
        r'\b(?:early|mid|late)\s+(\d{3,4})s\b',  # early 1200s, mid 1500s
    ]
    
    approx_dates = []
    for pattern in approx_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if match.isdigit():
                year = int(match)
                if 500 <= year <= 2000:
                    approx_dates.append(year)
            elif 's' in match.lower():
                # Handle "1200s" format
                year_str = match.replace('s', '').replace('S', '')
                if year_str.isdigit():
                    year = int(year_str)
                    if 500 <= year <= 2000:
                        approx_dates.append(year)
    
    if approx_dates:
        extracted_times['approximate_dates'] = list(set(approx_dates))
    
    return extracted_times

def convert_to_century_number(text):
    """Convert word or roman numeral century to number."""
    text = text.lower().strip()
    
    # Word to number mapping
    word_to_num = {
        'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5,
        'sixth': 6, 'seventh': 7, 'eighth': 8, 'ninth': 9, 'tenth': 10,
        'eleventh': 11, 'twelfth': 12, 'thirteenth': 13, 'fourteenth': 14,
        'fifteenth': 15, 'sixteenth': 16, 'seventeenth': 17, 'eighteenth': 18,
        'nineteenth': 19, 'twentieth': 20
    }
    
    # Roman numeral to number mapping
    roman_to_num = {
        'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6, 'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10,
        'XI': 11, 'XII': 12, 'XIII': 13, 'XIV': 14, 'XV': 15, 'XVI': 16, 'XVII': 17, 'XVIII': 18, 'XIX': 19, 'XX': 20
    }
    
    if text in word_to_num:
        return word_to_num[text]
    elif text.upper() in roman_to_num:
        return roman_to_num[text.upper()]
    
    return None

def extract_book_time_period(title, description=None):
    """Extract time period information specifically from book title and description."""
    combined_text = title
    if description:
        combined_text += " " + description
    
    time_info = extract_time_periods_from_text(combined_text)
    
    # Determine the most likely time period for the book
    start_year = None
    end_year = None
    time_description = []
    
    # Priority 1: Year ranges (most specific)
    if 'year_ranges' in time_info and time_info['year_ranges']:
        year_range = time_info['year_ranges'][0]  # Use first found
        start_year = year_range['start']
        end_year = year_range['end']
        time_description.append(f"Years: {year_range['text']}")
    
    # Priority 2: Centuries
    elif 'centuries' in time_info and time_info['centuries']:
        centuries = sorted(time_info['centuries'])
        if len(centuries) == 1:
            century = centuries[0]
            start_year = (century - 1) * 100 + 1
            end_year = century * 100
            time_description.append(f"{century}th century")
        else:
            # Multiple centuries - use range
            start_year = (min(centuries) - 1) * 100 + 1
            end_year = max(centuries) * 100
            time_description.append(f"Centuries: {', '.join([f'{c}th' for c in centuries])}")
    
    # Priority 3: Single years (approximate range)
    elif 'single_years' in time_info and time_info['single_years']:
        years = sorted(time_info['single_years'])
        if len(years) == 1:
            year = years[0]
            start_year = max(500, year - 50)
            end_year = min(2000, year + 50)
            time_description.append(f"Around {year}")
        else:
            # Multiple years - use range
            start_year = max(500, min(years) - 25)
            end_year = min(2000, max(years) + 25)
            time_description.append(f"Years: {', '.join(map(str, years))}")
    
    # Priority 4: Historical periods
    if 'periods' in time_info and time_info['periods']:
        periods = time_info['periods']
        time_description.append(f"Periods: {', '.join(periods)}")
    
    # Priority 5: Dynasties
    if 'dynasties' in time_info and time_info['dynasties']:
        dynasties = time_info['dynasties']
        time_description.append(f"Dynasties: {', '.join(dynasties)}")
    
    # Priority 6: Approximate dates
    if 'approximate_dates' in time_info and time_info['approximate_dates']:
        approx_years = sorted(time_info['approximate_dates'])
        if not start_year and not end_year:
            # Use approximate dates if no other time info
            start_year = max(500, min(approx_years) - 50)
            end_year = min(2000, max(approx_years) + 50)
        time_description.append(f"Approximate: {', '.join(map(str, approx_years))}")
    
    # If we still don't have years, try to infer from periods
    if not start_year and not end_year and 'periods' in time_info:
        start_year, end_year = infer_years_from_periods(time_info['periods'])
        if start_year and end_year:
            time_description.append(f"Inferred from periods: {start_year}-{end_year}")
    
    return {
        'start_year': start_year,
        'end_year': end_year,
        'description': '; '.join(time_description) if time_description else 'Time period extracted from title/description',
        'confidence': 'high' if start_year and end_year else 'medium' if time_description else 'low',
        'period_status': 'known' if start_year and end_year else 'unknown'
    }

def infer_years_from_periods(periods):
    """Infer year ranges from historical period names."""
    period_mappings = {
        'medieval': (500, 1500),
        'middle ages': (500, 1500),
        'early middle ages': (500, 1000),
        'high middle ages': (1000, 1300),
        'late middle ages': (1300, 1500),
        'renaissance': (1300, 1600),
        'early modern': (1500, 1800),
        'modern': (1800, 2000),
        'ancient': (-3000, 500),
        'classical': (-800, 500),
        'roman': (-27, 476),
        'byzantine': (330, 1453),
        'crusades': (1095, 1291),
        'viking': (793, 1066),
        'islamic golden age': (750, 1258),
        'holy roman empire': (800, 1806),
        'ottoman': (1299, 1922),
        'mongol': (1206, 1368),
        'aztec': (1325, 1521),
        'inca': (1438, 1533),
        'mayan': (2000, 1500),  # BCE to CE
        'ancient egypt': (-3100, -30),
        'ancient greece': (-800, -146),
        'ancient rome': (-753, 476),
        'ancient china': (-2100, 220),
        'ancient india': (-3300, 500),
        'ancient mesopotamia': (-3500, -539),
        'ancient persia': (-550, 651),
        'ancient babylon': (-1894, -539),
        'ancient assyria': (-2500, -609),
        'ancient sumer': (-4500, -1900),
        'ancient akkad': (-2334, -2154),
        'ancient ur': (-2100, -2000),
        'ancient uruk': (-4000, -2000),
        'ancient kish': (-3000, -2000),
        'ancient lagash': (-2500, -2000),
        'ancient umma': (-2500, -2000),
        'ancient adab': (-2500, -2000),
        'ancient shuruppak': (-2500, -2000),
        'ancient sippar': (-2500, -2000),
        'ancient nippur': (-2500, -2000),
        'ancient isin': (-2000, -1800),
        'ancient larsa': (-2000, -1800),
        'ancient eshnunna': (-2000, -1800),
        'ancient der': (-2000, -1800),
        'ancient kazallu': (-2000, -1800),
        'ancient malgium': (-2000, -1800),
        'ancient sabum': (-2000, -1800),
        'ancient kazallu': (-2000, -1800),
        'ancient malgium': (-2000, -1800),
        'ancient sabum': (-2000, -1800),
    }
    
    for period in periods:
        period_lower = period.lower()
        for key, (start, end) in period_mappings.items():
            if key in period_lower:
                return start, end
    
    return None, None

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

def update_all_books_with_time_periods():
    """Automatically extract and update time periods for all existing books."""
    conn = sqlite3.connect('history_map.db')
    cursor = conn.cursor()
    
    print("Updating all books with extracted time periods...")
    
    # Get all books that don't have time periods yet
    cursor.execute("""
        SELECT id, title, description 
        FROM books 
        WHERE historical_start_year IS NULL 
        OR historical_end_year IS NULL
    """)
    
    books = cursor.fetchall()
    print(f"Found {len(books)} books to update...")
    
    updated_count = 0
    for book_id, title, description in books:
        try:
            # Extract time period from title and description
            time_info = extract_book_time_period(title, description)
            
            if time_info['start_year'] and time_info['end_year']:
                # Update the book with extracted time period
                cursor.execute("""
                    UPDATE books 
                    SET 
                        historical_start_year = ?,
                        historical_end_year = ?,
                        time_period_description = ?,
                        period_status = ?
                    WHERE id = ?
                """, (
                    time_info['start_year'],
                    time_info['end_year'],
                    time_info['description'],
                    time_info['period_status']
                ))
                
                updated_count += 1
                print(f"✓ Updated '{title}': {time_info['start_year']}-{time_info['end_year']} ({time_info['confidence']} confidence)")
                if description:
                    print(f"  Description: {description[:100]}...")
            else:
                # Mark book as having unknown time period
                cursor.execute("""
                    UPDATE books 
                    SET 
                        period_status = ?,
                        time_period_description = ?
                    WHERE id = ?
                """, (
                    time_info['period_status'],
                    time_info['description']
                ))
                
                print(f"- No time period found for '{title}' - marked as {time_info['period_status']}")
                if description:
                    print(f"  Description: {description[:100]}...")
                
        except Exception as e:
            print(f"✗ Error processing book '{title}': {e}")
    
    conn.commit()
    conn.close()
    
    print(f"\n🎉 Updated {updated_count} out of {len(books)} books with time periods!")
    return updated_count

def mark_books_with_unknown_periods():
    """Explicitly mark books that have no time period information as 'unknown'."""
    conn = sqlite3.connect('history_map.db')
    cursor = conn.cursor()
    
    print("Marking books with unknown time periods...")
    
    # Find books that have NULL values for time periods and no period_status
    cursor.execute("""
        SELECT id, title 
        FROM books 
        WHERE (historical_start_year IS NULL OR historical_end_year IS NULL)
        AND (period_status IS NULL OR period_status = 'unknown')
    """)
    
    unknown_books = cursor.fetchall()
    print(f"Found {len(unknown_books)} books to mark as unknown...")
    
    marked_count = 0
    for book_id, title in unknown_books:
        try:
            cursor.execute("""
                UPDATE books 
                SET 
                    period_status = 'unknown',
                    time_period_description = 'No time period information available'
                WHERE id = ?
            """, (book_id,))
            
            marked_count += 1
            print(f"✓ Marked '{title}' as unknown period")
            
        except Exception as e:
            print(f"✗ Error marking book '{title}': {e}")
    
    conn.commit()
    conn.close()
    
    print(f"\n🎯 Marked {marked_count} books as having unknown time periods!")
    return marked_count

def show_time_period_statistics():
    """Show statistics about time period coverage in the database."""
    conn = sqlite3.connect('history_map.db')
    cursor = conn.cursor()
    
    print("\n📊 Time Period Coverage Statistics:")
    print("=" * 50)
    
    # Total books
    cursor.execute("SELECT COUNT(*) FROM books")
    total_books = cursor.fetchone()[0]
    
    # Books with time periods
    cursor.execute("SELECT COUNT(*) FROM books WHERE historical_start_year IS NOT NULL AND historical_end_year IS NOT NULL")
    books_with_periods = cursor.fetchone()[0]
    
    # Books without time periods
    books_without_periods = total_books - books_with_periods
    
    print(f"Total books: {total_books}")
    print(f"Books with time periods: {books_with_periods} ({books_with_periods/total_books*100:.1f}%)")
    print(f"Books without time periods: {books_without_periods} ({books_without_periods/total_books*100:.1f}%)")
    
    # Show period status breakdown
    cursor.execute("SELECT period_status, COUNT(*) FROM books GROUP BY period_status")
    status_counts = cursor.fetchall()
    
    if status_counts:
        print(f"\n📋 Period Status Breakdown:")
        for status, count in status_counts:
            percentage = (count / total_books) * 100
            print(f"  {status.capitalize()}: {count} ({percentage:.1f}%)")
    
    # Time period distribution
    if books_with_periods > 0:
        print(f"\n📅 Time Period Distribution:")
        
        # Early Middle Ages (500-1000)
        cursor.execute("SELECT COUNT(*) FROM books WHERE historical_start_year >= 500 AND historical_end_year <= 1000")
        early_medieval = cursor.fetchone()[0]
        
        # High Middle Ages (1000-1300)
        cursor.execute("SELECT COUNT(*) FROM books WHERE historical_start_year >= 1000 AND historical_end_year <= 1300")
        high_medieval = cursor.fetchone()[0]
        
        # Late Middle Ages (1300-1500)
        cursor.execute("SELECT COUNT(*) FROM books WHERE historical_start_year >= 1300 AND historical_end_year <= 1500")
        late_medieval = cursor.fetchone()[0]
        
        # Early Modern (1500-1800)
        cursor.execute("SELECT COUNT(*) FROM books WHERE historical_start_year >= 1500 AND historical_end_year <= 1800")
        early_modern = cursor.fetchone()[0]
        
        # Modern (1800+)
        cursor.execute("SELECT COUNT(*) FROM books WHERE historical_start_year >= 1800")
        modern = cursor.fetchone()[0]
        
        print(f"  Early Middle Ages (500-1000): {early_medieval}")
        print(f"  High Middle Ages (1000-1300): {high_medieval}")
        print(f"  Late Middle Ages (1300-1500): {late_medieval}")
        print(f"  Early Modern (1500-1800): {early_modern}")
        print(f"  Modern (1800+): {modern}")
    
    conn.close()

def force_re_extract_all_time_periods():
    """Force re-extract time periods from all books, even if they already have period_status."""
    conn = sqlite3.connect('history_map.db')
    cursor = conn.cursor()
    
    print("Force re-extracting time periods from all books...")
    
    # Get all books
    cursor.execute("SELECT id, title, description FROM books")
    books = cursor.fetchall()
    print(f"Found {len(books)} books to process...")
    
    updated_count = 0
    for book_id, title, description in books:
        try:
            print(f"\nProcessing: {title}")
            
            # Extract time period from title and description
            time_info = extract_book_time_period(title, description)
            
            if time_info['start_year'] and time_info['end_year']:
                # Update the book with extracted time period
                cursor.execute("""
                    UPDATE books 
                    SET 
                        historical_start_year = ?,
                        historical_end_year = ?,
                        time_period_description = ?,
                        period_status = ?
                    WHERE id = ?
                """, (
                    time_info['start_year'],
                    time_info['end_year'],
                    time_info['description'],
                    time_info['period_status'],
                    book_id
                ))
                
                updated_count += 1
                print(f"✓ Extracted: {time_info['start_year']}-{time_info['end_year']} ({time_info['confidence']} confidence)")
                print(f"  Description: {time_info['description']}")
            else:
                # Mark book as having unknown time period
                cursor.execute("""
                    UPDATE books 
                    SET 
                        period_status = ?,
                        time_period_description = ?
                    WHERE id = ?
                """, (
                    time_info['period_status'],
                    time_info['description'],
                    book_id
                ))
                
                print(f"⚠️  No time period found - marked as {time_info['period_status']}")
                print(f"  Description: {time_info['description']}")
                
        except Exception as e:
            print(f"✗ Error processing book '{title}': {e}")
    
    conn.commit()
    conn.close()
    
    print(f"\n🎉 Force re-extraction complete! Updated {updated_count} out of {len(books)} books.")
    return updated_count

if __name__ == "__main__":
    print("🚀 Starting Time Period Enhancement System...")
    print("=" * 60)
    
    # 1. Enhance database schema
    enhance_database_with_time_periods()
    
    # 2. Force re-extract time periods from all books
    updated_count = force_re_extract_all_time_periods()
    
    # 3. Mark books with unknown periods explicitly
    marked_unknown = mark_books_with_unknown_periods()
    
    # 4. Analyze mentions for time context
    analyze_mentions_with_time_context()
    
    # 5. Show statistics
    show_time_period_statistics()
    
    print("\n🎉 Time period analysis system ready!")
    print("\nNew capabilities:")
    print("- Automatic time period extraction from book titles and descriptions")
    print("- Enhanced pattern recognition for years, centuries, and historical periods")
    print("- Explicit period status tracking (known vs unknown)")
    print("- Book publication and historical coverage dates")
    print("- Location time periods and significance")
    print("- Mention-specific time context and estimated years")
    print("- Historical period reference table")
    print("- Time-based querying and filtering")
    print(f"- {updated_count} books automatically updated with time periods")
    print(f"- {marked_unknown} books marked as having unknown periods")

