import tkinter as tk
from tkinter import filedialog, messagebox
import threading

# 时间转换为秒的函数
def convert_to_seconds(time_str):
    parts = time_str.split(':')
    if len(parts) == 3:
        h, m, s = parts
    elif len(parts) == 2:
        h = 0
        m, s = parts
    else:
        raise ValueError(f"时间格式错误: {time_str}")
    
    return int(h) * 3600 + int(m) * 60 + float(s)

# 解析VTT文件的函数
def parse_vtt(vtt_content):
    subtitles = []
    entries = vtt_content.split("\n\n")
    for entry in entries:
        if '-->' in entry:
            parts = entry.split('\n')
            times = parts[0]
            text = '\n'.join(parts[1:]) if len(parts) > 1 else ""
            start_time, end_time = times.split(' --> ')
            subtitles.append({
                'start': convert_to_seconds(start_time.strip()),
                'end': convert_to_seconds(end_time.strip()),
                'text': text.strip(),
                'speakers': None  # Initialize speakers as None
            })
    return subtitles

# 解析RTTM文件的函数
def parse_rttm(rttm_content):
    speakers = []
    for line in rttm_content.splitlines():
        parts = line.split()
        start_time = float(parts[3])
        duration = float(parts[4])
        speaker_id = parts[7]
        speakers.append({
            'start': start_time,
            'end': start_time + duration,
            'speaker': speaker_id
        })
    return speakers

# 映射说话人到字幕的函数
def map_speakers_to_subtitles(subtitles, speakers):
    for subtitle in subtitles:
        max_overlap_speaker = None
        max_overlap_duration = 0
        
        for speaker in speakers:
            overlap_start = max(subtitle['start'], speaker['start'])
            overlap_end = min(subtitle['end'], speaker['end'])
            overlap_duration = max(0, overlap_end - overlap_start)
            
            if overlap_duration > max_overlap_duration:
                max_overlap_speaker = speaker['speaker']
                max_overlap_duration = overlap_duration
        
        if max_overlap_speaker:
            subtitle['speakers'] = {max_overlap_speaker}

# 格式化输出的函数
def format_output(subtitles):
    output = []
    current_speaker = None

    for sub in subtitles:
        if sub['speakers']:
            speaker = list(sub['speakers'])[0]
            if speaker != current_speaker:
                current_speaker = speaker
                output.append(f"[{current_speaker}]")
        output.append(sub['text'])

    return "\n".join(output)

# 处理文件的函数
def process_files():
    try:
        with open(vtt_path.get(), 'r', encoding='utf-8') as f:
            vtt_content = f.read()
        with open(rttm_path.get(), 'r', encoding='utf-8') as f:
            rttm_content = f.read()

        subtitles = parse_vtt(vtt_content)
        speakers = parse_rttm(rttm_content)
        map_speakers_to_subtitles(subtitles, speakers)

        output_content = format_output(subtitles)
        output_path.set(output_content)
        messagebox.showinfo("成功", "处理完成！")
    except Exception as e:
        messagebox.showerror("错误", str(e))

# 保存输出文件的函数
def save_output():
    file_path = filedialog.asksaveasfilename(defaultextension=".txt")
    if file_path:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(output_path.get())
        messagebox.showinfo("成功", "文件已保存！")

# 在线程中运行处理文件的函数以避免界面冻结
def process_files_thread():
    thread = threading.Thread(target=process_files)
    thread.start()

# 加载文件的函数
def load_file(file_type):
    file_path = filedialog.askopenfilename()
    if file_type == 'vtt':
        vtt_path.set(file_path)
    elif file_type == 'rttm':
        rttm_path.set(file_path)

# 创建主窗口
root = tk.Tk()
root.title("VTT和RTTM文件处理器")

vtt_path = tk.StringVar()
rttm_path = tk.StringVar()
output_path = tk.StringVar()

# 布局
tk.Button(root, text="载入VTT文件", command=lambda: load_file('vtt')).pack()
tk.Entry(root, textvariable=vtt_path, width=50).pack()

tk.Button(root, text="载入RTTM文件", command=lambda: load_file('rttm')).pack()
tk.Entry(root, textvariable=rttm_path, width=50).pack()

tk.Button(root, text="处理文件", command=process_files_thread).pack()

tk.Button(root, text="保存输出", command=save_output).pack()
tk.Entry(root, textvariable=output_path, width=50).pack()

root.mainloop()
