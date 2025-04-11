import asyncio
import logging
import os
import subprocess
import time
import uuid
import wave
from abc import ABC, ABCMeta, abstractmethod
from datetime import datetime
import pyaudio
from pydub import AudioSegment
from gtts import gTTS
import edge_tts
import ChatTTS
import torch
import torchaudio
import soundfile as sf

logger = logging.getLogger(__name__)


class AbstractTTS(ABC):
    __metaclass__ = ABCMeta

    @abstractmethod
    def to_tts(self, text):
        pass


class GTTS(AbstractTTS):
    def __init__(self, config):
        self.output_file = config.get("output_file")
        self.lang = config.get("lang")

    def _generate_filename(self, extension=".aiff"):
        return os.path.join(self.output_file, f"tts-{datetime.now().date()}@{uuid.uuid4().hex}{extension}")

    def _log_execution_time(self, start_time):
        end_time = time.time()
        execution_time = end_time - start_time
        logger.debug(f"执行时间: {execution_time:.2f} 秒")

    def to_tts(self, text):
        tmpfile = self._generate_filename(".aiff")
        try:
            start_time = time.time()
            tts = gTTS(text=text, lang=self.lang)
            tts.save(tmpfile)
            self._log_execution_time(start_time)
            return tmpfile
        except Exception as e:
            logger.debug(f"生成TTS文件失败: {e}")
            return None


class MacTTS(AbstractTTS):
    """
    macOS 系统自带的TTS
    voice: say -v ? 可以打印所有语音
    """

    def __init__(self, config):
        super().__init__()
        self.voice = config.get("voice")
        self.output_file = config.get("output_file")

    def _generate_filename(self, extension=".aiff"):
        return os.path.join(self.output_file, f"tts-{datetime.now().date()}@{uuid.uuid4().hex}{extension}")

    def _log_execution_time(self, start_time):
        end_time = time.time()
        execution_time = end_time - start_time
        logger.debug(f"执行时间: {execution_time:.2f} 秒")

    def to_tts(self, phrase):
        logger.debug(f"正在转换的tts：{phrase}")
        tmpfile = self._generate_filename(".aiff")
        try:
            start_time = time.time()
            res = subprocess.run(
                ["say", "-v", self.voice, "-o", tmpfile, phrase],
                shell=False,
                universal_newlines=True,
            )
            self._log_execution_time(start_time)
            if res.returncode == 0:
                return tmpfile
            else:
                logger.info("TTS 生成失败")
                return None
        except Exception as e:
            logger.info(f"执行TTS失败: {e}")
            return None


class EdgeTTS(AbstractTTS):
    def __init__(self, config):
        self.output_file = config.get("output_file", "tmp/")
        self.voice = config.get("voice")

    def _generate_filename(self, extension=".wav"):
        return os.path.join(self.output_file, f"tts-{datetime.now().date()}@{uuid.uuid4().hex}{extension}")

    def _log_execution_time(self, start_time):
        end_time = time.time()
        execution_time = end_time - start_time
        logger.debug(f"Execution Time: {execution_time:.2f} seconds")

    async def text_to_speak(self, text, output_file):
        print(f"正在转换的tts：{text}")
        communicate = edge_tts.Communicate(text, voice=self.voice)  # Use your preferred voice
        print(f"转换的tts：{text}")
        await communicate.save(output_file)

    def to_tts(self, text):
        tmpfile = self._generate_filename(".wav")
        start_time = time.time()
        try:
            asyncio.run(self.text_to_speak(text, tmpfile))
            self._log_execution_time(start_time)
            return tmpfile
        except Exception as e:
            logger.info(f"Failed to generate TTS file: {e}")
            return None


class CHATTTS(AbstractTTS):
    def __init__(self, config):
        self.output_file = config.get("output_file", ".")
        self.chat = ChatTTS.Chat()
        self.chat.load(compile=False)  # Set to True for better performance
        self.rand_spk = self.chat.sample_random_speaker()

    def _generate_filename(self, extension=".wav"):
        return os.path.join(self.output_file, f"tts-{datetime.now().date()}@{uuid.uuid4().hex}{extension}")

    def _log_execution_time(self, start_time):
        end_time = time.time()
        execution_time = end_time - start_time
        logger.debug(f"Execution Time: {execution_time:.2f} seconds")

    def to_tts(self, text):
        tmpfile = self._generate_filename(".wav")
        start_time = time.time()
        try:
            params_infer_code = ChatTTS.Chat.InferCodeParams(
                spk_emb=self.rand_spk,  # add sampled speaker
                temperature=.3,  # using custom temperature
                top_P=0.7,  # top P decode
                top_K=20,  # top K decode
            )
            params_refine_text = ChatTTS.Chat.RefineTextParams(
                prompt='[oral_2][laugh_0][break_6]',
            )
            wavs = self.chat.infer(
                [text],
                params_refine_text=params_refine_text,
                params_infer_code=params_infer_code,
            )
            try:
                torchaudio.save(tmpfile, torch.from_numpy(wavs[0]).unsqueeze(0), 24000)
            except:
                torchaudio.save(tmpfile, torch.from_numpy(wavs[0]), 24000)
            self._log_execution_time(start_time)
            return tmpfile
        except Exception as e:
            logger.error(f"Failed to generate TTS file: {e}")
            return None



