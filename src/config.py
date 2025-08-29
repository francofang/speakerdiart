"""
配置管理模块

提供应用程序配置的加载、验证和访问功能。
支持从YAML文件加载配置，并提供默认值。
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union
from loguru import logger


class Config:
    """配置管理器"""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_file: 配置文件路径，如果为None则使用默认配置
        """
        self._config: Dict[str, Any] = {}
        self._config_file = config_file
        self._project_root = Path(__file__).parent.parent
        
        self._load_config()
    
    def _load_config(self) -> None:
        """加载配置文件"""
        try:
            # 首先加载默认配置
            default_config_path = self._project_root / "config" / "default.yaml"
            if default_config_path.exists():
                with open(default_config_path, 'r', encoding='utf-8') as f:
                    self._config = yaml.safe_load(f)
                logger.info(f"已加载默认配置: {default_config_path}")
            
            # 如果指定了自定义配置文件，则覆盖默认配置
            if self._config_file and Path(self._config_file).exists():
                with open(self._config_file, 'r', encoding='utf-8') as f:
                    custom_config = yaml.safe_load(f)
                    self._config.update(custom_config)
                logger.info(f"已加载自定义配置: {self._config_file}")
                
        except Exception as e:
            logger.error(f"配置文件加载失败: {e}")
            # 使用最小化的默认配置
            self._config = self._get_minimal_config()
    
    def _get_minimal_config(self) -> Dict[str, Any]:
        """获取最小化默认配置"""
        return {
            "whisper": {
                "model_size": "small",
                "device": "cpu",
                "language": "zh"
            },
            "diarization": {
                "num_speakers": 2,
                "device": "cpu"
            },
            "chatgpt": {
                "enabled": False,
                "model": "gpt-4o-mini"
            },
            "output": {
                "directory": "outputs",
                "formats": ["txt"]
            },
            "logging": {
                "level": "INFO"
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值，支持点分隔的键名
        
        Args:
            key: 配置键名，支持"section.key"格式
            default: 默认值
            
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self._config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> None:
        """
        设置配置值，支持点分隔的键名
        
        Args:
            key: 配置键名
            value: 配置值
        """
        keys = key.split('.')
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def save(self, file_path: Optional[str] = None) -> None:
        """
        保存配置到文件
        
        Args:
            file_path: 保存路径，如果为None则保存到原配置文件
        """
        save_path = file_path or self._config_file
        if not save_path:
            save_path = self._project_root / "config" / "user.yaml"
        
        try:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, 'w', encoding='utf-8') as f:
                yaml.dump(self._config, f, default_flow_style=False, 
                         allow_unicode=True, indent=2)
            logger.info(f"配置已保存到: {save_path}")
        except Exception as e:
            logger.error(f"配置保存失败: {e}")
    
    def get_whisper_config(self) -> Dict[str, Any]:
        """获取Whisper配置"""
        return self.get("whisper", {})
    
    def get_diarization_config(self) -> Dict[str, Any]:
        """获取说话人分离配置"""
        return self.get("diarization", {})
    
    def get_chatgpt_config(self) -> Dict[str, Any]:
        """获取ChatGPT配置"""
        return self.get("chatgpt", {})
    
    def get_output_config(self) -> Dict[str, Any]:
        """获取输出配置"""
        return self.get("output", {})
    
    def get_logging_config(self) -> Dict[str, Any]:
        """获取日志配置"""
        return self.get("logging", {})
    
    def get_gui_config(self) -> Dict[str, Any]:
        """获取GUI配置"""
        return self.get("gui", {})
    
    @property
    def project_root(self) -> Path:
        """项目根目录"""
        return self._project_root
    
    @property
    def output_dir(self) -> Path:
        """输出目录"""
        output_dir = self.get("output.directory", "outputs")
        if not os.path.isabs(output_dir):
            output_dir = self._project_root / output_dir
        return Path(output_dir)
    
    @property
    def logs_dir(self) -> Path:
        """日志目录"""
        return self._project_root / "logs"


# 全局配置实例
config = Config()


def get_config() -> Config:
    """获取全局配置实例"""
    return config


def load_config(config_file: str) -> Config:
    """加载指定的配置文件"""
    global config
    config = Config(config_file)
    return config