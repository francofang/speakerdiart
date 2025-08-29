"""
监控和性能分析模块

提供系统资源监控、处理时间统计和性能分析功能。
"""

import time
import psutil
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from loguru import logger
import json


@dataclass 
class ProcessingMetrics:
    """处理指标数据类"""
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration: Optional[float] = None
    
    # 文件信息
    file_path: str = ""
    file_size: int = 0
    audio_duration: Optional[float] = None
    
    # 各阶段耗时
    transcription_time: Optional[float] = None
    diarization_time: Optional[float] = None
    merging_time: Optional[float] = None
    postprocessing_time: Optional[float] = None
    
    # 系统资源
    peak_memory_mb: float = 0.0
    avg_cpu_percent: float = 0.0
    
    # 处理结果统计
    total_segments: int = 0
    total_speakers: int = 0
    output_length: int = 0
    
    # 错误信息
    errors: List[str] = field(default_factory=list)
    success: bool = True
    
    def finish(self):
        """完成处理，计算总时长"""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "audio_duration": self.audio_duration,
            "transcription_time": self.transcription_time,
            "diarization_time": self.diarization_time,
            "merging_time": self.merging_time,
            "postprocessing_time": self.postprocessing_time,
            "peak_memory_mb": self.peak_memory_mb,
            "avg_cpu_percent": self.avg_cpu_percent,
            "total_segments": self.total_segments,
            "total_speakers": self.total_speakers,
            "output_length": self.output_length,
            "errors": self.errors,
            "success": self.success
        }