class KOKOROTTS(AbstractTTS):
    def __init__(self, config):
        from kokoro import KPipeline
        self.output_file = config.get("output_file", ".")
        self.lang = config.get("lang", "z")
        print(f"KOKOROTTS: lang: {self.lang}")
        self.pipeline = KPipeline(lang_code=self.lang)  # <= make sure lang_code matches voice
        self.voice = config.get("voice", "zm_yunyang")

    def _generate_filename(self, extension=".wav"):
        return os.path.join(self.output_file, f"tts-{datetime.now().date()}@{uuid.uuid4().hex}{extension}")

    def _log_execution_time(self, start_time):
        end_time = time.time()
        execution_time = end_time - start_time
        logger.debug(f"Execution Time: {execution_time:.2f} seconds")

    def to_tts(self, text):
        tmpfile = self._generate_filename(".wav")
        start_time = time.time()
        try:
            generator = self.pipeline(
                text, voice=self.voice,  # <= change voice here
                speed=1, split_pattern=r'\n+'
            )
            for i, (gs, ps, audio) in enumerate(generator):
                logger.debug(f"KOKOROTTS: i: {i}, gs：{gs}, ps：{ps}")  # i => index
                sf.write(tmpfile, audio, 24000)  # save each audio file
            self._log_execution_time(start_time)
            return tmpfile
        except Exception as e:
            logger.error(f"Failed to generate TTS file: {e}")
            return None



def create_instance(class_name, *args, **kwargs):
    # 获取类对象
    cls = globals().get(class_name)
    if cls:
        # 创建并返回实例
        return cls(*args, **kwargs)
    else:
        raise ValueError(f"Class {class_name} not found")




import sys
sys.path.append('third_party/Matcha-TTS')
import numpy as np
from cosyvoice.cli.cosyvoice import CosyVoice2
from cosyvoice.utils.file_utils import load_wav



class CosyVoice2TTS:
    def __init__(self,config):
        """保持与KOKOROTTS完全相同的初始化接口"""
        # 硬编码参数（保持项目统一配置）
        self.model_path = "pretrained_models/CosyVoice2-0.5B"
        # self.ref_dir = "./voices"  # 参考语音目录
        
        # 从config读取参数
        self.output_file = "./tmp"

        
        # 初始化引擎
        # self._load_reference()
        ref_path = 'your.wav'
        self.sample_rate = 16000  # 保持与KOKOROTTS相同采样率
        self.ref_audio = load_wav(ref_path, self.sample_rate)
        
        self._init_model()
       

    def _init_model(self):
        """模型初始化（对应KPipeline初始化）"""
        self.model = CosyVoice2(
            self.model_path,
            load_jit=True,
            load_trt=True,
            fp16=True
        )
              
        
        for i in range(10):
            # 流式生成（禁用文本切割）
            generator = self.model.inference_zero_shot(
                "这是一个热启动文本，用于后续加速",  # 直接传入完整文本
                prompt_text="your.wav文本",
                prompt_speech_16k=self.ref_audio,
                stream=True,
            )
            for chunk in generator:
                audio = chunk['tts_speech'].numpy().T
                # sf.write(tmpfile, audio, 24000) 
                continue


    def _generate_filename(self, extension=".wav"):
        """保持完全相同的文件名生成逻辑"""
        return os.path.join(
            self.output_file, 
            f"tts-{datetime.now().date()}@{uuid.uuid4().hex}{extension}"
        )

    def _log_execution_time(self, start_time):
        """完全相同的耗时记录方法"""
        execution_time = time.time() - start_time
        logger.debug(f"Execution Time: {execution_time:.2f} seconds")
    def _log_execution_time(self, start_time):
        """相同的耗时日志格式"""
        execution_time = time.time() - start_time
        logger.debug(f"Execution Time: {execution_time:.2f} seconds")
    def to_tts(self, text):
        """保持完全相同的接口规范"""
        tmpfile = self._generate_filename()
        start_time = time.time()
        
        try:
            # 流式生成（禁用文本切割）
            generator = self.model.inference_zero_shot(
                text,  # 直接传入完整文本
                prompt_text="今天天气真是太好了，阳光灿烂，心情超级棒！但是，朋友最近的感情问题也让我心痛不已，好像世界末日一样，真的好为她难过哦！",
                prompt_speech_16k=self.ref_audio,
                stream=True,
            )
            
            # 保存音频文件
            # audio_chunks = []
            for chunk in generator:
                audio = chunk['tts_speech'].numpy().T
                # audio_chunks.append(audio)
                sf.write(tmpfile, audio, 24000) 
            # 合并写入文件（对应sf.write）
            # full_audio = np.concatenate(audio_chunks)
            
            
            self._log_execution_time(start_time)
            return tmpfile
        except Exception as e:
            logger.error(f"Failed to generate TTS file: {str(e)}")
            if os.path.exists(tmpfile):
                os.remove(tmpfile)
            return None
        
        
if __name__ == "__main__":
    tts = CosyVoice2TTS(config={})
    audio_path = tts.to_tts("今天天气真好，我们一起去公园散步吧！")
    audio_path = tts.to_tts("今天天气真好，我们一起去公园散步吧！")
    audio_path = tts.to_tts("今天天气真好，我们一起去公园散步吧！")