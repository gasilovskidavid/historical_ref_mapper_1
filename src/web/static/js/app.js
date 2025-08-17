// Historical Reference Mapper Web App
class HistoricalMapper {
    constructor() {
        this.apiBase = '/api';
        this.currentResults = [];
        this.map = null;
        this.markers = [];
        this.selectedLocation = null;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.initMap();
    }

    setupEventListeners() {
        // Enter key support for search inputs
        document.getElementById('location-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                searchLocations();
            }
        });

        document.getElementById('start-year').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                searchLocations();
            }
        });

        document.getElementById('end-year').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                searchLocations();
            }
        });
    }

    async searchLocations() {
        const startYear = document.getElementById('start-year').value;
        const endYear = document.getElementById('end-year').value;
        const locationName = document.getElementById('location-input').value.trim();
        
        // Clear previous results
        this.clearResults();
        
        if (locationName) {
            // Search by specific location
            await this.searchByLocation(locationName);
        } else if (startYear && endYear) {
            // Search by year range
            if (parseInt(startYear) > parseInt(endYear)) {
                this.showError('Start year must be before end year');
                return;
            }
            await this.searchByYearRange(startYear, endYear);
        } else {
            this.showError('Please enter either a location name or year range');
            return;
        }
    }

    showLoading() {
        document.getElementById('loading').style.display = 'block';
        document.getElementById('results-section').style.display = 'none';
    }

    hideLoading() {
        document.getElementById('loading').style.display = 'none';
    }

    showError(message) {
        // Create a simple error notification
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-notification';
        errorDiv.innerHTML = `
            <div style="background: #fed7d7; border: 1px solid #feb2b2; color: #c53030; padding: 1rem; border-radius: 8px; margin: 1rem 0; text-align: center;">
                <i class="fas fa-exclamation-triangle"></i> ${message}
            </div>
        `;
        
        const mainContent = document.querySelector('.main-content');
        mainContent.insertBefore(errorDiv, mainContent.firstChild);
        
        // Remove error after 5 seconds
        setTimeout(() => {
            errorDiv.remove();
        }, 5000);
    }

    clearResults() {
        this.currentResults = [];
        document.getElementById('results-section').style.display = 'none';
        document.getElementById('results-container').innerHTML = '';
        // Clear map markers but keep map visible
        if (this.map) {
            this.clearMapMarkers();
            // Don't clear map selection here to preserve references panel
        }
    }

    displayResults(locations, searchType, searchParams) {
        this.currentResults = locations;
        
        const resultsSection = document.getElementById('results-section');
        const resultsContainer = document.getElementById('results-container');
        const resultsCount = document.getElementById('results-count');
        
        resultsCount.textContent = locations.length;
        resultsSection.style.display = 'block';
        
        if (locations.length === 0) {
            resultsContainer.innerHTML = `
                <div style="text-align: center; padding: 3rem; color: #718096;">
                    <i class="fas fa-search" style="font-size: 3rem; margin-bottom: 1rem; color: #cbd5e0;"></i>
                    <h3>No locations found</h3>
                    <p>Try adjusting your search parameters or try a different search method.</p>
                </div>
            `;
            return;
        }
        
        resultsContainer.innerHTML = locations.map(location => this.createLocationCard(location)).join('');
        
        // Update map with new results
        this.updateMapWithResults();
    }

    updateMapWithResults() {
        if (this.map) {
            this.clearMapMarkers();
            this.addMarkersToMap();
        }
    }

    toggleResultsView() {
        const resultsSection = document.getElementById('results-section');
        const toggleBtn = document.querySelector('.results-header .action-btn');
        
        if (resultsSection.style.display === 'none') {
            resultsSection.style.display = 'block';
            toggleBtn.innerHTML = '<i class="fas fa-eye-slash"></i> Hide Results';
        } else {
            resultsSection.style.display = 'none';
            toggleBtn.innerHTML = '<i class="fas fa-eye"></i> Show Results';
        }
    }

    createLocationCard(location) {
        const coords = location.latitude && location.longitude 
            ? `${location.latitude.toFixed(4)}, ${location.longitude.toFixed(4)}`
            : 'Coordinates not available';
        
        const yearInfo = location.historical_start_year && location.historical_end_year ?
            `<div class="detail-item">
                <i class="fas fa-calendar"></i>
                <span>Years: ${location.historical_start_year} - ${location.historical_end_year}</span>
            </div>` : '';
        
        return `
            <div class="location-card" onclick="historicalMapper.showLocationDetails('${location.name}')">
                <div class="location-header">
                    <div class="location-name">${location.name}</div>
                    <div class="location-coords">${coords}</div>
                </div>
                <div class="location-details">
                    ${yearInfo}
                    <div class="detail-item">
                        <i class="fas fa-map-marker-alt"></i>
                        <span>ID: ${location.id}</span>
                    </div>
                </div>
                <div class="location-actions">
                    <button class="action-btn primary" onclick="event.stopPropagation(); historicalMapper.showLocationDetails('${location.name}')">
                        <i class="fas fa-info-circle"></i> View Details
                    </button>
                    <button class="action-btn" onclick="event.stopPropagation(); historicalMapper.showOnMap(${location.latitude}, ${location.longitude})">
                        <i class="fas fa-map"></i> Show on Map
                    </button>
                </div>
            </div>
        `;
    }

    async showAllLocationsOnMap() {
        try {
            this.showLoading();
            
            // Fetch only locations that have references (mentions) from books
            const response = await fetch(`${this.apiBase}/locations_with_references`);
            const data = await response.json();
            
            this.hideLoading();
            
            if (data.error) {
                this.showError(data.error);
                return;
            }
            
            // Display locations with references on the map
            this.currentResults = data.locations;
            this.updateMapWithResults();
            
        } catch (error) {
            console.error('Error fetching locations with references:', error);
            this.hideLoading();
            this.showError('Failed to load locations with references');
        }
    }

    displayMap() {
        // This method is now called updateMapWithResults
        this.updateMapWithResults();
    }

    initMap() {
        // Initialize Leaflet map
        this.map = L.map('map').setView([50, 10], 4); // Center on Europe
        
        // Add OpenStreetMap tiles
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(this.map);
        
        // Add click handler for map
        this.map.on('click', () => {
            this.clearMapSelection();
        });
    }

    clearMapMarkers() {
        this.markers.forEach(marker => {
            this.map.removeLayer(marker);
        });
        this.markers = [];
    }

    addMarkersToMap() {
        if (!this.map || !this.currentResults.length) return;
        
        const locationsWithCoords = this.currentResults.filter(loc => loc.latitude && loc.longitude);
        
        if (locationsWithCoords.length === 0) {
            // Show message if no coordinates
            const mapContainer = document.getElementById('map-container');
            mapContainer.innerHTML = `
                <div class="map-placeholder">
                    <i class="fas fa-map"></i>
                    <p>No coordinates available for mapping</p>
                    <p class="map-note">Locations in this search don't have geographic coordinates</p>
                </div>
            `;
            return;
        }
        
        // Add markers for each location
        locationsWithCoords.forEach(location => {
            const marker = L.marker([location.latitude, location.longitude])
                .addTo(this.map)
                .bindPopup(this.createMarkerPopup(location));
            
            // Add click handler for marker
            marker.on('click', (e) => {
                e.originalEvent.stopPropagation();
                this.selectLocationOnMap(location);
            });
            
            this.markers.push(marker);
        });
        
        // Fit map to show all markers
        if (this.markers.length > 0) {
            const group = new L.featureGroup(this.markers);
            this.map.fitBounds(group.getBounds().pad(0.1));
        }
    }

    createMarkerPopup(location) {
        const yearInfo = location.historical_start_year && location.historical_end_year ?
            `<div><strong>Years:</strong> ${location.historical_start_year} - ${location.historical_end_year}</div>` : '';
        
        return `
            <div class="location-popup">
                <h4>${location.name}</h4>
                ${yearInfo}
                <div class="popup-actions">
                    <button class="popup-btn" onclick="historicalMapper.showLocationDetails('${location.name}')">
                        <i class="fas fa-info-circle"></i> Details
                    </button>
                    <button class="popup-btn secondary" onclick="historicalMapper.selectLocationOnMap('${location.name}')">
                        <i class="fas fa-crosshairs"></i> Select
                    </button>
                </div>
            </div>
        `;
    }

    selectLocationOnMap(location) {
        if (typeof location === 'string') {
            // Find location by name
            location = this.currentResults.find(loc => loc.name === location);
        }
        
        if (!location) return;
        
        // Clear previous selection first
        this.clearMapSelection();
        
        this.selectedLocation = location;
        
        // Highlight the selected marker
        this.markers.forEach(marker => {
            if (marker.getLatLng().lat === location.latitude && 
                marker.getLatLng().lng === location.longitude) {
                marker.setIcon(L.divIcon({
                    className: 'selected-marker',
                    html: '<div style="background: #667eea; border: 3px solid #4c51bf; border-radius: 50%; width: 20px; height: 20px;"></div>',
                    iconSize: [20, 20],
                    iconAnchor: [10, 10]
                }));
            }
        });
        
        // Show selection info
        this.showMapSelectionInfo(location);
        
        // Show location details and database references
        this.showLocationDetails(location.name);
        
        // Show database references panel
        this.showDatabaseReferences(location);
    }

    async showDatabaseReferences(location) {
        try {
            // Create references panel below the map but above results
            const mapSection = document.getElementById('map-section');
            
            // Remove existing references panel
            const existingPanel = document.getElementById('references-panel');
            if (existingPanel) {
                existingPanel.remove();
            }
            
            // Create new references panel
            const referencesPanel = document.createElement('div');
            referencesPanel.id = 'references-panel';
            referencesPanel.className = 'references-panel';
            referencesPanel.innerHTML = `
                <div style="background: white; border-radius: 8px; padding: 1.5rem; margin-top: 1rem; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                    <h4 style="margin-bottom: 1rem; color: #2d3748; display: flex; align-items: center;">
                        <i class="fas fa-database" style="color: #667eea; margin-right: 0.5rem;"></i>
                        Database References for ${location.name}
                    </h4>
                    <div id="references-content">
                        <div style="text-align: center; padding: 2rem;">
                            <div class="spinner"></div>
                            <p>Loading references...</p>
                        </div>
                    </div>
                </div>
            `;
            
            // Insert after the map section
            mapSection.parentNode.insertBefore(referencesPanel, mapSection.nextSibling);
            
            // Get current year range from the form
            const startYear = document.getElementById('start-year').value;
            const endYear = document.getElementById('end-year').value;
            
            // Fetch references from database with year filtering
            const mentionsResponse = await fetch(`${this.apiBase}/mentions_by_year/${encodeURIComponent(location.name)}?start_year=${startYear}&end_year=${endYear}`);
            const mentionsData = await mentionsResponse.json();
            
            // Update references content with two-tier display
            this.updateReferencesContentTwoTier(mentionsData, location.name);
            
        } catch (error) {
            console.error('Error fetching database references:', error);
            this.showError('Failed to load database references');
        }
    }

    updateReferencesContent(books, mentions, locationName) {
        const referencesContent = document.getElementById('references-content');
        
        let booksHtml = '';
        if (books.error) {
            booksHtml = '<p style="color: #e53e3e;">No books found for this location.</p>';
        } else {
            booksHtml = `
                <div style="margin-bottom: 1.5rem;">
                    <h5 style="margin-bottom: 0.75rem; color: #4a5568;">
                        <i class="fas fa-book"></i> Books Mentioning This Location (${books.length})
                    </h5>
                    <div style="max-height: 200px; overflow-y: auto;">
                        ${books.map(book => `
                            <div style="background: #f7fafc; padding: 0.75rem; border-radius: 6px; margin-bottom: 0.5rem; border-left: 3px solid #667eea;">
                                <strong>${book.title}</strong>
                                ${book.url ? `<br><a href="${book.url}" target="_blank" style="color: #667eea; font-size: 0.9rem;">View Source</a>` : ''}
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }
        
        let mentionsHtml = '';
        if (mentions.error) {
            mentionsHtml = '<p style="color: #e53e3e;">No mentions found for this location.</p>';
        } else {
            mentionsHtml = `
                <div>
                    <h5 style="margin-bottom: 0.75rem; color: #4a5568;">
                        <i class="fas fa-quote-left"></i> Textual References (${mentions.length})
                    </h5>
                    <div style="max-height: 300px; overflow-y: auto;">
                        ${mentions.map(mention => `
                            <div style="background: #f7fafc; padding: 0.75rem; border-radius: 6px; margin-bottom: 0.5rem;">
                                <div style="margin-bottom: 0.5rem; font-size: 0.9rem;">
                                    <strong>${mention.title}</strong>
                                    <span style="color: #718096; margin-left: 0.5rem;">Position: ${mention.text_position}</span>
                                </div>
                                <div style="background: white; padding: 0.75rem; border-radius: 6px; border-left: 3px solid #667eea; font-style: italic;">
                                    "${mention.context}"
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }
        
        referencesContent.innerHTML = booksHtml + mentionsHtml;
    }

    updateReferencesContentTwoTier(mentionsData, locationName) {
        const referencesContent = document.getElementById('references-content');
        
        let html = '';
        
        // Primary tier: Year-matched references
        const primaryTier = mentionsData.primary_tier;
        if (primaryTier.count > 0) {
            html += `
                <div style="margin-bottom: 2rem;">
                    <h5 style="margin-bottom: 1rem; color: #2d3748; border-bottom: 2px solid #48bb78; padding-bottom: 0.5rem;">
                        <i class="fas fa-check-circle" style="color: #48bb78;"></i> 
                        ${primaryTier.tier_name} (${primaryTier.count})
                    </h5>
                    <div style="max-height: 300px; overflow-y: auto;">
                        ${primaryTier.mentions.map(mention => `
                            <div style="background: #f0fff4; padding: 1rem; border-radius: 8px; margin-bottom: 0.75rem; border-left: 4px solid #48bb78;">
                                <div style="margin-bottom: 0.5rem; font-size: 0.9rem;">
                                    <strong>${mention.title}</strong>
                                    ${mention.historical_start_year && mention.historical_end_year ? 
                                        `<span style="color: #718096; margin-left: 0.5rem;">(${mention.historical_start_year}-${mention.historical_end_year})</span>` : 
                                        '<span style="color: #718096; margin-left: 0.5rem;">(Time period: Unknown)</span>'
                                    }
                                </div>
                                <div style="background: white; padding: 0.75rem; border-radius: 6px; border-left: 3px solid #48bb78; font-style: italic;">
                                    "${mention.context}"
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }
        
        // Secondary tier: Year-mismatched and unperiodized references
        const secondaryTier = mentionsData.secondary_tier;
        if (secondaryTier.count > 0) {
            // Separator line and warning message
            html += `
                <hr style="border: none; height: 2px; background: #e2e8f0; margin: 2rem 0;">
                <div style="background: #fff5f5; border: 1px solid #fed7d7; border-radius: 8px; padding: 1rem; margin-bottom: 1.5rem;">
                    <div style="color: #c53030; font-weight: 500; margin-bottom: 0.5rem;">
                        <i class="fas fa-exclamation-triangle"></i> ${secondaryTier.warning_message}
                    </div>
                </div>
            `;
            
            html += `
                <div style="margin-bottom: 1rem;">
                    <h5 style="margin-bottom: 1rem; color: #2d3748; border-bottom: 2px solid #e53e3e; padding-bottom: 0.5rem;">
                        <i class="fas fa-info-circle" style="color: #e53e3e;"></i> 
                        ${secondaryTier.tier_name} (${secondaryTier.count})
                    </h5>
                    <div style="max-height: 300px; overflow-y: auto;">
                        ${secondaryTier.mentions.map(mention => `
                            <div style="background: #fef5e7; padding: 1rem; border-radius: 8px; margin-bottom: 0.75rem; border-left: 4px solid #e53e3e;">
                                <div style="margin-bottom: 0.5rem; font-size: 0.9rem;">
                                    <strong>${mention.title}</strong>
                                    ${mention.historical_start_year && mention.historical_end_year ? 
                                        `<span style="color: #718096; margin-left: 0.5rem;">(${mention.historical_start_year}-${mention.historical_end_year})</span>` : 
                                        '<span style="color: #718096; margin-left: 0.5rem;">(Time period: Unknown)</span>'
                                    }
                                </div>
                                <div style="background: white; padding: 0.75rem; border-radius: 6px; border-left: 3px solid #e53e3e; font-style: italic;">
                                    "${mention.context}"
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }
        
        // If no references at all
        if (primaryTier.count === 0 && secondaryTier.count === 0) {
            html = '<p style="color: #e53e3e; text-align: center; padding: 2rem;">No references found for this location.</p>';
        }
        
        referencesContent.innerHTML = html;
    }

    showMapSelectionInfo(location) {
        // Add selection info above the map
        const mapContainer = document.getElementById('map-container');
        const selectionInfo = document.createElement('div');
        selectionInfo.id = 'selection-info';
        selectionInfo.className = 'selection-info';
        selectionInfo.innerHTML = `
            <div style="background: #667eea; color: white; padding: 0.75rem; border-radius: 8px; margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <i class="fas fa-crosshairs"></i> 
                    <strong>Selected:</strong> ${location.name}
                </div>
                <button onclick="historicalMapper.clearMapSelection()" style="background: rgba(255,255,255,0.2); border: none; color: white; padding: 4px 8px; border-radius: 4px; cursor: pointer;">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
        
        // Insert before the map
        const map = document.getElementById('map');
        mapContainer.insertBefore(selectionInfo, map);
    }

    clearMapSelection() {
        this.selectedLocation = null;
        
        // Remove selection info
        const selectionInfo = document.getElementById('selection-info');
        if (selectionInfo) {
            selectionInfo.remove();
        }
        
        // Remove references panel
        const referencesPanel = document.getElementById('references-panel');
        if (referencesPanel) {
            referencesPanel.remove();
        }
        
        // Reset marker icons
        this.markers.forEach(marker => {
            marker.setIcon(L.divIcon({
                className: 'default-marker',
                html: '<div style="background: #e53e3e; border: 2px solid #c53030; border-radius: 50%; width: 16px; height: 16px;"></div>',
                iconSize: [16, 16],
                iconAnchor: [8, 8]
            }));
        });
    }

    async showLocationDetails(locationName) {
        try {
            this.showLoading();
            
            // Get books by location
            const booksResponse = await fetch(`${this.apiBase}/books_by_location/${encodeURIComponent(locationName)}`);
            const books = await booksResponse.json();
            
            // Get mentions by location
            const mentionsResponse = await fetch(`${this.apiBase}/mentions/${encodeURIComponent(locationName)}`);
            const mentions = await mentionsResponse.json();
            
            this.hideLoading();
            
            // Display in modal
            this.showModal(locationName, books, mentions);
            
        } catch (error) {
            console.error('Error fetching location details:', error);
            this.hideLoading();
            this.showError('Failed to load location details');
        }
    }

    showModal(locationName, books, mentions) {
        const modal = document.getElementById('location-modal');
        const modalTitle = document.getElementById('modal-title');
        const modalBody = document.getElementById('modal-body');
        
        modalTitle.textContent = locationName;
        
        let booksHtml = '';
        if (books.error) {
            booksHtml = '<p style="color: #e53e3e;">No books found for this location.</p>';
        } else {
            booksHtml = `
                <h4 style="margin-bottom: 1rem; color: #2d3748;">
                    <i class="fas fa-book"></i> Books Mentioning This Location
                </h4>
                <div style="margin-bottom: 2rem;">
                    ${books.map(book => `
                        <div style="background: #f7fafc; padding: 1rem; border-radius: 8px; margin-bottom: 0.5rem;">
                            <strong>${book.title}</strong>
                            ${book.url ? `<br><a href="${book.url}" target="_blank" style="color: #667eea; font-size: 0.9rem;">View Source</a>` : ''}
                        </div>
                    `).join('')}
                </div>
            `;
        }
        
        let mentionsHtml = '';
        if (mentions.error) {
            mentionsHtml = '<p style="color: #e53e3e;">No mentions found for this location.</p>';
        } else {
            mentionsHtml = `
                <h4 style="margin-bottom: 1rem; color: #2d3748;">
                    <i class="fas fa-quote-left"></i> Textual References
                </h4>
                <div style="max-height: 300px; overflow-y: auto;">
                    ${mentions.map(mention => `
                        <div style="background: #f7fafc; padding: 1rem; border-radius: 8px; margin-bottom: 0.5rem;">
                            <div style="margin-bottom: 0.5rem;">
                                <strong>${mention.title}</strong>
                                <small style="color: #718096; margin-left: 0.5rem;">Position: ${mention.text_position}</small>
                            </div>
                            <div style="background: white; padding: 0.75rem; border-radius: 6px; border-left: 3px solid #667eea;">
                                "${mention.context}"
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        }
        
        modalBody.innerHTML = booksHtml + mentionsHtml;
        modal.style.display = 'block';
    }

    closeModal() {
        document.getElementById('location-modal').style.display = 'none';
    }

    showOnMap(lat, lng) {
        if (lat && lng) {
            // Center map on the specified coordinates
            if (this.map) {
                this.map.setView([lat, lng], 8);
            }
        }
    }
}

// Global functions for HTML onclick handlers
function searchLocations() {
    historicalMapper.searchLocations();
}

function closeModal() {
    historicalMapper.closeModal();
}

// Initialize the app when DOM is loaded
let historicalMapper;
document.addEventListener('DOMContentLoaded', () => {
    historicalMapper = new HistoricalMapper();
});

// Add search methods to HistoricalMapper class
HistoricalMapper.prototype.searchByLocation = async function(locationName) {
    try {
        this.showLoading();
        
        // First get books by location
        const booksResponse = await fetch(`${this.apiBase}/books_by_location/${encodeURIComponent(locationName)}`);
        const books = await booksResponse.json();
        
        this.hideLoading();
        
        if (books.error) {
            this.showError(books.error);
            return;
        }
        
        // Create a mock location object for display
        const location = {
            id: 'search-result',
            name: locationName,
            latitude: null,
            longitude: null,
            historical_start_year: null,
            historical_end_year: null
        };
        
        this.displayResults([location], 'location', { locationName });
        
        // Show the details immediately
        this.showLocationDetails(locationName);
        
    } catch (error) {
        console.error('Error searching by location:', error);
        this.hideLoading();
        this.showError('Failed to search by location');
    }
};

HistoricalMapper.prototype.searchByYearRange = async function(startYear, endYear) {
    try {
        this.showLoading();
        
        const url = `${this.apiBase}/locations_by_year?start_year=${startYear}&end_year=${endYear}`;
        const response = await fetch(url);
        const data = await response.json();
        
        this.hideLoading();
        
        if (data.error) {
            this.showError(data.error);
            return;
        }
        
        this.displayResults(data.locations, 'year', { startYear, endYear });
        
    } catch (error) {
        console.error('Error searching by year range:', error);
        this.hideLoading();
        this.showError('Failed to search by year range');
    }
};
