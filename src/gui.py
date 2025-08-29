"""
现代化GUI应用程序

提供用户友好的图形界面，支持：
- 完整音频处理管道
- 现有文件合并
- 实时进度显示
- 配置管理
- 结果导出
"""

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from typing import Optional, Dict, Any
import queue
from loguru import logger

from .config import get_config
from .pipeline import ProcessingPipeline
from .logging_setup import setup_logging
from .exceptions import SpeakerDiartError


class ProgressDialog:
    """进度对话框"""
    
    def __init__(self, parent, title="处理中..."):
        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("400x200")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # 居中显示
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (400 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (200 // 2)
        self.dialog.geometry(f"400x200+{x}+{y}")
        
        # 设置为不可关闭
        self.dialog.protocol("WM_DELETE_WINDOW", lambda: None)
        
        # 创建UI元素
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        self.status_label = ttk.Label(main_frame, text="准备开始...", font=("Arial", 10))
        self.status_label.pack(pady=(0, 10))
        
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.pack(fill=tk.X, pady=(0, 10))
        
        self.detail_label = ttk.Label(main_frame, text="", font=("Arial", 8), foreground="gray")
        self.detail_label.pack(pady=(0, 20))
        
        # 开始进度动画
        self.progress.start(10)
    
    def update_status(self, status: str, detail: str = ""):
        """更新状态"""
        self.status_label.config(text=status)
        self.detail_label.config(text=detail)
        self.dialog.update()
    
    def close(self):
        """关闭对话框"""
        self.progress.stop()
        self.dialog.destroy()


class ConfigFrame(ttk.LabelFrame):
    """配置框架"""
    
    def __init__(self, parent, config):
        super().__init__(parent, text="配置设置", padding="10")
        self.config = config
        self.create_widgets()
    
    def create_widgets(self):
        # Whisper配置
        whisper_frame = ttk.LabelFrame(self, text="语音识别设置", padding="5")
        whisper_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(whisper_frame, text="模型大小:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.whisper_model = ttk.Combobox(whisper_frame, values=["tiny", "base", "small", "medium", "large"], 
                                         state="readonly", width=15)
        self.whisper_model.set(self.config.get("whisper.model_size", "small"))
        self.whisper_model.grid(row=0, column=1, sticky=tk.W, padx=(0, 10))
        
        ttk.Label(whisper_frame, text="设备:").grid(row=0, column=2, sticky=tk.W, padx=(10, 5))
        self.device = ttk.Combobox(whisper_frame, values=["cpu", "cuda"], state="readonly", width=10)
        self.device.set(self.config.get("whisper.device", "cpu"))
        self.device.grid(row=0, column=3, sticky=tk.W)
        
        ttk.Label(whisper_frame, text="语言:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        self.language = ttk.Entry(whisper_frame, width=10)
        self.language.insert(0, self.config.get("whisper.language", "zh"))
        self.language.grid(row=1, column=1, sticky=tk.W, pady=(5, 0))
        
        # 说话人分离配置
        diarization_frame = ttk.LabelFrame(self, text="说话人分离设置", padding="5")
        diarization_frame.pack(fill=tk.X, pady=(5, 5))
        
        ttk.Label(diarization_frame, text="说话人数量:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.num_speakers = ttk.Spinbox(diarization_frame, from_=1, to=10, width=10)
        self.num_speakers.set(self.config.get("diarization.num_speakers", 2))
        self.num_speakers.grid(row=0, column=1, sticky=tk.W)
        
        # ChatGPT配置
        chatgpt_frame = ttk.LabelFrame(self, text="ChatGPT润色设置", padding="5")
        chatgpt_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.use_chatgpt = tk.BooleanVar(value=self.config.get("chatgpt.enabled", False))
        ttk.Checkbutton(chatgpt_frame, text="启用ChatGPT润色", variable=self.use_chatgpt).grid(row=0, column=0, sticky=tk.W)
        
        ttk.Label(chatgpt_frame, text="API密钥:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        self.openai_key = ttk.Entry(chatgpt_frame, show="*", width=40)
        self.openai_key.insert(0, os.getenv("OPENAI_API_KEY", ""))
        self.openai_key.grid(row=1, column=1, columnspan=2, sticky=tk.EW, pady=(5, 0))
        
        chatgpt_frame.columnconfigure(1, weight=1)
    
    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return {
            "whisper": {
                "model_size": self.whisper_model.get(),
                "device": self.device.get(),
                "language": self.language.get()
            },
            "diarization": {
                "num_speakers": int(self.num_speakers.get()),
                "device": self.device.get()
            },
            "chatgpt": {
                "enabled": self.use_chatgpt.get()
            },
            "use_chatgpt": self.use_chatgpt.get(),
            "openai_api_key": self.openai_key.get() if self.openai_key.get() else None
        }


class MainApplication:
    """主应用程序"""
    
    def __init__(self):
        self.config = get_config()
        self.pipeline = ProcessingPipeline()
        
        # 设置日志
        setup_logging()
        self.logger = logger.bind(name="GUI")
        
        # 创建主窗口
        self.root = tk.Tk()
        self.root.title(self.config.get("gui.window_title", "广东话采访处理系统 v2.0"))
        self.root.geometry("900x700")
        
        # 设置图标（如果存在）
        try:
            # 可以在这里设置应用程序图标
            pass
        except:
            pass
        
        # 创建界面
        self.create_widgets()
        
        # 线程队列用于跨线程通信
        self.result_queue = queue.Queue()
        self.root.after(100, self.check_queue)
        
        self.logger.info("GUI应用程序已启动")
    
    def create_widgets(self):
        """创建界面组件"""
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建左侧框架（控制面板）
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        # 创建右侧框架（结果显示）
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # 模式选择
        mode_frame = ttk.LabelFrame(left_frame, text="处理模式", padding="10")
        mode_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.processing_mode = tk.StringVar(value="pipeline")
        ttk.Radiobutton(mode_frame, text="完整管道处理", variable=self.processing_mode, 
                       value="pipeline", command=self.on_mode_change).pack(anchor=tk.W)
        ttk.Radiobutton(mode_frame, text="文件合并模式", variable=self.processing_mode, 
                       value="merge", command=self.on_mode_change).pack(anchor=tk.W)
        
        # 输入文件选择
        self.input_frame = ttk.LabelFrame(left_frame, text="输入文件", padding="10")
        self.input_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 音频文件输入（完整管道模式）
        self.audio_frame = ttk.Frame(self.input_frame)
        self.audio_frame.pack(fill=tk.X)
        
        ttk.Button(self.audio_frame, text="选择音频文件", command=self.choose_audio_file).pack(anchor=tk.W)
        self.audio_path = tk.StringVar()
        ttk.Entry(self.audio_frame, textvariable=self.audio_path, width=40, state="readonly").pack(fill=tk.X, pady=(5, 0))
        
        # VTT/RTTM文件输入（合并模式）
        self.merge_frame = ttk.Frame(self.input_frame)
        
        ttk.Button(self.merge_frame, text="选择VTT文件", command=self.choose_vtt_file).pack(anchor=tk.W)
        self.vtt_path = tk.StringVar()
        ttk.Entry(self.merge_frame, textvariable=self.vtt_path, width=40, state="readonly").pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(self.merge_frame, text="选择RTTM文件", command=self.choose_rttm_file).pack(anchor=tk.W, pady=(10, 0))
        self.rttm_path = tk.StringVar()
        ttk.Entry(self.merge_frame, textvariable=self.rttm_path, width=40, state="readonly").pack(fill=tk.X, pady=(5, 0))
        
        # 配置面板
        self.config_frame = ConfigFrame(left_frame, self.config)
        self.config_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 操作按钮
        button_frame = ttk.Frame(left_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(button_frame, text="开始处理", command=self.start_processing).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="导出结果", command=self.export_results).pack(side=tk.LEFT, padx=(5, 5))
        ttk.Button(button_frame, text="清除结果", command=self.clear_results).pack(side=tk.LEFT, padx=(5, 0))
        
        # 结果显示区域
        result_frame = ttk.LabelFrame(right_frame, text="处理结果", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True)
        
        # 结果标签页
        self.notebook = ttk.Notebook(result_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # 合并结果标签页
        self.merged_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.merged_frame, text="合并结果")
        
        self.merged_text = tk.Text(self.merged_frame, wrap=tk.WORD, font=("Microsoft YaHei", 10))
        merged_scroll = ttk.Scrollbar(self.merged_frame, orient=tk.VERTICAL, command=self.merged_text.yview)
        self.merged_text.config(yscrollcommand=merged_scroll.set)
        self.merged_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        merged_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 润色结果标签页
        self.polished_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.polished_frame, text="润色结果")
        
        self.polished_text = tk.Text(self.polished_frame, wrap=tk.WORD, font=("Microsoft YaHei", 10))
        polished_scroll = ttk.Scrollbar(self.polished_frame, orient=tk.VERTICAL, command=self.polished_text.yview)
        self.polished_text.config(yscrollcommand=polished_scroll.set)
        self.polished_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        polished_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 日志标签页
        self.log_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.log_frame, text="处理日志")
        
        self.log_text = tk.Text(self.log_frame, wrap=tk.WORD, font=("Consolas", 9))
        log_scroll = ttk.Scrollbar(self.log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.config(yscrollcommand=log_scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 状态栏
        self.status_frame = ttk.Frame(right_frame)
        self.status_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.status_label = ttk.Label(self.status_frame, text="就绪", relief=tk.SUNKEN)
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 初始化界面状态
        self.on_mode_change()
        
        # 处理结果缓存
        self.last_result = None
    
    def on_mode_change(self):
        """模式改变事件"""
        if self.processing_mode.get() == "pipeline":
            self.merge_frame.pack_forget()
            self.audio_frame.pack(fill=tk.X)
        else:
            self.audio_frame.pack_forget()
            self.merge_frame.pack(fill=tk.X)
    
    def choose_audio_file(self):
        """选择音频文件"""
        file_path = filedialog.askopenfilename(
            title="选择音频文件",
            filetypes=[
                ("音频文件", "*.wav *.mp3 *.m4a *.mp4 *.flac *.aac"),
                ("视频文件", "*.mp4 *.mkv *.mov"),
                ("所有文件", "*.*")
            ]
        )
        if file_path:
            self.audio_path.set(file_path)
    
    def choose_vtt_file(self):
        """选择VTT文件"""
        file_path = filedialog.askopenfilename(
            title="选择VTT文件",
            filetypes=[("VTT文件", "*.vtt"), ("所有文件", "*.*")]
        )
        if file_path:
            self.vtt_path.set(file_path)
    
    def choose_rttm_file(self):
        """选择RTTM文件"""
        file_path = filedialog.askopenfilename(
            title="选择RTTM文件",
            filetypes=[("RTTM文件", "*.rttm"), ("所有文件", "*.*")]
        )
        if file_path:
            self.rttm_path.set(file_path)
    
    def start_processing(self):
        """开始处理"""
        if self.processing_mode.get() == "pipeline":
            if not self.audio_path.get():
                messagebox.showwarning("提示", "请先选择音频文件")
                return
            input_file = self.audio_path.get()
        else:
            if not self.vtt_path.get() or not self.rttm_path.get():
                messagebox.showwarning("提示", "请选择VTT和RTTM文件")
                return
            input_file = (self.vtt_path.get(), self.rttm_path.get())
        
        # 获取配置
        config = self.config_frame.get_config()
        
        # 在后台线程中处理
        threading.Thread(target=self.process_in_thread, args=(input_file, config), daemon=True).start()
        
        # 显示进度对话框
        self.progress_dialog = ProgressDialog(self.root, "正在处理，请稍候...")
        self.status_label.config(text="处理中...")
    
    def process_in_thread(self, input_file, config):
        """在后台线程中处理"""
        try:
            # 创建管道实例
            pipeline = ProcessingPipeline(config_override=config)
            
            if self.processing_mode.get() == "pipeline":
                # 完整管道处理
                result = pipeline.process_audio(input_file, **config)
            else:
                # 文件合并处理
                vtt_file, rttm_file = input_file
                result = pipeline.process_existing_files(vtt_file, rttm_file, **config)
            
            # 将结果放入队列
            self.result_queue.put(("success", result))
            
        except Exception as e:
            self.logger.error(f"处理失败: {e}")
            self.result_queue.put(("error", str(e)))
    
    def check_queue(self):
        """检查结果队列"""
        try:
            result_type, data = self.result_queue.get_nowait()
            
            # 关闭进度对话框
            if hasattr(self, 'progress_dialog'):
                self.progress_dialog.close()
            
            if result_type == "success":
                self.display_results(data)
                self.status_label.config(text="处理完成")
                messagebox.showinfo("成功", "处理完成！")
            else:
                self.status_label.config(text="处理失败")
                messagebox.showerror("错误", f"处理失败：{data}")
                
        except queue.Empty:
            pass
        
        # 继续检查队列
        self.root.after(100, self.check_queue)
    
    def display_results(self, result: Dict[str, Any]):
        """显示处理结果"""
        self.last_result = result
        
        # 显示合并结果
        merged_text = result.get("merged_text", "")
        self.merged_text.delete(1.0, tk.END)
        self.merged_text.insert(tk.END, merged_text)
        
        # 显示润色结果
        polished_text = result.get("polished_text", "")
        self.polished_text.delete(1.0, tk.END)
        if polished_text and polished_text != merged_text:
            self.polished_text.insert(tk.END, polished_text)
        else:
            self.polished_text.insert(tk.END, merged_text)
        
        # 显示处理信息
        processing_info = result.get("processing_info", {})
        log_content = f"处理完成阶段: {', '.join(processing_info.get('stages_completed', []))}\n"
        if processing_info.get("errors"):
            log_content += f"错误信息: {'; '.join(processing_info['errors'])}\n"
        
        self.log_text.delete(1.0, tk.END)
        self.log_text.insert(tk.END, log_content)
        
        # 切换到合并结果标签页
        self.notebook.select(0)
    
    def export_results(self):
        """导出结果"""
        if not self.last_result:
            messagebox.showwarning("提示", "没有可导出的结果")
            return
        
        # 选择导出目录
        output_dir = filedialog.askdirectory(title="选择导出目录")
        if not output_dir:
            return
        
        try:
            # 生成基础文件名
            if self.processing_mode.get() == "pipeline":
                base_name = Path(self.audio_path.get()).stem
            else:
                base_name = Path(self.vtt_path.get()).stem
            
            # 导出文件
            exported_files = self.pipeline.export_results(self.last_result, output_dir, base_name)
            
            messagebox.showinfo("成功", f"结果已导出到:\n" + "\n".join(exported_files))
            self.logger.info(f"结果已导出到: {output_dir}")
            
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {e}")
            self.logger.error(f"导出失败: {e}")
    
    def clear_results(self):
        """清除结果"""
        self.merged_text.delete(1.0, tk.END)
        self.polished_text.delete(1.0, tk.END)
        self.log_text.delete(1.0, tk.END)
        self.last_result = None
        self.status_label.config(text="就绪")
    
    def run(self):
        """运行应用程序"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.logger.info("应用程序被用户中断")
        except Exception as e:
            self.logger.error(f"应用程序运行错误: {e}")
            raise


def main():
    """主函数"""
    try:
        app = MainApplication()
        app.run()
    except Exception as e:
        logger.error(f"应用程序启动失败: {e}")
        messagebox.showerror("错误", f"应用程序启动失败: {e}")


if __name__ == "__main__":
    main()