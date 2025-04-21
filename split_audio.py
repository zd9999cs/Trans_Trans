import os
import subprocess
import re
import pathlib
import math
import time
import argparse # Keep argparse for potential standalone use, though process_audio.py is the main entry point
import sys

# --- 配置 (保持与原文件一致，但注意单位转换) ---
OUTPUT_DIR = "temp_audio_chunks_new_api"  # 默认输出目录
MAX_CHUNK_LENGTH_SEC = 5 * 60  # 最大切片长度（秒，默认5分钟）
MIN_SILENCE_LENGTH_SEC = 0.5 # 最小静音长度（秒，默认0.5秒）
SILENCE_THRESH_DB = -40  # 静音阈值（dB，默认-40）
# -------------

def get_audio_duration_ffmpeg(input_file):
    """使用 ffprobe 获取音频时长（秒）"""
    command = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        input_file
    ]
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        stdout_output, stderr_output = process.communicate(timeout=60) # Add timeout
        if process.returncode != 0:
             print(f"错误：ffprobe 获取时长失败。命令: {' '.join(command)}")
             print(f"ffprobe 输出: {stderr_output}")
             return None
        return float(stdout_output.strip())
    except FileNotFoundError:
        print("错误: ffprobe 命令未找到。请确保 ffmpeg (包含 ffprobe) 已安装并添加到系统 PATH。")
        return None
    except subprocess.TimeoutExpired:
        print(f"错误：ffprobe 获取时长超时: {input_file}")
        if process:
            process.kill()
        return None
    except Exception as e:
        print(f"错误：使用 ffprobe 获取 {input_file} 时长时发生未知错误: {e}")
        return None

def detect_silence_with_ffmpeg(input_file, min_silence_duration_sec, noise_tolerance_db):
    """使用 ffmpeg silencedetect 检测静音（单位：秒）"""
    print(f"使用 ffmpeg 检测静音 (阈值: {noise_tolerance_db}dB, 最小静音长度: {min_silence_duration_sec}s)...")
    command = [
        'ffmpeg',
        '-i', input_file,
        '-af', f'silencedetect=noise={noise_tolerance_db}dB:d={min_silence_duration_sec}',
        '-f', 'null', '-' # 不输出文件，只分析
    ]
    silence_points_sec = []
    try:
        process = subprocess.Popen(command, stderr=subprocess.PIPE, universal_newlines=True)
        stderr_output = ""
        # Read stderr line by line to avoid large memory usage for long outputs
        for line in process.stderr:
             stderr_output += line
             # Parse start and end times as they appear
             start_match = re.search(r'silence_start: (\d+\.?\d*)', line)
             if start_match:
                 # Store start time temporarily, waiting for end time
                 current_start = float(start_match.group(1))
             end_match = re.search(r'silence_end: (\d+\.?\d*)', line)
             if end_match and 'current_start' in locals():
                 current_end = float(end_match.group(1))
                 # Ensure start is before end, sometimes ffmpeg might output them close together
                 if current_end > current_start:
                     silence_points_sec.append((current_start, current_end))
                 del current_start # Reset for the next pair

        process.wait(timeout=300) # Wait for ffmpeg to finish, with timeout

        if process.returncode != 0:
             print(f"警告：ffmpeg silencedetect 执行可能出错 (返回码: {process.returncode})。命令: {' '.join(command)}")
             # Continue with potentially partial results

    except FileNotFoundError:
        print("错误: ffmpeg 命令未找到。请确保 ffmpeg 已安装并添加到系统 PATH。")
        return [] # Return empty list on critical error
    except subprocess.TimeoutExpired:
        print(f"错误：ffmpeg silencedetect 超时: {input_file}")
        if process:
            process.kill()
        # Return potentially partial results found so far
    except Exception as e:
        print(f"错误：使用 ffmpeg silencedetect 时发生未知错误: {e}")
        return [] # Return empty list on critical error

    print(f"ffmpeg 检测到 {len(silence_points_sec)} 个静音段")
    return silence_points_sec # 返回秒为单位的列表 [(start1, end1), (start2, end2), ...]

