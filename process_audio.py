#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import pathlib
import argparse
import time
import queue
import shutil
import subprocess
from datetime import datetime

# 导入我们修改过的三个脚本中的函数
try:
    from split_audio import split_audio
    from transcript import run_transcription
    from combine_transcripts import generate_srt
except ImportError as e:
    print(f"错误：无法导入脚本模块。确保split_audio.py, transcript.py和combine_transcripts.py在同一目录下。详细错误: {e}")
    sys.exit(1)

def is_video_file(filepath):
    """
    检查文件是否为视频文件
    
    Args:
        filepath (str): 文件路径
    
    Returns:
        bool: 如果是视频文件则返回True，否则返回False
    """
    video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v']
    _, ext = os.path.splitext(filepath)
    return ext.lower() in video_extensions

def convert_video_to_mp3(video_path, output_dir=None, progress_queue=None):
    """
    将视频文件转换为MP3音频文件
    
    Args:
        video_path (str): 输入视频文件路径
        output_dir (str, optional): 输出目录，默认为视频文件所在目录
        progress_queue (Queue, optional): 用于报告进度的队列对象
    
    Returns:
        str: 生成的MP3文件路径，如果转换失败则返回None
    """
    if not os.path.isfile(video_path):
        error_msg = f"错误: 输入视频文件 '{video_path}' 不存在。"
        if progress_queue:
            progress_queue.put(error_msg)
        print(error_msg)
        return None
    
    video_path_obj = pathlib.Path(video_path)
    
    # 如果没有指定输出目录，则使用与视频相同的目录
    if not output_dir:
        output_dir = video_path_obj.parent
    else:
        # 确保输出目录存在
        pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # 设置输出MP3文件路径
    mp3_filename = f"{video_path_obj.stem}.mp3"
    mp3_path = os.path.join(output_dir, mp3_filename)
    
    status_msg = f"开始将视频转换为MP3: {video_path} -> {mp3_path}"
    if progress_queue:
        progress_queue.put(status_msg)
    print(status_msg)
    
    try:
        # 使用ffmpeg将视频转换为MP3
        cmd = ["ffmpeg", "-i", video_path, "-q:a", "0", "-map", "a", "-vn", mp3_path, "-y"]
        status_msg = f"执行命令: {' '.join(cmd)}"
        if progress_queue:
            progress_queue.put(status_msg)
        print(status_msg)
        
        # 执行ffmpeg命令
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        stdout, stderr = process.communicate()
        
        # 检查转换是否成功
        if process.returncode != 0:
            error_msg = f"视频转换失败。FFmpeg错误: {stderr}"
            if progress_queue:
                progress_queue.put(error_msg)
            print(error_msg)
            return None
        
        success_msg = f"视频成功转换为MP3: {mp3_path}"
        if progress_queue:
            progress_queue.put(success_msg)
        print(success_msg)
        
        return mp3_path
    
    except Exception as e:
        error_msg = f"视频转换过程中发生错误: {str(e)}"
        if progress_queue:
            progress_queue.put(error_msg)
        print(error_msg)
        return None

