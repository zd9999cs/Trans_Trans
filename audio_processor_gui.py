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
from datetime import datetime

# 导入主调用脚本中的处理函数和视频检测函数
try:
    from process_audio import run_pipeline, is_video_file
except ImportError as e:
    print(f"错误：无法导入process_audio.py模块。确保该文件在同一目录下。详细错误: {e}")
    sys.exit(1)

class AudioProcessorGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        
        # 设置窗口标题和大小
        self.title("音频/视频转录与字幕生成工具")
        self.geometry("800x700")
        self.minsize(700, 600)
        
        # 创建变量
        self.input_file_path = tk.StringVar()  # 改名从input_audio_path为input_file_path
        self.output_dir_path = tk.StringVar()
        self.api_key = tk.StringVar()
        self.content_choice = tk.StringVar(value="both")
        self.max_length = tk.IntVar(value=300)
        self.silence_length = tk.IntVar(value=500)
        self.silence_threshold = tk.IntVar(value=-40)
        self.first_chunk_offset = tk.DoubleVar(value=0.0)
        self.cleanup = tk.BooleanVar(value=False)
        
        # 存储当前处理状态
        self.processing = False
        self.process_thread = None
        
        # 创建进度队列
        self.progress_queue = queue.Queue()
        
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
        
        # 创建输入框架
        input_frame = ttk.LabelFrame(main_frame, text="基本设置", padding="10")
        input_frame.pack(fill=tk.X, pady=5)
        
        # 输入文件（音频或视频）
        ttk.Label(input_frame, text="输入文件(音频/视频):").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(input_frame, textvariable=self.input_file_path, width=50).grid(row=0, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
        ttk.Button(input_frame, text="浏览...", command=self.browse_input_file).grid(row=0, column=2, sticky=tk.W, pady=5)
        
        # 文件类型指示器
        self.file_type_var = tk.StringVar(value="未选择文件")
        ttk.Label(input_frame, textvariable=self.file_type_var, foreground="blue").grid(row=0, column=3, sticky=tk.W, pady=5, padx=5)
        
        # API密钥
        ttk.Label(input_frame, text="Google AI API密钥:").grid(row=1, column=0, sticky=tk.W, pady=5)
        api_key_entry = ttk.Entry(input_frame, textvariable=self.api_key, width=50, show="*")
        api_key_entry.grid(row=1, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
        ttk.Button(input_frame, text="显示/隐藏", command=lambda: self.toggle_api_key_visibility(api_key_entry)).grid(row=1, column=2, sticky=tk.W, pady=5)
        
        # 如果有环境变量API_KEY，就使用它
        env_api_key = os.environ.get("GOOGLE_API_KEY")
        if env_api_key:
            self.api_key.set(env_api_key)
        
        # 输出目录
        ttk.Label(input_frame, text="输出目录 (可选):").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(input_frame, textvariable=self.output_dir_path, width=50).grid(row=2, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
        ttk.Button(input_frame, text="浏览...", command=self.browse_output_dir).grid(row=2, column=2, sticky=tk.W, pady=5)
        
        # 创建参数框架
        params_frame = ttk.LabelFrame(main_frame, text="处理参数", padding="10")
        params_frame.pack(fill=tk.X, pady=5)
        
        # 创建参数网格
        # 内容选择
        ttk.Label(params_frame, text="字幕内容:").grid(row=0, column=0, sticky=tk.W, pady=5)
        content_combo = ttk.Combobox(params_frame, textvariable=self.content_choice, width=15)
        content_combo['values'] = ('transcript', 'translation', 'both')
        content_combo.current(2)  # 默认选择 'both'
        content_combo.grid(row=0, column=1, sticky=tk.W, pady=5)
        ttk.Label(params_frame, text="(transcript:仅转录, translation:仅翻译, both:两者)").grid(row=0, column=2, sticky=tk.W, pady=5)
        
        # 音频切分参数
        ttk.Label(params_frame, text="最大片段长度(秒):").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Spinbox(params_frame, from_=60, to=900, increment=30, textvariable=self.max_length, width=5).grid(row=1, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(params_frame, text="静音检测长度(毫秒):").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Spinbox(params_frame, from_=100, to=2000, increment=100, textvariable=self.silence_length, width=5).grid(row=2, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(params_frame, text="静音阈值(dB):").grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Spinbox(params_frame, from_=-60, to=-20, increment=5, textvariable=self.silence_threshold, width=5).grid(row=3, column=1, sticky=tk.W, pady=5)
        
        # 字幕参数
        ttk.Label(params_frame, text="首个片段偏移(秒):").grid(row=4, column=0, sticky=tk.W, pady=5)
        ttk.Spinbox(params_frame, from_=-5.0, to=5.0, increment=0.1, textvariable=self.first_chunk_offset, width=5).grid(row=4, column=1, sticky=tk.W, pady=5)
        
        # 清理选项
        ttk.Checkbutton(params_frame, text="处理完成后删除中间文件", variable=self.cleanup).grid(row=5, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        # 创建按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        # 添加按钮
        self.start_button = ttk.Button(button_frame, text="开始处理", command=self.start_processing)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(button_frame, text="停止处理", command=self.stop_processing, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # 创建进度框架
        progress_frame = ttk.LabelFrame(main_frame, text="处理进度", padding="10")
        progress_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 添加进度显示
        self.progress_text = scrolledtext.ScrolledText(progress_frame, wrap=tk.WORD, height=15)
        self.progress_text.pack(fill=tk.BOTH, expand=True)
        self.progress_text.config(state=tk.DISABLED)
        
        # 底部状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def toggle_api_key_visibility(self, entry):
        """切换API密钥的可见性"""
        if entry.cget('show') == '*':
            entry.config(show='')
        else:
            entry.config(show='*')
    
    def browse_input_file(self):
        """打开文件浏览器选择输入文件（音频或视频）"""
        filetypes = (
            ("所有支持的文件", "*.mp3 *.wav *.flac *.m4a *.aac *.ogg *.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v"),
            ("音频文件", "*.mp3 *.wav *.flac *.m4a *.aac *.ogg"),
            ("视频文件", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v"),
            ("所有文件", "*.*")
        )
        filepath = filedialog.askopenfilename(
            title="选择音频或视频文件",
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
                self.file_type_var.set("视频文件 (将自动转换为MP3)")
            else:
                self.file_type_var.set("音频文件")
    
    def browse_output_dir(self):
        """打开文件浏览器选择输出目录"""
        dirpath = filedialog.askdirectory(
            title="选择输出目录"
        )
        
        if dirpath:
            self.output_dir_path.set(dirpath)
    
    def start_processing(self):
        """开始处理音频文件"""
        # 检查必要参数
        if not self.input_file_path.get():
            messagebox.showerror("错误", "请选择输入文件(音频或视频)")
            return
        
        if not self.api_key.get():
            messagebox.showerror("错误", "请输入Google AI API密钥")
            return
        
        # 确认处理
        if not messagebox.askyesno("确认", "确定要开始处理吗？\n这可能需要一段时间，具体取决于文件长度。"):
            return
        
        # 准备参数
        params = {
            'input_audio': self.input_file_path.get(),  # 保持与process_audio.py兼容
            'output_dir': self.output_dir_path.get(),
            'api_key': self.api_key.get(),
            'content': self.content_choice.get(),
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
        self.status_var.set("处理中...")
        
        # 清空进度显示
        self.progress_text.config(state=tk.NORMAL)
        self.progress_text.delete(1.0, tk.END)
        self.progress_text.config(state=tk.DISABLED)
        
        # 记录开始时间
        self.start_time = time.time()
        
        # 启动线程
        self.process_thread = threading.Thread(
            target=self.run_processing_thread,
            args=(params,),
            daemon=True
        )
        self.process_thread.start()
    
    def run_processing_thread(self, params):
        """在单独的线程中运行处理流程"""
        try:
            # 在进度显示中添加开始信息
            filepath = params['input_audio']
            filename = os.path.basename(filepath)
            
            # 确定文件类型
            file_type = "视频" if is_video_file(filepath) else "音频"
            
            self.add_progress(f"开始处理{file_type}文件: {filename}")
            self.add_progress(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.add_progress("-" * 50)
            
            # 调用处理函数
            success = run_pipeline(params, self.progress_queue)
            
            # 处理完成后更新UI
            if success:
                elapsed = time.time() - self.start_time
                self.add_progress(f"\n处理成功完成！总耗时: {elapsed:.2f}秒")
                messagebox.showinfo("完成", f"处理已完成！\n输出目录: {params['output_dir']}")
            else:
                self.add_progress("\n处理失败。请查看上方错误信息。")
                messagebox.showerror("错误", "处理失败。请查看详细日志。")
        except Exception as e:
            # 处理意外错误
            self.add_progress(f"\n发生意外错误: {str(e)}")
            messagebox.showerror("错误", f"处理过程中发生错误:\n{str(e)}")
        finally:
            # 恢复UI状态
            self.processing = False
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.status_var.set("就绪")
    
    def stop_processing(self):
        """停止处理（目前只是逻辑预留，由于子进程不能轻易中断，实际中断操作需要更复杂的机制）"""
        if not self.processing:
            return
        
        if messagebox.askyesno("确认", "确定要停止处理吗？\n当前进度将丢失。"):
            self.add_progress("\n用户手动停止处理。")
            self.status_var.set("已停止")
            self.processing = False
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            
            # 注意：这只改变了UI状态，但实际上处理线程可能仍在继续
            # 想要完全停止处理需要更复杂的机制，例如在处理函数中检查取消标志
    
    def check_queue(self):
        """检查进度队列，更新进度显示"""
        try:
            while True:
                # 从队列中获取消息
                message = self.progress_queue.get_nowait()
                self.add_progress(message)
                self.progress_queue.task_done()
        except queue.Empty:
            pass
        
        # 每100毫秒检查一次队列
        self.after(100, self.check_queue)
    
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
            if not messagebox.askyesno("确认", "处理正在进行中。确定要退出吗？"):
                return
        
        self.destroy()

if __name__ == "__main__":
    app = AudioProcessorGUI()
    app.mainloop()