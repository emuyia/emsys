import os
import glob
import re 
from . import config

class SetManager:
    def __init__(self):
        self.sets_dir = config.SETS_DIR_PATH
        self.file_extension = config.MSET_FILE_EXTENSION
        self.set_files = [] 
        self.load_set_files()

    def load_set_files(self):
        pattern = os.path.join(self.sets_dir, f"*{self.file_extension}")
        
        # Initial load can be a simple sort, detailed sorting is for version listing.
        self.set_files = sorted([os.path.basename(f) for f in glob.glob(pattern)])
        print(f"Found {len(self.set_files)} set files: {self.set_files}")

    def get_set_names_for_display(self):
        return [self._extract_set_name_from_filename(f) for f in self.set_files]

    def _extract_set_name_from_filename(self, filename):
        if filename.endswith(self.file_extension):
            return filename[:-len(self.file_extension)]
        return filename

    def get_set_count(self):
        return len(self.set_files)

    def get_set_name_by_index(self, index):
        if 0 <= index < len(self.set_files):
            return self._extract_set_name_from_filename(self.set_files[index])
        return None

    def get_unique_base_names(self):
        base_names = set()
        for filename in self.set_files:
            name_part = self._extract_set_name_from_filename(filename)
            match = re.match(r'([a-zA-Z]{1,4})(\d*)$', name_part.lower()) 
            if match:
                base_names.add(match.group(1))
            else: 
                if re.match(r'^[a-zA-Z]{1,4}$', name_part.lower()):
                    base_names.add(name_part.lower())
        sorted_base_names = sorted(list(base_names))
        print(f"Unique base names: {sorted_base_names}")
        return sorted_base_names

    def get_versions_for_base_name(self, base_name):
        versions_filenames = []
        base_name_lower = base_name.lower()
        for filename in self.set_files:
            name_part_lower = self._extract_set_name_from_filename(filename).lower()
            if name_part_lower.startswith(base_name_lower):
                suffix = name_part_lower[len(base_name_lower):]
                if suffix == "" or suffix.isdigit():
                     versions_filenames.append(filename)
        
        # Refined sort_key for natural alphanumeric sorting of versions
        def sort_key_natural(filename):
            name_part = self._extract_set_name_from_filename(filename).lower()
            # Attempt to split into non-digit prefix and digit suffix
            # Handles cases like "name1", "name10", "name" (no number)
            match = re.match(rf"^{re.escape(base_name_lower)}(\d*)$", name_part)
            if match:
                numeric_part_str = match.group(1)
                if numeric_part_str: # If there is a number
                    return (base_name_lower, int(numeric_part_str)) 
                else: # No number after base_name, e.g. "stma.mset"
                    return (base_name_lower, -1) # Place items without numbers first or consistently
            return (name_part, 0) # Fallback for names not matching the pattern, sort alphabetically

        sorted_versions = sorted(versions_filenames, key=sort_key_natural)
        print(f"Versions for base '{base_name}' (sorted naturally): {sorted_versions}")
        return sorted_versions

    def get_segments_from_file(self, filename):
        segments = []
        filepath = os.path.join(self.sets_dir, filename)
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}")
            return segments

        try:
            with open(filepath, 'r') as f:
                content = f.read()
            
            # Segments are separated by semicolons. Clean up whitespace.
            segment_strings = [s.strip() for s in content.split(';') if s.strip()]

            for seg_str in segment_strings:
                segment_data = {}
                
                # Regex to find 'key value' pairs
                md_match = re.search(r'md\s+([A-Za-z0-9]+)', seg_str)
                mnm_match = re.search(r'mnm\s+([A-Za-z0-9]+)', seg_str)
                trk_match = re.search(r'trk\s+([A-Za-z0-9]+)', seg_str)

                if md_match:
                    segment_data['md'] = md_match.group(1)
                if mnm_match:
                    segment_data['mnm'] = mnm_match.group(1)
                if trk_match:
                    segment_data['trk'] = trk_match.group(1)
                
                # Only add if it contains some recognizable data
                if segment_data:
                    segments.append(segment_data)

        except Exception as e:
            print(f"Error reading or parsing {filename}: {e}")

        print(f"Found {len(segments)} segments in {filename}: {segments}")
        return segments


if __name__ == '__main__':
    manager = SetManager()
    print("\nAll set files (for display):")
    for name in manager.get_set_names_for_display():
        print(name)
    
    print("\nUnique base names:")
    unique_bases = manager.get_unique_base_names()
    for base in unique_bases:
        print(f"- {base}")
        versions = manager.get_versions_for_base_name(base)
        for v_file in versions:
            print(f"  - {v_file}")