def run_pipeline(params, progress_queue=None, control_queue=None):
    """
    运行完整的处理流程：(视频转MP3) -> 切分音频 -> 转录音频 -> 合并转录生成SRT
    
    Args:
        params (dict): 包含所有处理参数的字典
        progress_queue (Queue, optional): 用于报告进度的队列对象
        control_queue (Queue, optional): 用于从GUI接收控制信号的队列对象，用于处理用户干预情况

    Returns:
        bool: 操作是否成功
    """
    # 从参数字典中提取关键参数
    input_file = params.get('input_audio')  # 输入文件（音频或视频）
    output_dir = params.get('output_dir')
    api_key = params.get('api_key')
    content = params.get('content', 'both')
    first_chunk_offset = params.get('first_chunk_offset', 0.0)
    max_length = params.get('max_length', 300)  # 默认5分钟
    silence_length = params.get('silence_length', 500)  # 默认500毫秒
    silence_threshold = params.get('silence_threshold', -40)  # 默认-40dB
    cleanup = params.get('cleanup', False)
    target_language = params.get('target_language', 'Simplified Chinese')  # 默认简体中文
    
    # 验证必要参数
    if not input_file or not os.path.isfile(input_file):
        error_msg = f"错误：输入文件'{input_file}'不存在或不是有效文件。"
        if progress_queue:
            progress_queue.put(error_msg)
        print(error_msg)
        return False
    
    if not api_key:
        error_msg = "错误：未提供API密钥。"
        if progress_queue:
            progress_queue.put(error_msg)
        print(error_msg)
        return False
    
    # 设置输出目录
    input_path = pathlib.Path(input_file)
    if not output_dir:
        # 如果未指定输出目录，则使用输入文件名创建目录
        output_dir = os.path.join(input_path.parent, input_path.stem)
    
    # 创建输出主目录
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # 判断输入是否为视频文件
    input_audio = input_file  # 默认使用原始输入文件
    
    # 开始计时
    total_start_time = time.time()
    
    # 如果是视频文件，先转换为MP3
    if is_video_file(input_file):
        start_msg = f"\n--- 预处理: 视频转MP3 ---"
        if progress_queue:
            progress_queue.put(start_msg)
        print(start_msg)
        
        convert_start = time.time()
        mp3_path = convert_video_to_mp3(input_file, output_dir, progress_queue)
        
        if not mp3_path or not os.path.isfile(mp3_path):
            error_msg = "错误：视频转MP3失败，无法继续处理。"
            if progress_queue:
                progress_queue.put(error_msg)
            print(error_msg)
            return False
        
        # 更新输入音频文件为转换后的MP3
        input_audio = mp3_path
        convert_end = time.time()
        
        success_msg = f"视频转MP3完成。耗时: {convert_end - convert_start:.2f}秒"
        if progress_queue:
            progress_queue.put(success_msg)
        print(success_msg)
    
    # 设置子目录
    audio_chunk_dir = os.path.join(output_dir, "audio_chunks")
    intermediate_dir = os.path.join(output_dir, "intermediate_transcripts")
    srt_file = os.path.join(output_dir, f"{input_path.stem}.srt")
    
    # 1. 切分音频
    start_msg = f"\n--- 步骤 1: 切分音频 (最大长度: {max_length}秒, 静音长度: {silence_length}毫秒, 静音阈值: {silence_threshold}dB) ---"
    if progress_queue:
        progress_queue.put(start_msg)
    print(start_msg)
    
    step1_start = time.time()
    try:
        # 调用split_audio函数，注意单位转换（秒到毫秒）
        chunk_files = split_audio(
            input_audio, 
            audio_chunk_dir, 
            max_chunk_length=max_length * 1000,  # 转为毫秒
            min_silence_len=silence_length,
            silence_thresh=silence_threshold
        )
        
        if not chunk_files or len(chunk_files) == 0:
            error_msg = "错误：音频切分失败，未生成音频片段。"
            if progress_queue:
                progress_queue.put(error_msg)
            print(error_msg)
            return False
            
        step1_end = time.time()
        success_msg = f"音频切分完成，生成了 {len(chunk_files)} 个音频片段。耗时: {step1_end - step1_start:.2f}秒"
        if progress_queue:
            progress_queue.put(success_msg)
        print(success_msg)
    except Exception as e:
        error_msg = f"音频切分过程中发生错误: {e}"
        if progress_queue:
            progress_queue.put(error_msg)
        print(error_msg)
        return False
    
    # 2. 转录音频
    start_msg = f"\n--- 步骤 2: 转录音频片段 (目标语言: {target_language}) ---"
    if progress_queue:
        progress_queue.put(start_msg)
    print(start_msg)
    
    step2_start = time.time()
    try:
        # 使用目标语言生成系统指令
        from transcript import get_system_instruction
        custom_system_instruction = get_system_instruction(target_language)
        
        # 调用transcript.py中的run_transcription函数，传入自定义的system_instruction
        transcription_success = run_transcription(
            api_key=api_key,
            audio_dir=audio_chunk_dir,
            intermediate_dir=intermediate_dir,
            system_instruction=custom_system_instruction,
            progress_queue=progress_queue
        )
        
        if not transcription_success:
            error_msg = "错误：音频转录失败。"
            if progress_queue:
                progress_queue.put(error_msg)
            print(error_msg)
            return False
            
        step2_end = time.time()
        success_msg = f"音频转录完成。耗时: {step2_end - step2_start:.2f}秒"
        if progress_queue:
            progress_queue.put(success_msg)
        print(success_msg)
    except Exception as e:
        error_msg = f"音频转录过程中发生错误: {e}"
        if progress_queue:
            progress_queue.put(error_msg)
        print(error_msg)
        return False
    
    # 3. 合并转录生成SRT
    start_msg = f"\n--- 步骤 3: 合并转录生成SRT字幕 (内容类型: {content}, 第一块偏移: {first_chunk_offset}秒) ---"
    if progress_queue:
        progress_queue.put(start_msg)
    print(start_msg)
    
    step3_start = time.time()
    
    # 添加合并重试循环
    while True:
        try:
            # 调用combine_transcripts.py中的generate_srt函数
            srt_result = generate_srt(
                transcript_dir=intermediate_dir,
                audio_dir=audio_chunk_dir,
                output_srt_file=srt_file,
                content_choice=content,
                first_chunk_offset=first_chunk_offset,
                progress_queue=progress_queue
            )
            
            # 处理不同的返回值
            if srt_result == True:  # 成功完成
                step3_end = time.time()
                success_msg = f"SRT字幕生成完成。耗时: {step3_end - step3_start:.2f}秒"
                if progress_queue:
                    progress_queue.put(success_msg)
                print(success_msg)
                break  # 退出重试循环
            
            elif srt_result == 'PARSE_ERROR':  # 需要用户干预
                warning_msg = "检测到时间戳解析错误，需要用户修正后重试。"
                if progress_queue:
                    progress_queue.put(warning_msg)
                print(warning_msg)
                
                if control_queue:  # 如果有控制队列，等待用户通知
                    wait_msg = "等待用户修改文件。修改完成后，请在界面上点击'重试合并'按钮。"
                    if progress_queue:
                        progress_queue.put(wait_msg)
                    print(wait_msg)
                    
                    try:
                        # 阻塞等待用户操作
                        retry_signal = control_queue.get(block=True)
                        
                        # 处理不同的控制信号
                        if retry_signal == 'RETRY_COMBINE':
                            retry_msg = "收到重试信号，继续合并转录..."
                            if progress_queue:
                                progress_queue.put(retry_msg)
                            print(retry_msg)
                            # 继续循环，重新尝试 generate_srt
                            continue
                        elif retry_signal == 'STOP_PROCESSING':
                            stop_msg = "收到停止信号，终止处理。"
                            if progress_queue:
                                progress_queue.put(stop_msg)
                            print(stop_msg)
                            return False
                        else:
                            error_msg = f"接收到未知控制信号: {retry_signal}，终止处理。"
                            if progress_queue:
                                progress_queue.put(error_msg)
                            print(error_msg)
                            return False
                    except Exception as e:
                        error_msg = f"等待用户操作时发生错误: {e}"
                        if progress_queue:
                            progress_queue.put(error_msg)
                        print(error_msg)
                        return False
                else:  # 命令行模式，没有控制队列
                    error_msg = "检测到时间戳解析错误，但在命令行模式下无法等待用户修正。请手动修复后重新运行程序。"
                    if progress_queue:
                        progress_queue.put(error_msg)
                    print(error_msg)
                    return False
            
            elif srt_result == False:  # 其他失败
                error_msg = "错误：SRT字幕生成失败。"
                if progress_queue:
                    progress_queue.put(error_msg)
                print(error_msg)
                return False
            
            else:  # 未知返回值
                error_msg = f"错误：生成SRT时收到未知返回值: {srt_result}"
                if progress_queue:
                    progress_queue.put(error_msg)
                print(error_msg)
                return False
                
        except Exception as e:
            error_msg = f"SRT字幕生成过程中发生错误: {e}"
            if progress_queue:
                progress_queue.put(error_msg)
            print(error_msg)
            return False
    
    # 清理中间文件（如果需要）
    if cleanup:
        cleanup_msg = "\n--- 清理中间文件 ---"
        if progress_queue:
            progress_queue.put(cleanup_msg)
        print(cleanup_msg)
        
        try:
            shutil.rmtree(audio_chunk_dir)
            shutil.rmtree(intermediate_dir)
            
            # 如果输入是视频文件，且转换后的MP3不是原始输入，则删除转换的MP3文件
            if is_video_file(input_file) and input_audio != input_file:
                os.remove(input_audio)
                cleanup_msg = f"删除了转换的MP3文件: {input_audio}"
                if progress_queue:
                    progress_queue.put(cleanup_msg)
                print(cleanup_msg)
                
            cleanup_success = "中间文件清理完成。"
            if progress_queue:
                progress_queue.put(cleanup_success)
            print(cleanup_success)
        except Exception as e:
            error_msg = f"清理中间文件时出错: {e}"
            if progress_queue:
                progress_queue.put(error_msg)
            print(error_msg)
            # 清理失败不影响整体结果
    
    # 处理结束
    total_end_time = time.time()
    final_msg = f"\n处理完成! 总耗时: {total_end_time - total_start_time:.2f}秒"
    if progress_queue:
        progress_queue.put(final_msg)
    print(final_msg)
    
    output_msg = f"输出目录: {output_dir}\nSRT字幕文件: {srt_file}"
    if progress_queue:
        progress_queue.put(output_msg)
    print(output_msg)
    
    return True

