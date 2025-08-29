# 广东话采访处理系统 v2.0

一个现代化的端到端音频处理系统，专为广东话采访录音设计，集成了语音识别、说话人分离和文本后处理功能。

## ✨ 功能特色

- 🎯 **专为广东话优化** - 使用Whisper和diart进行高质量转录和说话人分离
- 🚀 **完整的处理管道** - 从音频文件到格式化文本的一站式处理
- 🤖 **ChatGPT集成** - 自动润色和格式化转录文本
- 🖥️ **双重界面** - 现代化GUI和强大的CLI工具
- 📊 **性能监控** - 实时资源使用和处理时间分析
- ⚙️ **灵活配置** - YAML配置文件支持和运行时参数调整
- 🔧 **错误恢复** - 完善的异常处理和失败恢复机制

## 📋 系统要求

### Python环境
- **Python**: 3.10, 3.11 或 3.12
- **包管理**: conda (推荐) 或 pip

### 系统依赖
- **FFmpeg** - 音频/视频处理
- **PortAudio** - 音频设备接口
- **libsndfile** - 音频文件读写

### 可选依赖
- **CUDA 12 + cuDNN 9** - GPU加速处理
- **OpenAI API密钥** - ChatGPT文本润色

## 🚀 快速开始

### 1. 环境安装

#### 使用conda（推荐）
```bash
# CPU版本（适合开发和轻量使用）
conda env create -f environment.yml
conda activate speakerdiart

# GPU版本（适合高性能处理）
conda env create -f environment-gpu.yml
conda activate speakerdiart-gpu
```

#### 使用pip
```bash
pip install -r requirements.txt
```

### 2. 配置Hugging Face访问

访问以下链接并接受模型使用条款：
- [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)
- [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)

