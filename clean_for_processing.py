import sqlite3

print("Cleaning database for fresh processing...")

# Connect to the database
conn = sqlite3.connect('history_map.db')
cursor = conn.cursor()

try:
    # Clear processed data but keep gazetteer locations
    cursor.execute("DELETE FROM mentions")
    cursor.execute("DELETE FROM books")
    
    # Try to reset auto-increment counters if sqlite_sequence exists
    try:
        cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('books', 'mentions')")
        print("- Auto-increment counters reset")
    except:
        print("- No sqlite_sequence table found (this is normal)")
    
    # Commit changes
    conn.commit()
    
    print("Database cleaned successfully!")
    print("- All books removed")
    print("- All mentions removed") 
    print("- Gazetteer locations preserved")
    
except Exception as e:
    print(f"Error cleaning database: {e}")
    conn.rollback()
finally:
    conn.close()
