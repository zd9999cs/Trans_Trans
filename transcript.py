import os
from google import genai
import time
import pathlib
from google.genai import types

# --- 配置 ---
API_KEY = "YOUR_API_KEY_HERE" # 默认API密钥，建议通过参数传入而非硬编码
AUDIO_DIR = "temp_audio_chunks_new_api" # 默认音频目录
INTERMEDIATE_DIR = "intermediate_transcripts" # 默认中间转录文件目录
# -------------

# --- 系统指令 ---
# 将固定的指令放在这里，但把目标语言作为参数
def get_system_instruction(target_language="Simplified Chinese"):
    return f"""You are a transcription and translation service. Your task is to process the audio file provided in the content.
First, provide the complete transcript in language used by audio.
Second, provide a fluent {target_language} translation of the entire transcript.
Third, Provide transcript with inserted timestamps in the format [mm:ss.msmsms] at the beginning of each sentence. Crucially, ensure timestamps accurately reflect the start time of each sentence, accounting for any initial silence in the audio. The first timestamp must correspond to the actual start time of the first utterance, even if there is silence before it.
Fourth, Provide translation with inserted timestamps in the format [mm:ss.msmsms] at the beginning of each sentence, mirroring the timing of the timestamped transcript and accounting for initial silence.

Output format MUST be:
Transcript:
[Transcript text]

Translation:
[{target_language} translation text]

Timestamped Transcript:
[Timestamped transcript text]

Timestamped Translation:
[Timestamped translation text]

"""

# 默认的系统指令使用简体中文
SYSTEM_INSTRUCTION = get_system_instruction()

def initialize_genai_client(api_key):
    """初始化GenAI客户端"""
    try:
        return genai.Client(api_key=api_key)
    except Exception as e:
        print(f"初始化 GenAI 客户端时出错: {e}")
        return None

def process_audio_file(filepath, client, intermediate_dir, system_instruction=SYSTEM_INSTRUCTION):
    """处理单个音频文件：上传、转录、删除，并保存中间转录文件。"""
    filename = os.path.basename(filepath)
    transcript_filename = pathlib.Path(filename).stem + ".txt"
    intermediate_filepath = os.path.join(intermediate_dir, transcript_filename)

    print(f"开始处理: {filename}")
    transcript = ""
    uploaded_file = None

    try:
        # 1. 上传文件
        print(f"  上传中: {filename}")
        uploaded_file = client.files.upload(file=filepath)
        print(f"  已上传: {filename} -> {uploaded_file.name}")

        # 2. 生成内容 (转录) - 使用 system_instruction
        print(f"  请求转录: {filename}")
        response = client.models.generate_content(
            model="gemini-2.5-pro-preview-03-25", # 确认模型支持 system_instruction
            config=types.GenerateContentConfig(
                system_instruction=system_instruction, # 使用传入的系统指令
            ),
            contents=[uploaded_file] # contents 只包含文件
        )

        transcript = response.text
        if transcript:
            print(f"  获取到转录: {filename}")
            # 尝试保存中间文件
            try:
                with open(intermediate_filepath, "w", encoding="utf-8") as f_inter:
                    f_inter.write(transcript)
                print(f"  已保存中间转录文件: {intermediate_filepath}")
            except IOError as e_write:
                print(f"  错误：无法写入中间文件 {intermediate_filepath}: {e_write}")
        else:
            print(f"  警告：文件 {filename} 未返回有效转录文本。")
            transcript = ""

        # 3. 删除已上传的文件
        print(f"  删除已上传文件: {uploaded_file.name}")
        client.files.delete(name=uploaded_file.name)
        print(f"  已删除: {uploaded_file.name}")

        return transcript

    except Exception as e:
        print(f"处理文件 {filename} 时出错: {e}")
        if uploaded_file:
            try:
                 print(f"  尝试删除出错文件对应的上传: {uploaded_file.name}")
                 client.files.delete(name=uploaded_file.name)
                 print(f"  已删除出错文件对应的上传: {uploaded_file.name}")
            except Exception as delete_err:
                 print(f"  删除文件 {uploaded_file.name} 时也发生错误: {delete_err}")
        try:
            with open(intermediate_filepath, "w", encoding="utf-8") as f_inter:
                f_inter.write(f"Error processing {filename}: {e}\n")
            print(f"  已保存错误信息到中间文件: {intermediate_filepath}")
        except IOError as e_write_err:
             print(f"  错误：无法写入错误信息的中间文件 {intermediate_filepath}: {e_write_err}")
        return ""

