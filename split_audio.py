import os
import numpy as np
import librosa
import soundfile as sf
from pydub import AudioSegment
from pydub.silence import detect_silence
import argparse
import pathlib
import time

# --- 配置 ---
# 输入/输出目录
INPUT_AUDIO = "input.mp3"  # 默认输入文件 
OUTPUT_DIR = "temp_audio_chunks_new_api"  # 默认输出目录
# 切分参数
MAX_CHUNK_LENGTH = 5 * 60 * 1000  # 最大切片长度（毫秒，默认5分钟）
MIN_CHUNK_LENGTH = 30 * 1000  # 最小切片长度（毫秒，默认30秒）
MIN_SILENCE_LENGTH = 500  # 最小静音长度（毫秒，默认500毫秒）
SILENCE_THRESH = -40  # 静音阈值（dB，默认-40）
# -------------

def detect_silence_points(audio, min_silence_len=MIN_SILENCE_LENGTH, silence_thresh=SILENCE_THRESH):
    """检测音频中的静音点，返回静音段的开始和结束时间（毫秒）"""
    print(f"检测静音点 (阈值: {silence_thresh}dB, 最小静音长度: {min_silence_len}ms)...")
    silence_points = detect_silence(audio, min_silence_len=min_silence_len, silence_thresh=silence_thresh)
    return silence_points

def find_optimal_split_points(audio_length, silence_points, max_chunk_length=MAX_CHUNK_LENGTH, min_chunk_length=MIN_CHUNK_LENGTH):
    """
    根据静音点和最大/最小切片长度要求找出最佳切分点
    返回最佳切分点列表（毫秒）
    """
    split_points = []
    last_split = 0
    
    # 遍历每个静音段
    for start, end in silence_points:
        # 取静音段的中点作为潜在切分点
        potential_split = (start + end) // 2
        chunk_length = potential_split - last_split
        
        # 如果当前切片长度超过最大长度，在这个静音段中间切分
        if chunk_length >= max_chunk_length:
            split_points.append(potential_split)
            last_split = potential_split
            continue
    
    # 如果最后一个切分点到音频结尾的距离超过最大长度，需要强制切分
    remaining_length = audio_length - last_split
    if remaining_length > max_chunk_length:
        # 计算需要多少个额外切分点
        num_additional_splits = remaining_length // max_chunk_length
        for i in range(1, num_additional_splits + 1):
            # 在没有静音点的情况下，均匀切分
            split_points.append(last_split + i * max_chunk_length)
    
    # 添加音频结尾作为最后一个切分点
    split_points.append(audio_length)
    
    print(f"计算得到 {len(split_points)} 个切分点")
    return split_points

def split_audio(input_file, output_dir, max_chunk_length=MAX_CHUNK_LENGTH, 
                min_silence_len=MIN_SILENCE_LENGTH, silence_thresh=SILENCE_THRESH):
    """
    将音频文件切分成较小的块，尽量在静音处切分
    
    Args:
        input_file (str): 输入音频文件的路径
        output_dir (str): 输出目录，保存切分后的音频片段
        max_chunk_length (int): 最大切片长度（毫秒）
        min_silence_len (int): 最小静音长度（毫秒）
        silence_thresh (int): 静音阈值（dB）
        
    Returns:
        list: 生成的音频片段文件路径列表
    """
    # 确保输出目录存在
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    print(f"加载音频文件: {input_file}")
    audio = AudioSegment.from_file(input_file)
    total_length = len(audio)
    print(f"音频总长度: {total_length/1000:.2f} 秒 ({total_length/1000/60:.2f} 分钟)")
    
    # 检测静音点
    silence_points = detect_silence_points(audio, min_silence_len, silence_thresh)
    print(f"检测到 {len(silence_points)} 个静音段")
    
    # 找出最佳切分点
    split_points = find_optimal_split_points(total_length, silence_points, max_chunk_length)
    
    # 执行切分
    chunks = []
    start_time = 0
    chunk_files = []
    
    for i, end_time in enumerate(split_points):
        # 提取当前片段
        chunk = audio[start_time:end_time]
        chunk_duration = len(chunk) / 1000  # 秒
        
        # 创建带有前导零的文件名
        chunk_filename = os.path.join(output_dir, f"chunk_{i+1:03d}.mp3")
        chunk_files.append(chunk_filename)
        
        print(f"导出片段 {i+1}/{len(split_points)}: {start_time/1000:.2f}s - {end_time/1000:.2f}s ({chunk_duration:.2f}s) -> {chunk_filename}")
        chunk.export(chunk_filename, format="mp3")
        
        # 更新下一个片段的起始时间
        start_time = end_time
    
    print(f"切分完成! 共生成 {len(chunk_files)} 个音频片段，保存在 {output_dir} 目录")
    return chunk_files

def main():
    parser = argparse.ArgumentParser(description="将长音频文件切分成较小的片段，尝试在静音处切分")
    parser.add_argument("-i", "--input", default=INPUT_AUDIO, help=f"输入音频文件路径 (默认: {INPUT_AUDIO})")
    parser.add_argument("-o", "--output-dir", default=OUTPUT_DIR, help=f"输出目录 (默认: {OUTPUT_DIR})")
    parser.add_argument("-m", "--max-length", type=int, default=MAX_CHUNK_LENGTH//1000, 
                        help=f"最大切片长度，单位为秒 (默认: {MAX_CHUNK_LENGTH//1000}秒)")
    parser.add_argument("-s", "--silence-length", type=int, default=MIN_SILENCE_LENGTH, 
                        help=f"最小静音长度，单位为毫秒 (默认: {MIN_SILENCE_LENGTH}毫秒)")
    parser.add_argument("-t", "--silence-threshold", type=int, default=SILENCE_THRESH, 
                        help=f"静音阈值，单位为dB (默认: {SILENCE_THRESH}dB)")
    
    args = parser.parse_args()
    
    # 转换参数
    max_chunk_length = args.max_length * 1000  # 秒转毫秒
    
    # 执行切分
    start_time = time.time()
    split_audio(args.input, args.output_dir, max_chunk_length, args.silence_length, args.silence_threshold)
    end_time = time.time()
    
    print(f"处理完成，总耗时: {end_time - start_time:.2f} 秒")
    print(f"现在你可以运行 transcript.py 来处理这些音频片段")

if __name__ == "__main__":
    main()