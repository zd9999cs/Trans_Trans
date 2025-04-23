# Audio/Video Transcription and Subtitle Generator

This is an integrated audio/video processing tool that can transcribe long audio or video files into text and generate SRT subtitles using Google Gemini. The tool automatically handles the entire process, including: audio extraction from video, audio splitting, transcription, translation, and subtitle generation.

[中文版说明](README_CN.md)

## Main Features

- **Video Processing**: Automatically extract audio from video files
- **Intelligent Audio Splitting**: Automatically split long audio files into smaller segments based on silence detection
- **Audio Transcription and Translation**: Use Google Gemini AI to transcribe audio to text and translate into multiple languages
- **Multilingual Support**: Support for translating audio content into Simplified Chinese, Traditional Chinese, English, Japanese, Korean, and other languages
- **Multilingual Interface**: Support for Chinese and English interfaces, switchable at any time
- **Subtitle Timestamp Generation**: Automatically add precise timestamps to transcriptions and translations
- **SRT Subtitle Generation**: Merge all transcription segments to generate standard SRT format subtitle files
- **Graphical User Interface**: Provide an intuitive interface to simplify the processing workflow
- **Flexible Output Options**: Support for transcription-only, translation-only, or both in subtitle files
- **Process Interruption**: Support for forcibly terminating ongoing processing tasks at any time

## System Requirements

- Python 3.8+
- FFmpeg (for video processing)
- Required Python libraries (see Installation section)
- Google AI API Key (Gemini 2.5 model)

## Installation

1. Clone or download this repository

2. Install the necessary Python dependencies:

```bash
pip install pydub librosa soundfile google-genai numpy psutil mutagen
```

3. Ensure FFmpeg is installed on your system (for video processing):

```bash
# On Ubuntu/Debian systems
sudo apt-get install ffmpeg

# On macOS (using Homebrew)
brew install ffmpeg

# On Windows
# Download from https://ffmpeg.org/download.html and add to your system PATH
```

4. Configure Google AI API Key:
   - Obtain a Google Gemini API key
   - You can set the environment variable `GOOGLE_API_KEY`, or enter it manually when using the tool

## Usage

### Graphical Interface Version

1. Run the GUI application:

```bash
python audio_processor_gui.py
```

2. In the interface:
   - Select interface language (Chinese or English)
   - Select input file (audio or video)
   - Enter Google AI API key
   - Adjust processing parameters (if needed)
   - Click "Start Processing"
   - To interrupt processing, click the "Stop Processing" button to forcibly terminate all processing processes

### Command Line Version

```bash
python process_audio.py input_file.mp3 --api-key YOUR_API_KEY [other options]
```

Examples:

```bash
# Basic usage
python process_audio.py recording.mp3 --api-key YOUR_API_KEY

# Process video and include both transcription and translation
python process_audio.py video.mp4 --api-key YOUR_API_KEY --content both

# Use a different target language (translate to English)
python process_audio.py chinese_speech.mp3 --api-key YOUR_API_KEY --target-language "English"

# Use Japanese as the target language
python process_audio.py speech.mp3 --api-key YOUR_API_KEY --target-language "Japanese"

# Adjust audio splitting parameters
python process_audio.py long_audio.mp3 --api-key YOUR_API_KEY --max-length 240 --silence-length 700 --silence-threshold -45

# Specify output directory and clean up intermediate files
python process_audio.py speech.mp3 --api-key YOUR_API_KEY --output-dir ./output_directory --cleanup
```

### Main Parameters

- `--api-key`: Google AI API Key (**required**)
- `--output-dir`: Output directory (defaults to creating a directory using the input filename)
- `--target-language`: Target language for translation (default is "Simplified Chinese", options include: Traditional Chinese, English, Japanese, Korean, etc.)
- `--content`: Choose subtitle content type
  - `transcript`: Transcription only
  - `translation`: Translation only
  - `both`: Both transcription and translation (default)
- `--model-name`: Gemini model to use for transcription (default: gemini-2.5-pro-preview-03-25)
- `--max-length`: Maximum audio segment length (seconds, default 300)
- `--silence-length`: Minimum length for silence detection (milliseconds, default 500)
- `--silence-threshold`: Silence detection threshold (dB, default -40)
- `--first-chunk-offset`: Time offset for the first audio segment (seconds, default 0)
- `--cleanup`: Delete intermediate files after processing

## Workflow

1. **Preprocessing**:
   - If the input is a video file, use FFmpeg to extract audio
   
2. **Audio Splitting**:
   - Detect silence points in the audio
   - Split audio at appropriate silence points
   - Generate multiple smaller audio segments
   
3. **Audio Transcription**:
   - Process each audio segment using Google Gemini AI
   - Generate transcription and translation for each segment
   - Transcription and translation text with timestamps
   
4. **Subtitle Generation**:
   - Calculate cumulative time offsets based on audio segment lengths
   - Merge all transcription files
   - Generate subtitle files in SRT format

## Project Structure

- `split_audio.py`: Audio splitting module
- `transcript.py`: Audio transcription and translation module
- `combine_transcripts.py`: Subtitle merging module
- `process_audio.py`: Main processing workflow coordination module
- `audio_processor_gui.py`: Graphical user interface module
- `verify_durations.py`: Utility script to verify audio chunk durations (for debugging)

## Notes

- Processing long audio/video files may take some time
- API calls may incur costs, depending on your Google AI API usage plan
- The accuracy of subtitle timestamps may vary depending on audio quality
- Internet connection is required to use the Google AI API

## Frequently Asked Questions

1. **Why is it necessary to split audio?**
   - Google Gemini API has limitations on file size and processing duration
   - Splitting into smaller segments improves transcription accuracy and reliability
   
2. **How to adjust timestamp offsets?**
   - If generated subtitles are not synchronized with the video, you can use the `--first-chunk-offset` parameter to adjust

3. **How to handle audio in different languages?**
   - The system automatically detects the audio language and transcribes it, then translates it to the specified target language
   - Default translation is to Simplified Chinese, but can be changed using the `--target-language` parameter

4. **What target languages are supported?**
   - Multiple languages are supported, including: Simplified Chinese, Traditional Chinese, English, Japanese, Korean, Russian, Spanish, French, German, etc.
   - In the GUI interface, you can select from a dropdown menu; in the command line, you can specify via parameter

5. **FFmpeg installation issues?**
   - Ensure FFmpeg is correctly installed and added to your system PATH
   - You can verify the installation by running `ffmpeg -version` in the command line

6. **How to stop ongoing processing?**
   - In the GUI interface, click the "Stop Processing" button
   - The program will forcibly terminate all related processing processes
   - Note: Forced stopping will lose current processing progress

## License

MIT License

Copyright (c) 2025 

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Contribution Guidelines

Contributions to this project are welcome! If you'd like to participate in development, you can follow these steps:

1. Fork this repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

If you find any bugs or have any suggestions for improvements, please feel free to submit an issue.

## TODO

- [ ] Improve recognition when there are multiple people speaking.
- [ ] Anti-degenerecy when repeated word is used in the speech
- [x] API error handling with retrial
- [ ] Parallel use of API? No need to provide context for different chunks it seems.
- [x] Allow selection of different Gemini models (e.g., Pro vs Flash)
- [ ] Imrpove prompt for 2.0 flassh model to work