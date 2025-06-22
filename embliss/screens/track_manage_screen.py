import logging
import time
from .base_screen import BaseScreen
from .. import config

logger = logging.getLogger(__name__)

class TrackManageScreen(BaseScreen):
    def __init__(self, screen_manager, midi_handler, set_manager, set_filename, source_track_name, restore_segment_index):
        super().__init__(screen_manager, midi_handler)
        self.set_manager = set_manager
        self.set_filename = set_filename
        self.source_track_name = source_track_name
        self.restore_segment_index = restore_segment_index

        self.target_tracks = []
        self.current_target_index = -1
        self.delete_confirm_active = False

        self.last_actual_display_time = 0
        self.display_update_pending = False
        self.display_refresh_interval = 0.075

    def activate(self):
        self.active = True
        logger.info(f"Activating TrackManageScreen for source: '{self.source_track_name}'")
        self._load_tracks()
        self.display_update_pending = True
        self.display()

    def _load_tracks(self):
        all_groups = self.set_manager.get_track_groups(self.set_filename)
        all_track_names = [g.name for g in all_groups if g.name not in ["UNSET", self.source_track_name]]
        self.target_tracks = all_track_names
        self.current_target_index = 0 if self.target_tracks else -1
        logger.debug(f"Loaded target tracks: {self.target_tracks}")

    def display(self):
        if not self.active: return
        
        line1 = f"<{self.source_track_name}>"
        line2 = ""

        if self.delete_confirm_active:
            line2 = "Del? P5=N P6=Y"
        elif self.current_target_index == -1:
            line2 = "No other tracks"
        else:
            target_name = self.target_tracks[self.current_target_index]
            line2 = f"P1 <{target_name}> P2"

        self.midi_handler.update_display(line1[:16], line2[:15])
        self.last_actual_display_time = time.time()
        self.display_update_pending = False

    def handle_midi_input(self, message):
        if not self.active: return

        # Handle delete confirmation mode first, as it's modal
        if self.delete_confirm_active:
            # Handle note on (regular pads)
            if message.type == 'note_on':
                if message.note == config.PAD_6_NOTE: # Confirm Delete
                    self._perform_delete()
                elif message.note == config.PAD_5_NOTE: # Cancel Delete
                    self.delete_confirm_active = False
                    self.display_update_pending = True
            # Handle control change (shifted pads)
            elif message.type == 'control_change' and message.value > 0:
                if message.control == config.SHIFT_PAD_6_CC: # Confirm Delete
                    self._perform_delete()
                elif message.control == config.SHIFT_PAD_5_CC: # Cancel Delete
                    self.delete_confirm_active = False
                    self.display_update_pending = True
            return # Consume the event so it's not processed further

        # Handle CC messages (Shift+Pads, Encoder)
        if message.type == 'control_change' and message.value > 0:
            if message.control == config.SHIFT_PAD_7_CC:
                self._perform_undo()
            elif message.control == config.SHIFT_PAD_5_CC:
                logger.info("Delete track initiated via Shift+P5.")
                self.delete_confirm_active = True
                self.display_update_pending = True
            elif message.control == config.SHIFT_PAD_4_CC:
                self._initiate_copy_flow()
            elif message.control == config.ENCODER_CC and self.target_tracks:
                if message.value == config.ENCODER_VALUE_UP: self.current_target_index = (self.current_target_index + 1) % len(self.target_tracks)
                elif message.value == config.ENCODER_VALUE_DOWN: self.current_target_index = (self.current_target_index - 1 + len(self.target_tracks)) % len(self.target_tracks)
                self.display_update_pending = True
            return

        # Handle regular pad presses
        if message.type == 'note_on':
            target_name = self.target_tracks[self.current_target_index] if self.current_target_index != -1 else None
            
            if message.note == config.PAD_1_NOTE and target_name:
                self._perform_move(target_name, after=False)
            elif message.note == config.PAD_2_NOTE and target_name:
                self._perform_move(target_name, after=True)
            elif message.note == config.PAD_5_NOTE:
                self._exit_screen()

    def _perform_move(self, target_track, after):
        logger.info(f"Moving '{self.source_track_name}' {'after' if after else 'before'} '{target_track}'")
        if self.set_manager.move_track(self.set_filename, self.source_track_name, target_track, after):
            self.midi_handler.update_display("Track Moved", "Success!"); time.sleep(1)
            self._exit_screen(find_new_index=True)
        else:
            self.midi_handler.update_display("Move Failed", "See logs"); time.sleep(2)
            self.display_update_pending = True

    def _perform_delete(self):
        logger.info(f"Deleting track '{self.source_track_name}'")
        if self.set_manager.delete_track(self.set_filename, self.source_track_name):
            self.midi_handler.update_display("Track Deleted", "Success!"); time.sleep(1)
            self._exit_screen()
        else:
            self.midi_handler.update_display("Delete Failed", "See logs"); time.sleep(2)
            self.delete_confirm_active = False; self.display_update_pending = True

    def _perform_undo(self):
        logger.info("Performing undo operation.")
        if self.set_manager.undo_last_operation(self.set_filename):
            self.midi_handler.update_display("Undo Successful", ""); time.sleep(1)
            self._load_tracks(); self.display_update_pending = True
        else:
            self.midi_handler.update_display("Undo Failed", "No undo data"); time.sleep(2)
            self.display_update_pending = True

    def _initiate_copy_flow(self):
        from .copy_track_screen import CopyTrackScreen
        logger.info(f"Initiating copy flow for track '{self.source_track_name}' from {self.set_filename}")
        self.screen_manager.change_screen(
            CopyTrackScreen(
                self.screen_manager,
                self.midi_handler,
                self.set_manager,
                source_filename=self.set_filename,
                source_track_name=self.source_track_name,
                original_screen=self
            )
        )

    def _exit_screen(self, find_new_index=False):
        from .segment_list_screen import SegmentListScreen
        restore_idx = 0 if find_new_index else self.restore_segment_index
        logger.info(f"Exiting TrackManageScreen, returning to index {restore_idx}.")
        self.screen_manager.change_screen(
            SegmentListScreen(self.screen_manager, self.midi_handler, self.set_manager, self.set_filename, restore_index=restore_idx)
        )

    def update(self):
        if not self.active: return
        if self.display_update_pending and (time.time() - self.last_actual_display_time >= self.display_refresh_interval):
            self.display()