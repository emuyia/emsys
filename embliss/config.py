# MIDI Configuration
MIDI_DEVICE_NAME_SUBSTRING = "MINILAB3 MIDI" # Substring to identify the Minilab3 MIDI ports
DEFAULT_MIDI_CHANNEL = 1 # MIDI channel for most controls (0-15, so 1 is Channel 2 in some DAWs)
PADS_MIDI_CHANNEL = 10 # MIDI channel for drum pads (0-15, so 10 is Channel 11 in some DAWs)

# Minilab 3 Specific SysEx
SYSEX_ARTURIA_HEADER = (0x00, 0x20, 0x6B, 0x7F, 0x42) # Standard Arturia Manufacturer ID
SYSEX_TEXT_CMD_PREFIX = SYSEX_ARTURIA_HEADER + (0x04, 0x02, 0x60) # Command to set text on screen

# User provided init SysEx (decimal): 240 0 32 107 127 66 2 2 64 106 33 247
# Data part for mido (tuple of integers):
SYSEX_INIT_DATA_TUPLE = (0, 32, 107, 127, 66, 2, 2, 64, 106, 33) # From em_pd_controller.py

# Screen display text (approximate limits, non-monospace font)
SCREEN_LINE_1_MAX_CHARS = 16 
SCREEN_LINE_2_MAX_CHARS = 15 # Changed from 16 to 15 to fit "Enc:Scroll P1:OK"

# MIDI Control Assignments (Minilab 3)
# Values are CC numbers or Note numbers

# --- Knobs (Discrete) ---
KNOB_1_CC = 86
KNOB_2_CC = 87
KNOB_3_CC = 89
KNOB_4_CC = 90
KNOB_5_CC = 110 # Bank 2
KNOB_6_CC = 111 # Bank 2
KNOB_7_CC = 116 # Bank 2
KNOB_8_CC = 117 # Bank 2

# --- Sliders (Discrete) ---
SLIDER_1_CC = 14
SLIDER_2_CC = 15
SLIDER_3_CC = 30
SLIDER_4_CC = 31

# --- Encoder ---
ENCODER_CC = 28
ENCODER_VALUE_UP = 65   # Relative value when turned "up" or "right"
ENCODER_VALUE_DOWN = 62 # Relative value when turned "down" or "left"

# --- Pads (Notes) ---
# Standard mode (without Shift)
PAD_1_NOTE = 36
PAD_2_NOTE = 37
PAD_3_NOTE = 38
PAD_4_NOTE = 39
PAD_5_NOTE = 40
PAD_6_NOTE = 41
PAD_7_NOTE = 42
PAD_8_NOTE = 43

# --- Shift Button (used as a modifier for pads) ---
SHIFT_BUTTON_CC = 27 # This is the "Shift" button on the Minilab 3 itself

# --- Pads with Shift (CCs) ---
# Note: Minilab3 sends CCs for pads 4-8 when Shift is held. Pads 1-3 might have fixed Shift functions.
# We'll use the ones you specified:
SHIFT_PAD_5_CC = 105 # Corresponds to Pad 5 + Shift
SHIFT_PAD_6_CC = 106 # Corresponds to Pad 6 + Shift
SHIFT_PAD_7_CC = 107 # Corresponds to Pad 7 + Shift
SHIFT_PAD_8_CC = 108 # Corresponds to Pad 8 + Shift
# CC 109 was mentioned, often associated with the "Program" button/encoder press with shift.
# Let's map it if you intend to use it, e.g. for a specific function key.
# For now, we'll stick to the pad-related CCs you listed.
# If CC 109 is from another control with Shift, we can add it.
# Example: FUNC_KEY_WITH_SHIFT_CC = 109

# File System Paths
SETS_DIR_PATH = "/home/patch/repos/emsys/sets"
MSET_FILE_EXTENSION = ".mset"

# Application Behavior
POLLING_INTERVAL = 0.005  # Reduced from 0.02 (20ms) to 5ms for faster MIDI processing
RECONNECT_INTERVAL = 5   # Seconds to wait before retrying MIDI connection