def run_transcription(api_key, audio_dir, intermediate_dir, system_instruction=SYSTEM_INSTRUCTION, progress_queue=None):
    """处理一个目录中的所有音频文件，生成转录文本"""
    # 初始化客户端
    client = initialize_genai_client(api_key)
    if not client:
        error_msg = "无法初始化GenAI客户端，请检查API密钥"
        if progress_queue:
            progress_queue.put(error_msg)
        print(error_msg)
        return False
    
    # 创建中间目录
    pathlib.Path(intermediate_dir).mkdir(parents=True, exist_ok=True)
    status_msg = f"中间转录文件将保存在: {intermediate_dir}"
    if progress_queue:
        progress_queue.put(status_msg)
    print(status_msg)

    # 获取并排序文件路径
    try:
        audio_files = sorted([
            os.path.join(audio_dir, f)
            for f in os.listdir(audio_dir)
            if f.endswith(".mp3")
        ])
    except FileNotFoundError:
        error_msg = f"错误：找不到目录 {audio_dir}"
        if progress_queue:
            progress_queue.put(error_msg)
        print(error_msg)
        return False
    except Exception as e:
        error_msg = f"读取目录 {audio_dir} 时出错: {e}"
        if progress_queue:
            progress_queue.put(error_msg)
        print(error_msg)
        return False

    if not audio_files:
        error_msg = f"在目录 {audio_dir} 中未找到 .mp3 文件。"
        if progress_queue:
            progress_queue.put(error_msg)
        print(error_msg)
        return False

    status_msg = f"找到 {len(audio_files)} 个音频文件，将按顺序处理..."
    if progress_queue:
        progress_queue.put(status_msg)
    print(status_msg)

    # 按顺序处理文件
    start_time = time.time()
    results = []
    for i, audio_file_path in enumerate(audio_files):
        status_msg = f"处理文件 {i+1}/{len(audio_files)}: {os.path.basename(audio_file_path)}"
        if progress_queue:
            progress_queue.put(status_msg)
        result = process_audio_file(audio_file_path, client, intermediate_dir, system_instruction)
        results.append(result)

    end_time = time.time()
    status_msg = f"所有文件处理完成，耗时: {end_time - start_time:.2f} 秒"
    if progress_queue:
        progress_queue.put(status_msg)
    print(status_msg)
    
    return True

# --- 主逻辑 ---
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="处理音频文件并生成转录文本")
    parser.add_argument("--api-key", required=True, help="Google AI API密钥")
    parser.add_argument("--audio-dir", default=AUDIO_DIR, help=f"音频文件目录 (默认: {AUDIO_DIR})")
    parser.add_argument("--intermediate-dir", default=INTERMEDIATE_DIR, help=f"中间转录文件目录 (默认: {INTERMEDIATE_DIR})")
    parser.add_argument("--target-language", default="Simplified Chinese", 
                      help="翻译的目标语言 (默认: Simplified Chinese，可选: Traditional Chinese, English, Japanese, Korean, 等)")
    
    args = parser.parse_args()
    
    # 根据目标语言生成系统指令
    system_instruction = get_system_instruction(args.target_language)
    
    run_transcription(args.api_key, args.audio_dir, args.intermediate_dir, system_instruction)