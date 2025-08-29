"""
合并处理模块

提供VTT字幕和RTTM说话人数据的解析、合并功能。
将转录文本与说话人信息进行时间对齐和标记。
"""

from typing import List, Dict, Optional, Set, Any
from loguru import logger

from .config import get_config
from .exceptions import FileFormatError


def convert_to_seconds(time_str: str) -> float:
    """
    将时间字符串转换为秒数
    
    Args:
        time_str: 时间字符串，支持 "MM:SS" 或 "HH:MM:SS" 格式
        
    Returns:
        秒数
        
    Raises:
        FileFormatError: 时间格式错误
    """
    try:
        parts = time_str.strip().split(":")
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        elif len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + float(seconds)
        else:
            raise ValueError(f"不支持的时间格式: {time_str}")
    except (ValueError, IndexError) as e:
        raise FileFormatError(f"时间格式错误: {time_str}") from e


class VTTParser:
    """WebVTT格式解析器"""
    
    def __init__(self):
        self.logger = logger.bind(name="VTTParser")
    
    def parse(self, vtt_content: str) -> List[Dict[str, Any]]:
        """
        解析VTT内容为字幕片段
        
        Args:
            vtt_content: VTT格式的字符串内容
            
        Returns:
            字幕片段列表，每个片段包含start, end, text, speakers字段
            
        Raises:
            FileFormatError: VTT格式错误
        """
        if not vtt_content.strip():
            return []
        
        subtitles = []
        entries = vtt_content.strip().split("\n\n")
        
        for entry in entries:
            entry = entry.strip()
            if not entry or entry == "WEBVTT":
                continue
            
            if "-->" in entry:
                lines = entry.split("\n")
                if len(lines) < 1:
                    continue
                
                try:
                    # 解析时间行
                    time_line = lines[0]
                    if "-->" not in time_line:
                        continue
                    
                    start_time_str, end_time_str = time_line.split(" --> ")
                    start_time = convert_to_seconds(start_time_str.strip())
                    end_time = convert_to_seconds(end_time_str.strip())
                    
                    # 提取文本内容
                    text_lines = lines[1:] if len(lines) > 1 else []
                    text = "\n".join(text_lines).strip()
                    
                    if text:  # 只添加非空文本的片段
                        subtitles.append({
                            "start": start_time,
                            "end": end_time,
                            "text": text,
                            "speakers": None  # 初始化为None，稍后映射说话人
                        })
                
                except Exception as e:
                    self.logger.warning(f"跳过无效的VTT条目: {e}")
                    continue
        
        self.logger.info(f"解析VTT完成，共 {len(subtitles)} 个字幕片段")
        return subtitles


class RTTMParser:
    """RTTM格式解析器"""
    
    def __init__(self):
        self.logger = logger.bind(name="RTTMParser")
    
    def parse(self, rttm_content: str) -> List[Dict[str, Any]]:
        """
        解析RTTM内容为说话人片段
        
        Args:
            rttm_content: RTTM格式的字符串内容
            
        Returns:
            说话人片段列表，每个片段包含start, end, speaker字段
            
        Raises:
            FileFormatError: RTTM格式错误
        """
        if not rttm_content.strip():
            return []
        
        speakers = []
        lines = rttm_content.strip().split("\n")
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            
            # 跳过空行和注释
            if not line or line.startswith("#"):
                continue
            
            try:
                parts = line.split()
                if len(parts) < 8:
                    self.logger.warning(f"RTTM第{line_num}行格式不完整，跳过: {line}")
                    continue
                
                # RTTM格式: SPEAKER <file-id> <chnl> <tbeg> <tdur> <ortho> <stype> <name> <conf>
                if parts[0] != "SPEAKER":
                    continue
                
                start_time = float(parts[3])
                duration = float(parts[4]) 
                speaker_id = parts[7]
                
                speakers.append({
                    "start": start_time,
                    "end": start_time + duration,
                    "speaker": speaker_id
                })
                
            except (ValueError, IndexError) as e:
                self.logger.warning(f"RTTM第{line_num}行解析失败，跳过: {line} - {e}")
                continue
        
        self.logger.info(f"解析RTTM完成，共 {len(speakers)} 个说话人片段")
        return speakers


