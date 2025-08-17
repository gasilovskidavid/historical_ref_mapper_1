# Historical Reference Mapper

A comprehensive web application for mapping historical locations mentioned in books, with intelligent location extraction, gazetteer matching, and interactive visualization.

## 🌟 Features

- **Interactive Map Interface**: Leaflet.js-based map showing locations with book references
- **Intelligent Location Extraction**: NLP-powered extraction using spaCy for named entity recognition
- **Comprehensive Gazetteer**: 50,000+ European locations from GeoNames and historical sources
- **Two-Tier Reference Display**: Primary (year-matched) and secondary (year-mismatched/unperiodized) references
- **Automatic Period Extraction**: Historical year ranges extracted from book titles
- **Batch Processing**: Efficient processing of thousands of books
- **Context Preservation**: Full context around each location mention stored

## 🏗️ Repository Structure

```
historical_ref_mapper/
├── src/                          # Source code
│   ├── processing/               # Book processing scripts
│   │   ├── extract_locations_updated.py
│   │   ├── batch_process_books.py
│   │   └── books_to_process.json
│   ├── database/                 # Database management scripts
│   │   ├── database_integration.py
│   │   ├── preprocess_gazetteer.py
│   │   └── enhance_time_periods.py
│   └── web/                      # Web application
│       ├── app_api.py
│       ├── templates/
│       │   └── index.html
│       └── static/
│           ├── css/
│           │   └── style.css
│           └── js/
│               └── app.js
├── data/                         # Data files
│   ├── gazetteer/                # Gazetteer source data
│   │   ├── allCountries.txt      # GeoNames European locations
│   │   ├── whg_europe.json      # World Historical Gazetteer
│   │   └── hre_gazetteer_lookup.json
│   └── history_map.db            # Main SQLite database
├── docs/                         # Documentation
└── README.md                     # This file
```

## 📁 File Descriptions

### **Processing Scripts** (`src/processing/`)

- **`extract_locations_updated.py`**: Core location extraction script using spaCy NLP
  - Downloads books from Gutenberg URLs
  - Extracts titles automatically from text
  - Identifies location entities (GPE, LOC, FAC)
  - Matches entities to gazetteer database
  - Stores mentions with context and confidence scores

- **`batch_process_books.py`**: Orchestrates processing of multiple books
  - Loads book configuration from JSON
  - Processes books in sequence
  - Handles existing books (skips if already processed)
  - Provides progress tracking and statistics

- **`books_to_process.json`**: Configuration file for books to process
  - Contains URLs, titles, authors, and metadata
  - Supports batch processing workflows

### **Database Scripts** (`src/database/`)

- **`database_integration.py`**: Database setup and integration utilities
  - Creates and manages database schema
  - Handles data migration and updates

- **`preprocess_gazetteer.py`**: Gazetteer data preprocessing
  - Processes raw GeoNames data
  - Filters for European locations
  - Creates optimized lookup tables

- **`enhance_time_periods.py`**: Historical period processing
  - Extracts year ranges from book titles
  - Assigns historical periods to books

### **Web Application** (`src/web/`)

- **`app_api.py`**: Flask web server and API endpoints
  - `/api/locations_by_year`: Year-filtered location data
  - `/api/locations_with_references`: All referenced locations
  - `/api/mentions_by_year/<location>`: Two-tier reference data
  - Database optimization and indexing

- **`templates/index.html`**: Main web interface
  - Interactive Leaflet.js map
  - Year range selector (500-1300+)
  - Location search functionality
  - Two-tier reference display

- **`static/css/style.css`**: Application styling
  - Map controls and markers
  - Reference panel styling
  - Responsive design elements

- **`static/js/app.js`**: Frontend functionality
  - Map initialization and management
  - API communication
  - Dynamic content updates
  - User interaction handling

### **Data Files** (`data/`)

- **`history_map.db`**: Main SQLite database
  - `locations`: Geographic locations with coordinates
  - `location_lookup`: Alternative names for matching
  - `books`: Processed books with metadata
  - `mentions`: Location mentions with context

- **`data/gazetteer/`**: Source gazetteer data
  - `allCountries.txt`: GeoNames European locations (1.6GB)
  - `whg_europe.json`: World Historical Gazetteer data
  - `hre_gazetteer_lookup.json`: Holy Roman Empire locations

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- spaCy with English model: `python -m spacy download en_core_web_sm`
- Required packages: `flask`, `sqlite3`, `requests`

