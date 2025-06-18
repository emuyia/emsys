import os
import glob
import re # For parsing base names
from . import config

class SetManager:
    def __init__(self):
        self.sets_dir = config.SETS_DIR_PATH
        self.file_extension = config.MSET_FILE_EXTENSION
        self.set_files = [] # Full list of actual filenames, e.g., "brnb0.mset"
        self.load_set_files()

    def load_set_files(self):
        """Scans the sets directory for .mset files and sorts them."""
        pattern = os.path.join(self.sets_dir, f"*{self.file_extension}")
        # Sort alphabetically, which usually groups base names and then versions
        self.set_files = sorted([os.path.basename(f) for f in glob.glob(pattern)])
        print(f"Found {len(self.set_files)} set files: {self.set_files}")

    def get_set_names_for_display(self):
        """Returns a list of set names (filenames without extension) for basic display."""
        return [self._extract_set_name_from_filename(f) for f in self.set_files]

    def _extract_set_name_from_filename(self, filename):
        """Removes the .mset extension from the filename."""
        if filename.endswith(self.file_extension):
            return filename[:-len(self.file_extension)]
        return filename

    def get_set_count(self):
        """Returns the total number of set files found."""
        return len(self.set_files)

    def get_set_name_by_index(self, index):
        """Returns the set name (no ext) at a given index from the full list."""
        if 0 <= index < len(self.set_files):
            return self._extract_set_name_from_filename(self.set_files[index])
        return None

    def get_unique_base_names(self):
        """
        Extracts unique base names from all set files.
        e.g., from ["brnb0.mset", "brnb1.mset", "test0.mset"], returns ["brnb", "test"]
        """
        base_names = set()
        for filename in self.set_files:
            name_part = self._extract_set_name_from_filename(filename)
            match = re.match(r'([a-zA-Z]{1,4})(\d*)$', name_part.lower()) # Match against lowercase
            if match:
                base_names.add(match.group(1))
            else: # Handle names without numbers like "stma.mset" -> "stma"
                if re.match(r'^[a-zA-Z]{1,4}$', name_part.lower()):
                    base_names.add(name_part.lower())

        sorted_base_names = sorted(list(base_names))
        print(f"Unique base names: {sorted_base_names}")
        return sorted_base_names

    def get_versions_for_base_name(self, base_name):
        """
        Returns a sorted list of full filenames for a given base name.
        e.g., for "brnb", returns ["brnb0.mset", "brnb1.mset", ...]
        """
        versions = []
        base_name_lower = base_name.lower()
        for filename in self.set_files:
            name_part_lower = self._extract_set_name_from_filename(filename).lower()
            
            # Check if the filename starts with the base_name and is followed by numbers or nothing
            # (for base names that might not have a version number like 'stma')
            if name_part_lower.startswith(base_name_lower):
                # Ensure it's not just a partial match like 'brn' matching 'brnb'.
                # The part after base_name should be digits or empty.
                suffix = name_part_lower[len(base_name_lower):]
                if suffix == "" or suffix.isdigit():
                     versions.append(filename)
        
        # Custom sort: try to sort numerically if versions exist, then alphabetically
        def sort_key(filename):
            name_part = self._extract_set_name_from_filename(filename).lower()
            match = re.match(rf"^{re.escape(base_name_lower)}(\d+)$", name_part)
            if match:
                return (0, int(match.group(1))) # Sort by number first
            return (1, name_part) # Then by name for non-versioned or oddly named files

        sorted_versions = sorted(versions, key=sort_key)
        print(f"Versions for base '{base_name}': {sorted_versions}")
        return sorted_versions


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