class SpeakerMapper:
    """说话人映射器"""
    
    def __init__(self):
        self.config = get_config()
        self.logger = logger.bind(name="SpeakerMapper")
    
    def map_speakers_to_subtitles(self, subtitles: List[Dict[str, Any]], 
                                 speakers: List[Dict[str, Any]]) -> None:
        """
        将说话人信息映射到字幕片段
        
        使用时间重叠度最大的说话人作为该字幕片段的说话人。
        
        Args:
            subtitles: 字幕片段列表（会被就地修改）
            speakers: 说话人片段列表
        """
        if not speakers:
            self.logger.warning("没有说话人数据，跳过映射")
            return
        
        mapped_count = 0
        
        for subtitle in subtitles:
            max_overlap_speaker: Optional[str] = None
            max_overlap_duration = 0.0
            
            subtitle_start = subtitle["start"]
            subtitle_end = subtitle["end"]
            
            # 找到与当前字幕重叠度最大的说话人
            for speaker in speakers:
                speaker_start = speaker["start"]
                speaker_end = speaker["end"]
                
                # 计算时间重叠
                overlap_start = max(subtitle_start, speaker_start)
                overlap_end = min(subtitle_end, speaker_end)
                overlap_duration = max(0.0, overlap_end - overlap_start)
                
                if overlap_duration > max_overlap_duration:
                    max_overlap_speaker = speaker["speaker"]
                    max_overlap_duration = overlap_duration
            
            # 设置说话人信息
            if max_overlap_speaker:
                subtitle["speakers"] = {max_overlap_speaker}
                mapped_count += 1
            else:
                subtitle["speakers"] = None
        
        self.logger.info(f"说话人映射完成，共映射 {mapped_count}/{len(subtitles)} 个字幕片段")


class OutputFormatter:
    """输出格式化器"""
    
    def __init__(self):
        self.config = get_config()
        self.logger = logger.bind(name="OutputFormatter")
    
    def format_output(self, subtitles: List[Dict[str, Any]], 
                     use_custom_labels: bool = True) -> str:
        """
        格式化输出文本
        
        Args:
            subtitles: 字幕片段列表
            use_custom_labels: 是否使用自定义说话人标签
            
        Returns:
            格式化的文本字符串
        """
        if not subtitles:
            return ""
        
        output_lines = []
        current_speaker: Optional[str] = None
        
        # 获取自定义标签映射
        speaker_labels = {}
        if use_custom_labels:
            speaker_labels = self.config.get("output.speaker_labels", {})
        
        for subtitle in subtitles:
            # 获取说话人信息
            speakers = subtitle.get("speakers")
            if speakers and isinstance(speakers, (set, list)):
                speaker = list(speakers)[0] if speakers else None
            else:
                speaker = speakers
            
            # 添加说话人标签
            if speaker and speaker != current_speaker:
                current_speaker = speaker
                # 使用自定义标签或原始标签
                display_label = speaker_labels.get(speaker, speaker)
                output_lines.append(f"[{display_label}]")
            
            # 添加文本内容
            text = subtitle.get("text", "").strip()
            if text:
                output_lines.append(text)
        
        result = "\n".join(output_lines)
        self.logger.info(f"格式化输出完成，共 {len(output_lines)} 行")
        return result
    
    def format_with_timestamps(self, subtitles: List[Dict[str, Any]]) -> str:
        """
        带时间戳的格式化输出
        
        Args:
            subtitles: 字幕片段列表
            
        Returns:
            带时间戳的格式化文本
        """
        if not subtitles:
            return ""
        
        output_lines = []
        
        for subtitle in subtitles:
            start_time = subtitle["start"]
            end_time = subtitle["end"]
            text = subtitle.get("text", "").strip()
            
            if text:
                # 格式化时间
                start_formatted = self._format_time(start_time)
                end_formatted = self._format_time(end_time)
                
                # 获取说话人
                speakers = subtitle.get("speakers")
                speaker = ""
                if speakers:
                    speaker_id = list(speakers)[0] if isinstance(speakers, (set, list)) else speakers
                    speaker_labels = self.config.get("output.speaker_labels", {})
                    speaker = speaker_labels.get(speaker_id, speaker_id)
                    speaker = f"[{speaker}] "
                
                output_lines.append(f"{start_formatted} - {end_formatted}: {speaker}{text}")
        
        return "\n".join(output_lines)
    
    def _format_time(self, seconds: float) -> str:
        """格式化时间为 MM:SS 格式"""
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes:02d}:{secs:05.2f}"


# 便利函数，保持向后兼容性

def parse_vtt(vtt_content: str) -> List[Dict[str, Any]]:
    """解析VTT内容（兼容性函数）"""
    parser = VTTParser()
    return parser.parse(vtt_content)


def parse_rttm(rttm_content: str) -> List[Dict[str, Any]]:
    """解析RTTM内容（兼容性函数）"""
    parser = RTTMParser()
    return parser.parse(rttm_content)


def map_speakers_to_subtitles(subtitles: List[Dict[str, Any]], 
                             speakers: List[Dict[str, Any]]) -> None:
    """映射说话人到字幕（兼容性函数）"""
    mapper = SpeakerMapper()
    mapper.map_speakers_to_subtitles(subtitles, speakers)


def format_output(subtitles: List[Dict[str, Any]]) -> str:
    """格式化输出（兼容性函数）"""
    formatter = OutputFormatter()
    return formatter.format_output(subtitles)