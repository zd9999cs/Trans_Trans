import os
import re
import datetime
import pathlib
import sys
import argparse # Import argparse
from mutagen.mp3 import MP3
from mutagen.wave import WAVE
from mutagen.flac import FLAC
from mutagen.mp4 import MP4 # For m4a etc.
from mutagen.oggvorbis import OggVorbis # For ogg

# --- 配置 ---
TRANSCRIPT_DIR = "intermediate_transcripts"
AUDIO_DIR = "temp_audio_chunks_new_api"
OUTPUT_SRT_FILE = "combined_subtitles.srt"
DEFAULT_SUB_DURATION_SECONDS = 5 # 如果无法确定下一个字幕的开始时间，则使用此默认持续时间
# -------------

# ... (get_audio_duration, parse_timestamp, timedelta_to_srt_time, extract_section functions remain the same) ...
def get_audio_duration(filepath):
    """获取音频文件的时长（秒）"""
    try:
        _, ext = os.path.splitext(filepath)
        ext = ext.lower()
        if ext == '.mp3':
            audio = MP3(filepath)
        elif ext == '.wav':
            audio = WAVE(filepath)
        elif ext == '.flac':
            audio = FLAC(filepath)
        elif ext in ['.m4a', '.mp4', '.aac']:
             audio = MP4(filepath)
        elif ext == '.ogg':
             audio = OggVorbis(filepath)
        else:
            print(f"  警告：不支持的文件类型 {ext}，无法获取时长: {filepath}")
            return 0.0 # 或者引发错误

        return audio.info.length
    except Exception as e:
        print(f"  错误：无法读取音频文件时长 {filepath}: {e}")
        return 0.0 # 或者引发错误

def parse_timestamp(timestamp_str, line_num=None, file=None, section=None):
    """
    解析时间戳字符串为秒数
    支持格式：'MM:SS.mmm'、'HH:MM:SS.mmm'、'SS.mmm'
    
    Args:
        timestamp_str (str): 要解析的时间戳字符串
        line_num (int, optional): 时间戳所在行号，用于错误报告
        file (str, optional): 时间戳所在文件，用于错误报告
        section (str, optional): 时间戳所在部分，用于错误报告
    
    Returns:
        float 或 None: 解析成功返回秒数，失败返回None
    """
    timestamp_str = timestamp_str.strip()
    
    # 检查空字符串
    if not timestamp_str:
        return None
    
    # 尝试匹配不同的时间戳格式
    formats = [
        # HH:MM:SS.mmm 格式
        r'^(\d+):(\d+):(\d+)\.(\d+)$',
        # MM:SS.mmm 格式
        r'^(\d+):(\d+)\.(\d+)$',
        # SS.mmm 格式
        r'^(\d+)\.(\d+)$'
    ]
    
    for fmt_idx, fmt in enumerate(formats):
        match = re.match(fmt, timestamp_str)
        if match:
            groups = match.groups()
            
            try:
                if fmt_idx == 0:  # HH:MM:SS.mmm
                    hours = int(groups[0])
                    minutes = int(groups[1])
                    seconds = int(groups[2])
                    milliseconds = int(groups[3])
                    
                    # 验证有效范围
                    if not (0 <= minutes < 60 and 0 <= seconds < 60 and 0 <= milliseconds < 1000):
                        # 收集错误信息
                        error_info = {
                            "file": file,
                            "line_num": line_num,
                            "section": section,
                            "timestamp_str": timestamp_str,
                            "reason": "时间格式数值超出有效范围"
                        }
                        parse_timestamp.errors.append(error_info)
                        return None
                    
                    total_seconds = hours * 3600 + minutes * 60 + seconds + milliseconds / 1000
                
                elif fmt_idx == 1:  # MM:SS.mmm
                    minutes = int(groups[0])
                    seconds = int(groups[1])
                    milliseconds = int(groups[2])
                    
                    # 验证有效范围
                    if not (0 <= seconds < 60 and 0 <= milliseconds < 1000):
                        # 收集错误信息
                        error_info = {
                            "file": file,
                            "line_num": line_num,
                            "section": section,
                            "timestamp_str": timestamp_str,
                            "reason": "时间格式数值超出有效范围"
                        }
                        parse_timestamp.errors.append(error_info)
                        return None
                    
                    total_seconds = minutes * 60 + seconds + milliseconds / 1000
                
                else:  # SS.mmm
                    seconds = int(groups[0])
                    milliseconds = int(groups[1])
                    total_seconds = seconds + milliseconds / 1000
                
                return total_seconds
            
            except (ValueError, IndexError) as e:
                # 收集错误信息
                error_info = {
                    "file": file,
                    "line_num": line_num,
                    "section": section,
                    "timestamp_str": timestamp_str,
                    "reason": str(e)
                }
                parse_timestamp.errors.append(error_info)
                return None
    
    # 如果所有格式都不匹配
    error_info = {
        "file": file,
        "line_num": line_num,
        "section": section,
        "timestamp_str": timestamp_str,
        "reason": "不匹配任何支持的时间戳格式"
    }
    parse_timestamp.errors.append(error_info)
    return None

