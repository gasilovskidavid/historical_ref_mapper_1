#!/usr/bin/env python3
"""
Startup script for Historical Reference Mapper
"""

import os
import sys

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Change to src/web directory
os.chdir(os.path.join(os.path.dirname(__file__), 'src', 'web'))

# Import and run the Flask app
from app_api import app

if __name__ == '__main__':
    print("🚀 Starting Historical Reference Mapper...")
    print("📖 Web application will be available at: http://127.0.0.1:5000")
    print("🗺️  Database: history_map.db")
    print("📚 Process books with: python src/processing/batch_process_books.py")
    print("\nPress Ctrl+C to stop the server")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
