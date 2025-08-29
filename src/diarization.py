"""
说话人分离模块

使用diart库进行说话人分离，支持CPU和GPU推理。
返回标准化的说话人片段数据。
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger

from .config import get_config
from .exceptions import DiarizationError, ModelLoadError


class SpeakerDiarizer:
    """说话人分离器类"""
    
    def __init__(self, config_override: Optional[Dict[str, Any]] = None):
        """
        初始化说话人分离器
        
        Args:
            config_override: 配置覆盖参数
        """
        self.config = get_config()
        self.diarization_config = self.config.get_diarization_config()
        
        # 应用配置覆盖
        if config_override:
            self.diarization_config.update(config_override)
        
        self.engine = None
        self.logger = logger.bind(name="SpeakerDiarizer")
    
    def _load_engine(self) -> None:
        """延迟加载diarization引擎"""
        if self.engine is not None:
            return
        
        try:
            import diart
            from diart import SpeakerDiarization
            
            num_speakers = self.diarization_config.get("num_speakers", 2)
            device = self.diarization_config.get("device", "cpu")
            
            self.logger.info(f"正在初始化说话人分离引擎: {num_speakers}个说话人 (设备: {device})")
            
            # 使用正确的 diart API
            self.engine = SpeakerDiarization()
            
            self.logger.success("说话人分离引擎初始化成功")
            
        except ImportError as e:
            error_msg = (
                "diart库未安装或版本不兼容。\n"
                "请运行: pip install diart onnxruntime\n"
                "并确保已接受Hugging Face模型使用条款"
            )
            self.logger.error(error_msg)
            raise ModelLoadError(error_msg) from e
        except Exception as e:
            error_msg = f"说话人分离引擎初始化失败: {e}"
            self.logger.error(error_msg)
            raise ModelLoadError(error_msg) from e
    
    def diarize_audio(self, audio_path: str) -> List[Dict[str, Any]]:
        """
        对音频文件进行说话人分离
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            说话人片段列表，每个片段包含start, end, speaker字段
            
        Raises:
            DiarizationError: 分离失败时抛出
        """
        audio_file = Path(audio_path)
        if not audio_file.exists():
            raise DiarizationError(f"音频文件不存在: {audio_path}")
        
        self._load_engine()
        
        try:
            import librosa
            from diart.sources import FileAudioSource
            
            self.logger.info(f"开始说话人分离: {audio_file.name}")
            
            # 获取音频文件信息
            audio_data, sample_rate = librosa.load(str(audio_file), sr=None)
            
            # 创建音频源
            source = FileAudioSource(str(audio_file), sample_rate)
            
            # 执行分离
            result = self.engine(source)
            
            # 转换结果为标准格式
            segments = self._convert_result_to_segments(result)
            
            self.logger.success(f"说话人分离完成，共 {len(segments)} 个片段")
            return segments
            
        except Exception as e:
            error_msg = f"说话人分离失败: {e}"
            self.logger.error(error_msg)
            raise DiarizationError(error_msg) from e
    
    def _convert_result_to_segments(self, result) -> List[Dict[str, Any]]:
        """
        转换diart结果为标准格式
        
        Args:
            result: diart分离结果
            
        Returns:
            标准化的片段列表
        """
        segments = []
        
        try:
            # 尝试使用新的API
            for (segment, track), label in result.itertracks(yield_label=True):
                segments.append({
                    "start": float(segment.start),
                    "end": float(segment.end),
                    "speaker": str(label)
                })
        except AttributeError:
            # 兼容旧的API
            try:
                for label in getattr(result, "labels_", []):
                    timeline = result.get_timeline(label)
                    for seg in timeline:
                        segments.append({
                            "start": float(seg.start),
                            "end": float(seg.end), 
                            "speaker": str(label)
                        })
            except Exception as e:
                self.logger.warning(f"结果转换失败，使用fallback方法: {e}")
                # 最后的fallback方法
                segments = self._fallback_conversion(result)
        
        # 标准化说话人标签
        segments = self._normalize_speaker_labels(segments)
        
        # 按时间排序
        segments.sort(key=lambda x: x["start"])
        
        # 过滤太短的片段
        min_length = self.diarization_config.get("min_segment_length", 0.5)
        segments = [s for s in segments if s["end"] - s["start"] >= min_length]
        
        return segments
    
    def _fallback_conversion(self, result) -> List[Dict[str, Any]]:
        """
        备用的结果转换方法
        
        Args:
            result: 分离结果
            
        Returns:
            片段列表
        """
        # 这是一个简单的fallback实现
        # 实际项目中可能需要根据具体的diart版本调整
        segments = []
        
        try:
            # 尝试直接访问时间轴数据
            if hasattr(result, "_timeline"):
                timeline = result._timeline
                for track in timeline.tracks():
                    for segment in timeline.track(track):
                        segments.append({
                            "start": float(segment.start),
                            "end": float(segment.end),
                            "speaker": f"SPEAKER_{track:02d}"
                        })
        except Exception:
            self.logger.warning("Fallback转换也失败，返回空结果")
        
        return segments
    
    def _normalize_speaker_labels(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        标准化说话人标签为SPEAKER_00, SPEAKER_01格式
        
        Args:
            segments: 片段列表
            
        Returns:
            标准化后的片段列表
        """
        # 收集所有唯一的说话人标签
        unique_speakers = sorted(set(seg["speaker"] for seg in segments))
        
        # 创建映射表
        speaker_map = {}
        for i, speaker in enumerate(unique_speakers):
            speaker_map[speaker] = f"SPEAKER_{i:02d}"
        
        # 应用映射
        for segment in segments:
            segment["speaker"] = speaker_map[segment["speaker"]]
        
        return segments


def diarize_audio_to_segments(audio_path: str, **kwargs) -> List[Dict[str, Any]]:
    """
    快速分离函数 - 兼容原有接口
    
    Args:
        audio_path: 音频文件路径
        **kwargs: 配置覆盖参数
        
    Returns:
        说话人片段列表
    """
    # 将旧的参数名映射到新的配置格式
    config_override = {}
    if "device" in kwargs:
        config_override["device"] = kwargs["device"]
    if "num_speakers" in kwargs:
        config_override["num_speakers"] = kwargs["num_speakers"]
    
    diarizer = SpeakerDiarizer(config_override=config_override)
    return diarizer.diarize_audio(audio_path)