# 添加错误收集列表作为函数的属性
parse_timestamp.errors = []

def timedelta_to_srt_time(td):
    """将 timedelta 转换为 SRT 时间格式 hh:mm:ss,ms"""
    # 处理负时间（如果偏移导致）
    if td.total_seconds() < 0:
        print(f"  警告：计算得到负时间戳 {td}，将重置为 00:00:00,000")
        td = datetime.timedelta(0)

    total_seconds = td.total_seconds()
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = td.microseconds // 1000
    return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02},{milliseconds:03}"

def extract_section(lines, start_marker):
    """从文件行列表中提取特定部分的内容，处理普通和强调标记"""
    section_lines = []
    in_section = False
    markers = ["Transcript:", "Translation:", "Timestamped Transcript:", "Timestamped Translation:"]
    # 创建包含普通和强调版本的标记列表
    all_marker_variants = markers + [f"**{m}**" for m in markers]
    start_marker_variants = [start_marker, f"**{start_marker}**"]

    for line in lines:
        stripped_line = line.strip()

        # 检查是否匹配当前部分的开始标记（普通或强调）
        if any(stripped_line.startswith(variant) for variant in start_marker_variants):
            in_section = True
            continue # 跳过标记行本身

        if in_section:
            # 检查是否遇到任何其他标记（普通或强调）
            is_next_marker = any(
                stripped_line.startswith(m_var)
                for m_var in all_marker_variants
                # 确保不是当前部分的开始标记变体
                if m_var not in start_marker_variants
            )

            # 如果需要更严格地按顺序查找，需要调整逻辑以处理变体
            # (当前简化逻辑：只要不是当前段落的开始标记变体，任何其他标记都视为结束)

            if is_next_marker or not stripped_line: # 如果遇到下一个标记或空行则停止
                in_section = False
                break
            section_lines.append(line) # 保留原始行以便提取文本
    return section_lines