def find_optimal_split_points_sec(audio_length_sec, silence_points_sec, max_chunk_length_sec):
    """根据静音点计算切分点（单位：秒）"""
    split_points_sec = []
    last_split_sec = 0.0

    # Add start point
    # split_points_sec.append(0.0) # Start is implicitly 0

    current_chunk_start = 0.0
    last_silence_midpoint = -1.0 # Track the last suitable silence midpoint

    # Iterate through silence periods to find good split points
    for start_sec, end_sec in silence_points_sec:
        silence_midpoint = (start_sec + end_sec) / 2.0
        potential_chunk_len = silence_midpoint - current_chunk_start

        # If adding this silence midpoint doesn't exceed max length, consider it
        if potential_chunk_len <= max_chunk_length_sec:
            last_silence_midpoint = silence_midpoint
        else:
            # Current chunk is too long if we go to this silence.
            # Did we have a previous suitable silence point?
            if last_silence_midpoint > current_chunk_start:
                split_points_sec.append(last_silence_midpoint)
                current_chunk_start = last_silence_midpoint
                # Re-evaluate the current silence period from the new start
                if (silence_midpoint - current_chunk_start) <= max_chunk_length_sec:
                     last_silence_midpoint = silence_midpoint
                else: # Even starting from the last split, this silence is too far
                     # Force a split before this silence if the segment is too long
                     if (start_sec - current_chunk_start) > max_chunk_length_sec:
                          # Force split at max length if no silence available
                          forced_split = current_chunk_start + max_chunk_length_sec
                          split_points_sec.append(forced_split)
                          current_chunk_start = forced_split
                          last_silence_midpoint = -1 # Reset last silence point
                     else:
                          # Split right before the current silence starts
                          split_points_sec.append(start_sec)
                          current_chunk_start = start_sec
                          last_silence_midpoint = silence_midpoint # This silence is now the potential next split

            else:
                # No suitable silence point found, and the chunk is too long.
                # Force split at max_chunk_length_sec.
                forced_split = current_chunk_start + max_chunk_length_sec
                split_points_sec.append(forced_split)
                current_chunk_start = forced_split
                # Re-evaluate the current silence period from the new start
                if (silence_midpoint - current_chunk_start) <= max_chunk_length_sec:
                     last_silence_midpoint = silence_midpoint
                else:
                     last_silence_midpoint = -1 # Reset

    # After checking all silences, handle the remaining audio segment
    remaining_length = audio_length_sec - current_chunk_start
    if remaining_length > 0:
        if remaining_length > max_chunk_length_sec:
             # If the remainder is too long, split it further
             num_additional_splits = math.ceil(remaining_length / max_chunk_length_sec)
             split_interval = remaining_length / num_additional_splits
             for i in range(1, num_additional_splits):
                 split_points_sec.append(current_chunk_start + i * split_interval)

    # Add the final end point
    split_points_sec.append(audio_length_sec)

    # Sort and remove duplicates, ensure points are within bounds
    split_points_sec = sorted(list(set(p for p in split_points_sec if 0 < p <= audio_length_sec)))

    print(f"计算得到 {len(split_points_sec)} 个切分点 (秒)")
    return split_points_sec


