"""
端到端处理管道

协调Whisper转录、diart说话人分离、文本合并和ChatGPT后处理的完整流程。
支持灵活的配置和错误处理。
"""

from pathlib import Path
from typing import Optional, Dict, Any, List
from loguru import logger

from .config import get_config
from .transcription import WhisperTranscriber
from .diarization import SpeakerDiarizer
from .merge import VTTParser, SpeakerMapper, OutputFormatter
from .postprocess import ChatGPTProcessor, TextProcessor
from .monitoring import PerformanceTracker
from .exceptions import SpeakerDiartError, TranscriptionError, DiarizationError, PostProcessingError


class ProcessingPipeline:
    """音频处理管道"""
    
    def __init__(self, config_override: Optional[Dict[str, Any]] = None):
        """
        初始化处理管道
        
        Args:
            config_override: 配置覆盖参数
        """
        self.config = get_config()
        self.logger = logger.bind(name="ProcessingPipeline")
        
        # 应用配置覆盖
        self.pipeline_config = config_override or {}
        
        # 初始化组件
        self.transcriber = None
        self.diarizer = None
        self.chatgpt_processor = None
        self.text_processor = TextProcessor()
        
        # 性能监控
        metrics_file = self.config.logs_dir / "metrics.json"
        self.performance_tracker = PerformanceTracker(str(metrics_file))
        
        # 处理结果缓存
        self._last_result = None
    
    def _init_transcriber(self) -> None:
        """初始化转录器"""
        if self.transcriber is None:
            whisper_config = self.pipeline_config.get("whisper", {})
            self.transcriber = WhisperTranscriber(config_override=whisper_config)
    
    def _init_diarizer(self) -> None:
        """初始化说话人分离器"""
        if self.diarizer is None:
            diarization_config = self.pipeline_config.get("diarization", {})
            self.diarizer = SpeakerDiarizer(config_override=diarization_config)
    
    def _init_chatgpt_processor(self) -> None:
        """初始化ChatGPT处理器"""
        if self.chatgpt_processor is None:
            chatgpt_config = self.pipeline_config.get("chatgpt", {})
            self.chatgpt_processor = ChatGPTProcessor(config_override=chatgpt_config)
    
    def process_audio(self, audio_path: str, **kwargs) -> Dict[str, Any]:
        """
        处理音频文件的完整流程
        
        Args:
            audio_path: 音频文件路径
            **kwargs: 其他处理参数
            
        Returns:
            处理结果字典，包含:
            - vtt_text: VTT格式转录文本
            - speakers: 说话人片段列表
            - merged_text: 合并后的文本
            - polished_text: ChatGPT润色后的文本（如果启用）
            - processing_info: 处理信息
            
        Raises:
            SpeakerDiartError: 处理失败时抛出
        """
        audio_file = Path(audio_path)
        if not audio_file.exists():
            raise SpeakerDiartError(f"音频文件不存在: {audio_path}")
        
        self.logger.info(f"开始处理音频文件: {audio_file.name}")
        
        # 开始性能监控
        metrics = self.performance_tracker.start_processing(str(audio_file))
        
        result = {
            "vtt_text": "",
            "speakers": [],
            "merged_text": "",
            "polished_text": None,
            "processing_info": {
                "audio_file": str(audio_file),
                "stages_completed": [],
                "errors": []
            }
        }
        
        try:
            # 第一步：音频转录
            self.logger.info("步骤 1/4: 开始音频转录...")
            self._init_transcriber()
            
            self.performance_tracker.start_stage("transcription")
            vtt_text = self.transcriber.transcribe_to_vtt(str(audio_file))
            self.performance_tracker.end_stage("transcription")
            
            result["vtt_text"] = vtt_text
            result["processing_info"]["stages_completed"].append("transcription")
            
            if not vtt_text.strip():
                self.logger.warning("转录结果为空")
                return result
            
            # 第二步：说话人分离
            self.logger.info("步骤 2/4: 开始说话人分离...")
            self._init_diarizer()
            
            self.performance_tracker.start_stage("diarization")
            speaker_segments = self.diarizer.diarize_audio(str(audio_file))
            self.performance_tracker.end_stage("diarization")
            
            result["speakers"] = speaker_segments
            result["processing_info"]["stages_completed"].append("diarization")
            
            if not speaker_segments:
                self.logger.warning("说话人分离结果为空")
            
            # 第三步：合并转录和说话人信息
            self.logger.info("步骤 3/4: 开始合并处理...")
            self.performance_tracker.start_stage("merging")
            merged_text = self._merge_transcription_and_speakers(vtt_text, speaker_segments)
            self.performance_tracker.end_stage("merging")
            
            result["merged_text"] = merged_text
            result["processing_info"]["stages_completed"].append("merging")
            
            # 第四步：ChatGPT后处理（可选）
            use_chatgpt = kwargs.get("use_chatgpt", self.config.get("chatgpt.enabled", False))
            if use_chatgpt and merged_text.strip():
                self.logger.info("步骤 4/4: 开始ChatGPT润色...")
                try:
                    self._init_chatgpt_processor()
                    self.performance_tracker.start_stage("postprocessing")
                    api_key = kwargs.get("openai_api_key")
                    polished_text = self.chatgpt_processor.polish_text(merged_text, api_key=api_key)
                    self.performance_tracker.end_stage("postprocessing")
                    result["polished_text"] = polished_text
                    result["processing_info"]["stages_completed"].append("chatgpt_polishing")
                except PostProcessingError as e:
                    self.performance_tracker.end_stage("postprocessing")
                    self.logger.error(f"ChatGPT润色失败: {e}")
                    result["processing_info"]["errors"].append(f"ChatGPT润色失败: {e}")
                    self.performance_tracker.add_error(f"ChatGPT润色失败: {e}")
                    # 应用基础格式化作为备选
                    result["polished_text"] = self.text_processor.basic_formatting(merged_text)
            else:
                self.logger.info("跳过ChatGPT润色")
                # 应用基础格式化
                result["polished_text"] = self.text_processor.basic_formatting(merged_text)
            
            # 添加结果统计到性能追踪
            self.performance_tracker.add_result_stats(result)
            
            # 完成性能追踪
            final_metrics = self.performance_tracker.finish_processing()
            result["processing_info"]["performance_metrics"] = final_metrics.to_dict()
            
            self.logger.success(f"音频处理完成: {audio_file.name}")
            self._last_result = result
            
            return result
            
        except Exception as e:
            error_msg = f"音频处理失败: {e}"
            self.logger.error(error_msg)
            result["processing_info"]["errors"].append(error_msg)
            
            # 记录错误到性能追踪
            self.performance_tracker.add_error(error_msg)
            final_metrics = self.performance_tracker.finish_processing()
            result["processing_info"]["performance_metrics"] = final_metrics.to_dict()
            
            raise SpeakerDiartError(error_msg) from e
    
    def _merge_transcription_and_speakers(self, vtt_text: str, speaker_segments: List[Dict[str, Any]]) -> str:
        """
        合并转录文本和说话人信息
        
        Args:
            vtt_text: VTT格式的转录文本
            speaker_segments: 说话人片段列表
            
        Returns:
            合并后的文本
        """
        # 解析VTT
        vtt_parser = VTTParser()
        subtitles = vtt_parser.parse(vtt_text)
        
        if not subtitles:
            self.logger.warning("VTT解析结果为空")
            return ""
        
        # 映射说话人
        speaker_mapper = SpeakerMapper()
        speaker_mapper.map_speakers_to_subtitles(subtitles, speaker_segments)
        
        # 格式化输出
        formatter = OutputFormatter()
        merged_text = formatter.format_output(subtitles, use_custom_labels=True)
        
        return merged_text
    
    def process_existing_files(self, vtt_file: str, rttm_file: str, **kwargs) -> Dict[str, Any]:
        """
        处理现有的VTT和RTTM文件
        
        Args:
            vtt_file: VTT文件路径
            rttm_file: RTTM文件路径
            **kwargs: 其他处理参数
            
        Returns:
            处理结果字典
        """
        vtt_path = Path(vtt_file)
        rttm_path = Path(rttm_file)
        
        if not vtt_path.exists():
            raise SpeakerDiartError(f"VTT文件不存在: {vtt_file}")
        if not rttm_path.exists():
            raise SpeakerDiartError(f"RTTM文件不存在: {rttm_file}")
        
        self.logger.info(f"处理现有文件: {vtt_path.name} + {rttm_path.name}")
        
        try:
            # 读取文件内容
            with open(vtt_path, 'r', encoding='utf-8') as f:
                vtt_content = f.read()
            
            with open(rttm_path, 'r', encoding='utf-8') as f:
                rttm_content = f.read()
            
            # 解析文件
            from .merge import RTTMParser
            
            vtt_parser = VTTParser()
            rttm_parser = RTTMParser()
            
            subtitles = vtt_parser.parse(vtt_content)
            speakers = rttm_parser.parse(rttm_content)
            
            # 映射和格式化
            speaker_mapper = SpeakerMapper()
            speaker_mapper.map_speakers_to_subtitles(subtitles, speakers)
            
            formatter = OutputFormatter()
            merged_text = formatter.format_output(subtitles, use_custom_labels=True)
            
            result = {
                "vtt_text": vtt_content,
                "speakers": speakers,
                "merged_text": merged_text,
                "polished_text": None,
                "processing_info": {
                    "vtt_file": str(vtt_path),
                    "rttm_file": str(rttm_path),
                    "stages_completed": ["file_parsing", "merging"],
                    "errors": []
                }
            }
            
            # ChatGPT后处理
            use_chatgpt = kwargs.get("use_chatgpt", self.config.get("chatgpt.enabled", False))
            if use_chatgpt and merged_text.strip():
                try:
                    self._init_chatgpt_processor()
                    api_key = kwargs.get("openai_api_key")
                    polished_text = self.chatgpt_processor.polish_text(merged_text, api_key=api_key)
                    result["polished_text"] = polished_text
                    result["processing_info"]["stages_completed"].append("chatgpt_polishing")
                except PostProcessingError as e:
                    self.logger.error(f"ChatGPT润色失败: {e}")
                    result["processing_info"]["errors"].append(f"ChatGPT润色失败: {e}")
                    result["polished_text"] = self.text_processor.basic_formatting(merged_text)
            else:
                result["polished_text"] = self.text_processor.basic_formatting(merged_text)
            
            self.logger.success("文件处理完成")
            return result
            
        except Exception as e:
            error_msg = f"文件处理失败: {e}"
            self.logger.error(error_msg)
            raise SpeakerDiartError(error_msg) from e
    
    def get_last_result(self) -> Optional[Dict[str, Any]]:
        """获取上次处理的结果"""
        return self._last_result
    
    def export_results(self, result: Dict[str, Any], output_dir: str, base_name: str) -> List[str]:
        """
        导出处理结果到文件
        
        Args:
            result: 处理结果
            output_dir: 输出目录
            base_name: 基础文件名
            
        Returns:
            导出的文件路径列表
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        exported_files = []
        
        # 导出合并文本
        if result.get("merged_text"):
            merged_file = output_path / f"{base_name}.merged.txt"
            with open(merged_file, 'w', encoding='utf-8') as f:
                f.write(result["merged_text"])
            exported_files.append(str(merged_file))
            self.logger.info(f"已导出合并文本: {merged_file}")
        
        # 导出润色文本
        if result.get("polished_text") and result["polished_text"] != result.get("merged_text"):
            polished_file = output_path / f"{base_name}.polished.txt"
            with open(polished_file, 'w', encoding='utf-8') as f:
                f.write(result["polished_text"])
            exported_files.append(str(polished_file))
            self.logger.info(f"已导出润色文本: {polished_file}")
        
        # 导出中间文件（如果配置启用）
        export_intermediate = self.config.get("output.export_intermediate", False)
        if export_intermediate:
            if result.get("vtt_text"):
                vtt_file = output_path / f"{base_name}.vtt"
                with open(vtt_file, 'w', encoding='utf-8') as f:
                    f.write(result["vtt_text"])
                exported_files.append(str(vtt_file))
                self.logger.info(f"已导出VTT文件: {vtt_file}")
            
            if result.get("speakers"):
                rttm_file = output_path / f"{base_name}.rttm"
                with open(rttm_file, 'w', encoding='utf-8') as f:
                    f.write(self._speakers_to_rttm(result["speakers"], base_name))
                exported_files.append(str(rttm_file))
                self.logger.info(f"已导出RTTM文件: {rttm_file}")
        
        return exported_files
    
    def _speakers_to_rttm(self, speakers: List[Dict[str, Any]], uri: str) -> str:
        """将说话人片段转换为RTTM格式"""
        lines = []
        for segment in speakers:
            start = float(segment["start"])
            end = float(segment["end"])
            duration = max(0.0, end - start)
            speaker = str(segment["speaker"])
            
            # RTTM格式: SPEAKER <uri> 1 <start> <dur> <ortho> <stype> <name> <conf>
            lines.append(
                f"SPEAKER {uri} 1 {start:.3f} {duration:.3f} <NA> <NA> {speaker} <NA>"
            )
        
        return "\n".join(lines) + "\n"


# 便利函数，保持向后兼容性

def run_pipeline(audio_path: str, **kwargs) -> Dict[str, Any]:
    """
    运行完整处理管道（兼容性函数）
    
    Args:
        audio_path: 音频文件路径
        **kwargs: 配置参数
        
    Returns:
        处理结果字典
    """
    # 转换旧的参数名到新的配置格式
    config_override = {}
    
    if "whisper_model" in kwargs:
        config_override["whisper"] = {"model_size": kwargs["whisper_model"]}
    if "device" in kwargs:
        if "whisper" not in config_override:
            config_override["whisper"] = {}
        config_override["whisper"]["device"] = kwargs["device"]
        config_override["diarization"] = {"device": kwargs["device"]}
    if "language" in kwargs:
        if "whisper" not in config_override:
            config_override["whisper"] = {}
        config_override["whisper"]["language"] = kwargs["language"]
    if "num_speakers" in kwargs:
        config_override["diarization"] = {"num_speakers": kwargs["num_speakers"]}
    
    pipeline = ProcessingPipeline(config_override=config_override)
    return pipeline.process_audio(audio_path, **kwargs)