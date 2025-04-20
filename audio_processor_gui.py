#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import threading
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import pathlib
import time
import multiprocessing
import signal
import psutil
import subprocess
from datetime import datetime

# 导入主调用脚本中的处理函数和视频检测函数
try:
    from process_audio import run_pipeline, is_video_file
except ImportError as e:
    print(f"错误：无法导入process_audio.py模块。确保该文件在同一目录下。详细错误: {e}")
    sys.exit(1)

# 确保多进程在Windows下正常工作
if __name__ == "__main__":
    # 设置多进程启动方法为spawn (在Windows上更稳定)
    multiprocessing.set_start_method('spawn', force=True)

# 定义翻译字典
translations = {
    "zh_CN": {  # 简体中文
        "title": "音频/视频转录与字幕生成工具",
        "basic_settings": "基本设置",
        "input_file": "输入文件(音频/视频):",
        "browse": "浏览...",
        "api_key": "Google AI API密钥:",
        "show_hide": "显示/隐藏",
        "output_dir": "输出目录 (可选):",
        "process_params": "处理参数",
        "content_type": "字幕内容:",
        "content_desc": "(transcript:仅转录, translation:仅翻译, both:两者)",
        "target_language": "翻译目标语言:",
        "max_length": "最大片段长度(秒):",
        "silence_length": "静音检测长度(毫秒):",
        "silence_threshold": "静音阈值(dB):",
        "first_chunk_offset": "首个片段偏移(秒):",
        "cleanup": "处理完成后删除中间文件",
        "start_process": "开始处理",
        "stop_process": "停止处理",
        "progress": "处理进度",
        "ready": "就绪",
        "processing": "处理中...",
        "stopped": "已停止",
        "file_not_selected": "未选择文件",
        "video_file": "视频文件 (将自动转换为MP3)",
        "audio_file": "音频文件",
        "error_no_input": "错误: 请选择输入文件(音频或视频)",
        "error_no_api_key": "错误: 请输入Google AI API密钥",
        "confirm_start": "确认", 
        "confirm_start_message": "确定要开始处理吗？\n这可能需要一段时间，具体取决于文件长度。",
        "confirm_stop": "确认",
        "confirm_stop_message": "确定要停止处理吗？\n当前进度将丢失。",
        "confirm_close": "确认",
        "confirm_close_message": "处理正在进行中。确定要退出吗？",
        "complete": "完成",
        "complete_message": "处理已完成！\n输出目录: {output_dir}",
        "error": "错误",
        "process_failed": "处理失败。请查看详细日志。",
        "unexpected_error": "处理过程中发生错误:\n{error}",
        "language": "语言/Language",
        "select_file": "选择音频或视频文件",
        "select_output_dir": "选择输出目录",
        "user_stop": "用户手动停止处理。",
    },
    "en_US": {  # 英文
        "title": "Audio/Video Transcription and Subtitle Generator",
        "basic_settings": "Basic Settings",
        "input_file": "Input File (Audio/Video):",
        "browse": "Browse...",
        "api_key": "Google AI API Key:",
        "show_hide": "Show/Hide",
        "output_dir": "Output Directory (Optional):",
        "process_params": "Processing Parameters",
        "content_type": "Subtitle Content:",
        "content_desc": "(transcript: Transcription only, translation: Translation only, both: Both)",
        "target_language": "Target Translation Language:",
        "max_length": "Max Segment Length (sec):",
        "silence_length": "Silence Detection Length (ms):",
        "silence_threshold": "Silence Threshold (dB):",
        "first_chunk_offset": "First Segment Offset (sec):",
        "cleanup": "Delete intermediate files after processing",
        "start_process": "Start Processing",
        "stop_process": "Stop Processing",
        "progress": "Progress",
        "ready": "Ready",
        "processing": "Processing...",
        "stopped": "Stopped",
        "file_not_selected": "No file selected",
        "video_file": "Video file (will be converted to MP3)",
        "audio_file": "Audio file",
        "error_no_input": "Error: Please select an input file (audio or video)",
        "error_no_api_key": "Error: Please enter a Google AI API Key",
        "confirm_start": "Confirm", 
        "confirm_start_message": "Are you sure you want to start processing?\nThis may take some time depending on the file length.",
        "confirm_stop": "Confirm",
        "confirm_stop_message": "Are you sure you want to stop processing?\nCurrent progress will be lost.",
        "confirm_close": "Confirm",
        "confirm_close_message": "Processing is in progress. Are you sure you want to exit?",
        "complete": "Complete",
        "complete_message": "Processing completed!\nOutput directory: {output_dir}",
        "error": "Error",
        "process_failed": "Processing failed. Please check the detailed log.",
        "unexpected_error": "An error occurred during processing:\n{error}",
        "language": "语言/Language",
        "select_file": "Select Audio or Video File",
        "select_output_dir": "Select Output Directory",
        "user_stop": "User manually stopped processing.",
    }
}

class AudioProcessorGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        
        # 设置当前语言
        self.current_language = tk.StringVar(value="zh_CN")  # 默认使用中文
        
        # 设置窗口标题和大小
        self.title("音频/视频转录与字幕生成工具")
        self.geometry("800x700")
        self.minsize(700, 600)
        
        # 创建变量
        self.input_file_path = tk.StringVar()  # 改名从input_audio_path为input_file_path
        self.output_dir_path = tk.StringVar()
        self.api_key = tk.StringVar()
        self.content_choice = tk.StringVar(value="both")
        self.target_language = tk.StringVar(value="Simplified Chinese")
        self.max_length = tk.IntVar(value=300)
        self.silence_length = tk.IntVar(value=500)
        self.silence_threshold = tk.IntVar(value=-40)
        self.first_chunk_offset = tk.DoubleVar(value=0.0)
        self.cleanup = tk.BooleanVar(value=False)
        
        # 存储当前处理状态
        self.processing = False
        self.process_thread = None
        self.process = None  # 存储子进程对象
        self.process_pid = None  # 存储进程PID
        self.waiting_for_user_fix = False  # 标记是否正在等待用户修复时间戳
        self.error_files = []  # 存储需要修复的文件信息
        
        # 创建进度队列和控制队列
        self.progress_queue = multiprocessing.Queue()
        self.control_queue = multiprocessing.Queue()  # 新增控制队列，用于发送用户干预信号
        
        # 存储UI组件的引用
        self.ui_elements = {}
        
        # 创建主界面
        self.create_widgets()
        
        # 启动队列检查
        self.check_queue()
        
        # 绑定关闭窗口事件
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def create_widgets(self):
        """创建所有GUI组件"""
        # 创建主框架
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 在顶部添加语言选择
        lang_frame = ttk.Frame(main_frame)
        lang_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(lang_frame, text=translations[self.current_language.get()]["language"]).pack(side=tk.LEFT, padx=5)
        lang_combo = ttk.Combobox(lang_frame, textvariable=self.current_language, width=10)
        lang_combo['values'] = ('zh_CN', 'en_US')
        lang_combo.current(0 if self.current_language.get() == 'zh_CN' else 1)
        lang_combo.pack(side=tk.LEFT, padx=5)
        
        # 绑定语言切换事件
        lang_combo.bind("<<ComboboxSelected>>", self.change_language)
        
        # 创建输入框架
        input_frame = ttk.LabelFrame(main_frame, text=translations[self.current_language.get()]["basic_settings"], padding="10")
        input_frame.pack(fill=tk.X, pady=5)
        self.ui_elements["basic_settings_frame"] = input_frame
        
        # 输入文件（音频或视频）
        input_file_label = ttk.Label(input_frame, text=translations[self.current_language.get()]["input_file"])
        input_file_label.grid(row=0, column=0, sticky=tk.W, pady=5)
        self.ui_elements["input_file_label"] = input_file_label
        
        ttk.Entry(input_frame, textvariable=self.input_file_path, width=50).grid(row=0, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
        browse_btn = ttk.Button(input_frame, text=translations[self.current_language.get()]["browse"], command=self.browse_input_file)
        browse_btn.grid(row=0, column=2, sticky=tk.W, pady=5)
        self.ui_elements["browse_input_btn"] = browse_btn
        
        # 文件类型指示器
        self.file_type_var = tk.StringVar(value=translations[self.current_language.get()]["file_not_selected"])
        file_type_label = ttk.Label(input_frame, textvariable=self.file_type_var, foreground="blue")
        file_type_label.grid(row=0, column=3, sticky=tk.W, pady=5, padx=5)
        self.ui_elements["file_type_label"] = file_type_label
        
        # API密钥
        api_key_label = ttk.Label(input_frame, text=translations[self.current_language.get()]["api_key"])
        api_key_label.grid(row=1, column=0, sticky=tk.W, pady=5)
        self.ui_elements["api_key_label"] = api_key_label
        
        api_key_entry = ttk.Entry(input_frame, textvariable=self.api_key, width=50, show="*")
        api_key_entry.grid(row=1, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
        
        show_hide_btn = ttk.Button(input_frame, text=translations[self.current_language.get()]["show_hide"], 
                               command=lambda: self.toggle_api_key_visibility(api_key_entry))
        show_hide_btn.grid(row=1, column=2, sticky=tk.W, pady=5)
        self.ui_elements["show_hide_btn"] = show_hide_btn
        
        # 如果有环境变量API_KEY，就使用它
        env_api_key = os.environ.get("GOOGLE_API_KEY")
        if env_api_key:
            self.api_key.set(env_api_key)
        
        # 输出目录
        output_dir_label = ttk.Label(input_frame, text=translations[self.current_language.get()]["output_dir"])
        output_dir_label.grid(row=2, column=0, sticky=tk.W, pady=5)
        self.ui_elements["output_dir_label"] = output_dir_label
        
        ttk.Entry(input_frame, textvariable=self.output_dir_path, width=50).grid(row=2, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
        
        browse_output_btn = ttk.Button(input_frame, text=translations[self.current_language.get()]["browse"], 
                                 command=self.browse_output_dir)
        browse_output_btn.grid(row=2, column=2, sticky=tk.W, pady=5)
        self.ui_elements["browse_output_btn"] = browse_output_btn
        
        # 创建参数框架
        params_frame = ttk.LabelFrame(main_frame, text=translations[self.current_language.get()]["process_params"], padding="10")
        params_frame.pack(fill=tk.X, pady=5)
        self.ui_elements["params_frame"] = params_frame
        
        # 创建参数网格
        # 内容选择
        content_label = ttk.Label(params_frame, text=translations[self.current_language.get()]["content_type"])
        content_label.grid(row=0, column=0, sticky=tk.W, pady=5)
        self.ui_elements["content_label"] = content_label
        
        content_combo = ttk.Combobox(params_frame, textvariable=self.content_choice, width=15)
        content_combo['values'] = ('transcript', 'translation', 'both')
        content_combo.current(2)  # 默认选择 'both'
        content_combo.grid(row=0, column=1, sticky=tk.W, pady=5)
        
        content_desc_label = ttk.Label(params_frame, text=translations[self.current_language.get()]["content_desc"])
        content_desc_label.grid(row=0, column=2, sticky=tk.W, pady=5)
        self.ui_elements["content_desc_label"] = content_desc_label
        
        # 目标语言
        target_lang_label = ttk.Label(params_frame, text=translations[self.current_language.get()]["target_language"])
        target_lang_label.grid(row=1, column=0, sticky=tk.W, pady=5)
        self.ui_elements["target_lang_label"] = target_lang_label
        
        target_lang_combo = ttk.Combobox(params_frame, textvariable=self.target_language, width=15)
        target_lang_combo['values'] = ('Simplified Chinese', 'Traditional Chinese', 'English', 'Japanese', 'Korean', 'Russian', 'Spanish', 'French', 'German')
        target_lang_combo.current(0)  # 默认选择 'Simplified Chinese'
        target_lang_combo.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        # 音频切分参数
        max_length_label = ttk.Label(params_frame, text=translations[self.current_language.get()]["max_length"])
        max_length_label.grid(row=2, column=0, sticky=tk.W, pady=5)
        self.ui_elements["max_length_label"] = max_length_label
        
        ttk.Spinbox(params_frame, from_=60, to=900, increment=30, textvariable=self.max_length, width=5).grid(row=2, column=1, sticky=tk.W, pady=5)
        
        silence_length_label = ttk.Label(params_frame, text=translations[self.current_language.get()]["silence_length"])
        silence_length_label.grid(row=3, column=0, sticky=tk.W, pady=5)
        self.ui_elements["silence_length_label"] = silence_length_label
        
        ttk.Spinbox(params_frame, from_=100, to=2000, increment=100, textvariable=self.silence_length, width=5).grid(row=3, column=1, sticky=tk.W, pady=5)
        
        silence_threshold_label = ttk.Label(params_frame, text=translations[self.current_language.get()]["silence_threshold"])
        silence_threshold_label.grid(row=4, column=0, sticky=tk.W, pady=5)
        self.ui_elements["silence_threshold_label"] = silence_threshold_label
        
        ttk.Spinbox(params_frame, from_=-60, to=-20, increment=5, textvariable=self.silence_threshold, width=5).grid(row=4, column=1, sticky=tk.W, pady=5)
        
        # 字幕参数
        first_chunk_offset_label = ttk.Label(params_frame, text=translations[self.current_language.get()]["first_chunk_offset"])
        first_chunk_offset_label.grid(row=5, column=0, sticky=tk.W, pady=5)
        self.ui_elements["first_chunk_offset_label"] = first_chunk_offset_label
        
        ttk.Spinbox(params_frame, from_=-5.0, to=5.0, increment=0.1, textvariable=self.first_chunk_offset, width=5).grid(row=5, column=1, sticky=tk.W, pady=5)
        
        # 清理选项
        cleanup_checkbox = ttk.Checkbutton(params_frame, text=translations[self.current_language.get()]["cleanup"], variable=self.cleanup)
        cleanup_checkbox.grid(row=6, column=0, columnspan=3, sticky=tk.W, pady=5)
        self.ui_elements["cleanup_checkbox"] = cleanup_checkbox
        
        # 创建按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        # 添加按钮
        self.start_button = ttk.Button(button_frame, text=translations[self.current_language.get()]["start_process"], command=self.start_processing)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(button_frame, text=translations[self.current_language.get()]["stop_process"], command=self.stop_processing, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # 添加用户修复错误和重试按钮 - 默认禁用
        self.retry_button = ttk.Button(button_frame, text="重试合并", command=self.retry_combine, state=tk.DISABLED)
        self.retry_button.pack(side=tk.LEFT, padx=5)
        self.ui_elements["retry_button"] = self.retry_button
        
        self.open_error_file_button = ttk.Button(button_frame, text="打开错误文件", command=self.open_error_file, state=tk.DISABLED)
        self.open_error_file_button.pack(side=tk.LEFT, padx=5)
        self.ui_elements["open_error_file_button"] = self.open_error_file_button
        
        # 创建进度框架
        progress_frame = ttk.LabelFrame(main_frame, text=translations[self.current_language.get()]["progress"], padding="10")
        progress_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.ui_elements["progress_frame"] = progress_frame
        
        # 添加进度显示
        self.progress_text = scrolledtext.ScrolledText(progress_frame, wrap=tk.WORD, height=15)
        self.progress_text.pack(fill=tk.BOTH, expand=True)
        self.progress_text.config(state=tk.DISABLED)
        
        # 底部状态栏
        self.status_var = tk.StringVar(value=translations[self.current_language.get()]["ready"])
        status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 添加翻译条目
        if "zh_CN" in translations:
            translations["zh_CN"]["retry_combine"] = "重试合并"
            translations["zh_CN"]["open_error_file"] = "打开错误文件"
            translations["zh_CN"]["timestamp_error"] = "时间戳解析错误"
            translations["zh_CN"]["timestamp_error_message"] = "检测到时间戳解析错误。请修改出错的文件后点击\"重试合并\"按钮。"
            translations["zh_CN"]["select_error_file"] = "请选择要打开的错误文件"
            translations["zh_CN"]["error_file_not_found"] = "错误文件未找到或已被移动"
            translations["zh_CN"]["waiting_for_fix"] = "等待修复..."
        if "en_US" in translations:
            translations["en_US"]["retry_combine"] = "Retry Combine"
            translations["en_US"]["open_error_file"] = "Open Error File"
            translations["en_US"]["timestamp_error"] = "Timestamp Parse Error"
            translations["en_US"]["timestamp_error_message"] = "Timestamp parsing errors detected. Please edit the error files and click 'Retry Combine' button."
            translations["en_US"]["select_error_file"] = "Please select an error file to open"
            translations["en_US"]["error_file_not_found"] = "Error file not found or has been moved"
            translations["en_US"]["waiting_for_fix"] = "Waiting for fix..."
    
    def toggle_api_key_visibility(self, entry):
        """切换API密钥的可见性"""
        if entry.cget('show') == '*':
            entry.config(show='')
        else:
            entry.config(show='*')
    
    def browse_input_file(self):
        """打开文件浏览器选择输入文件（音频或视频）"""
        lang = self.current_language.get()
        filetypes = (
            ("所有支持的文件", "*.mp3 *.wav *.flac *.m4a *.aac *.ogg *.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v"),
            ("音频文件", "*.mp3 *.wav *.flac *.m4a *.aac *.ogg"),
            ("视频文件", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v"),
            ("所有文件", "*.*")
        )
        filepath = filedialog.askopenfilename(
            title=translations[lang]["select_file"],
            filetypes=filetypes
        )
        
        if filepath:
            self.input_file_path.set(filepath)
            # 如果没有设置输出目录，则使用输入文件名创建目录路径
            if not self.output_dir_path.get():
                input_path = pathlib.Path(filepath)
                self.output_dir_path.set(os.path.join(input_path.parent, input_path.stem))
            
            # 更新文件类型指示器
            if is_video_file(filepath):
                self.file_type_var.set(translations[lang]["video_file"])
            else:
                self.file_type_var.set(translations[lang]["audio_file"])
    
    def browse_output_dir(self):
        """打开文件浏览器选择输出目录"""
        dirpath = filedialog.askdirectory(
            title=translations[self.current_language.get()]["select_output_dir"]
        )
        
        if dirpath:
            self.output_dir_path.set(dirpath)
    
    def start_processing(self):
        """开始处理音频文件"""
        # 检查必要参数
        if not self.input_file_path.get():
            messagebox.showerror(translations[self.current_language.get()]["error"], translations[self.current_language.get()]["error_no_input"])
            return
        
        if not self.api_key.get():
            messagebox.showerror(translations[self.current_language.get()]["error"], translations[self.current_language.get()]["error_no_api_key"])
            return
        
        # 确认处理
        if not messagebox.askyesno(translations[self.current_language.get()]["confirm_start"], translations[self.current_language.get()]["confirm_start_message"]):
            return
        
        # 重置错误文件列表和等待修复状态
        self.error_files = []
        self.waiting_for_user_fix = False
        
        # 确保重试和打开错误文件按钮处于禁用状态
        self.retry_button.config(state=tk.DISABLED)
        self.open_error_file_button.config(state=tk.DISABLED)
        
        # 准备参数
        params = {
            'input_audio': self.input_file_path.get(),  # 保持与process_audio.py兼容
            'output_dir': self.output_dir_path.get(),
            'api_key': self.api_key.get(),
            'content': self.content_choice.get(),
            'target_language': self.target_language.get(),
            'max_length': self.max_length.get(),
            'silence_length': self.silence_length.get(),
            'silence_threshold': self.silence_threshold.get(),
            'first_chunk_offset': self.first_chunk_offset.get(),
            'cleanup': self.cleanup.get()
        }
        
        # 更新UI状态
        self.processing = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_var.set(translations[self.current_language.get()]["processing"])
        
        # 清空进度显示
        self.progress_text.config(state=tk.NORMAL)
        self.progress_text.delete(1.0, tk.END)
        self.progress_text.config(state=tk.DISABLED)
        
        # 记录开始时间
        self.start_time = time.time()
        
        # 启动处理进程
        self.process = multiprocessing.Process(
            target=run_pipeline,
            args=(params, self.progress_queue, self.control_queue)  # 添加控制队列
        )
        self.process.start()
        self.process_pid = self.process.pid
        
        # 启动监控线程来检查进程状态
        self.process_thread = threading.Thread(
            target=self.monitor_process,
            daemon=True
        )
        self.process_thread.start()
    
    def retry_combine(self):
        """用户修复时间戳错误后，发送重试信号"""
        if not self.waiting_for_user_fix:
            return
            
        # 更新状态
        self.status_var.set(translations[self.current_language.get()]["processing"])
        self.add_progress("发送重试信号，继续合并转录...")
        
        # 发送重试信号到控制队列
        self.control_queue.put('RETRY_COMBINE')
        
        # 更新 UI 状态
        self.waiting_for_user_fix = False
        self.retry_button.config(state=tk.DISABLED)
        self.open_error_file_button.config(state=tk.DISABLED)
    
    def open_error_file(self):
        """打开包含时间戳错误的文件供用户修改"""
        if not self.error_files:
            messagebox.showinfo(
                translations[self.current_language.get()]["timestamp_error"],
                "没有需要修复的文件信息。"
            )
            return
            
        # 如果只有一个错误文件，直接打开
        if len(self.error_files) == 1:
            error_info = self.error_files[0]
            self.open_file_with_default_editor(error_info)
            return
            
        # 如果有多个错误文件，显示选择对话框
        error_file_options = []
        for i, error_info in enumerate(self.error_files):
            filename = error_info.get("file", "未知文件")
            section = error_info.get("section", "未知段落")
            timestamp = error_info.get("timestamp_str", "未知时间戳")
            error_file_options.append(f"{i+1}. {filename} - {section} - {timestamp}")
        
        # 创建一个简单的对话框让用户选择
        select_dialog = tk.Toplevel(self)
        select_dialog.title(translations[self.current_language.get()]["select_error_file"])
        select_dialog.geometry("500x300")
        select_dialog.resizable(False, False)
        select_dialog.transient(self)
        select_dialog.grab_set()
        
        ttk.Label(select_dialog, text="请选择要打开的错误文件:").pack(pady=10)
        
        listbox = tk.Listbox(select_dialog, width=70, height=10)
        for option in error_file_options:
            listbox.insert(tk.END, option)
        listbox.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        
        def on_select():
            selected_idx = listbox.curselection()
            if selected_idx:  # 确保选择了某项
                error_info = self.error_files[selected_idx[0]]
                self.open_file_with_default_editor(error_info)
                select_dialog.destroy()
            else:
                messagebox.showinfo("提示", "请选择一个文件")
        
        ttk.Button(select_dialog, text="打开选中文件", command=on_select).pack(pady=10)
        ttk.Button(select_dialog, text="取消", command=select_dialog.destroy).pack(pady=5)
    
    def open_file_with_default_editor(self, error_info):
        """使用系统默认编辑器打开包含错误的文件"""
        if not error_info or "file" not in error_info:
            return
            
        filename = error_info.get("file")
        output_dir = self.output_dir_path.get()
        
        if not output_dir:
            messagebox.showerror(
                translations[self.current_language.get()]["error"],
                "输出目录未设置，无法定位错误文件。"
            )
            return
            
        intermediate_dir = os.path.join(output_dir, "intermediate_transcripts")
        file_path = os.path.join(intermediate_dir, filename)
        
        if not os.path.exists(file_path):
            messagebox.showerror(
                translations[self.current_language.get()]["error"],
                translations[self.current_language.get()]["error_file_not_found"]
            )
            return
            
        # 获取行号信息
        line_num = error_info.get("line_num", 1)
        section = error_info.get("section", "未知段落")
        timestamp = error_info.get("timestamp_str", "未知时间戳")
        
        # 向用户显示错误详情
        self.add_progress(f"打开错误文件: {file_path}")
        self.add_progress(f"问题位置: 第 {line_num} 行, 段落: {section}, 时间戳: {timestamp}")
        self.add_progress("请修复不正确的时间戳格式，然后点击'重试合并'按钮。")
        
        # 尝试使用系统默认应用程序打开文件
        try:
            if sys.platform == 'win32':  # Windows
                os.startfile(file_path)
            elif sys.platform == 'darwin':  # macOS
                subprocess.call(['open', file_path])
            else:  # Linux
                subprocess.call(['xdg-open', file_path])
        except Exception as e:
            messagebox.showerror(
                translations[self.current_language.get()]["error"],
                f"无法打开文件: {str(e)}"
            )
    
    def stop_processing(self):
        """暴力停止处理进程及其所有子进程"""
        if not self.processing or not self.process_pid:
            return
        
        if messagebox.askyesno(translations[self.current_language.get()]["confirm_stop"], translations[self.current_language.get()]["confirm_stop_message"]):
            self.add_progress(f"\n{translations[self.current_language.get()]['user_stop']}")
            self.status_var.set(translations[self.current_language.get()]["stopped"])
            
            # 如果正在等待用户修复，发送停止信号
            if self.waiting_for_user_fix:
                self.control_queue.put('STOP_PROCESSING')
                self.waiting_for_user_fix = False
                self.retry_button.config(state=tk.DISABLED)
                self.open_error_file_button.config(state=tk.DISABLED)
            
            try:
                # 获取主进程
                parent = psutil.Process(self.process_pid)
                
                # 先获取所有子进程
                children = parent.children(recursive=True)
                
                # 终止所有子进程
                for child in children:
                    try:
                        child.terminate()
                    except:
                        # 如果无法正常终止，则强制终止
                        try:
                            child.kill()
                        except:
                            pass
                
                # 终止主进程
                try:
                    parent.terminate()
                except:
                    # 如果无法正常终止，则强制终止
                    try:
                        parent.kill()
                    except:
                        pass
                
                # 确保进程已终止
                gone, still_alive = psutil.wait_procs(children + [parent], timeout=3)
                
                # 强制杀死仍然存活的进程
                for p in still_alive:
                    try:
                        p.kill()
                    except:
                        pass
                
                self.add_progress("所有相关进程已强制终止。")
            except Exception as e:
                self.add_progress(f"终止进程时发生错误: {str(e)}")
            
            # 更新UI状态
            self.processing = False
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.process = None
            self.process_pid = None
    
    def check_queue(self):
        """检查进度队列，更新进度显示"""
        try:
            while True:
                # 从队列中获取消息
                message = self.progress_queue.get_nowait()
                
                # 检查是否为对象（例如错误数据字典）
                if isinstance(message, dict) and message.get('type') == 'PARSE_ERROR':
                    self.handle_parse_error(message)
                else:
                    self.add_progress(message)
        except queue.Empty:
            pass
        
        # 每100毫秒检查一次队列
        self.after(100, self.check_queue)
    
    def handle_parse_error(self, error_data):
        """处理时间戳解析错误的特殊消息"""
        self.error_files = error_data.get('errors', [])
        self.waiting_for_user_fix = True
        
        # 更新UI状态
        self.status_var.set(translations[self.current_language.get()]["waiting_for_fix"])
        
        # 启用重试按钮和打开错误文件按钮
        self.retry_button.config(state=tk.NORMAL)
        self.open_error_file_button.config(state=tk.NORMAL)
        
        # 添加提示信息到进度显示
        self.add_progress("\n" + "-" * 50)
        self.add_progress(f"检测到 {len(self.error_files)} 个时间戳解析错误！")
        self.add_progress(translations[self.current_language.get()]["timestamp_error_message"])
        self.add_progress("错误文件列表:")
        
        # 显示错误详情
        for i, error in enumerate(self.error_files):
            error_detail = (f"  {i+1}. 文件: {error.get('file', '未知')}, "
                           f"部分: {error.get('section', '未知')}, "
                           f"行号: {error.get('line_num', '未知')}, "
                           f"时间戳: '{error.get('timestamp_str', '未知')}'")
            self.add_progress(error_detail)
        
        self.add_progress("-" * 50)
        
        # 弹出提示消息
        messagebox.showinfo(
            translations[self.current_language.get()]["timestamp_error"],
            translations[self.current_language.get()]["timestamp_error_message"]
        )
    
    def add_progress(self, message):
        """向进度显示添加消息"""
        self.progress_text.config(state=tk.NORMAL)
        self.progress_text.insert(tk.END, f"{message}\n")
        self.progress_text.see(tk.END)  # 滚动到底部
        self.progress_text.config(state=tk.DISABLED)
        
        # 更新界面
        self.update_idletasks()
    
    def on_closing(self):
        """窗口关闭时的处理"""
        if self.processing:
            if not messagebox.askyesno(translations[self.current_language.get()]["confirm_close"], translations[self.current_language.get()]["confirm_close_message"]):
                return
        
        self.destroy()
    
    def change_language(self, event):
        """切换语言"""
        lang = self.current_language.get()
        
        # 更新所有UI元素的文本
        self.title(translations[lang]["title"])
        self.ui_elements["basic_settings_frame"].config(text=translations[lang]["basic_settings"])
        self.ui_elements["input_file_label"].config(text=translations[lang]["input_file"])
        self.ui_elements["browse_input_btn"].config(text=translations[lang]["browse"])
        self.ui_elements["api_key_label"].config(text=translations[lang]["api_key"])
        self.ui_elements["show_hide_btn"].config(text=translations[lang]["show_hide"])
        self.ui_elements["output_dir_label"].config(text=translations[lang]["output_dir"])
        self.ui_elements["browse_output_btn"].config(text=translations[lang]["browse"])
        self.ui_elements["params_frame"].config(text=translations[lang]["process_params"])
        self.ui_elements["content_label"].config(text=translations[lang]["content_type"])
        self.ui_elements["content_desc_label"].config(text=translations[lang]["content_desc"])
        self.ui_elements["target_lang_label"].config(text=translations[lang]["target_language"])
        self.ui_elements["max_length_label"].config(text=translations[lang]["max_length"])
        self.ui_elements["silence_length_label"].config(text=translations[lang]["silence_length"])
        self.ui_elements["silence_threshold_label"].config(text=translations[lang]["silence_threshold"])
        self.ui_elements["first_chunk_offset_label"].config(text=translations[lang]["first_chunk_offset"])
        self.ui_elements["cleanup_checkbox"].config(text=translations[lang]["cleanup"])
        self.start_button.config(text=translations[lang]["start_process"])
        self.stop_button.config(text=translations[lang]["stop_process"])
        self.ui_elements["progress_frame"].config(text=translations[lang]["progress"])
        self.ui_elements["retry_button"].config(text=translations[lang]["retry_combine"])
        self.ui_elements["open_error_file_button"].config(text=translations[lang]["open_error_file"])
        
        # 更新状态栏
        if self.waiting_for_user_fix:
            self.status_var.set(translations[lang]["waiting_for_fix"])
        else:
            self.status_var.set(translations[lang]["ready"])
        
        # 更新文件类型提示信息
        if self.input_file_path.get():
            if is_video_file(self.input_file_path.get()):
                self.file_type_var.set(translations[lang]["video_file"])
            else:
                self.file_type_var.set(translations[lang]["audio_file"])
        else:
            self.file_type_var.set(translations[lang]["file_not_selected"])

    def monitor_process(self):
        """监控处理进程，当进程完成时更新UI状态"""
        if not self.process:
            return
            
        # 等待进程完成
        self.process.join()
        
        # 如果进程自然完成（而不是被强制终止），更新UI状态
        if not self.processing:
            return  # 如果已经通过stop_processing更新了状态，不再处理
        
        # 如果在等待用户修复，则不改变界面状态
        if self.waiting_for_user_fix:
            return
            
        # 进程自然完成，更新UI状态
        elapsed = time.time() - self.start_time
        self.add_progress(f"\n处理完成! 总耗时: {elapsed:.2f}秒")
        
        self.processing = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_var.set(translations[self.current_language.get()]["ready"])
        
        # 显示处理完成的消息
        if self.output_dir_path.get():
            messagebox.showinfo(
                translations[self.current_language.get()]["complete"], 
                translations[self.current_language.get()]["complete_message"].format(output_dir=self.output_dir_path.get())
            )

if __name__ == "__main__":
    app = AudioProcessorGUI()
    app.mainloop()