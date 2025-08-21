#!/usr/bin/env python3
"""
Startup script for Historical Reference Mapper
"""

import os
import sys

# Add src directory to path
src_path = os.path.join(os.path.dirname(__file__), 'src')
sys.path.insert(0, src_path)

# Import and run the Flask app
from web.app_api import app

if __name__ == '__main__':
    print("Starting Historical Reference Mapper...")
    print("Web application will be available at: http://127.0.0.1:10000")
    print("Database: history_map.db")
    print("Process books with: python src/processing/batch_process_books.py")
    print("\nPress Ctrl+C to stop the server")

    port = int(os.environ.get('PORT', 10000))
    
    app.run(host='0.0.0.0', port=port, debug=False)
