import os
from google import genai
import time
import pathlib
from google.genai import types
import random # 导入 random 用于增加抖动

# --- 配置 ---
API_KEY = "YOUR_API_KEY_HERE" # 默认API密钥，建议通过参数传入而非硬编码
AUDIO_DIR = "temp_audio_chunks_new_api" # 默认音频目录
INTERMEDIATE_DIR = "intermediate_transcripts" # 默认中间转录文件目录
MAX_RETRIES = 3 # 最大重试次数
INITIAL_DELAY = 1 # 初始延迟秒数
DEFAULT_MODEL = "gemini-2.5-pro-preview-03-25" # 默认模型
# -------------

# --- 系统指令 ---
# 将固定的指令放在这里，但把目标语言作为参数
def get_system_instruction(target_language="Simplified Chinese"):
    return f"""You are a transcription and translation service. Your task is to process the audio file provided in the content.
First, provide the complete transcript in language used by audio.
Second, provide a fluent {target_language} translation of the entire transcript.
Third, Provide transcript with inserted timestamps. Timestamps MUST be in the format [mm:ss.msmsms] (minutes:seconds.milliseconds) at the beginning of each sentence. For example: [00:22.949]. Crucially, ensure timestamps accurately reflect the start time of each sentence, accounting for any initial silence in the audio. The first timestamp must correspond to the actual start time of the first utterance, even if there is silence before it. DO NOT use formats like '[ 4m33s271ms ]'.
Fourth, Provide translation with inserted timestamps. Timestamps MUST be in the format [mm:ss.msmsms] at the beginning of each sentence, mirroring the timing of the timestamped transcript and accounting for initial silence. For example: [00:22.949]. DO NOT use formats like '[ 4m33s271ms ]'.

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

def process_audio_file(filepath, client, intermediate_dir, system_instruction=SYSTEM_INSTRUCTION, model_name=DEFAULT_MODEL):
    """处理单个音频文件：上传、转录、删除，并保存中间转录文件，增加重试逻辑。"""
    filename = os.path.basename(filepath)
    transcript_filename = pathlib.Path(filename).stem + ".txt"
    intermediate_filepath = os.path.join(intermediate_dir, transcript_filename)

    print(f"开始处理: {filename}")
    transcript = ""
    uploaded_file = None
    last_exception = None # 存储最后一次异常

    # --- 文件上传重试逻辑 ---
    for attempt in range(MAX_RETRIES):
        try:
            print(f"  上传中 (尝试 {attempt + 1}/{MAX_RETRIES}): {filename}")
            uploaded_file = client.files.upload(file=filepath)
            print(f"  已上传: {filename} -> {uploaded_file.name}")
            last_exception = None # 成功后清除异常
            break # 上传成功，跳出重试循环
        except Exception as e:
            last_exception = e
            print(f"  上传失败 (尝试 {attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                # 指数退避 + 抖动
                delay = (INITIAL_DELAY * (2 ** attempt)) + random.uniform(0, 1)
                print(f"  将在 {delay:.2f} 秒后重试上传...")
                time.sleep(delay)
            else:
                print(f"  上传达到最大重试次数，放弃文件: {filename}")
                # 记录错误到中间文件
                try:
                    with open(intermediate_filepath, "w", encoding="utf-8") as f_inter:
                        f_inter.write(f"Error uploading {filename} after {MAX_RETRIES} attempts: {last_exception}\n")
                    print(f"  已保存上传错误信息到中间文件: {intermediate_filepath}")
                except IOError as e_write_err:
                     print(f"  错误：无法写入上传错误信息的中间文件 {intermediate_filepath}: {e_write_err}")
                return "" # 上传失败，返回空

    # 如果上传成功 (uploaded_file is not None)
    if uploaded_file:
        # --- 内容生成重试逻辑 ---
        for attempt in range(MAX_RETRIES):
            try:
                print(f"  请求转录 (尝试 {attempt + 1}/{MAX_RETRIES}, 模型: {model_name}): {filename}")
                response = client.models.generate_content(
                    model=model_name, # 使用传入的模型名称
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                    ),
                    contents=[uploaded_file]
                )
                transcript = response.text
                last_exception = None # 成功后清除异常
                print(f"  获取到转录: {filename}")
                break # 转录成功，跳出重试循环
            except Exception as e:
                last_exception = e
                print(f"  转录失败 (尝试 {attempt + 1}/{MAX_RETRIES}): {e}")
                # 修改这里，加入对 502 错误的判断
                error_str = str(e).lower() # 转小写方便判断
                # 检查是否是适合重试的错误类型或消息
                if "disconnected" in error_str or \
                   "unavailable" in error_str or \
                   "502 bad gateway" in error_str or \
                   "internal server error" in error_str or \
                   "500 internal server error" in error_str or \
                   "503 service unavailable" in error_str or \
                   "504 gateway timeout" in error_str or \
                   isinstance(e, types.generation_types.StopCandidateException):
                    if attempt < MAX_RETRIES - 1:
                        delay = (INITIAL_DELAY * (2 ** attempt)) + random.uniform(0, 1)
                        print(f"  检测到可重试错误，将在 {delay:.2f} 秒后重试转录...")
                        time.sleep(delay)
                    else:
                        print(f"  转录达到最大重试次数，放弃文件: {filename}")
                else:
                    # 对于可能不适合重试的错误（如API密钥错误、请求格式错误 4xx），直接跳出重试
                    print(f"  遇到非暂时性错误或未知错误，停止重试: {filename}")
                    break # 跳出重试循环，后续会记录错误

        # --- 保存转录或错误信息 ---
        if transcript:
            try:
                with open(intermediate_filepath, "w", encoding="utf-8") as f_inter:
                    f_inter.write(transcript)
                print(f"  已保存中间转录文件: {intermediate_filepath}")
            except IOError as e_write:
                print(f"  错误：无法写入中间文件 {intermediate_filepath}: {e_write}")
                # 即使写入失败，也尝试删除上传的文件
        elif last_exception: # 如果转录为空且有异常发生（无论是重试耗尽还是非暂时错误）
            print(f"  警告：文件 {filename} 未能成功转录。最后错误: {last_exception}")
            try:
                with open(intermediate_filepath, "w", encoding="utf-8") as f_inter:
                    f_inter.write(f"Error processing {filename} after retries: {last_exception}\n")
                print(f"  已保存转录错误信息到中间文件: {intermediate_filepath}")
            except IOError as e_write_err:
                 print(f"  错误：无法写入转录错误信息的中间文件 {intermediate_filepath}: {e_write_err}")
            transcript = "" # 确保返回空字符串
        else: # 转录为空但没有异常（例如模型返回空内容）
             print(f"  警告：文件 {filename} 返回了空转录文本，但没有检测到API错误。")
             try:
                 # 仍然可以写入一个空文件或包含警告的文件
                 with open(intermediate_filepath, "w", encoding="utf-8") as f_inter:
                     f_inter.write(f"Warning: Empty transcript returned for {filename} without API error.\n")
                 print(f"  已保存空转录警告到中间文件: {intermediate_filepath}")
             except IOError as e_write_err:
                 print(f"  错误：无法写入空转录警告的中间文件 {intermediate_filepath}: {e_write_err}")
             transcript = ""

        # --- 文件删除重试逻辑 ---
        last_delete_exception = None
        for attempt in range(MAX_RETRIES):
            try:
                print(f"  删除已上传文件 (尝试 {attempt + 1}/{MAX_RETRIES}): {uploaded_file.name}")
                client.files.delete(name=uploaded_file.name)
                print(f"  已删除: {uploaded_file.name}")
                last_delete_exception = None
                break # 删除成功
            except Exception as delete_err:
                last_delete_exception = delete_err
                print(f"  删除文件失败 (尝试 {attempt + 1}/{MAX_RETRIES}): {delete_err}")
                if attempt < MAX_RETRIES - 1:
                    delay = (INITIAL_DELAY * (2 ** attempt)) + random.uniform(0, 1)
                    print(f"  将在 {delay:.2f} 秒后重试删除...")
                    time.sleep(delay)
                else:
                    print(f"  删除文件 {uploaded_file.name} 达到最大重试次数，放弃删除。")

        if last_delete_exception:
             # 记录删除失败，但不影响函数返回值
             print(f"  最终未能删除文件 {uploaded_file.name}: {last_delete_exception}")

        return transcript

    else:
        # 如果 uploaded_file 为 None (即上传从未成功)
        print(f"文件 {filename} 未能上传，跳过后续处理。")
        return "" # 确保返回空字符串

def run_transcription(api_key, audio_dir, intermediate_dir, system_instruction=SYSTEM_INSTRUCTION, model_name=DEFAULT_MODEL, progress_queue=None):
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
        result = process_audio_file(audio_file_path, client, intermediate_dir, system_instruction, model_name) # 传递 model_name
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
    parser.add_argument("--model-name", default=DEFAULT_MODEL, help=f"使用的 Gemini 模型名称 (默认: {DEFAULT_MODEL})")

    args = parser.parse_args()

    # 根据目标语言生成系统指令
    system_instruction = get_system_instruction(args.target_language)

    run_transcription(args.api_key, args.audio_dir, args.intermediate_dir, system_instruction, args.model_name) # 传递 model_name