import logging
import time
from .base_screen import BaseScreen
from .. import config

logger = logging.getLogger(__name__)

class SegmentListScreen(BaseScreen):
    def __init__(self, screen_manager, midi_handler, set_manager, set_filename, restore_index=None):
        super().__init__(screen_manager, midi_handler)
        self.set_manager = set_manager
        self.set_filename = set_filename
        self.segments = []
        self.current_segment_index = -1
        self.selected_segment_index = None # To track the selected segment
        self.restore_index = restore_index # Store the index to restore

        # For refresh-rate based display updates
        self.last_actual_display_time = 0
        self.display_update_pending = False
        self.display_refresh_interval = 0.075 # 75ms interval

    def activate(self):
        self.active = True
        logger.info(f"Activating SegmentListScreen for set: {self.set_filename}")
        
        raw_segments = self.set_manager.get_segments_from_file(self.set_filename)
        self._process_segments_for_display(raw_segments)

        if self.segments:
            if self.restore_index is not None and 0 <= self.restore_index < len(self.segments):
                # If a restore index is provided, use it
                self.current_segment_index = self.restore_index
                self.selected_segment_index = self.restore_index # Also pre-select it
            else:
                # Otherwise, start at the beginning
                self.current_segment_index = 0
                self.selected_segment_index = None
        else:
            self.current_segment_index = -1
            self.selected_segment_index = None
        
        self.display_update_pending = True
        self.display() # Initial display call

    def _process_segments_for_display(self, segments):
        """
        Analyzes segments for display, implementing "fall-through" logic for
        track names and numbering occurrences correctly.
        """
        # Pass 1: Determine the effective display_trk for all segments and get final counts.
        display_trks = []
        last_known_trk = None
        for segment in segments:
            explicit_trk = segment.get('trk')
            if explicit_trk:
                last_known_trk = explicit_trk
                display_trks.append(explicit_trk)
            elif last_known_trk:
                display_trks.append(last_known_trk)
            else:
                display_trks.append(None)
        
        # Now, count the totals from the generated list of what will be displayed.
        trk_display_totals = {}
        for trk in display_trks:
            if trk:
                trk_display_totals[trk] = trk_display_totals.get(trk, 0) + 1

        # Pass 2: Build the formatted strings using the correct totals and continuous numbering.
        processed_segments = []
        trk_current_counts = {}
        for i, segment in enumerate(segments):
            new_segment = segment.copy()
            # We already know what will be displayed from Pass 1
            display_trk = display_trks[i]
            # A track is inherited if it has a display name that is not its own explicit name
            is_inherited = (display_trk is not None and segment.get('trk') != display_trk)

            if display_trk:
                total = trk_display_totals.get(display_trk, 0)
                current_count = trk_current_counts.get(display_trk, 0) + 1
                trk_current_counts[display_trk] = current_count
                
                # Add occurrence number if the track appears more than once in total
                trk_str = f"{display_trk} #{current_count}" if total > 1 else display_trk
                
                # Add parentheses for inherited tracks
                new_segment['formatted_trk'] = f"({trk_str})" if is_inherited else trk_str
            else:
                new_segment['formatted_trk'] = ''
            
            # Also store the original track name for the editor
            new_segment['trk'] = segment.get('trk', '')
            processed_segments.append(new_segment)
        
        self.segments = processed_segments

    def display(self):
        if not self.active: return
        line1, line2 = "", ""

        set_name_base = self.set_filename.replace(config.MSET_FILE_EXTENSION, "")

        if not self.segments or self.current_segment_index == -1:
            line1 = f"{set_name_base}"
            line2 = "No segments."
        else:
            total_segments = len(self.segments)
            current_segment = self.segments[self.current_segment_index]
            
            md_val = current_segment.get('md', '---')
            mnm_val = current_segment.get('mnm', '---')
            formatted_trk_val = current_segment.get('formatted_trk', '')
            is_selected = (self.current_segment_index == self.selected_segment_index)

            line1_content = f"{self.current_segment_index + 1}/{total_segments} {md_val}/{mnm_val}"
            
            if is_selected:
                line1 = f">{line1_content}<"
                line2 = "P4:EditTrk P5:Back"
            else:
                line1 = line1_content
                line2 = f"trk: {formatted_trk_val}"

        line1 = line1[:config.SCREEN_LINE_1_MAX_CHARS]
        line2 = line2[:config.SCREEN_LINE_2_MAX_CHARS]
        self.midi_handler.update_display(line1, line2)
        
        logger.debug(f"Displaying SegmentListScreen: L1='{line1}', L2='{line2}'")
        self.last_actual_display_time = time.time()
        self.display_update_pending = False

    def handle_midi_input(self, message):
        if not self.active: return

        if message.type == 'control_change' and message.control == config.ENCODER_CC:
            if self.segments and self.current_segment_index != -1:
                prev_idx = self.current_segment_index
                if message.value == config.ENCODER_VALUE_UP:
                    self.current_segment_index = (self.current_segment_index + 1) % len(self.segments)
                elif message.value == config.ENCODER_VALUE_DOWN:
                    self.current_segment_index = (self.current_segment_index - 1 + len(self.segments)) % len(self.segments)
                
                if prev_idx != self.current_segment_index:
                    # Deselect if user scrolls away from a selected item
                    if self.selected_segment_index is not None:
                        self.selected_segment_index = None
                    self.display_update_pending = True
            return

        if message.type == 'note_on':
            if message.note == config.PAD_6_NOTE: # Select
                if self.segments and self.current_segment_index != -1:
                    if self.selected_segment_index != self.current_segment_index:
                        self.selected_segment_index = self.current_segment_index
                        logger.info(f"Selected segment {self.selected_segment_index}")
                        self.display_update_pending = True
                return

            elif message.note == config.PAD_4_NOTE: # Edit Track (Rename)
                if self.selected_segment_index is not None and self.selected_segment_index == self.current_segment_index:
                    logger.info(f"Edit track for segment {self.current_segment_index}")
                    from .edit_segment_track_screen import EditSegmentTrackScreen
                    segment_data = self.segments[self.current_segment_index]
                    original_trk = segment_data.get('trk', '')
                    self.screen_manager.change_screen(
                        EditSegmentTrackScreen(
                            self.screen_manager, self.midi_handler, self.set_manager,
                            self.set_filename, self.current_segment_index, original_trk
                        )
                    )
                    return
                else:
                    logger.info("Pad 4 (Edit) pressed but no segment is selected.")

            elif message.note == config.PAD_5_NOTE: # Back / Cancel
                if self.selected_segment_index is not None:
                    logger.info("Deselecting segment.")
                    self.selected_segment_index = None
                    self.display_update_pending = True
                else:
                    logger.info("Back to Set List Screen from Segment List.")
                    from .set_list_screen import SetListScreen
                    self.screen_manager.change_screen(
                        SetListScreen(
                            self.screen_manager, self.midi_handler, self.set_manager,
                            target_filename=self.set_filename
                        )
                    )
                return

    def update(self):
        """Called periodically by the screen manager to handle non-input-driven updates."""
        if not self.active: return
        
        current_time = time.time()
        if self.display_update_pending and (current_time - self.last_actual_display_time >= self.display_refresh_interval):
            self.display()