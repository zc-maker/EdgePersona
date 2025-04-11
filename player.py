import logging
import os
import platform
import queue
import subprocess
import threading
import wave
import pyaudio
from pydub import  AudioSegment
import pygame
import sounddevice as sd
import numpy as np
from playsound import playsound
from live import Live2DManager


logger = logging.getLogger(__name__)


class AbstractPlayer(object):
    def __init__(self, *args, **kwargs):
        super(AbstractPlayer, self).__init__()
        self.is_playing = False
        self.play_queue = queue.Queue()
        self._stop_event = threading.Event()
        self.consumer_thread = threading.Thread(target=self._playing)
        self.consumer_thread.start()

    @staticmethod
    def to_wav(audio_file):
        tmp_file = audio_file + ".wav"
        wav_file = AudioSegment.from_file(audio_file)
        wav_file.export(tmp_file, format="wav")
        return tmp_file

    def _playing(self):
        while not self._stop_event.is_set():
            data = self.play_queue.get()
            self.is_playing = True
            try:
                self.do_playing(data)
            except Exception as e:
                logger.error(f"播放音频失败: {e}")
            finally:
                self.play_queue.task_done()
                self.is_playing = False

    def play(self, data):
        logger.info(f"play file {data}")
        audio_file = self.to_wav(data)
        self.play_queue.put(audio_file)

    def stop(self):
        self._clear_queue()

    def shutdown(self):
        self._clear_queue()
        self._stop_event.set()
        if self.consumer_thread.is_alive():
            self.consumer_thread.join()

    def get_playing_status(self):
        """正在播放和队列非空，为正在播放状态"""
        return self.is_playing or (not self.play_queue.empty())

    def _clear_queue(self):
        with self.play_queue.mutex:
            self.play_queue.queue.clear()

    def do_playing(self, audio_file):
        """播放音频的具体实现，由子类实现"""
        raise NotImplementedError("Subclasses must implement do_playing")


class CmdPlayer(AbstractPlayer):
    def __init__(self, *args, **kwargs):
        super(CmdPlayer, self).__init__(*args, **kwargs)
        self.p = pyaudio.PyAudio()

    def do_playing(self, audio_file):
        system = platform.system()
        cmd = ["afplay", audio_file] if system == "Darwin" else ["play", audio_file]
        logger.debug(f"Executing command: {' '.join(cmd)}")
        try:
            subprocess.run(cmd, shell=False, universal_newlines=True)
            logger.debug(f"播放完成：{audio_file}")
        except subprocess.CalledProcessError as e:
            logger.error(f"命令执行失败: {e}")
        except Exception as e:
            logger.error(f"未知错误: {e}")


class PyaudioPlayer(AbstractPlayer):
    def __init__(self, *args, **kwargs):
        super(PyaudioPlayer, self).__init__(*args, **kwargs)
        self.p = pyaudio.PyAudio()

    def do_playing(self, audio_file):
        chunk = 1024
        try:
            with wave.open(audio_file, 'rb') as wf:
                stream = self.p.open(format=self.p.get_format_from_width(wf.getsampwidth()),
                                     channels=wf.getnchannels(),
                                     rate=wf.getframerate(),
                                     output=True)
                data = wf.readframes(chunk)
                while data:
                    stream.write(data)
                    data = wf.readframes(chunk)
                stream.stop_stream()
                stream.close()
            logger.debug(f"播放完成：{audio_file}")
        except Exception as e:
            logger.error(f"播放音频失败: {e}")

    def stop(self):
        super().stop()
        if self.p:
            self.p.terminate()


class PygamePlayer(AbstractPlayer):
    def __init__(self, *args, **kwargs):
        super(PygamePlayer, self).__init__(*args, **kwargs)
        pygame.mixer.init()

    def do_playing(self, audio_file):
        try:
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(100)
            logger.debug("PygamePlayer 加载音频中")
            pygame.mixer.music.load(audio_file)
            logger.debug("PygamePlayer 加载音频结束，开始播放")
            pygame.mixer.music.play()
            logger.debug(f"播放完成：{audio_file}")
        except Exception as e:
            logger.error(f"播放音频失败: {e}")

    def get_playing_status(self):
        """正在播放和队列非空，为正在播放状态"""
        return self.is_playing or (not self.play_queue.empty()) or pygame.mixer.music.get_busy()

    def stop(self):
        super().stop()
        pygame.mixer.music.stop()

