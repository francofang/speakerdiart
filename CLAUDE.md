# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a modern Cantonese interview processing system (v2.0) that combines speech recognition and speaker diarization to create labeled transcripts. The system processes audio/video files through a multi-stage pipeline with comprehensive monitoring, configuration management, and error handling.

**Processing Pipeline:**
1. **Whisper transcription** (via faster-whisper) → VTT format
2. **Speaker diarization** (via diart) → RTTM format  
3. **Merge/mapping** → Speaker-labeled text
4. **Optional ChatGPT post-processing** → Polished output with paragraphs and punctuation

## Architecture v2.0

### Project Structure
```
speakerdiart/
├── src/                    # Main source code
│   ├── __init__.py        # Package initialization
│   ├── __main__.py        # Module entry point
│   ├── config.py          # Configuration management
│   ├── pipeline.py        # Main processing orchestration
│   ├── transcription.py   # Whisper transcription
│   ├── diarization.py     # Speaker diarization
│   ├── merge.py           # VTT/RTTM parsing and merging
│   ├── postprocess.py     # ChatGPT and text processing
│   ├── gui.py             # Modern unified GUI
│   ├── cli.py             # Enhanced command-line interface
│   ├── monitoring.py      # Performance tracking and monitoring
│   ├── logging_setup.py   # Logging configuration
│   └── exceptions.py      # Custom exceptions
├── config/                # Configuration files
│   ├── default.yaml       # Default configuration
│   └── user.yaml          # User customizations (auto-generated)
├── logs/                  # Application logs and metrics
├── outputs/               # Default output directory
├── tests/                 # Test files
├── main.py               # Main entry point
├── requirements.txt      # Python dependencies
├── environment.yml       # Conda environment (CPU)
├── environment-gpu.yml   # Conda environment (GPU)
└── CLAUDE.md            # This file
```

### Core Modules

#### Configuration System (`src/config.py`)
- YAML-based configuration with hierarchical structure
- Environment variable support
- Runtime configuration override
- Auto-saving user preferences

#### Processing Pipeline (`src/pipeline.py`)
- Orchestrates all processing stages with error recovery
- Integrated performance monitoring
- Flexible configuration per processing run
- Support for both audio files and existing VTT/RTTM pairs

#### Modern GUI (`src/gui.py`)
- Unified interface replacing legacy GUIs
- Real-time progress tracking
- Tabbed result display (merged/polished/logs)
- Configuration panel with validation

#### Enhanced CLI (`src/cli.py`)
- Batch processing with progress bars
- Comprehensive argument parsing
- Dry-run mode for validation
- Recursive directory processing

#### Monitoring System (`src/monitoring.py`)
- Real-time resource usage tracking
- Stage-by-stage performance metrics
- Historical performance analysis
- JSON-based metrics storage

## Development Commands

### Environment Setup
```bash
# CPU environment (recommended for development)
conda env create -f environment.yml
conda activate speakerdiart

# GPU environment (for production)
conda env create -f environment-gpu.yml  
conda activate speakerdiart-gpu

# Alternative: pip installation
pip install -r requirements.txt
```

### Running the Application
```bash
# Main entry point - auto-detects GUI vs CLI
python main.py                          # Launch GUI
python main.py audio.wav               # Launch CLI

# Module-based execution
python -m src gui                       # Launch GUI explicitly
python -m src cli audio.wav --chatgpt  # Launch CLI explicitly

# Direct module execution
python src/gui.py                       # GUI only
python src/cli.py audio.wav --help     # CLI with help
```

### Development and Testing
```bash
# Run tests
pytest tests/

# Code formatting and linting
black src/
isort src/
flake8 src/

# Performance analysis
python -c "from src.monitoring import MetricsAnalyzer; print(MetricsAnalyzer('logs/metrics.json').generate_report())"
```

## Configuration Management

### Configuration Files
- `config/default.yaml` - System defaults (do not modify)
- `config/user.yaml` - User customizations (auto-generated)
- Custom config via `--config path/to/config.yaml`

