from flask import Flask, jsonify, request, render_template
import sqlite3
from difflib import get_close_matches
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Configuration ---
DATABASE_FILE = 'history_map.db'

# Initialize the Flask application
app = Flask(__name__)

# --- Database Configuration ---
def get_database_type() -> str:
    """Determine which database to use based on environment variables."""
    if os.getenv('DB_TYPE') == 'postgresql':
        return 'postgresql'
    return 'sqlite'  # Default fallback

def get_db_connection():
    """Creates a connection to the database based on configuration."""
    db_type = get_database_type()
    
    if db_type == 'postgresql':
        return get_postgresql_connection()
    else:
        return get_sqlite_connection()

def get_sqlite_connection():
    """Creates a connection to the SQLite database (existing functionality)."""
    conn = sqlite3.connect(DATABASE_FILE)
    # This allows us to access columns by name (like a dictionary)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrent performance
    conn.execute("PRAGMA journal_mode=WAL")
    # Set timeout to avoid busy database errors
    conn.execute("PRAGMA busy_timeout=5000")
    # Additional performance optimizations
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=10000")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn

def get_postgresql_connection():
    """Creates a connection to the PostgreSQL database."""
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

def optimize_database():
    """Create indexes and optimize the database for better performance."""
    db_type = get_database_type()
    
    if db_type == 'postgresql':
        optimize_postgresql_database()
    else:
        optimize_sqlite_database()

