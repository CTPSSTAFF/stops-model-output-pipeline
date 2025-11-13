import sys
from pathlib import Path
import shutil
from configurations.config_manager import ConfigManager
from extractor import run_extraction


def clear_and_create_folder(folder_path: Path):
    """
    Deletes a folder if it exists, then recreates it to ensure a clean state.
    """
    print(f"Initializing folder: '{folder_path}'")
    if folder_path.exists() and folder_path.is_dir():
        print(f"  - Deleting existing folder...")
        shutil.rmtree(folder_path)
    
    print(f"  - Creating new folder...")
    folder_path.mkdir(parents=True, exist_ok=True)
    print("  - Folder ready.")


def main():
    """
    Main pipeline wrapper. Instantiates a ConfigManager and runs steps based on flags.
    """
    print("Starting the data processing pipeline...")
    print(f"Running {Path(__file__).name}")
    print("--------------------------------------------------")

    # Instantiate the manager and load all configurations
    config_manager = ConfigManager()
    config_manager.load_all()

    # Get the fully loaded configuration objects
    extraction_config = config_manager.extraction_config
    reporting_config = config_manager.reporting_config

    print("--------------------------------------------------")
    
    # Run Data Extraction
    try:
        # Initialize folder for a clean extraction run
        extraction_output_folder = Path(extraction_config.get("output_base_folder", "extracted_csv_tables"))
        clear_and_create_folder(extraction_output_folder)
        
        # Run the extraction process
        run_extraction(extraction_config)
    except Exception as e:
        print(f"\n❌ FATAL ERROR during Data Extraction: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    else:
        print("\nSkipping Data Extraction as per config.")

    print("\n🎉 Pipeline finished successfully!")
    print("--------------------------------------------------")

if __name__ == "__main__":
    main()