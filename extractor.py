import pandas as pd
import io
import re
import os
import json
import sqlite3
from pathlib import Path

class StopsPRNExtractor:

    @staticmethod
    def _get_table_format_config(config):
        """ Retrieves the pre-loaded table structures configs. """

        structures = config.get("prn_table_structures")
        if not structures:
            print("ERROR: 'prn_table_structures' key not found in config object.")
            return {}
        return structures

    @staticmethod
    def _generate_colspecs_from_widths(widths):
        """Generates (start, end) tuples from a list of widths."""
        colspecs = []
        start = 0
        for width in widths:
            end = start + width
            colspecs.append((start, end))
            start = end
        return colspecs

    @staticmethod
    def _extract_metadata_from_prn(lines, start_index):
        """Extracts metadata (Program, Version, Run) from lines above a table."""
        metadata = {}
        for meta_line_offset in range(1, 10):
            meta_line_num = start_index - meta_line_offset
            if meta_line_num < 0:
                break
            
            meta_line = lines[meta_line_num].strip()
            
            if "Program STOPS" in meta_line:
                parts = meta_line.split(" - ", 1)
                if len(parts) > 0:
                    metadata["Program"] = parts[0].replace("Program ", "").strip()
                if len(parts) > 1 and "Version:" in parts[1]:
                    match = re.search(r'Version:\s*(\S+)\s*-\s*(\d{2}/\d{2}/\d{4})', parts[1])
                    if match:
                        metadata["Version"] = f"{match.group(1)} - {match.group(2)}"
            elif "Run:" in meta_line:
                parts = meta_line.split("Run:")
                if len(parts) > 1:
                    match = re.search(r'^(.*?)(?:\s+System:\s*(.*))?$', parts[1].strip())
                    if match:
                        metadata["Run"] = match.group(1).strip()
                        if match.group(2):
                            metadata["System"] = match.group(2).strip()
        return metadata

    @staticmethod
    def _extract_table_9_01_from_prn(file_path, table_id, config):
        """Extractor for Table 9.01."""
        metadata = {}
        actual_data_lines = []
        in_table_section = False
        start_of_table_data = -1
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except FileNotFoundError:
            return pd.DataFrame(), {}

        for i, line in enumerate(lines):
            if re.search(r"Table\s+" + re.escape(table_id), line):
                in_table_section = True
                metadata = StopsPRNExtractor._extract_metadata_from_prn(lines, i)
            if in_table_section and start_of_table_data == -1:
                if (re.search(r"Stop_id1.*WLK.*KNR", line) or re.search(r"Stop_id1", line)):
                    if i + 1 < len(lines) and re.search(r"^=+", lines[i+1]):
                        start_of_table_data = i + 2
                        break
        if start_of_table_data == -1:
             return pd.DataFrame(), metadata

        format_config = StopsPRNExtractor._get_table_format_config(config)
        table_format = format_config.get(table_id)
        try:
            columns_def = table_format["columns"]
            names = [col["name"] for col in columns_def]
            widths = [col["width"] for col in columns_def]
            colspecs = StopsPRNExtractor._generate_colspecs_from_widths(widths)
        except (KeyError, TypeError, AttributeError) as e:
            print(f"ERROR: Invalid 'columns' format for Table {table_id} in config: {e}")
            return pd.DataFrame(), metadata
        
        for line_to_collect in lines[start_of_table_data:]:
            if "Total" in line_to_collect:
                actual_data_lines.append(line_to_collect.rstrip())
                break
            if re.search(r"Table\s+\d+\.\d+", line_to_collect) or (line_to_collect.strip() and "Program STOPS" in line_to_collect):
                break
            if line_to_collect.strip() and not re.fullmatch(r"={2,}", line_to_collect.strip()) and not re.fullmatch(r"-{2,}", line_to_collect.strip()):
                actual_data_lines.append(line_to_collect.rstrip())
        
        if not actual_data_lines:
            return pd.DataFrame(), metadata

        data_for_df = io.StringIO('\n'.join(actual_data_lines))
        df = pd.read_fwf(data_for_df, colspecs=colspecs, header=None, names=names, dtype=str)

        for col in df.columns:
            if isinstance(df[col].dtype, object):
                df[col] = df[col].str.strip()
            if col not in ["Stop_id1", "Station_Name"]:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0).astype(int)

        if not df.empty and "Station_Name" in df.columns and pd.notna(df.iloc[-1]["Station_Name"]) and str(df.iloc[-1]["Station_Name"]).strip().lower() == "total":
            df.at[df.index[-1], "Station_Name"] = "Total"
            df.at[df.index[-1], "Stop_id1"] = "Total"
        return df, metadata
    
    @staticmethod
    def _extract_table_10_01_from_prn(file_path, table_id, config):
        """Extractor for Table 10.01."""
        metadata = {}
        actual_data_lines = []
        in_table_section = False
        start_of_table_data = -1
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except FileNotFoundError:
            return pd.DataFrame(), {}

        for i, line in enumerate(lines):
            if re.search(r"Table\s+" + re.escape(table_id), line):
                in_table_section = True
                metadata = StopsPRNExtractor._extract_metadata_from_prn(lines, i)
            if in_table_section and start_of_table_data == -1:
                if (re.search(r"Route_ID.*WLK.*KNR", line) or re.search(r"Route_ID", line)):
                    if i + 1 < len(lines) and re.search(r"^=+", lines[i+1]):
                        start_of_table_data = i + 2
                        break
        
        if start_of_table_data == -1:
            return pd.DataFrame(), metadata
        
        format_config = StopsPRNExtractor._get_table_format_config(config)
        table_format = format_config.get(table_id)
        try:
            columns_def = table_format["columns"]
            names = [col["name"] for col in columns_def]
            widths = [col["width"] for col in columns_def]
            colspecs = StopsPRNExtractor._generate_colspecs_from_widths(widths)
        except (KeyError, TypeError, AttributeError) as e:
            print(f"ERROR: Invalid 'columns' format for Table {table_id} in config: {e}")
            return pd.DataFrame(), metadata
        
        for line_to_collect in lines[start_of_table_data:]:
            if "Total" in line_to_collect:
                actual_data_lines.append(line_to_collect.rstrip())
                break
            if re.search(r"Table\s+\d+\.\d+", line_to_collect) or (line_to_collect.strip() and "Program STOPS" in line_to_collect):
                break
            if line_to_collect.strip() and not re.fullmatch(r"={2,}", line_to_collect.strip()) and not re.fullmatch(r"-{2,}", line_to_collect.strip()):
                actual_data_lines.append(line_to_collect.rstrip())
        
        if not actual_data_lines:
            return pd.DataFrame(), metadata
        
        data_for_df = io.StringIO('\n'.join(actual_data_lines))
        df = pd.read_fwf(data_for_df, colspecs=colspecs, header=None, names=names, dtype=str)

        for col in df.columns:
            if isinstance(df[col].dtype, object):
                df[col] = df[col].str.strip()
            if col not in ["Route_ID", "Route_Name", "Station_Name", "Stop_id1", "Group_Name", "HH_Cars", "Sub_mode", "Access_mode"]:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0).astype(int)

        if not df.empty and "Route_Name" in df.columns and pd.notna(df.iloc[-1]["Route_Name"]) and str(df.iloc[-1]["Route_Name"]).strip().lower() == "total":
            df.at[df.index[-1], "Route_Name"] = "Total"
            df.at[df.index[-1], "Route_ID"] = "Total"
        return df, metadata

    @staticmethod
    def _extract_table_10_02_from_prn(file_path, table_id, config):
        """Extractor for Table 10.02."""
        metadata = {}
        all_data_text = []
        in_table_section = False
        start_of_data = -1
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except FileNotFoundError:
            return pd.DataFrame(), {}
        
        for i, line in enumerate(lines):
            if re.search(r"Table\s+" + re.escape(table_id), line):
                in_table_section = True
                metadata = StopsPRNExtractor._extract_metadata_from_prn(lines, i)
            if in_table_section and start_of_data == -1:
                if re.search(r"Route_ID.*Count", line):
                    if i + 1 < len(lines) and re.search(r"^=+", lines[i + 1]):
                        start_of_data = i + 2
                        break
        
        if start_of_data == -1:
            return pd.DataFrame(), metadata
        
        format_config = StopsPRNExtractor._get_table_format_config(config)
        table_format = format_config.get(table_id)
        try:
            columns_def = table_format["columns"]
            names = [col["name"] for col in columns_def]
            widths = [col["width"] for col in columns_def]
            colspecs = StopsPRNExtractor._generate_colspecs_from_widths(widths)
        except (KeyError, TypeError, AttributeError) as e:
            print(f"ERROR: Invalid 'columns' format for Table {table_id} in config: {e}")
            return pd.DataFrame(), metadata

        for line in lines[start_of_data:]:
            if re.search(r"Table\s+\d+\.\d+", line) or re.search(r"Program STOPS", line):
                break
            stripped_line = line.strip()
            if not stripped_line or re.fullmatch(r"[-=]{2,}", stripped_line):
                continue
            all_data_text.append(line)
        
        if not all_data_text:
            return pd.DataFrame(), metadata
        
        data_io = io.StringIO('\n'.join(all_data_text))
        df = pd.read_fwf(data_io, colspecs=colspecs, header=None, names=names, dtype=str)
        
        df["Route_ID"] = df["Route_ID"].str.strip().replace('', pd.NA).ffill()
        df['Route_Name'] = df['Group_Name'].apply(lambda x: x if pd.notna(x) and x.startswith('--') else pd.NA).ffill()
        df.loc[df['Group_Name'].str.startswith('--', na=False), 'Group_Name'] = pd.NA
        df["Group_Name"] = df["Group_Name"].str.strip().replace('', pd.NA)
        is_total_header = df['Route_ID'].str.lower().str.strip() == 'total'
        df.loc[is_total_header, 'Route_Name'] = 'Total'
        is_total_group_name = df['Group_Name'].str.lower().str.strip() == 'total'
        df.loc[is_total_group_name, 'Group_Name'] = 'Total'
        df.loc[is_total_group_name, 'Route_Name'] = 'Total'
        
        if 'Route_Name' in df.columns:
            static_cols = ["Route_ID", "Route_Name", "Group_Name"]
            dynamic_cols = [name for name in names if name not in static_cols]
            final_names_ordered = static_cols + dynamic_cols
            df = df[[col for col in final_names_ordered if col in df.columns]]
        
        for col in df.columns:
            if col not in ["Route_ID", "Route_Name", "Group_Name"]:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce')

        return df, metadata
    
    @staticmethod
    def _extract_table_10_03_04_from_prn(file_path, table_id, config):
        """Extractor for Tables 10.03 & 10.04."""
        metadata = {}
        actual_data_lines = []
        in_table_section = False
        start_of_table_data = -1
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except FileNotFoundError:
            return pd.DataFrame(), {}

        for i, line in enumerate(lines):
            if re.search(r"Table\s+" + re.escape(table_id), line):
                in_table_section = True
                metadata = StopsPRNExtractor._extract_metadata_from_prn(lines, i)
            if in_table_section and start_of_table_data == -1:
                if re.search(r"Route_ID.*Hours", line):
                    if i + 1 < len(lines) and re.search(r"^=+", lines[i+1]):
                        start_of_table_data = i + 2
                        break
        
        if start_of_table_data == -1:
            return pd.DataFrame(), metadata
        
        format_config = StopsPRNExtractor._get_table_format_config(config)
        table_format = format_config.get(table_id)
        try:
            columns_def = table_format["columns"]
            names = [col["name"] for col in columns_def]
            widths = [col["width"] for col in columns_def]
            colspecs = StopsPRNExtractor._generate_colspecs_from_widths(widths)
        except (KeyError, TypeError, AttributeError) as e:
            print(f"ERROR: Invalid 'columns' format for Table {table_id} in config: {e}")
            return pd.DataFrame(), metadata
        
        for line_to_collect in lines[start_of_table_data:]:
            if "Total" in line_to_collect:
                actual_data_lines.append(line_to_collect.rstrip())
                break
            if re.search(r"Table\s+\d+\.\d+", line_to_collect) or (line_to_collect.strip() and "Program STOPS" in line_to_collect):
                break
            if line_to_collect.strip() and not re.fullmatch(r"={2,}", line_to_collect.strip()) and not re.fullmatch(r"-{2,}", line_to_collect.strip()):
                actual_data_lines.append(line_to_collect.rstrip())
        
        if not actual_data_lines:
            return pd.DataFrame(), metadata
        
        data_for_df = io.StringIO('\n'.join(actual_data_lines))
        df = pd.read_fwf(data_for_df, colspecs=colspecs, header=None, names=names, dtype=str)

        for col in df.columns:
            df[col] = df[col].str.strip()
            if "Miles" in col or "Hours" in col:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            elif col not in ["Route_ID", "Route_Name"]:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

        if not df.empty and pd.notna(df.iloc[-1]["Route_Name"]) and str(df.iloc[-1]["Route_Name"]).strip().lower() == "total":
            df.at[df.index[-1], "Route_Name"] = "Total"
            df.at[df.index[-1], "Route_ID"] = "Total"
        
        return df, metadata

    @staticmethod
    def _extract_table_10_05_from_prn(file_path, table_id, config):
        """Extractor for Table 10.05."""
        metadata = {}
        actual_data_lines = []
        in_table_section = False
        start_of_table_data = -1
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except FileNotFoundError:
            return pd.DataFrame(), {}

        for i, line in enumerate(lines):
            if re.search(r"Table\s+" + re.escape(table_id), line):
                in_table_section = True
                metadata = StopsPRNExtractor._extract_metadata_from_prn(lines, i)
            if in_table_section and start_of_table_data == -1:
                if re.search(r"Route_ID.*ALL", line):
                    if i + 1 < len(lines) and re.search(r"^=+", lines[i+1]):
                        start_of_table_data = i + 2
                        break
        
        if start_of_table_data == -1:
            return pd.DataFrame(), metadata
        
        format_config = StopsPRNExtractor._get_table_format_config(config)
        table_format = format_config.get(table_id)
        try:
            columns_def = table_format["columns"]
            names = [col["name"] for col in columns_def]
            widths = [col["width"] for col in columns_def]
            colspecs = StopsPRNExtractor._generate_colspecs_from_widths(widths)
        except (KeyError, TypeError, AttributeError) as e:
            print(f"ERROR: Invalid 'columns' format for Table {table_id} in config: {e}")
            return pd.DataFrame(), metadata
        
        for line_to_collect in lines[start_of_table_data:]:
            if "Total" in line_to_collect:
                actual_data_lines.append(line_to_collect.rstrip())
                break
            if re.search(r"Table\s+\d+\.\d+", line_to_collect) or (line_to_collect.strip() and "Program STOPS" in line_to_collect):
                break
            if line_to_collect.strip() and not re.fullmatch(r"={2,}", line_to_collect.strip()) and not re.fullmatch(r"-{2,}", line_to_collect.strip()):
                actual_data_lines.append(line_to_collect.rstrip())
        
        if not actual_data_lines:
            return pd.DataFrame(), metadata
        
        data_for_df = io.StringIO('\n'.join(actual_data_lines))
        df = pd.read_fwf(data_for_df, colspecs=colspecs, header=None, names=names, dtype=str)

        for col in df.columns:
            if isinstance(df[col].dtype, object):
                df[col] = df[col].str.strip()
            if col not in ["Route_ID", "Route_Name"]:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0).astype(int)

        if not df.empty and "Route_Name" in df.columns and pd.notna(df.iloc[-1]["Route_Name"]) and str(df.iloc[-1]["Route_Name"]).strip().lower() == "total":
            df.at[df.index[-1], "Route_Name"] = "Total"
            df.at[df.index[-1], "Route_ID"] = "Total"
        return df, metadata
    
    @staticmethod
    def _extract_table_12_01_from_prn(file_path, table_id, config):
        """Extractor for Table 12.01."""
        metadata = {}
        actual_data_lines = []
        in_table_section = False
        start_of_table_data = -1
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except FileNotFoundError:
            return pd.DataFrame(), {}

        for i, line in enumerate(lines):
            if re.search(r"Table\s+" + re.escape(table_id), line):
                in_table_section = True
                metadata = StopsPRNExtractor._extract_metadata_from_prn(lines, i)
            if in_table_section and start_of_table_data == -1:
                if (re.search(r"^={8,}", line)):
                    start_of_table_data = i + 1
                    break
        if start_of_table_data == -1:
             return pd.DataFrame(), metadata

        format_config = StopsPRNExtractor._get_table_format_config(config)
        table_format = format_config.get(table_id)
        try:
            columns_def = table_format["columns"]
            names = [col["name"] for col in columns_def]
            widths = [col["width"] for col in columns_def]
            colspecs = StopsPRNExtractor._generate_colspecs_from_widths(widths)
        except (KeyError, TypeError, AttributeError) as e:
            print(f"ERROR: Invalid 'columns' format for Table {table_id} in config: {e}")
            return pd.DataFrame(), metadata
        
        for line_to_collect in lines[start_of_table_data:]:
            stripped_line = line_to_collect.strip()
            if stripped_line.startswith("Total"):
                actual_data_lines.append(stripped_line)
                break
            if re.search(r"Table\s+\d+\.\d+", stripped_line) or "Program STOPS" in stripped_line:
                break
            if stripped_line:
                actual_data_lines.append(stripped_line)
        
        if not actual_data_lines:
            return pd.DataFrame(), metadata

        data_for_df = io.StringIO('\n'.join(actual_data_lines))
        df = pd.read_fwf(data_for_df, colspecs=colspecs, header=None, names=names, dtype=str)

        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].str.strip()
            if col not in ["District"]:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(float)

        return df, metadata

    @staticmethod
    def _extract_table_11_XX_from_prn(file_path, table_id, config):
        """Extractor for Table 11.XX variants."""
        metadata = {}
        data_text = []
        in_table_section = False
        start_of_data = -1
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except FileNotFoundError:
            return pd.DataFrame(), {}

        for i, line in enumerate(lines):
            if re.search(r"Table\s+" + re.escape(table_id), line):
                in_table_section = True
                metadata = StopsPRNExtractor._extract_metadata_from_prn(lines, i)
            if in_table_section and start_of_data == -1:
                if re.search(r"^[=-]+\s*.*", line.strip()) and i + 1 < len(lines):
                    start_of_data = i + 1
                    for j in range(start_of_data, min(start_of_data + 5, len(lines))):
                        if lines[j].strip() and not re.search(r"^[=-]+\s*.*", lines[j].strip()):
                            start_of_data = j
                            break
                    break
        
        if start_of_data == -1:
            return pd.DataFrame(), metadata

        format_config = StopsPRNExtractor._get_table_format_config(config)
        table_format = format_config.get(table_id)

        if not table_format or table_format.get("format_type") != "fixed_width":
            print(f"WARNING: No fixed_width format definition found for Table {table_id}. Skipping.")
            return pd.DataFrame(), metadata
        
        try:
            columns_def = table_format["columns"]
            names = [col["name"] for col in columns_def]
            widths = [col["width"] for col in columns_def]
            colspecs = StopsPRNExtractor._generate_colspecs_from_widths(widths)
        except (KeyError, TypeError, AttributeError) as e:
            print(f"ERROR: Invalid fixed_width format definition for Table {table_id} in config: {e}")
            return pd.DataFrame(), metadata

        for line in lines[start_of_data:]:
            if re.search(r"Table\s+\d+\.\d+", line) or re.search(r"Program STOPS", line) or "..." in line:
                break
            if not line.strip() or re.fullmatch(r"[-=]+\s*.*", line.strip()):
                continue
            data_text.append(line.rstrip())
        
        if not data_text:
            return pd.DataFrame(), metadata
        
        data_io = io.StringIO('\n'.join(data_text))
        df = pd.read_fwf(data_io, colspecs=colspecs, header=None, names=names, dtype=str)

        sep_cols = [col for col in df.columns if col.startswith('_sep')]
        df = df.drop(columns=sep_cols)

        df = df[~df['HH_Cars'].str.strip().str.startswith('. . .', na=False)].copy()
        for col in df.columns:
            if isinstance(df[col].dtype, object):
                df[col] = df[col].str.strip()
            if col not in ["HH_Cars", "Sub_mode", "Access_mode"]:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0).astype(int)
        df['HH_Cars'] = df['HH_Cars'].mask(df['HH_Cars'].eq('')).ffill()
        df['Sub_mode'] = df['Sub_mode'].mask(df['Sub_mode'].eq('')).ffill()

        return df, metadata

    @staticmethod
    def _extract_district_table(file_path, table_id, config):
        """Extractor for matrix-style 'District' tables."""
        metadata = {}
        data_lines = []
        in_table_section = False
        header_line = None
        start_of_data = -1

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except FileNotFoundError:
            return pd.DataFrame(), {}

        for i, line in enumerate(lines):
            stripped_line = line.strip()
            if re.search(r"Table\s+" + re.escape(table_id), line):
                in_table_section = True
                metadata = StopsPRNExtractor._extract_metadata_from_prn(lines, i)
            if in_table_section and header_line is None and (stripped_line.startswith("Idist")):
                header_line = line
            if header_line and re.search(r"^=+", stripped_line):
                start_of_data = i + 1
                break
        
        if start_of_data == -1 or header_line is None:
            print(f"           - WARNING: Could not find a valid header row for Table {table_id}. Skipping.")
            return pd.DataFrame(), metadata

        headers = header_line.strip().split()
        if headers[0].lower() in ['idist', 'district']:
            headers[0] = "Origin_District"
        
        for line in lines[start_of_data:]:
            stripped_line = line.strip()
            if not stripped_line or "Program STOPS" in line or re.search(r"Table\s+\d+\.\d+", line):
                break
            data_lines.append(stripped_line)
            if stripped_line.startswith("Total"):
                break
            
        if not data_lines:
            return pd.DataFrame(), metadata

        parsed_rows = []
        for line in data_lines:
            parts = line.split()
            if len(parts) > 1:
                parsed_rows.append(parts)

        if not parsed_rows:
            return pd.DataFrame(), metadata

        num_data_cols = len(parsed_rows[0])
        if len(headers) < num_data_cols:
             print(f"           - WARNING: Mismatch in Table {table_id}. Header has {len(headers)} columns, data has {num_data_cols}. Truncating.")
             parsed_rows = [row[:len(headers)] for row in parsed_rows]
             num_data_cols = len(headers)

        df = pd.DataFrame(parsed_rows, columns=headers[:num_data_cols])
        
        for col in df.columns:
            if col != 'Origin_District':
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0).astype(float)

        return df, metadata

    @staticmethod
    def _extract_station_group_table(file_path, table_id, config):
        """Extractor for 'Station Group' table formats."""
        
        metadata = {}
        in_table_section = False
        header_line_list = []
        separator_index = -1
        is_two_line_header = False

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except FileNotFoundError:
            return pd.DataFrame(), {}

        for i, line in enumerate(lines):
            if re.search(r"Table\s+" + re.escape(table_id), line):
                in_table_section = True
                metadata = StopsPRNExtractor._extract_metadata_from_prn(lines, i)
            if in_table_section and separator_index == -1 and re.search(r"^=+", line.strip()):
                separator_index = i
                if separator_index > 0:
                    header_line_list.insert(0, lines[separator_index - 1])
                if separator_index > 1:
                    prev_line = lines[separator_index - 2].strip()
                    if prev_line and not re.search(r"^=+", prev_line):
                        header_line_list.insert(0, lines[separator_index - 2])
                        is_two_line_header = True
                break

        if separator_index == -1:
            return pd.DataFrame(), metadata

        start_of_data = separator_index + 1

        headers = []
        if is_two_line_header:
            h1_parts = header_line_list[0].strip().split()
            headers = [p for p in h1_parts if p.lower() not in ['origin', 'group']]
        else:
            parts = header_line_list[0].strip().split()
            if len(parts) > 2 and parts[0].lower() == 'origin' and parts[1].lower() == 'group':
                 headers = parts[2:]
            else:
                 headers = parts

        parsed_rows = []
        stop_prefixes = ("2-WAY",)
        if table_id != "2.04":
            stop_prefixes += ("TOTAL", "GOAL", "COUNT")
        
        for line in lines[start_of_data:]:
            stripped_line = line.strip()
            if not stripped_line or stripped_line.upper().startswith(stop_prefixes) or "Program STOPS" in line:
                break
            
            parts = stripped_line.split()
            if not parts:
                continue
            
            first_number_idx = -1
            for i, part in enumerate(parts):
                try:
                    float(part.replace(',', ''))
                    first_number_idx = i
                    break 
                except ValueError:
                    continue

            if first_number_idx != -1:
                origin_group_raw = " ".join(parts[:first_number_idx])
                numbers = parts[first_number_idx:]
                origin_label = origin_group_raw.replace(':', '').strip()
                if origin_label:
                    parsed_rows.append([origin_label] + numbers)

        if not parsed_rows:
            return pd.DataFrame(), metadata

        df = pd.DataFrame(parsed_rows)
        final_headers = ["Origin_Group"] + headers
        num_cols_data = len(df.columns)
        num_cols_header = len(final_headers)
        
        if num_cols_data != num_cols_header:
            print(f"           - WARNING: Column count mismatch in Table {table_id}. Data has {num_cols_data}, Header has {num_cols_header}. Adjusting.")
            min_cols = min(num_cols_data, num_cols_header)
            df = df.iloc[:, :min_cols]
            df.columns = final_headers[:min_cols]
        else:
            df.columns = final_headers

        for col in df.columns:
            if col != 'Origin_Group':
                df[col] = df[col].replace('-', pd.NA)
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        df = df[df['Origin_Group'] != ''].reset_index(drop=True)
        return df, metadata

