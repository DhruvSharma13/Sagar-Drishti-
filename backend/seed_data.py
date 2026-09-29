import sys
import os

# Ensure backend directory is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_pipeline import generate_indian_ocean_dataset, CACHE_FILE

if __name__ == "__main__":
    import traceback
    print("Generating Indian Ocean Float & Anomaly Dataset...")
    try:
        dataset = generate_indian_ocean_dataset()
        print(f"Data Cache File Status: {os.path.exists(CACHE_FILE)}")
        print(f"Cache File Path: {CACHE_FILE}")
        print(f"Generated {len(dataset['profiles'])} profiles, {len(dataset['gliders'])} gliders, {len(dataset['model_comparisons'])} model comparisons.")
    except Exception as ex:
        print("ERROR IN SEED_DATA:")
        traceback.print_exc()
