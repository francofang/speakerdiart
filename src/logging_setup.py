"""
日志设置模块

配置和初始化应用程序的日志系统。
"""

import sys
from pathlib import Path
from loguru import logger
from typing import Optional

from .config import get_config


def setup_logging(log_level: Optional[str] = None, log_file: Optional[str] = None) -> None:
    """
    设置应用程序日志
    
    Args:
        log_level: 日志级别，如果为None则从配置文件读取
        log_file: 日志文件路径，如果为None则使用默认路径
    """
    config = get_config()
    
    # 移除默认的logger
    logger.remove()
    
    # 获取配置
    log_config = config.get_logging_config()
    level = log_level or log_config.get("level", "INFO")
    format_str = log_config.get("format", 
                               "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}")
    
    # 控制台输出
    logger.add(
        sys.stdout,
        format=format_str,
        level=level,
        colorize=True,
        backtrace=True,
        diagnose=True
    )
    
    # 文件输出
    if log_file is None:
        log_file = config.logs_dir / "speakerdiart.log"
    
    # 确保日志目录存在
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    
    logger.add(
        log_file,
        format=format_str,
        level=level,
        rotation=log_config.get("rotation", "100 MB"),
        retention=log_config.get("retention", "1 week"),
        compression="zip",
        backtrace=True,
        diagnose=True,
        encoding="utf-8"
    )
    
    logger.info(f"日志系统已初始化，级别: {level}")
    logger.info(f"日志文件: {log_file}")


def get_logger(name: str):
    """
    获取指定名称的logger
    
    Args:
        name: logger名称
        
    Returns:
        logger实例
    """
    return logger.bind(name=name)