# --- Main Function (Replaces the old pydub-based split_audio) ---
def split_audio(input_file, output_dir, max_chunk_length=MAX_CHUNK_LENGTH_SEC * 1000,
                min_silence_len=int(MIN_SILENCE_LENGTH_SEC * 1000), silence_thresh=SILENCE_THRESH_DB):
    """
    使用 ffmpeg 进行内存高效的音频切分。
    接口保持与旧函数兼容 (接受毫秒单位的长度参数)。

    Args:
        input_file (str): 输入音频文件的路径
        output_dir (str): 输出目录，保存切分后的音频片段
        max_chunk_length (int): 最大切片长度（毫秒）
        min_silence_len (int): 最小静音长度（毫秒）
        silence_thresh (int): 静音阈值（dB）

    Returns:
        list: 生成的音频片段文件路径列表
    """
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)

    # --- 参数单位转换 ---
    max_chunk_length_sec = max_chunk_length / 1000.0
    min_silence_len_sec = min_silence_len / 1000.0
    silence_thresh_db = silence_thresh # dB单位不变
    # --------------------

    print(f"加载音频信息: {input_file}")
    total_length_sec = get_audio_duration_ffmpeg(input_file)
    if total_length_sec is None:
        print(f"错误：无法获取音频时长，无法继续切分 {input_file}")
        return [] # 返回空列表表示失败
    print(f"音频总长度: {total_length_sec:.2f} 秒 ({total_length_sec/60:.2f} 分钟)")

    # 检测静音点 (使用ffmpeg)
    silence_points_sec = detect_silence_with_ffmpeg(input_file, min_silence_len_sec, silence_thresh_db)

    # 计算切分点 (使用ffmpeg检测到的静音点)
    split_points_sec = find_optimal_split_points_sec(total_length_sec, silence_points_sec, max_chunk_length_sec)

    # 执行切分 (使用ffmpeg)
    chunk_files = []
    start_time_sec = 0.0
    for i, end_time_sec in enumerate(split_points_sec):
        # 确保切片有有效长度
        if end_time_sec <= start_time_sec + 0.01: # 增加一个小的阈值避免零长度或极短片段
            print(f"  跳过无效切分点: {start_time_sec:.2f}s -> {end_time_sec:.2f}s")
            continue

        chunk_filename = os.path.join(output_dir, f"chunk_{i+1:03d}.mp3")
        duration_sec = end_time_sec - start_time_sec

        print(f"导出片段 {i+1}/{len(split_points_sec)}: {start_time_sec:.2f}s - {end_time_sec:.2f}s ({duration_sec:.2f}s) -> {chunk_filename}")

        # 使用 ffmpeg 提取片段
        command_split = [
            'ffmpeg',
            '-i', input_file,
            '-ss', str(start_time_sec), # 起始时间
            '-to', str(end_time_sec),   # 结束时间 (使用 -to 比 -t 更精确)
            '-c', 'copy',             # 直接复制流，速度快 (如果输入是MP3)
            # '-acodec', 'libmp3lame', '-ab', '192k', # 如果需要重新编码，取消注释并调整参数
            '-map_metadata', '-1',    # 去除元数据，避免潜在问题
            '-loglevel', 'error',     # 只显示错误信息
            '-y',                     # 覆盖已存在的文件
            chunk_filename
        ]
        try:
            # 运行ffmpeg命令
            process = subprocess.run(command_split, check=True, capture_output=True, text=True, timeout=300) # Add timeout
            chunk_files.append(chunk_filename)
        except FileNotFoundError:
             print("错误: ffmpeg 命令未找到。请确保 ffmpeg 已安装并添加到系统 PATH。")
             return [] # 关键错误，停止处理
        except subprocess.CalledProcessError as e:
            print(f"  错误：ffmpeg 导出片段 {chunk_filename} 失败。")
            print(f"  命令: {' '.join(e.cmd)}")
            print(f"  返回码: {e.returncode}")
            print(f"  错误输出: {e.stderr}")
            # 可以选择继续处理其他片段或停止
            # continue
            # return [] # 如果一个失败就停止
        except subprocess.TimeoutExpired:
             print(f"错误：ffmpeg 导出片段 {chunk_filename} 超时。")
             # 可以选择继续或停止
        except Exception as e:
             print(f"  导出片段 {chunk_filename} 时发生未知错误: {e}")
             # 可以选择继续或停止

        start_time_sec = end_time_sec # 更新下一个片段的起始时间

    if not chunk_files:
         print("错误：未能成功导出任何音频片段。")
         return []

    print(f"切分完成! 共生成 {len(chunk_files)} 个音频片段，保存在 {output_dir} 目录")
    return chunk_files

# --- Main function for standalone execution (optional) ---
def main():
    # 使用与 process_audio.py 兼容的参数名称和单位
    parser = argparse.ArgumentParser(description="使用 ffmpeg 将长音频文件切分成较小的片段")
    parser.add_argument("-i", "--input", required=True, help="输入音频文件路径")
    parser.add_argument("-o", "--output-dir", default=OUTPUT_DIR, help=f"输出目录 (默认: {OUTPUT_DIR})")
    parser.add_argument("-m", "--max-length", type=int, default=MAX_CHUNK_LENGTH_SEC,
                        help=f"最大切片长度，单位为秒 (默认: {MAX_CHUNK_LENGTH_SEC}秒)")
    parser.add_argument("-s", "--silence-length", type=int, default=int(MIN_SILENCE_LENGTH_SEC * 1000),
                        help=f"最小静音长度，单位为毫秒 (默认: {int(MIN_SILENCE_LENGTH_SEC * 1000)}毫秒)")
    parser.add_argument("-t", "--silence-threshold", type=int, default=SILENCE_THRESH_DB,
                        help=f"静音阈值，单位为dB (默认: {SILENCE_THRESH_DB}dB)")

    args = parser.parse_args()

    start_time_wall = time.time()
    # 调用主函数，注意单位转换
    split_audio(args.input, args.output_dir,
                max_chunk_length=args.max_length * 1000, # 秒转毫秒
                min_silence_len=args.silence_length,     # 毫秒
                silence_thresh=args.silence_threshold)   # dB
    end_time_wall = time.time()

    print(f"处理完成，总耗时: {end_time_wall - start_time_wall:.2f} 秒")

if __name__ == "__main__":
    # 确保 ffmpeg 和 ffprobe 可用
    try:
        subprocess.run(['ffmpeg', '-version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(['ffprobe', '-version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print("错误：ffmpeg 或 ffprobe 未找到或无法执行。请确保它们已正确安装并添加到系统 PATH。")
        sys.exit(1)

    main()