创建访问令牌：[hf.co/settings/tokens](https://huggingface.co/settings/tokens)

### 3. 运行应用程序

#### 图形界面（GUI）
```bash
python main.py
```

#### 命令行界面（CLI）
```bash
# 处理单个文件
python main.py audio.wav

# 批量处理目录
python main.py /path/to/audio/files --recursive

# 使用GPU和ChatGPT
python main.py audio.wav --device cuda --chatgpt
```

## 📖 使用指南

### GUI使用方法

1. **选择处理模式**
   - 完整管道处理：处理音频文件
   - 文件合并模式：合并现有VTT和RTTM文件

2. **配置参数**
   - Whisper模型大小（tiny/base/small/medium/large）
   - 计算设备（CPU/GPU）
   - 说话人数量
   - ChatGPT设置

3. **查看结果**
   - 合并结果：带说话人标签的文本
   - 润色结果：ChatGPT优化后的文本
   - 处理日志：详细的处理信息

### CLI命令参考

```bash
# 基础用法
python main.py input.wav                    # 处理单个文件
python main.py /audio/dir --recursive       # 递归处理目录
python main.py --merge audio.vtt audio.rttm # 合并现有文件

# 模型配置
python main.py input.wav --model medium     # 使用medium模型
python main.py input.wav --device cuda      # 使用GPU加速
python main.py input.wav --speakers 3       # 指定3个说话人

# ChatGPT润色
python main.py input.wav --chatgpt          # 启用ChatGPT
python main.py input.wav --openai-key "sk-..." # 指定API密钥

# 输出控制
python main.py input.wav --output results   # 指定输出目录
python main.py input.wav --export-intermediate # 导出中间文件
python main.py input.wav --format txt vtt   # 指定输出格式

# 其他选项
python main.py /audio/dir --dry-run         # 预览要处理的文件
python main.py input.wav --verbose          # 详细日志输出
python main.py input.wav --config my.yaml  # 使用自定义配置
```

## ⚙️ 配置文件

### 配置文件位置
- `config/default.yaml` - 系统默认配置
- `config/user.yaml` - 用户自定义配置（自动生成）

### 主要配置项

#### Whisper设置
```yaml
whisper:
  model_size: "small"      # 模型大小
  device: "cpu"           # 计算设备
  language: "zh"          # 语言代码
  vad_filter: true        # 语音活动检测
```

#### 说话人分离设置
```yaml
diarization:
  num_speakers: 2         # 说话人数量
  device: "cpu"          # 计算设备
  min_segment_length: 0.5 # 最小片段长度
```

#### ChatGPT设置
```yaml
chatgpt:
  enabled: false          # 是否启用
  model: "gpt-4o-mini"   # 模型名称
  temperature: 0.2        # 生成温度
  system_prompt: |        # 系统提示词
    你是中文编辑助手...
```

#### 输出设置
```yaml
output:
  directory: "outputs"    # 输出目录
  formats: ["txt"]        # 输出格式
  speaker_labels:         # 说话人标签映射
    SPEAKER_00: "主持人"
    SPEAKER_01: "受访者"
```

## 📊 性能监控

系统自动跟踪处理性能：

- **实时监控**: CPU使用率、内存占用
- **阶段计时**: 转录、分离、合并、后处理各阶段耗时
- **历史统计**: 保存在`logs/metrics.json`中
- **性能报告**: 可通过CLI查看统计信息

```bash
# 查看性能报告
python -c "from src.monitoring import MetricsAnalyzer; print(MetricsAnalyzer('logs/metrics.json').generate_report())"
```

## 🔧 故障排除

### 常见问题

#### 1. 模型加载失败
```
Error: faster-whisper库未安装
```
**解决方案**: 
```bash
pip install faster-whisper
```

#### 2. diart导入错误
```
Error: diart is required for diarization
```
**解决方案**: 
```bash
pip install diart onnxruntime
# 确保已接受Hugging Face模型使用条款
```

#### 3. ChatGPT API错误
```
Error: 未提供OpenAI API密钥
```
**解决方案**: 
```bash
export OPENAI_API_KEY="your-api-key-here"
# 或在GUI中配置API密钥
```

#### 4. CUDA相关问题
```
Error: CUDA out of memory
```
**解决方案**: 
- 使用较小的Whisper模型
- 减少并发处理数量
- 切换到CPU处理

### 日志文件位置
- **应用日志**: `logs/speakerdiart.log`
- **性能指标**: `logs/metrics.json`
- **配置文件**: `config/user.yaml`

## 🏗️ 开发指南

### 项目结构
```
speakerdiart/
├── src/                # 源代码
│   ├── config.py      # 配置管理
│   ├── pipeline.py    # 主处理流程
│   ├── transcription.py # Whisper转录
│   ├── diarization.py # 说话人分离
│   ├── merge.py       # 文件合并
│   ├── postprocess.py # 文本后处理
│   ├── gui.py         # 图形界面
│   ├── cli.py         # 命令行界面
│   └── monitoring.py  # 性能监控
├── config/            # 配置文件
├── tests/             # 测试用例
└── logs/              # 日志文件
```

### 代码规范
```bash
# 格式化代码
black src/
isort src/

# 代码检查
flake8 src/

# 运行测试
pytest tests/
```

### 添加新功能
1. 在相应模块中实现功能
2. 添加配置选项到`default.yaml`
3. 更新CLI参数解析
4. 添加GUI控件（如需要）
5. 编写测试用例
6. 更新文档

## 📄 许可证

[请根据实际情况添加许可证信息]

## 🤝 贡献

欢迎提交Issue和Pull Request来帮助改进这个项目！

## 📞 支持

如果遇到问题或有功能建议，请：
1. 查看本文档的故障排除部分
2. 检查`logs/speakerdiart.log`中的错误信息
3. 在GitHub上提交Issue

---

**注意**: 本系统需要网络连接以下载AI模型和访问ChatGPT API。首次运行时会自动下载必要的模型文件。