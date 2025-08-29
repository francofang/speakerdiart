"""
后处理模块

使用ChatGPT对合并后的文本进行润色，包括：
- 自然语气断句分段
- 补充标点符号
- 规范化说话人标签
"""

import os
from typing import Optional, Dict, Any
from loguru import logger

from .config import get_config
from .exceptions import PostProcessingError


class ChatGPTProcessor:
    """ChatGPT后处理器"""
    
    def __init__(self, config_override: Optional[Dict[str, Any]] = None):
        """
        初始化ChatGPT处理器
        
        Args:
            config_override: 配置覆盖参数
        """
        self.config = get_config()
        self.chatgpt_config = self.config.get_chatgpt_config()
        
        # 应用配置覆盖
        if config_override:
            self.chatgpt_config.update(config_override)
        
        self.client = None
        self.logger = logger.bind(name="ChatGPTProcessor")
    
    def _init_client(self, api_key: Optional[str] = None) -> None:
        """初始化OpenAI客户端"""
        if self.client is not None:
            return
        
        # 获取API密钥
        key = api_key or self.chatgpt_config.get("api_key") or os.getenv("OPENAI_API_KEY")
        
        if not key:
            raise PostProcessingError(
                "未提供OpenAI API密钥。请设置OPENAI_API_KEY环境变量或在配置中指定api_key"
            )
        
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=key)
            self.logger.info("OpenAI客户端初始化成功")
        except ImportError as e:
            raise PostProcessingError(
                "openai库未安装。请运行: pip install openai"
            ) from e
        except Exception as e:
            raise PostProcessingError(f"OpenAI客户端初始化失败: {e}") from e
    
    def polish_text(self, text: str, api_key: Optional[str] = None, 
                   custom_prompt: Optional[str] = None) -> str:
        """
        使用ChatGPT润色文本
        
        Args:
            text: 待润色的文本
            api_key: OpenAI API密钥
            custom_prompt: 自定义系统提示词
            
        Returns:
            润色后的文本
            
        Raises:
            PostProcessingError: 处理失败时抛出
        """
        if not text.strip():
            return text
        
        # 检查是否启用ChatGPT
        if not self.chatgpt_config.get("enabled", False):
            self.logger.info("ChatGPT未启用，返回原文本")
            return text
        
        self._init_client(api_key)
        
        try:
            # 构建提示词
            system_prompt = custom_prompt or self.chatgpt_config.get(
                "system_prompt", 
                self._get_default_system_prompt()
            )
            
            # 获取模型参数
            model = self.chatgpt_config.get("model", "gpt-4o-mini")
            temperature = self.chatgpt_config.get("temperature", 0.2)
            max_tokens = self.chatgpt_config.get("max_tokens", 4000)
            
            self.logger.info(f"开始ChatGPT润色，模型: {model}")
            self.logger.debug(f"文本长度: {len(text)} 字符")
            
            # 调用ChatGPT API
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ]
            
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            polished_text = response.choices[0].message.content or text
            
            # 统计信息
            usage = response.usage
            if usage:
                self.logger.info(
                    f"ChatGPT润色完成 - "
                    f"输入: {usage.prompt_tokens} tokens, "
                    f"输出: {usage.completion_tokens} tokens, "
                    f"总计: {usage.total_tokens} tokens"
                )
            
            return polished_text.strip()
            
        except Exception as e:
            error_msg = f"ChatGPT润色失败: {e}"
            self.logger.error(error_msg)
            
            # 根据配置决定是否抛出异常还是返回原文本
            if self.chatgpt_config.get("fail_silently", True):
                self.logger.warning("ChatGPT失败，返回原文本")
                return text
            else:
                raise PostProcessingError(error_msg) from e
    
    def _get_default_system_prompt(self) -> str:
        """获取默认的系统提示词"""
        return (
            "你是中文编辑助手。请在不改变原意的前提下：\n"
            "1) 按自然语气断句分段；2) 补充合理标点；3) 保留并规范化说话人标签（如[SPEAKER_00] → 主持人，[SPEAKER_01] → 受访者）。\n"
            "输出纯文本，不要解释。"
        )
    
    def polish_with_speaker_mapping(self, text: str, speaker_mapping: Optional[Dict[str, str]] = None,
                                  api_key: Optional[str] = None) -> str:
        """
        润色文本并应用说话人标签映射
        
        Args:
            text: 待润色的文本
            speaker_mapping: 说话人标签映射，如 {"SPEAKER_00": "主持人"}
            api_key: OpenAI API密钥
            
        Returns:
            润色后的文本
        """
        if not speaker_mapping:
            speaker_mapping = self.config.get("output.speaker_labels", {})
        
        # 构建包含说话人映射的系统提示词
        mapping_info = ""
        if speaker_mapping:
            mapping_lines = [f"{old} → {new}" for old, new in speaker_mapping.items()]
            mapping_info = f"\n说话人标签映射: {', '.join(mapping_lines)}"
        
        custom_prompt = (
            "你是中文编辑助手。请在不改变原意的前提下：\n"
            "1) 按自然语气断句分段\n"
            "2) 补充合理标点符号\n"
            "3) 根据以下映射规范化说话人标签"
            f"{mapping_info}\n"
            "输出纯文本，不要解释。"
        )
        
        return self.polish_text(text, api_key, custom_prompt)


def polish_with_chatgpt(text: str, api_key: Optional[str] = None, **kwargs) -> str:
    """
    使用ChatGPT润色文本（兼容性函数）
    
    Args:
        text: 待润色的文本
        api_key: OpenAI API密钥
        **kwargs: 其他配置参数
        
    Returns:
        润色后的文本
    """
    processor = ChatGPTProcessor(config_override=kwargs)
    return processor.polish_text(text, api_key)


class TextProcessor:
    """文本处理器 - 提供非AI的文本处理功能"""
    
    def __init__(self):
        self.config = get_config()
        self.logger = logger.bind(name="TextProcessor")
    
    def basic_formatting(self, text: str) -> str:
        """
        基础文本格式化
        
        Args:
            text: 原文本
            
        Returns:
            格式化后的文本
        """
        if not text.strip():
            return text
        
        # 基本的格式化操作
        lines = []
        current_speaker = None
        
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            
            # 检测说话人标签
            if line.startswith("[") and line.endswith("]"):
                current_speaker = line
                lines.append("")  # 添加空行分隔
                lines.append(line)
            else:
                # 应用基础的标点符号规则
                line = self._add_basic_punctuation(line)
                lines.append(line)
        
        # 清理多余的空行
        result = "\n".join(lines)
        result = "\n".join(line for line in result.split("\n") if line.strip())
        
        return result
    
    def _add_basic_punctuation(self, text: str) -> str:
        """添加基础标点符号"""
        if not text.strip():
            return text
        
        # 简单的标点符号规则
        text = text.strip()
        
        # 如果句子没有结束符，添加句号
        if text and text[-1] not in "。！？.,!?":
            text += "。"
        
        return text
    
    def apply_speaker_labels(self, text: str, speaker_mapping: Optional[Dict[str, str]] = None) -> str:
        """
        应用说话人标签映射
        
        Args:
            text: 原文本
            speaker_mapping: 标签映射
            
        Returns:
            应用映射后的文本
        """
        if not speaker_mapping:
            speaker_mapping = self.config.get("output.speaker_labels", {})
        
        if not speaker_mapping:
            return text
        
        result = text
        for old_label, new_label in speaker_mapping.items():
            result = result.replace(f"[{old_label}]", f"[{new_label}]")
        
        return result