# class PygameSoundPlayer(AbstractPlayer):
#     """支持预加载"""
#     def __init__(self, *args, **kwargs):
#         super(PygameSoundPlayer, self).__init__(*args, **kwargs)
#         pygame.mixer.init()

#     def do_playing(self, current_sound):
#         try:
#             logger.debug("PygameSoundPlayer 播放音频中")
#             current_sound.play()  # 播放音频
#             while pygame.mixer.get_busy(): #current_sound.get_busy():  # 检查当前音频是否正在播放
#                 pygame.time.Clock().tick(100)  # 每秒检查100次
#             del current_sound
#             logger.debug(f"PygameSoundPlayer 播放完成")
#         except Exception as e:
#             logger.error(f"播放音频失败: {e}")

#     def play(self, data):
#         logger.info(f"play file {data}")
#         audio_file = self.to_wav(data)
#         sound = pygame.mixer.Sound(audio_file)
#         self.play_queue.put(sound)

#     def stop(self):
#         super().stop()

import math
import threading
import pygame
from pygame.locals import *
import time
import live2d.v3 as live2d
from live2d.utils.lipsync import WavHandler
import math
import time
import pygame
import live2d.v3 as live2d
from live2d.utils.lipsync import WavHandler
from pygame.locals import *
import multiprocessing as mp

      
        
class PygameSoundPlayer(AbstractPlayer):
    _instance = None  # 单例控制
    def __new__(cls, model_path="../../live2/models/兔兔/520兔兔.model3.json"):
        """单例模式保证进程安全"""
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._init_player(model_path)
        return cls._instance

    def _init_player(self, model_path):
        """实际初始化方法"""
        # 验证模型路径
        self.model_path = model_path

        # 父类初始化
        super().__init__()

        # 音频系统初始化
        pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=2048)

        # 进程间通信
        self.rms_value = mp.Value('d', 0.0)
        self.sync_flag = mp.Value('b', False)
        self.lipsync = WavHandler()

        # 启动独立渲染进程
        self.model_process = mp.Process(
            target=self._render_entry,
            args=(self.model_path, self.rms_value, self.sync_flag),
            daemon=True
        )
        self.model_process.start()
        time.sleep(1)  # 等待初始化

    @staticmethod
    def _render_entry(model_path, rms_value, sync_flag):
        """渲染进程入口（完全独立的环境）"""
        # 隔离初始化
        import pygame
        import live2d.v3 as live2d
        
        pygame.init()
        screen = pygame.display.set_mode((800, 600), DOUBLEBUF | OPENGL|RESIZABLE )
        live2d.init()
        if live2d.LIVE2D_VERSION == 3:
            live2d.glewInit()

        # 加载模型
        model = live2d.LAppModel()
        model.LoadModelJson(model_path)
        model.Resize(800, 600)
        model.SetExpression("hands")

        # 渲染循环
        clock = pygame.time.Clock()
        while True:
            # 事件处理
            for event in pygame.event.get():
                if event.type == QUIT or (event.type == KEYDOWN and event.key == K_q):
                    return

            # 获取RMS值
            current_rms = rms_value.value if sync_flag.value else 0.1 + math.sin(time.time() * 3) * 0.05

            # 更新模型
            model.SetParameterValue("ParamMouthOpenY", current_rms)
            model.Update()

            # 渲染
            live2d.clearBuffer(1.0, 1.0, 1.0, 1.0)
            model.Draw()
            pygame.display.flip()
            clock.tick(60)

    def play(self, data):
            """重写播放方法"""
            audio_file = self.to_wav(data)
            sound = pygame.mixer.Sound(audio_file)
            self.play_queue.put((sound,audio_file))
    def do_playing(self, sound):
        """带口型同步的播放实现"""
        try:
            # 初始化音频分析
            sound,audio_file=sound
            # wav_path = sound.filename
            
            self.lipsync.Start(audio_file)

            # 播放控制
            channel = pygame.mixer.Channel(0)
            self.sync_flag.value = True
            channel.play(sound)

            # 实时分析循环
            while channel.get_busy():
                if self.lipsync.Update():
                    with self.rms_value.get_lock():
                        self.rms_value.value = self.lipsync.GetRms() * 2.5
                pygame.time.Clock().tick(100)  # 100Hz采样

        except Exception as e:
            logger.error(f"播放失败: {str(e)}")
        finally:
            self.sync_flag.value = False
            # self.lipsync.Stop()

    def shutdown(self):
        """安全关闭"""
        if self.model_process.is_alive():
            self.model_process.terminate()
        pygame.mixer.quit()
        super().shutdown()        


