# Reaper whisper-stream integration

This ReaScript provides real-time audio transcription in [REAPER](https://www.reaper.fm/) by integrating [`whisper.cpp`](https://github.com/ggml-org/whisper.cpp)'s `whisper-stream` tool. The script automatically starts transcribing when Reaper is recording and adds the text as project markers on the timeline.

## Requirements

1. **REAPER:** The script must be run inside the Reaper DAW. [7.40]
2. **Python for ReaScript:** A configured Python 3 installation is required. [3.13]
3. **whisper.cpp:** A compiled version of the `whisper.cpp` project. [1ad258c]
4. **A Whisper Model:** A GGML-format model file (e.g., [`ggml-base.en.bin`](https://huggingface.co/ggerganov/whisper.cpp/blob/main/ggml-base.en.bin)).

## Setup

* Compile whisper.cpp with `-DWHISPER_SDL2=ON` to allow for audio device input. 
* Run `./build/bin/whisper-stream` in your command prompt to determine the ID of your intended capture device. This should match the input device you are using in Reaper.
* Open the `whisper_stream_to_markers.py` script and edit the `WHISPER_DEVICE`, `WHISPER_EXECUTABLE` and `WHISPER_MODEL` variables to match the details on your system.

## Usage

Run the script from the Reaper Action List to open its console and begin monitoring. When you press record in Reaper, the script will automatically launch `whisper-stream` and start transcribing. Markers will appear on the timeline as you record.

When you stop recording, the transcription process will automatically stop and the script will terminate.

## Configuration

You can adjust the `LENGTH_MS` (audio chunk length) and `STEP_MS` (processing interval) values in the script's configuration section. These values determine the `g_commit_interval`, which controls how often markers are created. Larger values tend to increase the accuracy and reduce responsiveness.
