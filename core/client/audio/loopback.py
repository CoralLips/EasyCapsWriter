# coding: utf-8
"""
系统音混录

按 system_audio_key（默认 F3）在「仅麦克风」与「麦克风 + 系统音」之间切换。
系统音用 WASAPI loopback 采集，录音回调里与麦克风数据相加；
不装虚拟声卡，不改系统音频路由，采集失败就回到仅麦克风。
"""
import ctypes
import threading

import numpy as np

from core.ui.recording_indicator import tip
from . import logger

_BLOCK = 2400   # 每次读取的采样点数，与麦克风流的块大小一致
_CAP = 4800     # 缓冲上限（0.1 秒），不积攒旧的系统音


class SystemAudio:
    def __init__(self, samplerate: int = 48000) -> None:
        self.samplerate = samplerate
        self.on = False       # 用户选择了混录
        self.ready = False    # 采集设备已打开
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.Lock()
        self._buf = np.zeros(0, dtype='float32')
        self._recording = False

    def toggle(self) -> None:
        if self.on:
            self.stop()
            tip('🎤 仅麦克风')
            return
        self.on = True
        self._stop = threading.Event()
        # 新线程先等旧线程释放设备，按键钩子里不做任何等待
        self._thread = threading.Thread(
            target=self._run, args=(self._stop, self._thread),
            name='CapsWriter-loopback', daemon=True)
        self._thread.start()
        tip('正在开启系统音')

    def stop(self) -> None:
        self.on = self.ready = False
        self._stop.set()
        with self._lock:
            self._buf = np.zeros(0, dtype='float32')

    def begin_recording(self) -> None:
        with self._lock:
            self._recording = True
            self._buf = np.zeros(0, dtype='float32')

    def end_recording(self) -> None:
        with self._lock:
            self._recording = False
            self._buf = np.zeros(0, dtype='float32')

    def _run(self, stop: threading.Event, previous) -> None:
        if previous is not None:
            previous.join()
        if stop.is_set():
            return
        com = ctypes.windll.ole32.CoInitializeEx(None, 0) in (0, 1)
        try:
            import soundcard as sc
            speaker = sc.default_speaker()
            device = sc.get_microphone(id=speaker.id, include_loopback=True)
            with device.recorder(samplerate=self.samplerate, channels=1) as rec:
                if stop.is_set():
                    return
                self.ready = True
                logger.info('系统音采集已就绪: %s', speaker.name)
                tip('🔊 已含系统音')
                while not stop.is_set():
                    block = rec.record(numframes=_BLOCK).reshape(-1).astype('float32')
                    with self._lock:
                        if self._recording and not stop.is_set():
                            self._buf = np.concatenate((self._buf, block))[-_CAP:]
        except Exception as exc:
            logger.warning('系统音采集失败: %s', exc)
            if not stop.is_set():
                self.stop()
                tip(f'系统音采集失败，已回到仅麦克风：{exc}', error=True)
        finally:
            if com:
                ctypes.windll.ole32.CoUninitialize()

    def mix(self, indata: np.ndarray) -> np.ndarray:
        """把系统音加进麦克风数据 (frames, channels)；没有系统音时原样复制。"""
        if not self.ready:
            return indata.copy()
        frames = indata.shape[0]
        with self._lock:
            block, self._buf = self._buf[:frames], self._buf[frames:]
        if not len(block):
            return indata.copy()
        mixed = indata.astype('float32', copy=True)
        mixed[:len(block)] += block[:, None]
        return np.clip(mixed, -1.0, 1.0)


system_audio = SystemAudio()