### Key Configuration Sections
- **whisper**: Model size, device, language, VAD settings
- **diarization**: Speaker count, clustering algorithm, device
- **chatgpt**: Model, prompts, API settings
- **output**: Formats, speaker label mapping, export options
- **logging**: Levels, rotation, retention policies
- **gui**: Window settings, themes, auto-save behavior

## Command Line Interface

### Basic Usage
```bash
# Process single file
python main.py audio.wav

# Batch process directory
python main.py /path/to/audio/files --recursive

# GPU accelerated with ChatGPT
python main.py audio.wav --device cuda --chatgpt

# Merge existing files
python main.py --merge audio.vtt audio.rttm

# Custom configuration
python main.py audio.wav --config my_config.yaml
```

### Advanced Options
```bash
# Export intermediate files
python main.py audio.wav --export-intermediate

# Specify output formats
python main.py audio.wav --format txt --format vtt

# Dry run (show files to process)
python main.py /audio/dir --recursive --dry-run

# Verbose logging to file
python main.py audio.wav --verbose --log-file processing.log
```

## Error Handling and Monitoring

### Exception Hierarchy
- `SpeakerDiartError` - Base exception
- `TranscriptionError` - Whisper-related issues
- `DiarizationError` - Speaker separation issues  
- `PostProcessingError` - ChatGPT/text processing issues
- `ConfigurationError` - Configuration problems

### Performance Monitoring
- Automatic resource usage tracking (CPU, memory)
- Stage-by-stage timing analysis
- Historical performance metrics in `logs/metrics.json`
- Built-in performance reporting tools

### Logging
- Structured logging with loguru
- Automatic log rotation and retention
- Multiple output levels (DEBUG, INFO, WARNING, ERROR)
- Per-component logger binding for troubleshooting

## Dependencies and Compatibility

### Core Dependencies
- `faster-whisper>=1.0.3` - CPU-optimized Whisper
- `diart>=0.9.0` - Speaker diarization
- `onnxruntime>=1.17.0` - AI inference backend
- `loguru>=0.7.0` - Advanced logging
- `pyyaml>=6.0` - Configuration management

### Audio Processing
- `librosa>=0.10.0` - Audio analysis utilities
- `soundfile>=0.12.0` - Audio file I/O

### Optional Dependencies  
- `openai>=1.0` - ChatGPT integration
- `psutil` - System monitoring
- `tkinter-tooltip>=2.1.0` - GUI enhancements

### Environment Requirements
- **Python**: 3.10, 3.11, or 3.12
- **System**: FFmpeg, PortAudio, libsndfile
- **GPU**: CUDA 12 + cuDNN 9 (optional)

## File Formats and Data Flow

### Supported Input Formats
Audio: `.wav`, `.mp3`, `.m4a`, `.flac`, `.aac`, `.wma`  
Video: `.mp4`, `.mkv`, `.mov`

### Processing Data Flow
1. **Audio** → Whisper → **VTT** (timed transcription)
2. **Audio** → Diart → **Speaker segments** (time + speaker ID)
3. **VTT + Segments** → Merge → **Labeled text** (speaker tags)
4. **Labeled text** → ChatGPT → **Polished output** (optional)

### Output Formats
- **Primary**: `.merged.txt` (speaker-labeled transcript)
- **Polished**: `.polished.txt` (ChatGPT-enhanced version)
- **Intermediate**: `.vtt` (subtitles), `.rttm` (speaker timeline)

## Integration Notes

### Hugging Face Integration
Requires accepting terms for pyannote models:
- `pyannote/segmentation-3.0`
- `pyannote/speaker-diarization-3.1`

### API Keys
- OpenAI: Set `OPENAI_API_KEY` environment variable or configure in GUI
- Hugging Face: Create access token at hf.co/settings/tokens

### Performance Optimization
- CPU: Use `model_size: small` for balanced speed/quality
- GPU: Ensure CUDA toolkit matches environment requirements  
- Memory: Monitor peak usage in logs for large files
- Batch: Use CLI recursive mode for multiple files