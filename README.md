# 音频/视频转录与字幕生成工具

这是一个集成的音频/视频处理工具，可以将长音频或视频文件转录为文本并生成 SRT 字幕。该工具自动处理整个流程，包括：视频提取音频、音频切分、转录、翻译和字幕生成。

## 主要功能

- **视频处理**：自动从视频文件中提取音频
- **智能音频切分**：根据静音点自动将长音频文件切分为较小的片段
- **音频转录与翻译**：使用 Google Gemini AI 将音频转录为文本并翻译成中文
- **字幕时间戳生成**：自动为转录和翻译内容添加精确的时间戳
- **SRT 字幕生成**：将所有转录片段合并，生成标准 SRT 格式字幕文件
- **图形用户界面**：提供直观的界面，简化处理流程
- **灵活的输出选项**：支持仅转录、仅翻译或两者都包含的字幕文件

## 系统要求

- Python 3.8+
- FFmpeg (用于视频处理)
- 必要的 Python 库 (见安装部分)
- Google AI API 密钥 (Gemini 2.5 模型)

## 安装

1. 克隆或下载此仓库

2. 安装必要的 Python 依赖：

```bash
pip install pydub librosa soundfile google-generativeai numpy mutagen
```

3. 确保系统中已安装 FFmpeg (用于视频处理)：

```bash
# 在 Ubuntu/Debian 系统上
sudo apt-get install ffmpeg

# 在 macOS 上 (使用 Homebrew)
brew install ffmpeg

# 在 Windows 上
# 请从 https://ffmpeg.org/download.html 下载，并将其添加到系统 PATH
```

4. 配置 Google AI API 密钥：
   - 获取 Google Gemini API 密钥
   - 可以设置环境变量 `GOOGLE_API_KEY`，或在使用时手动输入

## 使用方法

### 图形界面版本

1. 运行 GUI 应用程序：

```bash
python audio_processor_gui.py
```

2. 在界面上：
   - 选择输入文件（音频或视频）
   - 输入 Google AI API 密钥
   - 调整处理参数（如需要）
   - 点击「开始处理」

### 命令行版本

```bash
python process_audio.py 输入文件.mp3 --api-key YOUR_API_KEY [其他选项]
```

示例：

```bash
# 基本用法
python process_audio.py 录音.mp3 --api-key YOUR_API_KEY

# 处理视频并包含转录和翻译
python process_audio.py 视频.mp4 --api-key YOUR_API_KEY --content both

# 调整音频切分参数
python process_audio.py 长音频.mp3 --api-key YOUR_API_KEY --max-length 240 --silence-length 700 --silence-threshold -45

# 指定输出目录并清理中间文件
python process_audio.py 演讲.mp3 --api-key YOUR_API_KEY --output-dir ./输出目录 --cleanup
```

### 主要参数

- `--api-key`：Google AI API 密钥 (**必需**)
- `--output-dir`：输出目录 (默认使用输入文件名创建目录)
- `--content`：选择字幕内容类型
  - `transcript`：仅包含转录
  - `translation`：仅包含翻译
  - `both`：同时包含转录和翻译 (默认)
- `--max-length`：最大音频片段长度 (秒，默认 300)
- `--silence-length`：静音检测的最小长度 (毫秒，默认 500)
- `--silence-threshold`：静音检测阈值 (dB，默认 -40)
- `--first-chunk-offset`：第一个音频片段的时间偏移 (秒，默认 0)
- `--cleanup`：处理完成后删除中间文件

## 工作流程

1. **预处理**：
   - 如果输入是视频文件，使用 FFmpeg 提取音频
   
2. **音频切分**：
   - 检测音频中的静音点
   - 在适当的静音点处切分音频
   - 生成多个较小的音频片段
   
3. **音频转录**：
   - 使用 Google Gemini AI 处理每个音频片段
   - 为每个片段生成转录和翻译
   - 带有时间戳的转录和翻译文本
   
4. **字幕生成**：
   - 根据音频片段长度计算累积时间偏移
   - 合并所有转录文件
   - 生成 SRT 格式的字幕文件

## 项目结构

- `split_audio.py`：音频切分模块
- `transcript.py`：音频转录与翻译模块
- `combine_transcripts.py`：字幕合并模块
- `process_audio.py`：主处理流程协调模块
- `audio_processor_gui.py`：图形用户界面模块

## 注意事项

- 处理长音频/视频文件可能需要一定时间
- API 调用可能产生费用，具体取决于您的 Google AI API 使用计划
- 字幕时间戳的准确性可能会因音频质量而有所不同
- 需要网络连接才能使用 Google AI API

## 常见问题

1. **为什么需要切分音频？**
   - Google Gemini API 对文件大小和处理时长有限制
   - 切分为较小片段可以提高转录准确性和可靠性
   
2. **如何调整时间戳偏移？**
   - 如果生成的字幕与视频不同步，可以使用 `--first-chunk-offset` 参数调整

3. **如何处理不同语言的音频？**
   - 系统会自动检测音频语言并转录，然后翻译为中文

4. **FFmpeg 安装问题？**
   - 确保 FFmpeg 正确安装并添加到系统 PATH 中
   - 可以通过命令行运行 `ffmpeg -version` 验证安装

## 许可证

[添加您的许可证信息]