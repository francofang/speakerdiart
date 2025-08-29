"""
自定义异常模块

定义应用程序中使用的各种自定义异常类。
"""


class SpeakerDiartError(Exception):
    """基础异常类"""
    pass


class TranscriptionError(SpeakerDiartError):
    """转录相关异常"""
    pass


class DiarizationError(SpeakerDiartError):
    """说话人分离相关异常"""
    pass


class PostProcessingError(SpeakerDiartError):
    """后处理相关异常"""
    pass


class ConfigurationError(SpeakerDiartError):
    """配置相关异常"""
    pass


class ModelLoadError(SpeakerDiartError):
    """模型加载异常"""
    pass


class AudioProcessingError(SpeakerDiartError):
    """音频处理异常"""
    pass


class FileFormatError(SpeakerDiartError):
    """文件格式异常"""
    pass