def generate_srt(transcript_dir, audio_dir, output_srt_file, content_choice='transcript', first_chunk_offset=0.0, progress_queue=None):
    """
    合并转录块并生成SRT字幕文件
    
    Args:
        transcript_dir (str): 转录文件目录的路径
        audio_dir (str): 音频文件目录的路径
        output_srt_file (str): 输出SRT文件的路径
        content_choice (str): 选择输出内容类型 ('transcript', 'translation', 'both')
        first_chunk_offset (float): 第一个块的手动时间偏移量（秒）
        progress_queue (Queue, optional): 用于报告进度的队列对象
    
    Returns:
        bool or str: 操作成功返回 True，失败返回 False，需要用户干预返回 'PARSE_ERROR'
    """
    parsing_errors = [] # 用于收集解析错误
    first_chunk_offset_td = datetime.timedelta(seconds=first_chunk_offset)
    
    status_msg = f"开始合并字幕文件... 输出内容: {content_choice}, 输出文件: {output_srt_file}"
    if progress_queue:
        progress_queue.put(status_msg)
    print(status_msg)
    
    if first_chunk_offset != 0.0:
        status_msg = f"将为第一个块的时间戳添加额外偏移: {first_chunk_offset_td}"
        if progress_queue:
            progress_queue.put(status_msg)
        print(status_msg)

    # 1. 获取并排序文件
    try:
        transcript_files = sorted([
            f for f in os.listdir(transcript_dir)
            if f.endswith(".txt") and f.startswith("chunk_")
        ])
        audio_files = sorted([
            f for f in os.listdir(audio_dir)
            if f.startswith("chunk_") and any(f.endswith(ext) for ext in ['.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg'])
        ])
    except FileNotFoundError as e:
        error_msg = f"错误：找不到目录 {e.filename}"
        if progress_queue:
            progress_queue.put(error_msg)
        print(error_msg)
        return False
    except Exception as e:
        error_msg = f"读取目录时出错: {e}"
        if progress_queue:
            progress_queue.put(error_msg)
        print(error_msg)
        return False

    if not transcript_files:
        error_msg = f"错误：在 {transcript_dir} 中未找到 chunk 文件。"
        if progress_queue:
            progress_queue.put(error_msg)
        print(error_msg)
        return False
    
    if not audio_files:
        warning_msg = f"警告：在 {audio_dir} 中未找到音频文件，将无法计算累积偏移。"
        if progress_queue:
            progress_queue.put(warning_msg)
        print(warning_msg)

    # 确保文件一一对应 (如果音频文件存在)
    if audio_files and len(transcript_files) != len(audio_files):
        warning_msg = "警告：转录文件数量与音频文件数量不匹配。将尝试处理匹配的部分。"
        if progress_queue:
            progress_queue.put(warning_msg)
        print(warning_msg)

    # 2. 计算音频时长和累积偏移
    status_msg = "计算音频时长和偏移..."
    if progress_queue:
        progress_queue.put(status_msg)
    print(status_msg)
    
    cumulative_offset = datetime.timedelta(0)
    chunk_offsets = {}  # {transcript_filename: offset_timedelta}
    durations = {}  # {transcript_filename: duration_timedelta}

    processed_audio_count = 0
    # 仅当音频文件存在时才计算偏移
    if audio_files:
        for i, transcript_filename in enumerate(transcript_files):
            base_name = pathlib.Path(transcript_filename).stem
            corresponding_audio = None
            # 在 audio_files 中查找匹配项
            for audio_filename in audio_files:
                if pathlib.Path(audio_filename).stem == base_name:
                    corresponding_audio = audio_filename
                    break

            if corresponding_audio:
                audio_filepath = os.path.join(audio_dir, corresponding_audio)
                status_msg = f"  处理音频: {corresponding_audio}"
                if progress_queue:
                    progress_queue.put(status_msg)
                print(status_msg)
                
                duration_seconds = get_audio_duration(audio_filepath)
                duration_td = datetime.timedelta(seconds=duration_seconds)

                chunk_offsets[transcript_filename] = cumulative_offset
                durations[transcript_filename] = duration_td
                
                status_msg = f"    时长: {duration_td}, 累积偏移: {cumulative_offset}"
                if progress_queue:
                    progress_queue.put(status_msg)
                print(status_msg)

                cumulative_offset += duration_td
                processed_audio_count += 1
            else:
                warning_msg = f"  警告：找不到 {transcript_filename} 对应的音频文件，将无法计算此文件的累积偏移。"
                if progress_queue:
                    progress_queue.put(warning_msg)
                print(warning_msg)
                # a将此文件的偏移设为上一个累积值，后续文件偏移将不准确
                chunk_offsets[transcript_filename] = cumulative_offset

        if processed_audio_count == 0:
            warning_msg = "警告：未能处理任何音频文件以计算时长。后续块的偏移量可能不准确。"
            if progress_queue:
                progress_queue.put(warning_msg)
            print(warning_msg)
        
        status_msg = "音频处理完毕。"
        if progress_queue:
            progress_queue.put(status_msg)
        print(status_msg)
    else:
        status_msg = "未找到音频文件，跳过累积偏移计算。仅处理第一个转录文件的时间戳（如果存在）。"
        if progress_queue:
            progress_queue.put(status_msg)
        print(status_msg)
        # 为所有文件设置偏移为0，但第一个文件仍可应用手动偏移
        for transcript_filename in transcript_files:
            chunk_offsets[transcript_filename] = datetime.timedelta(0)

    # 3. 解析转录文件并合并字幕条目
    status_msg = "解析转录文件并合并字幕..."
    if progress_queue:
        progress_queue.put(status_msg)
    print(status_msg)
    
    all_subs_data = {}  # 使用字典存储，键为全局开始时间，值为 {'transcript': text, 'translation': text}

    for i, filename in enumerate(transcript_files):
        filepath = os.path.join(transcript_dir, filename)
        status_msg = f"  处理转录文件: {filename} (块索引: {i})"
        if progress_queue:
            progress_queue.put(status_msg)
        print(status_msg)

        # 获取当前块的基础偏移（来自音频时长累积）
        offset = chunk_offsets.get(filename, datetime.timedelta(0))  # 如果找不到则默认为0

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            error_msg = f"    错误：无法读取文件 {filepath}: {e}"
            if progress_queue:
                progress_queue.put(error_msg)
            print(error_msg)
            continue

        # 根据 content_choice 提取和处理
        if content_choice in ['transcript', 'both']:
            ts_transcript_lines = extract_section(lines, "Timestamped Transcript:")
            if not ts_transcript_lines:
                warning_msg = f"    警告: 在 {filename} 中未找到 'Timestamped Transcript:' 部分。"
                if progress_queue:
                    progress_queue.put(warning_msg)
                print(warning_msg)
            else:
                for line_num, line in enumerate(ts_transcript_lines):
                    # 修改正则表达式，直接提取方括号内的内容
                    match = re.match(r'\[([^\]]+)\]\s*(.*)', line.strip())
                    if match:
                        ts_str, text = match.groups()
                        local_time = parse_timestamp(ts_str, line_num=line_num + 1, file=filename, section="Timestamped Transcript")
                        if local_time is None:
                            # 收集解析错误信息
                            parsing_errors.append({
                                "file": filename,
                                "line_num": line_num + 1,
                                "section": "Timestamped Transcript",
                                "timestamp_str": ts_str,
                                "content": text[:50] + "..." if len(text) > 50 else text
                            })
                            continue # 跳过此错误行
                        
                        if text:  # 确保有文本内容
                            # 将local_time转为timedelta，然后与offset相加
                            local_timedelta = datetime.timedelta(seconds=local_time)
                            absolute_time = offset + local_timedelta
                            
                            # 如果是第一个块 (i == 0) 并且设置了手动偏移，则加上它
                            if i == 0 and first_chunk_offset_td.total_seconds() != 0.0:
                                absolute_time += first_chunk_offset_td
                            
                            if absolute_time.total_seconds() not in all_subs_data:
                                all_subs_data[absolute_time.total_seconds()] = {'transcript': None, 'translation': None}
                            all_subs_data[absolute_time.total_seconds()]['transcript'] = text.strip()

        if content_choice in ['translation', 'both']:
            ts_translation_lines = extract_section(lines, "Timestamped Translation:")
            if not ts_translation_lines:
                warning_msg = f"    警告: 在 {filename} 中未找到 'Timestamped Translation:' 部分。"
                if progress_queue:
                    progress_queue.put(warning_msg)
                print(warning_msg)
            else:
                for line_num, line in enumerate(ts_translation_lines):
                    # 修改正则表达式，直接提取方括号内的内容
                    match = re.match(r'\[([^\]]+)\]\s*(.*)', line.strip())
                    if match:
                        ts_str, text = match.groups()
                        local_time = parse_timestamp(ts_str, line_num=line_num + 1, file=filename, section="Timestamped Translation")
                        if local_time is None:
                            # 收集解析错误信息
                            parsing_errors.append({
                                "file": filename,
                                "line_num": line_num + 1,
                                "section": "Timestamped Translation",
                                "timestamp_str": ts_str,
                                "content": text[:50] + "..." if len(text) > 50 else text
                            })
                            continue # 跳过此错误行
                        
                        if text:  # 确保有文本内容
                            # 将local_time转为timedelta，然后与offset相加
                            local_timedelta = datetime.timedelta(seconds=local_time)
                            absolute_time = offset + local_timedelta
                            
                            # 如果是第一个块 (i == 0) 并且设置了手动偏移，则加上它
                            if i == 0 and first_chunk_offset_td.total_seconds() != 0.0:
                                absolute_time += first_chunk_offset_td
                            
                            if absolute_time.total_seconds() not in all_subs_data:
                                all_subs_data[absolute_time.total_seconds()] = {'transcript': None, 'translation': None}
                            all_subs_data[absolute_time.total_seconds()]['translation'] = text.strip()

    # 4. 检查是否有解析错误
    if parsing_errors:
        error_msg_header = "\n错误：在合并过程中发现时间戳解析错误。请检查并修正以下文件："
        print(error_msg_header, file=sys.stderr)
        
        if progress_queue:
            # 发送详细错误信息和需要干预的信号
            error_data = {
                'type': 'PARSE_ERROR',
                'errors': parsing_errors,
                'message': error_msg_header
            }
            progress_queue.put(error_data)

        # 打印详细错误到控制台（无论是否有GUI）
        for error in parsing_errors:
            err_detail = (f"  - 文件: {error['file']}, "
                        f"部分: {error['section']}, "
                        f"行号: {error['line_num']}, "
                        f"时间戳: '{error['timestamp_str']}', "
                        f"内容预览: '{error['content']}'")
            print(err_detail, file=sys.stderr)

        final_err_msg = "请修正上述文件中的时间戳格式后再试。"
        print(final_err_msg, file=sys.stderr)
        
        # 返回特殊标志，表示需要用户干预
        return 'PARSE_ERROR'

    # 5. 格式化并排序最终字幕列表 (如果无错误则继续)
    status_msg = "格式化并排序所有字幕条目..."
    if progress_queue:
        progress_queue.put(status_msg)
    print(status_msg)
    
    final_subs = []  # 存储 (start_time_td, combined_text)
    for start_time, texts in sorted(all_subs_data.items()):  # 按时间排序
        t_text = texts.get('transcript')
        tr_text = texts.get('translation')
        combined_text = ""

        if content_choice == 'transcript':
            if t_text:
                combined_text = t_text
        elif content_choice == 'translation':
            if tr_text:
                combined_text = tr_text
        elif content_choice == 'both':
            parts = []
            if t_text:
                parts.append(t_text)
            if tr_text:
                parts.append(tr_text)
            combined_text = "\n".join(parts)  # 转录在上，翻译在下

        if combined_text:  # 只有当有内容时才添加
            # 将时间戳float转换为timedelta对象
            start_time_td = datetime.timedelta(seconds=start_time)
            final_subs.append((start_time_td, combined_text))

    # 6. 生成 SRT 文件
    status_msg = f"生成 SRT 文件: {output_srt_file}"
    if progress_queue:
        progress_queue.put(status_msg)
    print(status_msg)
    
    try:
        with open(output_srt_file, 'w', encoding='utf-8') as f_out:
            for i, sub in enumerate(final_subs):
                start_time, text = sub
                end_time = None

                # 计算结束时间：使用下一个字幕的开始时间
                if i + 1 < len(final_subs):
                    next_start_time, _ = final_subs[i+1]
                    if next_start_time <= start_time:
                        # 如果下一个开始时间不合理，使用默认时长
                        end_time = start_time + datetime.timedelta(seconds=DEFAULT_SUB_DURATION_SECONDS)
                        warning_msg = f"  警告: 字幕 {i+1} 的下一个开始时间 ({timedelta_to_srt_time(next_start_time)}) <= 当前开始时间 ({timedelta_to_srt_time(start_time)})。使用默认时长。"
                        if progress_queue:
                            progress_queue.put(warning_msg)
                        print(warning_msg)
                    else:
                        end_time = next_start_time
                else:
                    # 对于最后一个字幕，使用默认时长
                    end_time = start_time + datetime.timedelta(seconds=DEFAULT_SUB_DURATION_SECONDS)

                # 写入 SRT 条目
                f_out.write(f"{i + 1}\n")
                f_out.write(f"{timedelta_to_srt_time(start_time)} --> {timedelta_to_srt_time(end_time)}\n")
                f_out.write(f"{text}\n\n")  # SRT 需要空行分隔

        status_msg = "SRT 文件生成成功。"
        if progress_queue:
            progress_queue.put(status_msg)
        print(status_msg)
        return True

    except IOError as e:
        error_msg = f"错误：无法写入 SRT 文件 {output_srt_file}: {e}"
        if progress_queue:
            progress_queue.put(error_msg)
        print(error_msg)
        return False
    except Exception as e:
        error_msg = f"生成 SRT 文件时发生意外错误: {e}"
        if progress_queue:
            progress_queue.put(error_msg)
        print(error_msg)
        return False

