import threading
import tkinter as tk
from tkinter import filedialog, messagebox

from typing import Optional


def run_in_thread(fn):
    def wrapper(*args, **kwargs):
        t = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
        t.start()
    return wrapper


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Cantonese Interview Pipeline (CPU)")

        self.mode = tk.StringVar(value="pipeline")  # pipeline | merge
        self.audio_path = tk.StringVar()
        self.vtt_path = tk.StringVar()
        self.rttm_path = tk.StringVar()
        self.whisper_model = tk.StringVar(value="small")
        self.device = tk.StringVar(value="cpu")
        self.use_chatgpt = tk.BooleanVar(value=False)
        self.openai_key = tk.StringVar()

        self._build_ui()

    def _build_ui(self) -> None:
        # Mode selection
        frame_mode = tk.Frame(self)
        frame_mode.pack(fill=tk.X, padx=8, pady=6)
        tk.Label(frame_mode, text="模式:").pack(side=tk.LEFT)
        tk.Radiobutton(frame_mode, text="一体化管线(音频)", variable=self.mode, value="pipeline", command=self._refresh_mode).pack(side=tk.LEFT)
        tk.Radiobutton(frame_mode, text="仅合并(VTT+RTTM)", variable=self.mode, value="merge", command=self._refresh_mode).pack(side=tk.LEFT)

        # Pipeline frame
        self.frame_pipeline = tk.LabelFrame(self, text="Pipeline")
        self.frame_pipeline.pack(fill=tk.X, padx=8, pady=4)
        tk.Button(self.frame_pipeline, text="选择音频", command=self._choose_audio).pack(anchor=tk.W)
        tk.Entry(self.frame_pipeline, textvariable=self.audio_path, width=60).pack(fill=tk.X)

        sub = tk.Frame(self.frame_pipeline)
        sub.pack(fill=tk.X, pady=2)
        tk.Label(sub, text="Whisper模型:").pack(side=tk.LEFT)
        tk.Entry(sub, textvariable=self.whisper_model, width=10).pack(side=tk.LEFT)
        tk.Label(sub, text="设备:").pack(side=tk.LEFT, padx=(8, 0))
        tk.Entry(sub, textvariable=self.device, width=8).pack(side=tk.LEFT)

        gpt = tk.Frame(self.frame_pipeline)
        gpt.pack(fill=tk.X, pady=2)
        tk.Checkbutton(gpt, text="使用ChatGPT润色", variable=self.use_chatgpt).pack(side=tk.LEFT)
        tk.Label(gpt, text="API Key:").pack(side=tk.LEFT, padx=(8, 0))
        tk.Entry(gpt, textvariable=self.openai_key, width=40, show="*").pack(side=tk.LEFT)

        # Merge-only frame
        self.frame_merge = tk.LabelFrame(self, text="Merge")
        self.frame_merge.pack(fill=tk.X, padx=8, pady=4)
        tk.Button(self.frame_merge, text="载入VTT", command=lambda: self._choose_file(self.vtt_path)).pack(anchor=tk.W)
        tk.Entry(self.frame_merge, textvariable=self.vtt_path, width=60).pack(fill=tk.X)
        tk.Button(self.frame_merge, text="载入RTTM", command=lambda: self._choose_file(self.rttm_path)).pack(anchor=tk.W)
        tk.Entry(self.frame_merge, textvariable=self.rttm_path, width=60).pack(fill=tk.X)

        # Actions
        frame_actions = tk.Frame(self)
        frame_actions.pack(fill=tk.X, padx=8, pady=6)
        tk.Button(frame_actions, text="开始", command=self._start).pack(side=tk.LEFT)
        tk.Button(frame_actions, text="保存结果", command=self._save).pack(side=tk.LEFT, padx=6)

        # Output
        self.out = tk.Text(self, height=24)
        self.out.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        self._refresh_mode()

    def _choose_audio(self) -> None:
        p = filedialog.askopenfilename(filetypes=[("Audio/Video", "*.*")])
        if p:
            self.audio_path.set(p)

    def _choose_file(self, var: tk.StringVar) -> None:
        p = filedialog.askopenfilename()
        if p:
            var.set(p)

    def _refresh_mode(self) -> None:
        if self.mode.get() == "pipeline":
            # Show pipeline, hide merge
            try:
                self.frame_merge.pack_forget()
            except Exception:
                pass
            if not self.frame_pipeline.winfo_ismapped():
                self.frame_pipeline.pack(fill=tk.X, padx=8, pady=4)
        else:
            # Show merge, hide pipeline
            try:
                self.frame_pipeline.pack_forget()
            except Exception:
                pass
            if not self.frame_merge.winfo_ismapped():
                self.frame_merge.pack(fill=tk.X, padx=8, pady=4)

    @run_in_thread
    def _start(self) -> None:
        try:
            if self.mode.get() == "pipeline":
                from pipeline import run_pipeline

                if not self.audio_path.get():
                    messagebox.showwarning("提示", "请先选择音频文件")
                    return
                res = run_pipeline(
                    self.audio_path.get(),
                    whisper_model=self.whisper_model.get(),
                    device=self.device.get(),
                    use_chatgpt=self.use_chatgpt.get(),
                    openai_api_key=self.openai_key.get() or None,
                )
                text = res.get("polished_text") or res.get("merged_text")
            else:
                # Merge-only path using existing files
                from merge import parse_vtt, parse_rttm, map_speakers_to_subtitles, format_output

                if not self.vtt_path.get() or not self.rttm_path.get():
                    messagebox.showwarning("提示", "请先选择 VTT 和 RTTM 文件")
                    return
                with open(self.vtt_path.get(), "r", encoding="utf-8") as f:
                    vtt = f.read()
                with open(self.rttm_path.get(), "r", encoding="utf-8") as f:
                    rttm = f.read()
                subs = parse_vtt(vtt)
                speakers = parse_rttm(rttm)
                map_speakers_to_subtitles(subs, speakers)
                text = format_output(subs)

            self._set_output(text)
            messagebox.showinfo("完成", "处理完成！")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def _set_output(self, text: str) -> None:
        self.out.configure(state=tk.NORMAL)
        self.out.delete("1.0", tk.END)
        self.out.insert(tk.END, text)
        self.out.configure(state=tk.NORMAL)

    def _save(self) -> None:
        content = self.out.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("提示", "没有可保存的内容")
            return
        p = filedialog.asksaveasfilename(defaultextension=".txt")
        if not p:
            return
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        messagebox.showinfo("成功", "文件已保存！")


if __name__ == "__main__":
    App().mainloop()
