"""
音频转录模块

使用faster-whisper进行高效的语音转文字转录，支持多种音频格式。
优化了CPU性能，支持GPU加速。
"""

import io
from pathlib import Path
from typing import Iterable, Tuple, Dict, Any, Optional
from loguru import logger

from .config import get_config
from .exceptions import TranscriptionError


def _format_timestamp(seconds: float) -> str:
    """
    将秒数转换为WebVTT时间格式
    
    Args:
        seconds: 秒数
        
    Returns:
        格式化的时间字符串 (HH:MM:SS.mmm)
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def _segments_to_vtt(segments: Iterable[Tuple[float, float, str]]) -> str:
    """
    将转录片段转换为WebVTT格式
    
    Args:
        segments: 转录片段列表 (start_time, end_time, text)
        
    Returns:
        WebVTT格式的字符串
    """
    buffer = io.StringIO()
    buffer.write("WEBVTT\n\n")
    
    for start_time, end_time, text in segments:
        if text.strip():  # 跳过空文本
            buffer.write(f"{_format_timestamp(start_time)} --> {_format_timestamp(end_time)}\n")
            buffer.write(f"{text.strip()}\n\n")
    
    return buffer.getvalue()


class WhisperTranscriber:
    """Whisper转录器类"""
    
    def __init__(self, config_override: Optional[Dict[str, Any]] = None):
        """
        初始化转录器
        
        Args:
            config_override: 配置覆盖参数
        """
        self.config = get_config()
        self.whisper_config = self.config.get_whisper_config()
        
        # 应用配置覆盖
        if config_override:
            self.whisper_config.update(config_override)
        
        self.model = None
        self.logger = logger.bind(name="WhisperTranscriber")
        
    def _load_model(self):
        """延迟加载Whisper模型"""
        if self.model is not None:
            return
            
        try:
            from faster_whisper import WhisperModel
            
            model_size = self.whisper_config.get("model_size", "small")
            device = self.whisper_config.get("device", "cpu")
            
            self.logger.info(f"正在加载Whisper模型: {model_size} (设备: {device})")
            self.model = WhisperModel(model_size, device=device)
            self.logger.success("Whisper模型加载成功")
            
        except ImportError as e:
            raise TranscriptionError(
                "faster-whisper库未安装。请运行: pip install faster-whisper"
            ) from e
        except Exception as e:
            raise TranscriptionError(f"Whisper模型加载失败: {e}") from e
    
    def transcribe_to_vtt(self, audio_path: str) -> str:
        """
        转录音频文件为WebVTT格式
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            WebVTT格式的转录文本
            
        Raises:
            TranscriptionError: 转录失败时抛出
        """
        audio_file = Path(audio_path)
        if not audio_file.exists():
            raise TranscriptionError(f"音频文件不存在: {audio_path}")
        
        self._load_model()
        
        try:
            language = self.whisper_config.get("language", "zh")
            task = self.whisper_config.get("task", "transcribe")
            vad_filter = self.whisper_config.get("vad_filter", True)
            vad_parameters = self.whisper_config.get("vad_parameters", {})
            
            self.logger.info(f"开始转录音频文件: {audio_file.name}")
            self.logger.debug(f"转录参数 - 语言: {language}, 任务: {task}, VAD: {vad_filter}")
            
            segments, info = self.model.transcribe(
                str(audio_file),
                language=language,
                task=task,
                vad_filter=vad_filter,
                vad_parameters=vad_parameters,
            )
            
            self.logger.info(f"转录信息 - 语言: {info.language}, 概率: {info.language_probability:.2f}")
            
            # 收集转录片段
            collected_segments = []
            segment_count = 0
            
            for segment in segments:
                if segment.text.strip():  # 跳过空文本段
                    collected_segments.append((segment.start, segment.end, segment.text))
                    segment_count += 1
            
            self.logger.success(f"转录完成，共 {segment_count} 个片段")
            
            if not collected_segments:
                self.logger.warning("转录结果为空")
                return "WEBVTT\n\n"
            
            return _segments_to_vtt(collected_segments)
            
        except Exception as e:
            error_msg = f"音频转录失败: {e}"
            self.logger.error(error_msg)
            raise TranscriptionError(error_msg) from e
    
    def transcribe_to_segments(self, audio_path: str) -> list:
        """
        转录音频文件为片段列表
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            片段列表，每个片段包含start, end, text字段
        """
        audio_file = Path(audio_path)
        if not audio_file.exists():
            raise TranscriptionError(f"音频文件不存在: {audio_path}")
        
        self._load_model()
        
        try:
            language = self.whisper_config.get("language", "zh")
            task = self.whisper_config.get("task", "transcribe")
            vad_filter = self.whisper_config.get("vad_filter", True)
            vad_parameters = self.whisper_config.get("vad_parameters", {})
            
            self.logger.info(f"开始转录音频文件: {audio_file.name}")
            
            segments, _ = self.model.transcribe(
                str(audio_file),
                language=language,
                task=task,
                vad_filter=vad_filter,
                vad_parameters=vad_parameters,
            )
            
            # 转换为标准格式
            result_segments = []
            for segment in segments:
                if segment.text.strip():
                    result_segments.append({
                        "start": float(segment.start),
                        "end": float(segment.end),
                        "text": segment.text.strip()
                    })
            
            self.logger.success(f"转录完成，共 {len(result_segments)} 个片段")
            return result_segments
            
        except Exception as e:
            error_msg = f"音频转录失败: {e}"
            self.logger.error(error_msg)
            raise TranscriptionError(error_msg) from e


def transcribe_to_vtt(audio_path: str, **kwargs) -> str:
    """
    快速转录函数 - 兼容原有接口
    
    Args:
        audio_path: 音频文件路径
        **kwargs: 配置覆盖参数
        
    Returns:
        WebVTT格式的转录文本
    """
    transcriber = WhisperTranscriber(config_override=kwargs)
    return transcriber.transcribe_to_vtt(audio_path)


def get_supported_formats() -> list:
    """
    获取支持的音频格式列表
    
    Returns:
        支持的文件扩展名列表
    """
    config = get_config()
    return config.get("audio.supported_extensions", [
        ".wav", ".mp3", ".m4a", ".mp4", ".flac", 
        ".aac", ".wma", ".mkv", ".mov"
    ])