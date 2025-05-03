# VideoLab Pro

A powerful, modular Python toolkit for automated video processing, editing, and enhancement.

![VideoLab Pro](https://img.shields.io/badge/VideoLab-Pro-brightgreen)
![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

## Overview

VideoLab Pro streamlines video post-production with automated tools for caption generation, dynamic overlay creation, and video enhancement. Built with a modular architecture, it allows for flexible customization and extension of the video processing pipeline.

## Key Features

### Automated Video Editing
- Intelligent caption generation from audio tracks
- Dynamic overlay creation and positioning
- Video fixing and enhancement capabilities
- AI-generated human-like emotional song transcription overlays

### Modular Architecture
- Separate modules for each function
- Main orchestrator for seamless workflow
- Easy to extend with new features

### Media Processing
- Audio extraction (WAV/MP3)
- Subtitle generation (SRT)
- Emotional song transcription with mood detection
- High-quality video output generation

## Installation

### Prerequisites
- Python 3.8 or higher
- FFmpeg installed and available in PATH
- Git (for cloning repository)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/Swapnil565/videolab-pro.git
cd videolab-pro
```

2. Create and activate a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

## Project Structure

```
videolab-pro/
├── main.py                  # Main application orchestrator
├── fixed_video.py           # Video repair and enhancement
├── caption/
│   ├── create_caption.py    # Caption generation
│   ├── make_caption.py      # Caption formatting and styling
│   └── emotional_song.py    # AI emotional song transcription
├── overlay/
│   ├── create_overlay.py    # Overlay creation
│   └── make_overlay.py      # Overlay application
├── config/
│   └── settings.py          # Configuration settings
├── utils/
│   ├── audio.py             # Audio extraction utilities
│   └── video.py             # Video processing utilities
├── requirements.txt         # Project dependencies
└── .env                     # Environment variables
```

## Usage

### Basic Usage

Process a video with default settings:

```bash
python main.py --input path/to/video.mp4 --output enhanced_video.mp4
```

### Advanced Options

```bash
python main.py --input path/to/video.mp4 --output enhanced_video.mp4 --captions true --overlay logo.png --enhance high --emotional-song true
```

### Processing Pipeline

1. Input video is loaded via `main.py`
2. Audio is extracted for processing
3. Captions are generated from audio
4. AI analyzes audio for emotional content and generates song-like transcriptions
5. Overlays are created and applied
6. Video is enhanced and fixed
7. Final output is rendered and saved

## Configuration Options

Edit the `.env` file to configure default behavior:

```
# Video Processing
DEFAULT_RESOLUTION=1080p
CAPTION_FONT=Arial
CAPTION_SIZE=24

# Emotional Song Processing
EMOTION_DETECTION=true
SONG_STYLE=modern
EMOTION_INTENSITY=medium

# Performance
PROCESSING_THREADS=4
USE_GPU=true

# Output
DEFAULT_FORMAT=mp4
DEFAULT_QUALITY=high
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Development Notes

- Exclude media files (*.mp4, *.wav) and temporary folders (b_roll/, chunks/) from version control
- Run tests before submitting PRs: `python -m unittest discover tests`
- Follow the existing code style and documentation patterns

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- FFmpeg for video processing capabilities
- SpeechRecognition for caption generation
- MoviePy for video editing features
- AI emotion detection libraries for song-like emotional transcriptions
