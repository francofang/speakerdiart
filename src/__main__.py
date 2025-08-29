"""
模块入口点

支持通过 python -m src 运行应用程序。
"""

import sys
import argparse


def main():
    """主入口点"""
    parser = argparse.ArgumentParser(
        description="广东话采访处理系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
子命令:
  cli     - 命令行界面
  gui     - 图形用户界面
  
示例:
  python -m src gui              # 启动GUI
  python -m src cli audio.wav   # CLI处理音频文件
        """
    )
    
    parser.add_argument("mode", nargs="?", choices=["cli", "gui"], 
                       default="gui", help="运行模式（默认: gui）")
    parser.add_argument("args", nargs=argparse.REMAINDER, 
                       help="传递给子命令的参数")
    
    args = parser.parse_args()
    
    if args.mode == "gui":
        # 启动GUI
        from .gui import main as gui_main
        gui_main()
    elif args.mode == "cli":
        # 启动CLI，传递剩余参数
        sys.argv = ["cli"] + args.args
        from .cli import main as cli_main
        return cli_main()
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())