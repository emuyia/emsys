import logging
import time
from .base_screen import BaseScreen
from .. import config

logger = logging.getLogger(__name__)

class SegmentListScreen(BaseScreen):
    def __init__(self, screen_manager, midi_handler, set_manager, set_filename):
        super().__init__(screen_manager, midi_handler)
        self.set_manager = set_manager
        self.set_filename = set_filename
        self.segments = []
        self.current_segment_index = -1

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
            self.current_segment_index = 0
        else:
            self.current_segment_index = -1
        
        self.display_update_pending = True
        self.display() # Initial display call

    def _process_segments_for_display(self, segments):
        """
        Analyzes segments to count track occurrences and adds a formatted
        track string to each segment dictionary for easy display.
        """
        trk_totals = {}
        for segment in segments:
            trk_val = segment.get('trk')
            if trk_val:
                trk_totals[trk_val] = trk_totals.get(trk_val, 0) + 1

        trk_current_counts = {}
        processed_segments = []
        for segment in segments:
            new_segment = segment.copy()
            trk_val = new_segment.get('trk')
            
            if trk_val:
                total = trk_totals.get(trk_val, 0)
                if total > 1:
                    current_count = trk_current_counts.get(trk_val, 0) + 1
                    trk_current_counts[trk_val] = current_count
                    new_segment['formatted_trk'] = f"{trk_val} #{current_count}"
                else:
                    new_segment['formatted_trk'] = trk_val
            else:
                new_segment['formatted_trk'] = ''
            
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

            # Trimmed display: "1/16 A01/B12"
            line1 = f"{self.current_segment_index + 1}/{total_segments} {md_val}/{mnm_val}"
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
                    self.display_update_pending = True # Set flag instead of calling display()
            return

        if message.type == 'note_on' and message.note == config.PAD_5_NOTE:
            logger.info("Back to Set List Screen from Segment List.")
            from .set_list_screen import SetListScreen
            self.screen_manager.change_screen(
                SetListScreen(
                    self.screen_manager, 
                    self.midi_handler, 
                    self.set_manager,
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