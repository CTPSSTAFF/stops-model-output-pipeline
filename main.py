import json
import sys
from pathlib import Path
import shutil
from extractor import run_extraction 

class ConfigManager:
    """ Loads JSON configuration files for the pipeline. """
    _EXTRACTION_CONFIG_PATH = Path("config_data_extract.json")
    _TABLES_TO_EXTRACT_PATH = Path("config_data_tables.json")
    _PRN_TABLES_STRUCT_PATH = Path("prn_tables.json")

    def __init__(self):
        """Initializes the config paths."""
        self.extraction_config_path = self._EXTRACTION_CONFIG_PATH
        self.tables_to_extract_path = self._TABLES_TO_EXTRACT_PATH
        self.prn_tables_struct_path = self._PRN_TABLES_STRUCT_PATH
        
        self.config = {}

    def _load_json_file(self, file_path, description):
        """Safely loads a single JSON file."""
        if not file_path.is_file():
            print(f"INFO: {description} file not found at '{file_path}'.")
            return None
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"❌ FATAL: '{file_path}' is not a valid JSON file.")
            sys.exit(1)
        except Exception as e:
            print(f"❌ FATAL: Could not read {file_path}. Reason: {e}")
            sys.exit(1)

    def load_config_jsons(self):
        """ Loads all configuration files into a single object. """
        print("--- ⚙️ Loading Configurations ---")
        
        self.config = self._load_json_file(self.extraction_config_path, "Extraction config")
        if self.config is None:
            print(f"❌ FATAL: Main config file '{self.extraction_config_path}' not found. Exiting.")
            sys.exit(1)

        tables_config = self._load_json_file(self.tables_to_extract_path, "Data Tables list")
        if tables_config is not None:
            self.config["tables_to_extract"] = tables_config
            print(f"   - Loaded {len(tables_config)} table definitions from '{self.tables_to_extract_path}'")
        else:
            print(f"   - WARNING: Data Tables file not found. No tables will be extracted.")
            self.config["tables_to_extract"] = []

        struct_config_list = self._load_json_file(self.prn_tables_struct_path, "PRN Table Structures")
        if struct_config_list is not None:
            try:
                processed_structs = {item['table_id']: item for item in struct_config_list}
                self.config["prn_table_structures"] = processed_structs
                print(f"   - Loaded and processed {len(processed_structs)} table structures from '{self.prn_tables_struct_path}'")
            except KeyError:
                print(f"   - ❌ FATAL: Error processing '{self.prn_tables_struct_path}'. Ensure all items have a 'table_id'.")
                sys.exit(1)
        else:
            print(f"   - WARNING: PRN Table Structures file not found. Extractor will fail.")
            self.config["prn_table_structures"] = {}

        print("--- ✅ Configurations Loaded ---")
        return self.config

def clear_and_create_folder(folder_path: Path):
    
    print(f"Initializing folder: '{folder_path}'")
    if folder_path.exists() and folder_path.is_dir():
        print(f"   - Deleting existing folder...")
        shutil.rmtree(folder_path)
    
    print(f"   - Creating new folder...")
    folder_path.mkdir(parents=True, exist_ok=True)
    print("   - Folder ready.")

def main():
    """ Prepares and runs extractor. """

    print("Starting the data processing pipeline...")
    print(f"Running {Path(__file__).name}")
    print("--------------------------------------------------")

    config_manager = ConfigManager()
    extraction_config = config_manager.load_config_jsons()

    print("--------------------------------------------------")
    
    try:
        output_folder = Path(extraction_config.get("output_base_folder", "outputs"))
        clear_and_create_folder(output_folder)
        
        run_extraction(extraction_config)
        
    except Exception as e:
        print(f"\n❌ FATAL ERROR during Data Extraction: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n🎉 Pipeline finished successfully!")
    print("--------------------------------------------------")

if __name__ == "__main__":
    main()