def get_extraction_method(table_id_str, config):
    """
    Gets the correct extraction function (e.g., _extract_table_9_01_from_prn)
    """
    format_config = StopsPRNExtractor._get_table_format_config(config)
    table_format = format_config.get(table_id_str)

    if not table_format:
        print(f"WARNING: No configuration found for Table {table_id_str}.")
        return None

    function_name = table_format.get("extraction_function")
    if not function_name:
        print(f"WARNING: 'extraction_function' not specified for Table {table_id_str} in config.")
        return None

    try:
        extraction_func = getattr(StopsPRNExtractor, function_name)
        return extraction_func
    except AttributeError:
        print(f"ERROR: The function '{function_name}' specified for Table {table_id_str} does not exist.")
        return None


def run_extraction(config):
    """ Data extraction logic. """

    print("--- 🎬 Starting Data Extraction ---")
    
    output_base_dir = Path(config.get("output_base_folder", "pipeline_outputs"))
    output_db_name = config.get("output_db_name", "extraction_output.db")
    
    output_base_dir.mkdir(parents=True, exist_ok=True)
    db_path = output_base_dir / output_db_name
    
    db_conn = None
    cleared_prn_tables = set()

    try:
        db_conn = sqlite3.connect(db_path)
        print(f"--- 💾 Opened SQLite database connection at: {db_path} ---")
        
        print("\n--- 📠 Starting PRN to SQLite Extraction ---")
        
        tables_to_extract_config = config.get("tables_to_extract", [])
        aliases_to_extract_config = config.get("aliases_to_extract")
        
        if not aliases_to_extract_config or not isinstance(aliases_to_extract_config, list) or len(aliases_to_extract_config) == 0:
            print("❗️ WARNING: 'aliases_to_extract' key is missing or empty. Halting PRN extraction.")
            return

        files_to_process_nested = aliases_to_extract_config[0]
        
        if not files_to_process_nested or not isinstance(files_to_process_nested, list):
            print("❗️ WARNING: No file definitions found inside 'aliases_to_extract'. Halting PRN extraction.")
            return
        
        # Filter out commented-out entries (those with "_alias")
        files_to_process = [f for f in files_to_process_nested if "alias" in f and "filename" in f]
        
        if not files_to_process:
            print("❗️ WARNING: No valid files to process. Halting PRN extraction.")
            return
        
        print(f"ℹ️  Will process {len(files_to_process)} PRN files defined in 'aliases_to_extract'.")
        
        if not tables_to_extract_config:
            print("❗️ WARNING: No 'tables_to_extract' defined in config. Halting PRN extraction.")
            return
        
        for file_info in files_to_process:
            alias = file_info["alias"]
            filename = file_info["filename"]
            
            file_path = Path(filename)

            if not file_path.exists():
                print(f"❗️ WARNING: File not found for alias '{alias}': {file_path}. Skipping.")
                continue
                
            print(f"\nProcessing File: '{file_path.name}' (Alias: '{alias}')")

            for output_config in tables_to_extract_config:
                table_id_str = output_config['table_id']
                print(f"   -> Attempting to extract Table {table_id_str}...")
                
                extraction_func = get_extraction_method(table_id_str, config)
                
                if not extraction_func:
                    print(f"                         - No extraction method found for Table {table_id_str}. Skipping.")
                    continue

                df, metadata = extraction_func(str(file_path), table_id_str, config)
                
                if df.empty:
                    print(f"                         - No data found for Table {table_id_str} in this file.")
                    continue

                default_table_name = f"Table_{table_id_str.replace('.', '_')}"
                table_name = output_config.get("output_subfolder", default_table_name)

                write_mode = 'append'
                if table_name not in cleared_prn_tables:
                    write_mode = 'replace'
                    cleared_prn_tables.add(table_name)

                df.insert(0, 'scenario_alias', alias)
                
                df.to_sql(table_name, db_conn, if_exists=write_mode, index=False)
                print(f"                         ✅ Wrote data to table: '{table_name}' (Mode: {write_mode})")

    except sqlite3.Error as e:
        print(f"❌ DATABASE ERROR: {e}")
    except Exception as e:
        print(f"❌ A general error occurred: {e}")
    finally:
        if db_conn:
            db_conn.commit()
            db_conn.close()
            print(f"\n--- ✅ Data Extraction Complete. Database connection closed. ---")