class SystemMonitor:
    """系统资源监控器"""
    
    def __init__(self, interval: float = 1.0):
        """
        初始化监控器
        
        Args:
            interval: 监控间隔（秒）
        """
        self.interval = interval
        self.monitoring = False
        self.monitor_thread = None
        
        # 监控数据
        self.cpu_samples = []
        self.memory_samples = []
        self.disk_io_samples = []
        
        self.logger = logger.bind(name="SystemMonitor")
    
    def start_monitoring(self):
        """开始监控"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.cpu_samples.clear()
        self.memory_samples.clear()
        self.disk_io_samples.clear()
        
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        self.logger.debug("系统监控已启动")
    
    def stop_monitoring(self) -> Dict[str, float]:
        """停止监控并返回统计数据"""
        if not self.monitoring:
            return {}
        
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
        
        # 计算统计数据
        stats = {
            "avg_cpu_percent": sum(self.cpu_samples) / len(self.cpu_samples) if self.cpu_samples else 0.0,
            "peak_memory_mb": max(self.memory_samples) if self.memory_samples else 0.0,
            "avg_memory_mb": sum(self.memory_samples) / len(self.memory_samples) if self.memory_samples else 0.0,
        }
        
        self.logger.debug(f"系统监控已停止，平均CPU: {stats['avg_cpu_percent']:.1f}%, 峰值内存: {stats['peak_memory_mb']:.1f}MB")
        return stats
    
    def _monitor_loop(self):
        """监控循环"""
        process = psutil.Process()
        
        while self.monitoring:
            try:
                # CPU使用率
                cpu_percent = process.cpu_percent()
                self.cpu_samples.append(cpu_percent)
                
                # 内存使用
                memory_info = process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024
                self.memory_samples.append(memory_mb)
                
                time.sleep(self.interval)
                
            except Exception as e:
                self.logger.warning(f"监控数据采集失败: {e}")
                break


class PerformanceTracker:
    """性能跟踪器"""
    
    def __init__(self, metrics_file: Optional[str] = None):
        """
        初始化性能跟踪器
        
        Args:
            metrics_file: 指标保存文件路径
        """
        self.metrics_file = metrics_file
        self.current_metrics: Optional[ProcessingMetrics] = None
        self.system_monitor = SystemMonitor()
        self.stage_start_time: Optional[float] = None
        
        self.logger = logger.bind(name="PerformanceTracker")
    
    def start_processing(self, file_path: str) -> ProcessingMetrics:
        """
        开始处理跟踪
        
        Args:
            file_path: 处理的文件路径
            
        Returns:
            指标对象
        """
        self.current_metrics = ProcessingMetrics(file_path=file_path)
        
        # 获取文件信息
        try:
            file_info = Path(file_path)
            if file_info.exists():
                self.current_metrics.file_size = file_info.stat().st_size
        except Exception as e:
            self.logger.warning(f"获取文件信息失败: {e}")
        
        # 开始系统监控
        self.system_monitor.start_monitoring()
        
        self.logger.info(f"开始性能跟踪: {Path(file_path).name}")
        return self.current_metrics
    
    def start_stage(self, stage_name: str):
        """开始一个处理阶段"""
        self.stage_start_time = time.time()
        self.logger.debug(f"开始阶段: {stage_name}")
    
    def end_stage(self, stage_name: str):
        """结束一个处理阶段"""
        if self.stage_start_time is None or self.current_metrics is None:
            return
        
        stage_duration = time.time() - self.stage_start_time
        
        # 记录阶段耗时
        if stage_name == "transcription":
            self.current_metrics.transcription_time = stage_duration
        elif stage_name == "diarization":
            self.current_metrics.diarization_time = stage_duration
        elif stage_name == "merging":
            self.current_metrics.merging_time = stage_duration
        elif stage_name == "postprocessing":
            self.current_metrics.postprocessing_time = stage_duration
        
        self.logger.debug(f"结束阶段 {stage_name}: {stage_duration:.2f}s")
        self.stage_start_time = None
    
    def add_result_stats(self, result: Dict[str, Any]):
        """添加处理结果统计"""
        if self.current_metrics is None:
            return
        
        # 统计片段数量
        if "speakers" in result:
            self.current_metrics.total_speakers = len(set(
                seg.get("speaker", "") for seg in result["speakers"]
            ))
            self.current_metrics.total_segments = len(result["speakers"])
        
        # 统计输出长度
        merged_text = result.get("merged_text", "")
        self.current_metrics.output_length = len(merged_text)
    
    def add_error(self, error_message: str):
        """添加错误信息"""
        if self.current_metrics is None:
            return
        
        self.current_metrics.errors.append(error_message)
        self.current_metrics.success = False
    
    def finish_processing(self) -> ProcessingMetrics:
        """
        完成处理跟踪
        
        Returns:
            完整的指标数据
        """
        if self.current_metrics is None:
            raise ValueError("没有正在进行的处理跟踪")
        
        # 停止系统监控并获取统计
        system_stats = self.system_monitor.stop_monitoring()
        self.current_metrics.avg_cpu_percent = system_stats.get("avg_cpu_percent", 0.0)
        self.current_metrics.peak_memory_mb = system_stats.get("peak_memory_mb", 0.0)
        
        # 完成指标记录
        self.current_metrics.finish()
        
        # 保存到文件
        if self.metrics_file:
            self._save_metrics(self.current_metrics)
        
        # 记录性能摘要
        self._log_performance_summary(self.current_metrics)
        
        result = self.current_metrics
        self.current_metrics = None
        
        return result
    
    def _save_metrics(self, metrics: ProcessingMetrics):
        """保存指标到文件"""
        try:
            metrics_file = Path(self.metrics_file)
            metrics_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 读取现有数据
            existing_data = []
            if metrics_file.exists():
                with open(metrics_file, 'r', encoding='utf-8') as f:
                    try:
                        existing_data = json.load(f)
                        if not isinstance(existing_data, list):
                            existing_data = []
                    except json.JSONDecodeError:
                        existing_data = []
            
            # 添加新数据
            existing_data.append(metrics.to_dict())
            
            # 保持最近1000条记录
            if len(existing_data) > 1000:
                existing_data = existing_data[-1000:]
            
            # 保存文件
            with open(metrics_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)
            
            self.logger.debug(f"指标已保存到: {metrics_file}")
            
        except Exception as e:
            self.logger.error(f"保存指标失败: {e}")
    
    def _log_performance_summary(self, metrics: ProcessingMetrics):
        """记录性能摘要"""
        file_name = Path(metrics.file_path).name
        
        if metrics.success:
            self.logger.success(f"处理完成: {file_name}")
        else:
            self.logger.error(f"处理失败: {file_name}")
        
        self.logger.info(f"总耗时: {metrics.duration:.2f}s")
        
        if metrics.transcription_time:
            self.logger.info(f"  转录: {metrics.transcription_time:.2f}s")
        if metrics.diarization_time:
            self.logger.info(f"  分离: {metrics.diarization_time:.2f}s")
        if metrics.merging_time:
            self.logger.info(f"  合并: {metrics.merging_time:.2f}s")
        if metrics.postprocessing_time:
            self.logger.info(f"  后处理: {metrics.postprocessing_time:.2f}s")
        
        self.logger.info(f"峰值内存: {metrics.peak_memory_mb:.1f}MB")
        self.logger.info(f"平均CPU: {metrics.avg_cpu_percent:.1f}%")
        
        if metrics.errors:
            self.logger.warning(f"错误数量: {len(metrics.errors)}")


class MetricsAnalyzer:
    """指标分析器"""
    
    def __init__(self, metrics_file: str):
        """
        初始化分析器
        
        Args:
            metrics_file: 指标文件路径
        """
        self.metrics_file = Path(metrics_file)
        self.logger = logger.bind(name="MetricsAnalyzer")
    
    def load_metrics(self) -> List[Dict[str, Any]]:
        """加载指标数据"""
        if not self.metrics_file.exists():
            return []
        
        try:
            with open(self.metrics_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception as e:
            self.logger.error(f"加载指标数据失败: {e}")
            return []
    
    def analyze_performance(self) -> Dict[str, Any]:
        """分析性能数据"""
        metrics_data = self.load_metrics()
        if not metrics_data:
            return {}
        
        # 过滤成功的处理记录
        successful_records = [m for m in metrics_data if m.get("success", False)]
        
        if not successful_records:
            return {"total_records": len(metrics_data), "successful_records": 0}
        
        # 计算统计数据
        durations = [m["duration"] for m in successful_records if m.get("duration")]
        transcription_times = [m["transcription_time"] for m in successful_records if m.get("transcription_time")]
        diarization_times = [m["diarization_time"] for m in successful_records if m.get("diarization_time")]
        memory_usage = [m["peak_memory_mb"] for m in successful_records if m.get("peak_memory_mb")]
        
        analysis = {
            "total_records": len(metrics_data),
            "successful_records": len(successful_records),
            "success_rate": len(successful_records) / len(metrics_data) * 100,
        }
        
        if durations:
            analysis.update({
                "avg_duration": sum(durations) / len(durations),
                "min_duration": min(durations),
                "max_duration": max(durations)
            })
        
        if transcription_times:
            analysis["avg_transcription_time"] = sum(transcription_times) / len(transcription_times)
        
        if diarization_times:
            analysis["avg_diarization_time"] = sum(diarization_times) / len(diarization_times)
        
        if memory_usage:
            analysis.update({
                "avg_memory_mb": sum(memory_usage) / len(memory_usage),
                "peak_memory_mb": max(memory_usage)
            })
        
        return analysis
    
    def generate_report(self) -> str:
        """生成性能报告"""
        analysis = self.analyze_performance()
        
        if not analysis:
            return "没有可用的性能数据"
        
        report_lines = [
            "=== 性能分析报告 ===",
            f"总处理记录: {analysis['total_records']}",
            f"成功记录: {analysis['successful_records']}",
            f"成功率: {analysis.get('success_rate', 0):.1f}%",
        ]
        
        if "avg_duration" in analysis:
            report_lines.extend([
                "",
                "处理时间统计:",
                f"  平均耗时: {analysis['avg_duration']:.2f}s",
                f"  最短耗时: {analysis['min_duration']:.2f}s", 
                f"  最长耗时: {analysis['max_duration']:.2f}s"
            ])
        
        if "avg_transcription_time" in analysis:
            report_lines.append(f"  平均转录时间: {analysis['avg_transcription_time']:.2f}s")
        
        if "avg_diarization_time" in analysis:
            report_lines.append(f"  平均分离时间: {analysis['avg_diarization_time']:.2f}s")
        
        if "avg_memory_mb" in analysis:
            report_lines.extend([
                "",
                "内存使用统计:",
                f"  平均内存: {analysis['avg_memory_mb']:.1f}MB",
                f"  峰值内存: {analysis['peak_memory_mb']:.1f}MB"
            ])
        
        return "\n".join(report_lines)