### Installation
1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Download spaCy model: `python -m spacy download en_core_web_sm`

### Running the Application
1. **Start the web server**: `python src/web/app_api.py`
2. **Open browser**: Navigate to `http://127.0.0.1:5000`
3. **Process books**: Use `python src/processing/batch_process_books.py`

## 🔧 Usage

### **Processing New Books**
1. Add book URLs to `src/processing/books_to_process.json`
2. Run `python src/processing/batch_process_books.py`
3. Books are automatically processed and added to database

### **Web Interface**
1. **Map Navigation**: Pan and zoom to explore locations
2. **Year Filtering**: Set year range to filter references
3. **Location Selection**: Click markers to view references
4. **Reference Display**: Two-tier system shows relevant and additional references

### **Database Management**
- **Add locations**: Use gazetteer preprocessing scripts
- **Update periods**: Run time period enhancement scripts
- **Optimize performance**: Database indexes are automatically created

## 🎯 Key Workflows

### **Location Extraction Pipeline**
1. **Download**: Book text from Gutenberg URLs
2. **Process**: NLP entity recognition with spaCy
3. **Match**: Entities to gazetteer database
4. **Store**: Mentions with context and metadata
5. **Display**: Interactive map with references

### **Two-Tier Reference System**
- **Primary Tier**: References matching selected year range
- **Secondary Tier**: References outside year range or unperiodized
- **Context**: Full text context around each mention

## 🔍 Technical Details

### **NLP Processing**
- **Model**: spaCy `en_core_web_sm`
- **Entities**: GPE (countries), LOC (locations), FAC (facilities)
- **Chunking**: 500K character chunks for memory efficiency
- **Confidence**: Scoring based on entity type and name matching

### **Database Schema**
- **Normalized design** with foreign key relationships
- **Indexed queries** for performance
- **Efficient storage** of large text contexts
- **Scalable structure** for thousands of books

### **Performance Optimizations**
- **Chunked text processing** for large books
- **Database indexing** on frequently queried columns
- **Efficient gazetteer matching** with multiple strategies
- **Memory management** for large datasets

## 🚀 Production Deployment

### **Scaling Considerations**
- **Database**: Consider PostgreSQL for larger datasets
- **Processing**: Implement queue-based processing for thousands of books
- **Caching**: Add Redis for frequently accessed data
- **Load Balancing**: Multiple web server instances

### **Security**
- **Input validation** for book URLs
- **Rate limiting** for API endpoints
- **Database connection** pooling
- **Error handling** and logging

## 🤝 Contributing

### **Development Setup**
1. Fork the repository
2. Create feature branch
3. Follow existing code style
4. Test thoroughly
5. Submit pull request

### **Code Standards**
- **Python**: PEP 8 compliance
- **JavaScript**: ES6+ with consistent formatting
- **Documentation**: Clear docstrings and comments
- **Testing**: Unit tests for critical functions

## 📊 Performance Metrics

### **Current Capabilities**
- **Books processed**: 3 (tested)
- **Locations extracted**: 1,181 mentions
- **Processing speed**: ~2-3 minutes per book
- **Database size**: ~20MB (with test data)

### **Scalability Targets**
- **Books**: 10,000+ books
- **Locations**: 100,000+ mentions
- **Users**: Concurrent web interface access
- **Performance**: Sub-second query response

## 🔮 Future Enhancements

### **Planned Features**
- **Advanced search**: Full-text search across contexts
- **Temporal visualization**: Timeline-based location display
- **Export functionality**: Data export in various formats
- **API documentation**: OpenAPI/Swagger specification

### **Research Applications**
- **Historical analysis**: Temporal and spatial patterns
- **Text mining**: Advanced NLP for historical research
- **Data visualization**: Interactive charts and graphs
- **Collaborative features**: Multi-user annotation

## 📞 Support

For questions, issues, or contributions:
- **Repository**: GitHub issues and discussions
- **Documentation**: Check this README and code comments
- **Development**: Follow contribution guidelines

---

**Historical Reference Mapper** - Bringing historical texts to life through intelligent location mapping and interactive visualization.
