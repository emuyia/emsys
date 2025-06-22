import os
import glob
import logging
import re
import time
from packaging.version import parse as parse_version

from . import config

logger = logging.getLogger(__name__)

class TrackGroup:
    """A helper class to represent a track and its associated segments."""
    def __init__(self, name, segments):
        self.name = name
        self.segments = segments

class SetManager:
    def __init__(self):
        self.sets_dir = config.SETS_DIR_PATH
        self.file_extension = config.MSET_FILE_EXTENSION
        self.set_files = []
        self._undo_buffer = {} # {filename: file_content}
        self.load_set_files()

    def load_set_files(self):
        """Scans the sets directory and loads all .mset filenames."""
        self.set_files = []
        glob_pattern = os.path.join(self.sets_dir, f"*{self.file_extension}")
        try:
            self.set_files = sorted([os.path.basename(f) for f in glob.glob(glob_pattern)])
            logger.info(f"Loaded {len(self.set_files)} set files from {self.sets_dir}")
        except Exception as e:
            logger.error(f"Error loading set files: {e}")

    def _save_undo_state(self, filename):
        """Saves the current content of the file to the undo buffer."""
        filepath = os.path.join(self.sets_dir, filename)
        try:
            with open(filepath, 'r') as f:
                self._undo_buffer[filename] = f.read()
            logger.info(f"Undo state saved for {filename}")
        except Exception as e:
            logger.error(f"Failed to save undo state for {filename}: {e}")
            self._undo_buffer.pop(filename, None)

    def undo_last_operation(self, filename):
        """Restores the file content from the undo buffer."""
        if filename not in self._undo_buffer:
            logger.warning("No undo state available for this file.")
            return False
        
        filepath = os.path.join(self.sets_dir, filename)
        try:
            with open(filepath, 'w') as f:
                f.write(self._undo_buffer[filename])
            logger.info(f"Undo operation successful for {filename}.")
            self._undo_buffer.pop(filename, None) # Clear buffer after use
            return True
        except Exception as e:
            logger.error(f"Failed to perform undo for {filename}: {e}")
            return False

    def get_track_groups(self, filename):
        """Parses a .mset file into a list of TrackGroup objects."""
        filepath = os.path.join(self.sets_dir, filename)
        groups = []
        current_group_segments = []
        last_trk_name = "UNSET"

        try:
            with open(filepath, 'r') as f:
                all_segments = [s.strip() for s in f.read().split(';') if s.strip()]

            for seg_str in all_segments:
                trk_match = re.search(r'\btrk\s+([a-zA-Z0-9]+)\b', seg_str)
                if trk_match:
                    if current_group_segments:
                        groups.append(TrackGroup(last_trk_name, current_group_segments))
                    last_trk_name = trk_match.group(1)
                    current_group_segments = [seg_str]
                else:
                    current_group_segments.append(seg_str)
            
            if current_group_segments:
                groups.append(TrackGroup(last_trk_name, current_group_segments))
        except Exception as e:
            logger.error(f"Error parsing track groups from {filename}: {e}")
            return []
        return groups

    def _write_groups_to_file(self, filename, groups):
        """Helper to write a list of TrackGroups back to a file."""
        filepath = os.path.join(self.sets_dir, filename)
        new_content_list = [seg for group in groups for seg in group.segments]
        new_content = ";\n".join(new_content_list) + ";\n"
        try:
            with open(filepath, 'w') as f:
                f.write(new_content)
            logger.info(f"File {filename} successfully rewritten.")
            return True
        except Exception as e:
            logger.error(f"Failed to write groups to {filename}: {e}")
            return False

    def move_track(self, filename, source_track_name, target_track_name, after=True):
        """Moves a track group relative to another."""
        self._save_undo_state(filename)
        groups = self.get_track_groups(filename)
        
        source_group = next((g for g in groups if g.name == source_track_name), None)
        if not source_group:
            logger.error(f"Source track '{source_track_name}' not found.")
            return False

        groups.remove(source_group)
        
        try:
            target_idx = next(i for i, g in enumerate(groups) if g.name == target_track_name)
            insert_idx = target_idx + 1 if after else target_idx
            groups.insert(insert_idx, source_group)
            return self._write_groups_to_file(filename, groups)
        except StopIteration:
            logger.error(f"Target track '{target_track_name}' not found.")
            return False

    def _get_used_banks(self, filename):
        """Scans a set file and returns sets of used bank numbers for md and mnm."""
        filepath = os.path.join(self.sets_dir, filename)
        used_md = set()
        used_mnm = set()
        if not os.path.exists(filepath):
            return used_md, used_mnm

        try:
            with open(filepath, 'r') as f:
                content = f.read()
            
            md_matches = re.findall(r'\bmd\s+([A-H])(\d{2})\b', content)
            mnm_matches = re.findall(r'\bmnm\s+([A-H])(\d{2})\b', content)

            for bank_char, slot_str in md_matches:
                numeric_val = (ord(bank_char.upper()) - ord('A')) * 16 + (int(slot_str) - 1)
                used_md.add(numeric_val)

            for bank_char, slot_str in mnm_matches:
                numeric_val = (ord(bank_char.upper()) - ord('A')) * 16 + (int(slot_str) - 1)
                used_mnm.add(numeric_val)

        except Exception as e:
            logger.error(f"Error getting used banks from {filename}: {e}")

        return used_md, used_mnm

    def _format_bank(self, numeric_val):
        """Converts a numeric bank value (0-127) back to 'A01' format."""
        if not (0 <= numeric_val < 128):
            raise ValueError("Bank value out of range 0-127")
        
        bank_char = chr(ord('A') + (numeric_val // 16))
        slot = (numeric_val % 16) + 1
        return f"{bank_char}{slot:02d}"

    def copy_track_to_set(self, source_filename, track_name_to_copy, dest_filename):
        """Copies a track group from one set to another, remapping banks."""
        if source_filename == dest_filename:
            logger.warning("Source and destination files cannot be the same.")
            return False, "Src=Dest"

        source_groups = self.get_track_groups(source_filename)
        source_track_group = next((g for g in source_groups if g.name == track_name_to_copy), None)
        if not source_track_group:
            logger.error(f"Track '{track_name_to_copy}' not found in '{source_filename}'.")
            return False, "Src Trk Not Fnd"

        used_md_banks, used_mnm_banks = self._get_used_banks(dest_filename)
        logger.debug(f"Destination '{dest_filename}' used MD banks: {sorted(list(used_md_banks))}")
        logger.debug(f"Destination '{dest_filename}' used MNM banks: {sorted(list(used_mnm_banks))}")

        bank_mappings = []
        new_segments = []
        next_free_md = 0
        next_free_mnm = 0

        for seg_str in source_track_group.segments:
            new_seg_str = seg_str
            
            md_match = re.search(r'\bmd\s+([A-H]\d{2})\b', new_seg_str)
            if md_match:
                original_md_bank = md_match.group(1)
                while next_free_md in used_md_banks:
                    next_free_md += 1
                if next_free_md >= 128: return False, "No MD Banks"
                
                new_md_bank_str = self._format_bank(next_free_md)
                new_seg_str = re.sub(r'(\bmd\s+)[A-H]\d{2}\b', r'\g<1>' + new_md_bank_str, new_seg_str, 1)
                used_md_banks.add(next_free_md)
                bank_mappings.append({'type': 'md', 'source': original_md_bank, 'dest': new_md_bank_str})

            mnm_match = re.search(r'\bmnm\s+([A-H]\d{2})\b', new_seg_str)
            if mnm_match:
                original_mnm_bank = mnm_match.group(1)
                while next_free_mnm in used_mnm_banks:
                    next_free_mnm += 1
                if next_free_mnm >= 128: return False, "No MNM Banks"

                new_mnm_bank_str = self._format_bank(next_free_mnm)
                new_seg_str = re.sub(r'(\bmnm\s+)[A-H]\d{2}\b', r'\g<1>' + new_mnm_bank_str, new_seg_str, 1)
                used_mnm_banks.add(next_free_mnm)
                bank_mappings.append({'type': 'mnm', 'source': original_mnm_bank, 'dest': new_mnm_bank_str})
            
            new_segments.append(new_seg_str)

        self._save_undo_state(dest_filename)
        dest_filepath = os.path.join(self.sets_dir, dest_filename)
        
        try:
            # Read the entire destination content first
            dest_content = ""
            if os.path.exists(dest_filepath):
                with open(dest_filepath, 'r') as f:
                    dest_content = f.read()

            # Ensure the existing content ends with a newline and semicolon for clean appending
            dest_content = dest_content.strip()
            if dest_content and not dest_content.endswith(';'):
                dest_content += ';'
            
            # Join the new segments and append
            new_part = ";\n".join(new_segments)
            
            # Combine old and new content
            final_content = dest_content + "\n" + new_part + ";\n" if dest_content else new_part + ";\n"

            # Write the full, corrected content back to the file
            with open(dest_filepath, 'w') as f:
                f.write(final_content)
            
            logger.info(f"Successfully copied track '{track_name_to_copy}' to '{dest_filename}'")
            return True, bank_mappings
        except Exception as e:
            logger.error(f"Failed to write copied track to '{dest_filename}': {e}", exc_info=True)
            return False, "File Write Err"

    def delete_track(self, filename, track_name_to_delete):
        """Deletes an entire track group from the file."""
        self._save_undo_state(filename)
        groups = self.get_track_groups(filename)
        groups_to_keep = [g for g in groups if g.name != track_name_to_delete]
        
        if len(groups_to_keep) == len(groups):
            logger.warning(f"Track '{track_name_to_delete}' not found for deletion.")
            return False
        return self._write_groups_to_file(filename, groups_to_keep)

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
        
        def sort_key_natural(filename):
            name_part = self._extract_set_name_from_filename(filename).lower()
            match = re.match(rf"^{re.escape(base_name_lower)}(\d*)$", name_part)
            if match:
                numeric_part_str = match.group(1)
                if numeric_part_str:
                    return (base_name_lower, int(numeric_part_str)) 
                else:
                    return (base_name_lower, -1)
            return (name_part, 0)

        sorted_versions = sorted(versions_filenames, key=sort_key_natural)
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
            
            segment_strings = [s.strip() for s in content.split(';') if s.strip()]

            for seg_str in segment_strings:
                segment_data = {}
                
                md_match = re.search(r'md\s+([A-Za-z0-9]+)', seg_str)
                mnm_match = re.search(r'mnm\s+([A-Za-z0-9]+)', seg_str)
                trk_match = re.search(r'trk\s+([A-Za-z0-9]+)', seg_str)

                if md_match: segment_data['md'] = md_match.group(1)
                if mnm_match: segment_data['mnm'] = mnm_match.group(1)
                if trk_match: segment_data['trk'] = trk_match.group(1)
                
                if segment_data: segments.append(segment_data)
        except Exception as e:
            print(f"Error reading or parsing {filename}: {e}")

        return segments

    def update_segment_track(self, filename, segment_index, new_trk_name):
        filepath = os.path.join(config.SETS_DIR_PATH, filename)
        if not os.path.exists(filepath):
            logger.error(f"File not found for update: {filepath}")
            return False

        try:
            with open(filepath, 'r') as f:
                content = f.read()
            
            segment_strings = [s.strip() for s in content.split(';') if s.strip()]

            if not (0 <= segment_index < len(segment_strings)):
                logger.error(f"Segment index {segment_index} out of bounds for {filename}")
                return False

            target_segment = segment_strings[segment_index]
            trk_pattern = re.compile(r'\s*\btrk\s+[a-zA-Z0-9]+\b')
            
            if new_trk_name:
                sanitized_name = "".join(filter(str.isalpha, new_trk_name.lower()))[:4]
                if trk_pattern.search(target_segment):
                    modified_segment = trk_pattern.sub(f" trk {sanitized_name}", target_segment, count=1)
                else:
                    modified_segment = f"{target_segment.strip()} trk {sanitized_name}"
            else:
                modified_segment = trk_pattern.sub('', target_segment, count=1)

            segment_strings[segment_index] = modified_segment.strip()
            new_content = ";\n".join(segment_strings) + ";\n"

            with open(filepath, 'w') as f:
                f.write(new_content)
            
            logger.info(f"Successfully updated segment {segment_index} in {filename}.")
            return True
        except Exception as e:
            logger.error(f"Failed to update segment in {filename}: {e}", exc_info=True)
            return False

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