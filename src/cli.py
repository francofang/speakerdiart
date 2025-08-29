"""
改进的命令行界面

提供功能丰富的CLI，支持：
- 批量音频处理
- 文件合并模式
- 灵活的配置选项
- 进度显示
- 多种输出格式
"""

import argparse
import sys
from pathlib import Path
from typing import List, Dict, Any
import time
from loguru import logger

from .config import get_config, load_config
from .pipeline import ProcessingPipeline
from .logging_setup import setup_logging
from .transcription import get_supported_formats
from .exceptions import SpeakerDiartError


class CLIProgressBar:
    """简单的CLI进度条"""
    
    def __init__(self, total: int, description: str = "处理中"):
        self.total = total
        self.current = 0
        self.description = description
        self.start_time = time.time()
    
    def update(self, increment: int = 1, description: str = None):
        """更新进度"""
        self.current += increment
        if description:
            self.description = description
        
        # 计算进度百分比
        if self.total > 0:
            percent = min(100, (self.current / self.total) * 100)
        else:
            percent = 0
        
        # 计算ETA
        elapsed_time = time.time() - self.start_time
        if self.current > 0 and self.current < self.total:
            eta = (elapsed_time / self.current) * (self.total - self.current)
            eta_str = f"ETA: {eta:.0f}s"
        else:
            eta_str = ""
        
        # 创建进度条
        bar_length = 30
        filled_length = int(bar_length * percent // 100)
        bar = '█' * filled_length + '-' * (bar_length - filled_length)
        
        # 打印进度
        print(f'\r{self.description}: |{bar}| {percent:.1f}% ({self.current}/{self.total}) {eta_str}', end='', flush=True)
        
        if self.current >= self.total:
            print()  # 完成后换行


def find_media_files(root_path: Path, recursive: bool = False, supported_extensions: List[str] = None) -> List[Path]:
    """
    查找媒体文件
    
    Args:
        root_path: 根路径
        recursive: 是否递归查找
        supported_extensions: 支持的扩展名列表
        
    Returns:
        找到的媒体文件列表
    """
    if supported_extensions is None:
        supported_extensions = get_supported_formats()
    
    if root_path.is_file():
        if root_path.suffix.lower() in supported_extensions:
            return [root_path]
        else:
            return []
    
    if not root_path.is_dir():
        return []
    
    pattern = "**/*" if recursive else "*"
    files = []
    
    for ext in supported_extensions:
        files.extend(root_path.glob(f"{pattern}{ext}"))
        files.extend(root_path.glob(f"{pattern}{ext.upper()}"))
    
    return sorted(files)


def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="广东话采访处理系统 - 命令行界面",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 处理单个音频文件
  python -m src.cli audio.wav
  
  # 批量处理目录中的文件
  python -m src.cli /path/to/audio/files --recursive
  
  # 使用GPU加速和ChatGPT润色
  python -m src.cli audio.wav --device cuda --chatgpt
  
  # 仅合并现有的VTT和RTTM文件
  python -m src.cli --merge audio.vtt audio.rttm
  
  # 使用自定义配置文件
  python -m src.cli audio.wav --config config/my_config.yaml
        """
    )
    
    # 主要参数
    parser.add_argument("input", nargs="?", help="输入音频文件或目录")
    parser.add_argument("input2", nargs="?", help="第二个输入文件（合并模式下的RTTM文件）")
    
    # 模式选择
    parser.add_argument("--merge", action="store_true", 
                       help="合并模式：处理现有的VTT和RTTM文件")
    
    # 输出配置
    parser.add_argument("--output", "-o", default="outputs", 
                       help="输出目录（默认: outputs）")
    parser.add_argument("--export-intermediate", action="store_true",
                       help="导出中间文件（VTT和RTTM）")
    parser.add_argument("--format", choices=["txt", "vtt", "rttm"], 
                       action="append", help="输出格式（可多选）")
    
    # Whisper配置
    whisper_group = parser.add_argument_group("Whisper设置")
    whisper_group.add_argument("--model", default="small",
                             choices=["tiny", "base", "small", "medium", "large"],
                             help="Whisper模型大小（默认: small）")
    whisper_group.add_argument("--device", default="cpu", choices=["cpu", "cuda"],
                             help="计算设备（默认: cpu）")
    whisper_group.add_argument("--language", default="zh",
                             help="转录语言代码（默认: zh）")
    
    # 说话人分离配置
    diarization_group = parser.add_argument_group("说话人分离设置")
    diarization_group.add_argument("--speakers", type=int, default=2,
                                 help="说话人数量（默认: 2）")
    
    # ChatGPT配置
    chatgpt_group = parser.add_argument_group("ChatGPT设置")
    chatgpt_group.add_argument("--chatgpt", action="store_true",
                             help="启用ChatGPT润色")
    chatgpt_group.add_argument("--openai-key", 
                             help="OpenAI API密钥（也可通过OPENAI_API_KEY环境变量设置）")
    chatgpt_group.add_argument("--chatgpt-model", default="gpt-4o-mini",
                             help="ChatGPT模型（默认: gpt-4o-mini）")
    
    # 处理选项
    processing_group = parser.add_argument_group("处理选项")
    processing_group.add_argument("--recursive", "-r", action="store_true",
                                help="递归处理子目录")
    processing_group.add_argument("--config", 
                                help="自定义配置文件路径")
    processing_group.add_argument("--dry-run", action="store_true",
                                help="仅显示将要处理的文件，不实际处理")
    
    # 输出控制
    output_group = parser.add_argument_group("输出控制")
    output_group.add_argument("--verbose", "-v", action="store_true",
                            help="详细输出")
    output_group.add_argument("--quiet", "-q", action="store_true",
                            help="静默模式")
    output_group.add_argument("--log-file", 
                            help="日志文件路径")
    
    return parser


def process_single_audio_file(pipeline: ProcessingPipeline, audio_file: Path, 
                            config: Dict[str, Any], output_dir: Path) -> bool:
    """
    处理单个音频文件
    
    Args:
        pipeline: 处理管道
        audio_file: 音频文件路径
        config: 处理配置
        output_dir: 输出目录
        
    Returns:
        是否处理成功
    """
    try:
        logger.info(f"开始处理: {audio_file.name}")
        
        # 执行处理
        result = pipeline.process_audio(str(audio_file), **config)
        
        # 导出结果
        exported_files = pipeline.export_results(result, str(output_dir), audio_file.stem)
        
        logger.success(f"处理完成: {audio_file.name}")
        logger.info(f"输出文件: {', '.join(Path(f).name for f in exported_files)}")
        
        return True
        
    except Exception as e:
        logger.error(f"处理失败 {audio_file.name}: {e}")
        return False


def process_merge_files(pipeline: ProcessingPipeline, vtt_file: Path, rttm_file: Path,
                      config: Dict[str, Any], output_dir: Path) -> bool:
    """
    处理VTT和RTTM文件合并
    
    Args:
        pipeline: 处理管道
        vtt_file: VTT文件路径
        rttm_file: RTTM文件路径
        config: 处理配置
        output_dir: 输出目录
        
    Returns:
        是否处理成功
    """
    try:
        logger.info(f"合并处理: {vtt_file.name} + {rttm_file.name}")
        
        # 执行合并
        result = pipeline.process_existing_files(str(vtt_file), str(rttm_file), **config)
        
        # 导出结果
        base_name = vtt_file.stem
        exported_files = pipeline.export_results(result, str(output_dir), base_name)
        
        logger.success(f"合并完成: {vtt_file.name}")
        logger.info(f"输出文件: {', '.join(Path(f).name for f in exported_files)}")
        
        return True
        
    except Exception as e:
        logger.error(f"合并失败: {e}")
        return False


def main():
    """主函数"""
    parser = create_parser()
    args = parser.parse_args()
    
    # 加载配置
    if args.config:
        config = load_config(args.config)
    else:
        config = get_config()
    
    # 设置日志级别
    log_level = "DEBUG" if args.verbose else "WARNING" if args.quiet else "INFO"
    setup_logging(log_level=log_level, log_file=args.log_file)
    
    logger.info("广东话采访处理系统 CLI 启动")
    
    try:
        # 验证输入参数
        if args.merge:
            if not args.input or not args.input2:
                logger.error("合并模式需要提供VTT和RTTM文件")
                parser.print_help()
                return 1
            
            vtt_file = Path(args.input)
            rttm_file = Path(args.input2)
            
            if not vtt_file.exists():
                logger.error(f"VTT文件不存在: {vtt_file}")
                return 1
            if not rttm_file.exists():
                logger.error(f"RTTM文件不存在: {rttm_file}")
                return 1
            
            files_to_process = [(vtt_file, rttm_file)]
            
        else:
            if not args.input:
                logger.error("请提供输入文件或目录")
                parser.print_help()
                return 1
            
            input_path = Path(args.input)
            if not input_path.exists():
                logger.error(f"输入路径不存在: {input_path}")
                return 1
            
            # 查找音频文件
            media_files = find_media_files(input_path, recursive=args.recursive)
            if not media_files:
                logger.error(f"在 {input_path} 中没有找到支持的音频文件")
                return 1
            
            files_to_process = media_files
        
        if args.dry_run:
            logger.info("DRY RUN 模式 - 将要处理的文件:")
            for i, file_info in enumerate(files_to_process, 1):
                if args.merge:
                    vtt_file, rttm_file = file_info
                    logger.info(f"  {i}. 合并: {vtt_file} + {rttm_file}")
                else:
                    logger.info(f"  {i}. 音频: {file_info}")
            return 0
        
        # 准备输出目录
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 构建处理配置
        processing_config = {
            "whisper": {
                "model_size": args.model,
                "device": args.device,
                "language": args.language
            },
            "diarization": {
                "num_speakers": args.speakers,
                "device": args.device
            },
            "chatgpt": {
                "enabled": args.chatgpt,
                "model": args.chatgpt_model if args.chatgpt else "gpt-4o-mini"
            },
            "output": {
                "export_intermediate": args.export_intermediate,
                "formats": args.format or ["txt"]
            },
            "use_chatgpt": args.chatgpt,
            "openai_api_key": args.openai_key
        }
        
        # 创建处理管道
        pipeline = ProcessingPipeline(config_override=processing_config)
        
        # 处理文件
        total_files = len(files_to_process)
        success_count = 0
        
        if total_files > 1:
            progress_bar = CLIProgressBar(total_files, "处理文件")
        
        for i, file_info in enumerate(files_to_process):
            if total_files > 1:
                progress_bar.update(0, f"处理文件 {i+1}/{total_files}")
            
            if args.merge:
                vtt_file, rttm_file = file_info
                success = process_merge_files(pipeline, vtt_file, rttm_file, 
                                           processing_config, output_dir)
            else:
                success = process_single_audio_file(pipeline, file_info, 
                                                  processing_config, output_dir)
            
            if success:
                success_count += 1
            
            if total_files > 1:
                progress_bar.update(1)
        
        # 总结
        logger.info(f"处理完成！成功: {success_count}/{total_files}")
        logger.info(f"输出目录: {output_dir}")
        
        return 0 if success_count == total_files else 1
        
    except KeyboardInterrupt:
        logger.info("用户中断处理")
        return 1
    except Exception as e:
        logger.error(f"CLI执行失败: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())