# ReaScript: whisper-stream to markers

import subprocess
import os
import sys
import re

# fcntl is used for non-blocking I/O, essential for macOS/Linux
try:
    import fcntl
except ImportError:
    RPR_ShowMessageBox(
        "This script requires the 'fcntl' module, which is available on macOS and Linux.",
        "Module Not Found", 0
    )
    sys.exit()

# Configuration
WHISPER_DEVICE = 3
WHISPER_EXECUTABLE = os.path.join(
    os.path.expanduser('~'),
    'shel/whisper.cpp/build/bin/whisper-stream'
)
WHISPER_MODEL = os.path.join(
    os.path.expanduser('~'),
    'shel/whisper.cpp/models/ggml-base.en.bin'
)

# Arguments for whisper-stream.
LENGTH_MS = 10000
STEP_MS = 1000
WHISPER_ARGS = [
    '-m', WHISPER_MODEL,
    '-c', str(WHISPER_DEVICE),
    '-t', '8',
    '--length', str(LENGTH_MS),
    '--step', str(STEP_MS)
]

# Globals
g_process = None
g_speech_started = False
g_commit_interval = 0
g_iter_count = 0
g_utterance_start_pos = 0.0 # Holds the play position at the start of a processing buffer
g_is_recording = False # Tracks Reaper's recording state

# --- Helper Functions ---

def log(message):
    """Prints a message to the Reaper console."""
    RPR_ShowConsoleMsg(str(message) + "\n")

def strip_ansi_codes(s):
    """Removes ANSI escape codes and carriage returns from a string."""
    return re.sub(r'\r|\x1b\[([0-9]{1,2}(;[0-9]{1,2})?)?[mK]', '', s)

def check_reaper_context():
    """Checks if the script is running inside Reaper."""
    try:
        RPR_GetProjectName
        return True
    except NameError:
        return False

def add_marker(text, position):
    """
    Adds a new marker and forces the Region/Marker Manager to refresh.
    """
    proj = 0
    stripped_text = text.strip()
    if not stripped_text:
        return
    
    marker_name = "{}".format(stripped_text)

    # Create a new marker
    RPR_AddProjectMarker2(proj, False, position, 0, marker_name, -1, 0)


def poll_whisper_output():
    """
    Reads line-by-line, using combined logic to commit/update markers.
    This is the inner loop that runs only while the whisper process is active.
    """
    global g_process, g_speech_started, g_commit_interval, g_iter_count, g_utterance_start_pos

    # Stop polling if the process has been terminated
    if not g_process or g_process.poll() is not None:
        return

    try:
        line = g_process.stdout.readline()
        if line:
            cleaned_line = strip_ansi_codes(line).strip()
            if not g_speech_started:
                # log(cleaned_line) # Print start-up info from whisper-stream
                if "[Start speaking]" in cleaned_line:
                    log("Speech detected. Marker creation enabled.")
                    g_speech_started = True
                    g_utterance_start_pos = RPR_GetPlayPosition()
            elif cleaned_line:
                if cleaned_line.upper() in ["[BLANK AUDIO]", "[ SILENCE ]", "[BLANK_AUDIO]", "[SILENCE]"]:
                    return
                g_iter_count = (g_iter_count + 1 ) % g_commit_interval

                buffer_end = g_iter_count is 0

                if buffer_end:
                    add_marker(cleaned_line, g_utterance_start_pos)
                    g_utterance_start_pos = RPR_GetPlayPosition()

    except IOError:
        # Expected when no data is available in non-blocking mode
        pass

    # Keep polling as long as the process is alive
    if g_process and g_process.poll() is None:
        RPR_defer("poll_whisper_output()")


def start_process():
    """
    Main function to start the whisper-stream process and the polling loop.
    """
    global g_process, g_speech_started, g_commit_interval, g_iter_count, g_utterance_start_pos
    if not check_reaper_context(): return

    # Prevent starting a new process if one is already running
    if g_process and g_process.poll() is None:
        return

    log("--- Starting Whisper-Stream to Markers Script ---")
    g_speech_started = False
    g_iter_count = 0
    g_utterance_start_pos = 0.0
    
    # Calculate the commit interval based on the C++ logic in compiled stream.cpp
    if STEP_MS > 0:
        g_commit_interval = max(1, LENGTH_MS // STEP_MS - 1)
    else:
        g_commit_interval = 9 # A safe default if step_ms is 0

    if not os.path.isfile(WHISPER_EXECUTABLE):
        RPR_ShowMessageBox("Executable not found", "Script Error", 0)
        return

    command = [WHISPER_EXECUTABLE] + WHISPER_ARGS
    log("Running command: {}".format(' '.join(command)))

    try:
        # bufsize=1 is critical for line-buffering.
        # stderr is redirected to stdout to create a single, stable stream.
        # encoding='utf-8' is added to correctly handle non-ASCII characters.
        g_process = subprocess.Popen(
            command, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, 
            bufsize=1,
            encoding='utf-8',
            errors='ignore'
        )

        # Set the combined stream to non-blocking
        fd_out = g_process.stdout.fileno()
        fl_out = fcntl.fcntl(fd_out, fcntl.F_GETFL)
        fcntl.fcntl(fd_out, fcntl.F_SETFL, fl_out | os.O_NONBLOCK)

        log("Process started (PID: {}). Waiting for output...".format(g_process.pid))
        poll_whisper_output() # Start the inner polling loop

    except Exception as e:
        RPR_ShowMessageBox("Failed to start process: {}".format(e), "Script Error", 0)
        g_process = None

def stop_process():
    """Stops the running whisper-stream process."""
    global g_process
    if g_process and g_process.poll() is None:
        log("Stopping whisper-stream process...")
        g_process.terminate()
        g_process = None
        # Reset globals
        g_speech_started = False
        g_iter_count = 0
        g_utterance_start_pos = 0.0

def check_recording_state():
    """
    The main outer loop. Checks Reaper's recording state and starts/stops
    the whisper process accordingly.
    """
    global g_is_recording
    
    # RPR_GetPlayState() returns a bitmask: &1=play, &2=pause, &4=record
    is_currently_recording = (RPR_GetPlayState() & 4) != 0

    if is_currently_recording and not g_is_recording:
        # Recording has just started
        log("Reaper recording started. Starting transcription...")
        g_is_recording = True
        start_process()
        RPR_defer("check_recording_state()") # Continue monitoring
    elif not is_currently_recording and g_is_recording:
        # Recording has just stopped
        log("Reaper recording stopped. Stopping transcription...")
        g_is_recording = False
        stop_process()
        log("Script finished. Run action again to restart monitoring.")
        # Do not defer here, which stops the main loop.
    else:
        # Not recording yet, or already stopped. Keep waiting.
        RPR_defer("check_recording_state()")


def __reaper_atexit():
    """

    This special function is called by Reaper when the script is terminated.
    Ensures the whisper-stream process is cleaned up properly.
    """
    log("Script terminated. Cleaning up...")
    stop_process()

# Start the main loop that checks the recording state.
if check_reaper_context():
    check_recording_state()

