#!/usr/bin/env python3
"""
主程序入口

自动检测运行模式并启动相应的界面。
"""

import sys
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.logging_setup import setup_logging
from src.config import get_config


def main():
    """主函数"""
    # 初始化日志
    setup_logging()
    
    # 获取配置
    config = get_config()
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        # 有命令行参数，启动CLI
        from src.cli import main as cli_main
        return cli_main()
    else:
        # 无参数，启动GUI
        from src.gui import main as gui_main
        gui_main()
        return 0


if __name__ == "__main__":
    sys.exit(main())