class SoundDevicePlayer(AbstractPlayer):
    def do_playing(self, audio_file):
        try:
            wf = wave.open(audio_file, 'rb')
            data = wf.readframes(wf.getnframes())
            sd.play(np.frombuffer(data, dtype=np.int16), samplerate=wf.getframerate())
            sd.wait()
            logger.debug(f"播放完成：{audio_file}")
        except Exception as e:
            logger.error(f"播放音频失败: {e}")

    def stop(self):
        super().stop()
        sd.stop()


class PydubPlayer(AbstractPlayer):
    def do_playing(self, audio_file):
        try:
            audio = AudioSegment.from_file(audio_file)
            audio.play()
            logger.debug(f"播放完成：{audio_file}")
        except Exception as e:
            logger.error(f"播放音频失败: {e}")

    def stop(self):
        super().stop()
        # Pydub does not provide a stop method


class PlaysoundPlayer(AbstractPlayer):
    def do_playing(self, audio_file):
        try:
            playsound(audio_file)
            logger.debug(f"播放完成：{audio_file}")
        except Exception as e:
            logger.error(f"播放音频失败: {e}")

    def stop(self):
        super().stop()
        # playsound does not provide a stop method


def create_instance(class_name, *args, **kwargs):
    # 获取类对象
    cls = globals().get(class_name)
    if cls:
        # 创建并返回实例
        print(args,kwargs)
        return cls(*args, **kwargs)
    else:
        raise ValueError(f"Class {class_name} not found")
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
class EnhancedModel:
    def __init__(self, model_path):
        """增强的Live2D模型控制器"""
        self.model = live2d.LAppModel()
        
        # 验证模型路径
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
        print(f"加载模型中: {model_path}")
        
        self.model.LoadModelJson(model_path)
        
        # 获取模型信息
        self.motion_groups = self.model.GetMotionGroups()
        self.param_ids = self.model.GetParamIds()
        self.mouth_params = [p for p in self.param_ids if "Mouth" in p]
        
        print("== 可用动作组 ==")
        for group in self.motion_groups:
            print(f"{group}: {self.motion_groups[group]} motions")
            
        print("== 嘴部参数 ==")
        for p in self.mouth_params:
            print(p)

    def start_motion(self, group_name, priority=3):
        """安全启动动作"""
        if group_name in self.motion_groups:
            print(f"触发动作: {group_name} (优先级 {priority})")
            self.model.StartRandomMotion(group_name, priority)
        else:
            print(f"动作组不存在: {group_name}")

    def update_mouth(self, value):
        """更新所有嘴部参数（线程安全）"""
        for param in self.mouth_params:
            clamped_value = max(0.0, min(value, 1.0))
            self.model.SetParameterValue(param, clamped_value)

class LipSyncController:
    def __init__(self):
        self.wav_handler = WavHandler()
        self.is_playing = False
        self.lip_factor = 20  # 增大口型系数
        self.lock = threading.Lock()
        self.audio_thread = None
        
    def play(self, audio_path):
        """启动音频播放（线程安全）"""
        if self.is_playing:
            self.stop()
            
        try:
            # 初始化音频系统
            if pygame.mixer.get_init() is None:
                # pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
                pygame.mixer.init()
                
            # 启动音频线程
            self.audio_thread = threading.Thread(target=self._audio_worker, args=(audio_path,))
            # self.audio_thread.daemon = True
            self.is_playing = True
            self.audio_thread.start()
            return True
        except Exception as e:
            print(f"音频播放失败: {str(e)}")
            return False

    def _audio_worker(self, audio_path):
        """音频处理线程"""
        try:
            print(f"加载音频: {audio_path}")
            pygame.mixer.Sound(audio_path).play()
            self.wav_handler.Start(audio_path)
            
            # 实时处理音频数据
            while pygame.mixer.get_busy():
                    if self.wav_handler.Update():
                        rms = self.wav_handler.GetRms()
                        # 传递到主线程更新嘴型
                        self.current_rms = rms * self.lip_factor
                    pygame.time.Clock().tick(60)  # 每秒检查100次
                # time.sleep(0.01)  # 防止CPU占用过高
                
        except Exception as e:
            print(f"音频线程错误: {str(e)}")
        finally:
            self.is_playing = False

    def stop(self):
        """停止播放"""
        if self.is_playing:
            pygame.mixer.music.stop()
            self.audio_thread.join(timeout=1)
            self.is_playing = False