# --- 主逻辑 ---
if __name__ == "__main__":
    # --- 添加命令行参数解析 ---
    parser = argparse.ArgumentParser(description="合并转录块并生成SRT字幕文件。")
    parser.add_argument(
        '--content',
        type=str,
        choices=['transcript', 'translation', 'both'],
        default='transcript', # 默认只输出转录
        help="选择输出内容: 'transcript' (仅转录), 'translation' (仅翻译), 'both' (两者皆有，转录在上，翻译在下)"
    )
    parser.add_argument(
        '--output',
        type=str,
        default=OUTPUT_SRT_FILE,
        help=f"指定输出SRT文件的名称 (默认: {OUTPUT_SRT_FILE})"
    )
    # --- 新增：第一个块的偏移量参数 ---
    parser.add_argument(
        '--first-chunk-offset',
        type=float,
        default=0.0,
        help="手动为第一个音频块的时间戳添加偏移量（秒），例如 1.5"
    )
    # ---------------------------------
    parser.add_argument(
        '--transcript-dir',
        type=str,
        default=TRANSCRIPT_DIR,
        help=f"指定转录文件目录 (默认: {TRANSCRIPT_DIR})"
    )
    parser.add_argument(
        '--audio-dir',
        type=str,
        default=AUDIO_DIR,
        help=f"指定音频文件目录 (默认: {AUDIO_DIR})"
    )
    # ---------------------------------
    args = parser.parse_args()
    
    # 调用主函数
    generate_srt(
        transcript_dir=args.transcript_dir,
        audio_dir=args.audio_dir,
        output_srt_file=args.output,
        content_choice=args.content,
        first_chunk_offset=args.first_chunk_offset
    )