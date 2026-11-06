# coding: utf-8
"""
音频流管理模块

后台线程跟随 Windows 默认麦克风：插拔耳麦、切换默认设备或流意外中断时，
自动关闭旧流并在新设备上重开，不退出程序。
"""

from __future__ import annotations

import asyncio
import ctypes
import threading
import time
from typing import TYPE_CHECKING, Optional

import sounddevice as sd
import soundcard as sc

from core.client.state import console
from core.ui.recording_indicator import tip
from .loopback import system_audio
from . import logger

if TYPE_CHECKING:
    from ..app import CapsWriterClient


PERMISSION_HINT = """
[bold red]检测到麦克风被占用或权限异常（错误码 -9999）[/bold red]
请尝试以下解决方案：

  1. 设置 > 隐私和安全性 > 麦克风，将「允许桌面应用访问麦克风」打开
  2. 状态栏右下角音量图标 > 右键菜单 > 声音 > 麦克风的属性，关闭「允许应用程序独占控制该设备」
  3. 状态栏右下角音量图标 > 右键菜单 > 声音 > 麦克风的属性，关闭「增强效果」
"""


class AudioStreamManager:
    SAMPLE_RATE = 48000
    BLOCK_DURATION = 0.05  # 50ms
    POLL_INTERVAL = 0.5
    RETRY_INTERVAL = 2.0

    def __init__(self, app: CapsWriterClient):
        self.app = app
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._reopen = threading.Event()
        self._thread = None
        self._device_id = None
        self._last_callback = 0.0
        self._last_notice = None
        self._hint_shown = False

    @property
    def state(self):
        return self.app.state

    @property
    def ready(self) -> bool:
        return self._ready.is_set()

    def _notify(self, message: str, error: bool = False) -> None:
        if message == self._last_notice:
            return
        self._last_notice = message
        logger.info(message)
        console.print(message)
        tip(message, error=error)

    def _audio_callback(self, indata, frames, time_info, status) -> None:
        self._last_callback = time.monotonic()
        if not self.state.recording or not self.app.loop:
            return
        asyncio.run_coroutine_threadsafe(
            self.state.queue_in.put({
                'type': 'data', 'time': time.time(), 'data': system_audio.mix(indata),
            }),
            self.app.loop,
        )

    def _on_stream_finished(self) -> None:
        # PortAudio 回调里不能关闭或重开自己的流，交给后台线程处理
        self._ready.clear()
        self._reopen.set()

    @staticmethod
    def _default_microphone():
        """实时查询 Windows 默认麦克风，返回 (id, name)；没有可用麦克风时返回 None。"""
        try:
            mic = sc.default_microphone()
        except RuntimeError as exc:
            if '0x80070490' in str(exc).lower():  # E_NOTFOUND：当前没有默认输入
                return None
            raise
        if 'steam streaming' in mic.name.casefold():
            return None  # 不自动使用 Steam 虚拟麦克风
        return mic.id, mic.name

    @staticmethod
    def _select_input(name: str):
        # 按 WASAPI 设备全名匹配，避免 MME 名称截断与过期的设备序号
        hosts = sd.query_hostapis()
        for index, device in enumerate(sd.query_devices()):
            if (device['name'] == name and device['max_input_channels'] > 0
                    and hosts[device['hostapi']]['name'] == 'Windows WASAPI'):
                return index, min(2, device['max_input_channels'])
        raise RuntimeError('默认麦克风尚未就绪: ' + name)

    def _close_stream(self) -> None:
        self._ready.clear()
        stream, self.state.stream = self.state.stream, None
        self._device_id = None
        if stream is not None:
            stream.close()

    def _finish_interrupted_recording(self) -> None:
        owner = self.state.recording_owner
        if owner is not None:
            owner.finish()

    def _recover(self, target) -> None:
        if self.state.recording:
            self.app.loop.call_soon_threadsafe(self._finish_interrupted_recording)
            self._notify('麦克风已切换或断开，本次录音已结束', error=True)
        self._close_stream()
        self._reopen.clear()
        if target is None:
            self._notify('等待麦克风连接', error=True)
            return

        # 关闭旧流后重载 PortAudio，才能看到新插入的设备
        sd._terminate()
        sd._initialize()
        device_id, name = target
        index, channels = self._select_input(name)
        stream = sd.InputStream(
            samplerate=self.SAMPLE_RATE,
            blocksize=int(self.BLOCK_DURATION * self.SAMPLE_RATE),
            device=index, dtype='float32', channels=channels,
            extra_settings=sd.WasapiSettings(auto_convert=True),
            callback=self._audio_callback, finished_callback=self._on_stream_finished,
        )
        self.state.stream = stream
        self._last_callback = time.monotonic()
        stream.start()
        self._device_id = device_id
        self._ready.set()
        self._notify('麦克风已连接：' + name)
        logger.info('音频流已启动: 设备=%s, 声道数=%s', name, channels)

    def _needs_recovery(self, target) -> bool:
        if self._reopen.is_set() or (target[0] if target else None) != self._device_id:
            return True
        if target is None:
            return self._last_notice is None  # 启动时没有麦克风，也要提示一次
        stream = self.state.stream
        return stream is None or not stream.active or time.monotonic() - self._last_callback > 3.0

    def _monitor(self) -> None:
        com = ctypes.windll.ole32.CoInitializeEx(None, 0) in (0, 1)
        try:
            while not self._stop.is_set():
                try:
                    target = self._default_microphone()
                    if self._needs_recovery(target):
                        self._recover(target)
                except Exception as exc:
                    self._ready.clear()
                    self._reopen.set()
                    logger.warning('音频设备恢复失败: %s', exc)
                    self._notify('麦克风暂不可用，正在自动重连', error=True)
                    if '-9999' in str(exc) and not self._hint_shown:
                        self._hint_shown = True
                        console.print(PERMISSION_HINT)
                    self._stop.wait(self.RETRY_INTERVAL)
                self._stop.wait(self.POLL_INTERVAL)
        finally:
            self._close_stream()
            if com:
                ctypes.windll.ole32.CoUninitialize()

    def start(self) -> Optional[sd.InputStream]:
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._monitor, name='CapsWriter-microphone', daemon=True)
            self._thread.start()
        return self.state.stream

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=3.0)

    def reopen(self) -> Optional[sd.InputStream]:
        """托盘「重启音频」：交给后台线程重开"""
        self._ready.clear()
        self._reopen.set()
        return self.state.stream
