import ijson
import json

def create_lookup_from_whg(whg_filepath, output_filepath):
    """
    Parses a large WHG Linked Places Format (LPF) JSON file and creates
    a streamlined lookup dictionary for fast matching.

    The output format is:
    { "variant_name_lowercase": {"name": "Primary Name", "lat": 12.34, "lon": 56.78} }
    """
    print(f"Starting to process large WHG file: {whg_filepath}")
    lookup = {}
    
    try:
        with open(whg_filepath, 'rb') as f:
            features = ijson.items(f, 'features.item')
            
            count = 0
            for feature in features:
                # Extract the primary name
                primary_name = feature.get('properties', {}).get('title')
                
                # Extract coordinates
                geometry = feature.get('geometry')
                if not primary_name or not geometry or geometry['type'] != 'Point':
                    continue
                
                lon, lat = geometry['coordinates']
                
                # Convert Decimal to float for JSON serialization
                lat = float(lat) if lat is not None else None
                lon = float(lon) if lon is not None else None
                
                # Create the core record
                record = {"name": primary_name, "lat": lat, "lon": lon}
                
                # Add the primary name to the lookup
                lookup[primary_name.lower()] = record
                
                # Add all variant names to the lookup
                names = feature.get('names', [])
                for name_obj in names:
                    if 'toponym' in name_obj:
                        variant = name_obj['toponym']
                        lookup[variant.lower()] = record
                
                count += 1
                if count % 10000 == 0:
                    print(f"Processed {count} places...")

        print(f"\nProcessing complete. Found {count} total places.")
        print(f"Saving streamlined lookup file to: {output_filepath}")

        with open(output_filepath, 'w', encoding='utf-8') as outfile:
            json.dump(lookup, outfile, indent=2)
            
        print("Lookup file created successfully.")

    except FileNotFoundError:
        print(f"Error: Input file not found at '{whg_filepath}'.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    # The name of the file you downloaded from WHG
    INPUT_WHG_FILE = 'whg_europe.json' 
    # The name of our new, optimized gazetteer file
    OUTPUT_LOOKUP_FILE = 'hre_gazetteer_lookup.json'
    
    create_lookup_from_whg(INPUT_WHG_FILE, OUTPUT_LOOKUP_FILE)