def optimize_sqlite_database():
    """Optimize SQLite database (existing functionality)."""
    conn = get_sqlite_connection()
    cursor = conn.cursor()
    
    # Create indexes for frequently queried columns
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_locations_name ON locations(name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_mentions_location_id ON mentions(location_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_mentions_book_id ON mentions(book_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_mentions_position ON mentions(text_position)")
    
    # Analyze the database for better query planning
    cursor.execute("ANALYZE")
    
    conn.commit()
    conn.close()
    print("SQLite database optimized with indexes!")

def optimize_postgresql_database():
    """Optimize PostgreSQL database."""
    try:
        conn = get_postgresql_connection()
        cursor = conn.cursor()
        
        # Create indexes for frequently queried columns
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_locations_name ON locations(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mentions_location_id ON mentions(location_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mentions_book_id ON mentions(book_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mentions_position ON mentions(text_position)")
        
        # Analyze the database for better query planning
        cursor.execute("ANALYZE")
        
        conn.commit()
        cursor.close()
        conn.close()
        print("PostgreSQL database optimized with indexes!")
        
    except Exception as e:
        print(f"Warning: PostgreSQL optimization failed ({e}), falling back to SQLite")
        optimize_sqlite_database()

# --- Web Interface ---
@app.route('/')
def index():
    """Main web interface for the Historical Reference Mapper."""
    return render_template('index.html')

# --- API Endpoints ---

@app.route('/api/locations', methods=['GET'])
def get_all_locations():
    """
    Endpoint to get a list of all unique locations from the database.
    This is useful for populating the map or a dropdown list on the frontend.
    
    Query parameters:
    - limit: Maximum number of locations to return (default: 100)
    - offset: Number of locations to skip (default: 0)
    - search: Optional search term to filter locations
    """
    # Get query parameters with defaults
    limit = request.args.get('limit', default=100, type=int)
    offset = request.args.get('offset', default=0, type=int)
    search = request.args.get('search', default='', type=str)
    
    # Validate parameters
    if limit < 1 or limit > 1000:
        return jsonify({"error": "Limit must be between 1 and 1000"}), 400
    if offset < 0:
        return jsonify({"error": "Offset must be non-negative"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Use a single optimized query with window functions for better performance
        # Only show locations that have references (mentions)
        if search:
            query = """
                SELECT 
                    l.id, l.name, l.latitude, l.longitude,
                    COUNT(*) OVER() as total_count
                FROM locations l
                INNER JOIN mentions m ON l.id = m.location_id
                WHERE l.name LIKE ? 
                GROUP BY l.id, l.name, l.latitude, l.longitude
                ORDER BY l.name 
                LIMIT ? OFFSET ?
            """
            cursor.execute(query, (f'%{search}%', limit, offset))
        else:
            query = """
                SELECT 
                    l.id, l.name, l.latitude, l.longitude,
                    COUNT(*) OVER() as total_count
                FROM locations l
                INNER JOIN mentions m ON l.id = m.location_id
                GROUP BY l.id, l.name, l.latitude, l.longitude
                ORDER BY l.name 
                LIMIT ? OFFSET ?
            """
            cursor.execute(query, (limit, offset))
        
        results = cursor.fetchall()
        
        if not results:
            return jsonify({
                "locations": [],
                "pagination": {
                    "total": 0,
                    "limit": limit,
                    "offset": offset,
                    "has_more": False,
                    "total_pages": 0
                }
            })
        
        # Extract total count from first row
        total_count = results[0]['total_count'] if results else 0
        
        # Convert the database rows to a list of dictionaries
        locations_list = [dict(row) for row in results]
        
        # Add pagination metadata
        response = {
            "locations": locations_list,
            "pagination": {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + limit) < total_count,
                "total_pages": (total_count + limit - 1) // limit
            }
        }
        
        return jsonify(response)
        
    finally:
        conn.close()

@app.route('/api/locations_with_references', methods=['GET'])
def get_locations_with_references():
    """
    Endpoint to get all locations that have references (mentions) from books.
    This is used for the "Show All Locations" button.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        query = """
            SELECT DISTINCT l.id, l.name, l.latitude, l.longitude
            FROM locations l
            INNER JOIN mentions m ON l.id = m.location_id
            ORDER BY l.name
        """
        cursor.execute(query)
        
        locations = cursor.fetchall()
        locations_list = [dict(row) for row in locations]
        
        response = {
            "locations": locations_list,
            "total_locations": len(locations_list)
        }
        
        return jsonify(response)
        
    finally:
        conn.close()

@app.route('/api/books_by_location/<string:location_name>', methods=['GET'])
def get_books_by_location(location_name):
    """
    Endpoint to find all books that mention a specific location.
    The location_name is passed directly in the URL.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # This is the powerful SQL query that joins our three tables
    query = """
        SELECT
            b.id,
            b.title,
            b.url
        FROM
            books b
        JOIN
            mentions m ON b.id = m.book_id
        JOIN
            locations l ON l.id = m.location_id
        WHERE
            l.name = ?
    """
    
    cursor.execute(query, (location_name,))
    books = cursor.fetchall()
    conn.close()
    
    if not books:
        # Return a 404 Not Found error if the location has no mentions
        return jsonify({"error": "Location not found or no books mention it"}), 404
        
    # Convert the database rows to a list of dictionaries
    books_list = [dict(row) for row in books]
    
    return jsonify(books_list)

@app.route('/api/mentions/<string:location_name>', methods=['GET'])
def get_mentions_by_location(location_name):
    """
    Endpoint to get all mentions of a specific location with context and position.
    This provides the rich textual data for researchers.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT
            b.title,
            l.name as location_name,
            l.latitude,
            l.longitude,
            m.text_position,
            m.context
        FROM
            books b
        JOIN
            mentions m ON b.id = m.book_id
        JOIN
            locations l ON l.id = m.location_id
        WHERE
            l.name = ?
        ORDER BY
            m.text_position
    """
    
    cursor.execute(query, (location_name,))
    mentions = cursor.fetchall()
    conn.close()
    
    if not mentions:
        return jsonify({"error": "Location not found or no mentions available"}), 404
        
    mentions_list = [dict(row) for row in mentions]
    return jsonify(mentions_list)

@app.route('/api/mentions_by_year/<string:location_name>', methods=['GET'])
def get_mentions_by_location_and_year(location_name):
    """
    Endpoint to get mentions of a specific location filtered by year range.
    Returns mentions in two tiers: year-matched and year-mismatched/unperiodized.
    """
    start_year = request.args.get('start_year', type=int)
    end_year = request.args.get('end_year', type=int)
    
    # Validate parameters
    if not (start_year and end_year):
        return jsonify({"error": "Both 'start_year' and 'end_year' parameters are required"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get year-matched mentions (books that overlap with the selected range)
        year_matched_query = """
            SELECT
                b.title,
                b.historical_start_year,
                b.historical_end_year,
                l.name as location_name,
                l.latitude,
                l.longitude,
                m.text_position,
                m.context,
                'year_matched' as tier
            FROM
                books b
            JOIN
                mentions m ON b.id = m.book_id
            JOIN
                locations l ON l.id = m.location_id
            WHERE
                l.name = ? 
                AND b.historical_start_year IS NOT NULL 
                AND b.historical_end_year IS NOT NULL
                AND b.historical_start_year <= ? 
                AND b.historical_end_year >= ?
            ORDER BY
                m.text_position
        """
        
        # Get year-mismatched and unperiodized mentions
        other_mentions_query = """
            SELECT
                b.title,
                b.historical_start_year,
                b.historical_end_year,
                l.name as location_name,
                l.latitude,
                l.longitude,
                m.text_position,
                m.context,
                CASE 
                    WHEN b.historical_start_year IS NULL OR b.historical_end_year IS NULL 
                    THEN 'unperiodized'
                    ELSE 'year_mismatched'
                END as tier
            FROM
                books b
            JOIN
                mentions m ON b.id = m.book_id
            JOIN
                locations l ON l.id = m.location_id
            WHERE
                l.name = ?
                AND (
                    b.historical_start_year IS NULL 
                    OR b.historical_end_year IS NULL
                    OR b.historical_start_year > ? 
                    OR b.historical_end_year < ?
                )
            ORDER BY
                m.text_position
        """
        
        # Execute both queries
        cursor.execute(year_matched_query, (location_name, end_year, start_year))
        year_matched = cursor.fetchall()
        
        cursor.execute(other_mentions_query, (location_name, end_year, start_year))
        other_mentions = cursor.fetchall()
        
        # Convert to lists of dictionaries
        year_matched_list = [dict(row) for row in year_matched]
        other_mentions_list = [dict(row) for row in other_mentions]
        
        response = {
            "location_name": location_name,
            "year_range": {
                "start_year": start_year,
                "end_year": end_year
            },
            "primary_tier": {
                "tier_name": "References within selected time period",
                "mentions": year_matched_list,
                "count": len(year_matched_list)
            },
            "secondary_tier": {
                "tier_name": "Additional references outside selected time period",
                "mentions": other_mentions_list,
                "count": len(other_mentions_list),
                "warning_message": "These references are outside the selected date range or have no assigned time period."
            }
        }
        
        return jsonify(response)
        
    finally:
        conn.close()

@app.route('/api/search', methods=['GET'])
def search_locations():
    """
    Endpoint to search locations by name with optimized search.
    Uses database-level search for better performance.
    """
    query = request.args.get('q', '')
    if not query:
        return jsonify({"error": "Search query parameter 'q' is required"}), 400
    
    # Limit query length to prevent abuse
    if len(query) < 2:
        return jsonify({"error": "Search query must be at least 2 characters"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Use database-level search with multiple strategies for better results
        search_pattern = f'%{query}%'
        
        # First try exact match
        cursor.execute("""
            SELECT id, name, latitude, longitude, 1 as relevance
            FROM locations 
            WHERE LOWER(name) = LOWER(?)
        """, (query,))
        exact_matches = cursor.fetchall()
        
        # Then try starts with
        cursor.execute("""
            SELECT id, name, latitude, longitude, 2 as relevance
            FROM locations 
            WHERE LOWER(name) LIKE LOWER(?) AND LOWER(name) != LOWER(?)
        """, (f'{query}%', query))
        starts_with = cursor.fetchall()
        
        # Finally try contains
        cursor.execute("""
            SELECT id, name, latitude, longitude, 3 as relevance
            FROM locations 
            WHERE LOWER(name) LIKE ? 
            AND LOWER(name) NOT LIKE LOWER(?) 
            AND LOWER(name) NOT LIKE LOWER(?)
        """, (search_pattern, f'{query}%', query))
        contains = cursor.fetchall()
        
        # Combine and sort by relevance
        all_results = list(exact_matches) + list(starts_with) + list(contains)
        all_results.sort(key=lambda x: x['relevance'])
        
        # Limit results
        limited_results = all_results[:20]
        
        if not limited_results:
            return jsonify({"error": "No locations found matching your search"}), 404
        
        locations_list = [dict(row) for row in limited_results]
        return jsonify(locations_list)
        
    finally:
        conn.close()

@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    """
    Endpoint to get database statistics.
    Useful for dashboards and understanding the scope of your data.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get counts from each table
    cursor.execute("SELECT COUNT(*) as count FROM books")
    book_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM locations")
    location_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM mentions")
    mention_count = cursor.fetchone()['count']
    
    # Get some interesting stats
    cursor.execute("SELECT COUNT(DISTINCT book_id) as count FROM mentions")
    books_with_mentions = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(DISTINCT location_id) as count FROM mentions")
    locations_with_mentions = cursor.fetchone()['count']
    
    # Get year range covered
    cursor.execute("SELECT MIN(historical_start_year), MAX(historical_end_year) FROM books WHERE historical_start_year IS NOT NULL")
    year_range = cursor.fetchone()
    min_year = year_range[0] if year_range[0] else None
    max_year = year_range[1] if year_range[1] else None
    
    conn.close()
    
    stats = {
        "total_books": book_count,
        "total_locations": location_count,
        "total_mentions": mention_count,
        "books_with_mentions": books_with_mentions,
        "locations_with_mentions": locations_with_mentions,
        "historical_coverage": {
            "earliest_year": min_year,
            "latest_year": max_year,
            "span_years": max_year - min_year if min_year and max_year else None
        },
        "average_mentions_per_book": round(mention_count / book_count, 2) if book_count > 0 else 0,
        "average_mentions_per_location": round(mention_count / location_count, 2) if location_count > 0 else 0
    }
    
    return jsonify(stats)



@app.route('/api/locations_by_year', methods=['GET'])
def get_locations_by_year():
    """
    Endpoint to get locations filtered by year range.
    Query parameters:
    - start_year: Start year for filtering
    - end_year: End year for filtering
    """
    start_year = request.args.get('start_year', type=int)
    end_year = request.args.get('end_year', type=int)
    
    # Validate parameters
    if not (start_year and end_year):
        return jsonify({"error": "Both 'start_year' and 'end_year' parameters are required"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Use year range filtering - only show locations with references
        query = """
            SELECT DISTINCT l.id, l.name, l.latitude, l.longitude,
                   b.historical_start_year, b.historical_end_year
            FROM locations l
            INNER JOIN mentions m ON l.id = m.location_id
            INNER JOIN books b ON m.book_id = b.id
            WHERE (b.historical_start_year <= ? AND b.historical_end_year >= ?)
            ORDER BY l.name
        """
        cursor.execute(query, (end_year, start_year))
        
        locations = cursor.fetchall()
        locations_list = [dict(row) for row in locations]
        
        response = {
            "locations": locations_list,
            "filters": {
                "start_year": start_year,
                "end_year": end_year
            },
            "total_locations": len(locations_list)
        }
        
        return jsonify(response)
        
    finally:
        conn.close()





# --- Error Handlers ---
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Resource not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

@app.errorhandler(400)
def bad_request(error):
    return jsonify({"error": "Bad request"}), 400

# --- Main Execution ---
if __name__ == '__main__':
    # Optimize the database for better performance
    optimize_database()
    
    # The host='0.0.0.0' makes the server accessible on your local network
    # Disable debug mode for better performance in production
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)