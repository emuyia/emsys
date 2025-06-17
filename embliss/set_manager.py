import os
import glob
from . import config

class SetManager:
    def __init__(self):
        self.sets_dir = config.SETS_DIR_PATH
        self.file_extension = config.MSET_FILE_EXTENSION
        self.set_files = []
        self.load_set_files()

    def load_set_files(self):
        """Scans the sets directory for .mset files and sorts them."""
        pattern = os.path.join(self.sets_dir, f"*{self.file_extension}")
        self.set_files = sorted([os.path.basename(f) for f in glob.glob(pattern)])
        print(f"Found {len(self.set_files)} set files: {self.set_files}") # For debugging

    def get_set_names(self):
        """Returns a list of set names (filenames without extension)."""
        return [self._extract_set_name(f) for f in self.set_files]

    def _extract_set_name(self, filename):
        """Removes the .mset extension from the filename."""
        if filename.endswith(self.file_extension):
            return filename[:-len(self.file_extension)]
        return filename

    def get_set_count(self):
        """Returns the total number of sets found."""
        return len(self.set_files)

    def get_set_name_by_index(self, index):
        """Returns the set name at a given index."""
        if 0 <= index < len(self.set_files):
            return self._extract_set_name(self.set_files[index])
        return None

if __name__ == '__main__':
    # Quick test
    manager = SetManager()
    print("Available sets:")
    for i, name in enumerate(manager.get_set_names()):
        print(f"{i+1}. {name}")
    print(f"Total sets: {manager.get_set_count()}")
    if manager.get_set_count() > 0:
        print(f"Set at index 0: {manager.get_set_name_by_index(0)}")