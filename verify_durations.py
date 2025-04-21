import os
import subprocess
import argparse
import sys
import time

# --- 从 split_audio.py 复制或导入 get_audio_duration_ffmpeg ---
# (这里直接复制过来，确保脚本独立性)
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
             print(f"  错误：ffprobe 获取时长失败 for {os.path.basename(input_file)}. 返回码: {process.returncode}")
             # print(f"  ffprobe 输出: {stderr_output}") # 可选：打印详细错误
             return None
        # 尝试去除可能的空行或无效输出
        duration_str = stdout_output.strip()
        if not duration_str:
             print(f"  错误：ffprobe for {os.path.basename(input_file)} 返回了空输出。")
             return None
        return float(duration_str)
    except FileNotFoundError:
        print("错误: ffprobe 命令未找到。请确保 ffmpeg (包含 ffprobe) 已安装并添加到系统 PATH。")
        return None # 返回 None 表示失败
    except subprocess.TimeoutExpired:
        print(f"错误：ffprobe 获取时长超时: {os.path.basename(input_file)}")
        if process:
            process.kill()
        return None
    except ValueError:
         print(f"错误：无法将 ffprobe 的输出 '{stdout_output.strip()}' 转换为浮点数 for {os.path.basename(input_file)}。")
         return None
    except Exception as e:
        print(f"错误：使用 ffprobe 获取 {os.path.basename(input_file)} 时长时发生未知错误: {e}")
        return None
# -------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="比较原始音频文件时长与所有切片时长之和。")
    parser.add_argument("--original-file", required=True, help="原始音频文件路径 (例如 rust.mp3)")
    parser.add_argument("--chunk-dir", required=True, help="包含音频切片的目录 (例如 temp_audio_chunks_new_api)")
    parser.add_argument("--chunk-prefix", default="chunk_", help="切片文件名的前缀 (默认: chunk_)")
    parser.add_argument("--chunk-ext", default=".mp3", help="切片文件的扩展名 (默认: .mp3)")

    args = parser.parse_args()

    # 1. 获取原始文件时长
    print(f"获取原始文件时长: {args.original_file}")
    original_duration = get_audio_duration_ffmpeg(args.original_file)
    if original_duration is None:
        print("无法获取原始文件时长，脚本终止。")
        sys.exit(1)
    print(f"原始文件时长: {original_duration:.6f} 秒")

    # 2. 获取并累加所有切片文件时长
    print(f"\n扫描切片目录: {args.chunk_dir}")
    total_chunk_duration = 0.0
    chunk_count = 0
    failed_chunks = 0

    try:
        files_in_dir = os.listdir(args.chunk_dir)
    except FileNotFoundError:
        print(f"错误：找不到切片目录 '{args.chunk_dir}'。")
        sys.exit(1)

    # 过滤并排序切片文件
    chunk_files = sorted([
        f for f in files_in_dir
        if f.startswith(args.chunk_prefix) and f.endswith(args.chunk_ext)
    ])

    if not chunk_files:
        print("错误：在指定目录中未找到匹配的切片文件。")
        sys.exit(1)

    print(f"找到 {len(chunk_files)} 个切片文件，开始计算总时长...")

    start_time = time.time()
    for i, filename in enumerate(chunk_files):
        filepath = os.path.join(args.chunk_dir, filename)
        duration = get_audio_duration_ffmpeg(filepath)
        if duration is not None and duration > 0: # 确保时长有效
            total_chunk_duration += duration
            chunk_count += 1
        else:
            print(f"  警告：无法获取或获取到无效时长 for chunk: {filename}。已跳过。")
            failed_chunks += 1

        # 打印进度
        if (i + 1) % 50 == 0 or (i + 1) == len(chunk_files):
             elapsed = time.time() - start_time
             print(f"  已处理 {i + 1}/{len(chunk_files)} 个切片... (耗时: {elapsed:.2f}s)")


    print("\n--- 结果 ---")
    print(f"原始文件 ({os.path.basename(args.original_file)}) 时长: {original_duration:.6f} 秒")
    print(f"成功处理的切片数量: {chunk_count}")
    if failed_chunks > 0:
        print(f"获取时长失败的切片数量: {failed_chunks}")
    print(f"所有成功处理的切片时长总和: {total_chunk_duration:.6f} 秒")

    difference = total_chunk_duration - original_duration
    print(f"\n差值 (总切片时长 - 原始时长): {difference:+.6f} 秒")

    if abs(difference) < 0.1: # 允许非常小的误差 (例如 100ms)
        print("结论：总切片时长与原始时长基本一致。")
    elif difference > 0:
        print("警告：总切片时长显著大于原始时长，可能存在重叠或计算错误。")
    else:
        print("警告：总切片时长显著小于原始时长，这可能导致累积计时误差（字幕超前）。")

if __name__ == "__main__":
    # 检查 ffprobe 是否可用
    try:
        subprocess.run(['ffprobe', '-version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print("错误：ffprobe 未找到或无法执行。请确保 ffmpeg (包含 ffprobe) 已正确安装并添加到系统 PATH。")
        sys.exit(1)
    main()