def main():
    parser = argparse.ArgumentParser(description="音频/视频转录与字幕生成一站式工具")
    
    # 基本参数
    parser.add_argument("input_file", help="输入的音频或视频文件路径")
    parser.add_argument("--api-key", required=True, help="Google AI API密钥")
    parser.add_argument("--output-dir", help="指定输出目录 (默认使用输入文件名创建同名目录)")
    
    # 翻译选项
    parser.add_argument("--target-language", default="Simplified Chinese",
                      help="翻译的目标语言 (默认: Simplified Chinese，可选: Traditional Chinese, English, Japanese, Korean, 等)")
    
    # 内容选项
    parser.add_argument("--content", choices=['transcript', 'translation', 'both'], default='both',
                      help="选择SRT内容: transcript(仅转录), translation(仅翻译), both(两者) (默认: both)")
    
    # 音频切分参数
    parser.add_argument("--max-length", type=int, default=300,
                      help="最大音频片段长度(秒) (默认: 300)")
    parser.add_argument("--silence-length", type=int, default=500,
                      help="检测静音的最小长度(毫秒) (默认: 500)")
    parser.add_argument("--silence-threshold", type=int, default=-40,
                      help="静音检测阈值(dB) (默认: -40)")
    
    # SRT参数
    parser.add_argument("--first-chunk-offset", type=float, default=0.0,
                      help="第一个音频块的手动时间偏移(秒) (默认: 0.0)")
    
    # 其他选项
    parser.add_argument("--cleanup", action="store_true",
                      help="处理完成后删除中间文件")
    
    args = parser.parse_args()
    
    # 将args转换为params字典
    params = vars(args)
    
    # 将输入文件参数重命名为input_audio以保持兼容
    params['input_audio'] = params.pop('input_file')
    
    # 运行处理流程
    success = run_pipeline(params)
    
    if success:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()