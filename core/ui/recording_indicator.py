"""右下角状态浮窗：录音计时与短提示共用同一种样式。"""
import logging
import threading
import time

logger = logging.getLogger(__name__)

_OK = '#1F6F3F'
_ERROR = '#B3261E'
_STYLE = dict(font_size=10, fg='white', initial_width=260, window_type='label', markdown=False)


def tip(text: str, error: bool = False) -> None:
    """右下角短提示，几秒后自动消失。"""
    try:
        from core.ui.toast import toast
        toast(text, bg=_ERROR if error else _OK, duration=3500 if error else 1800, **_STYLE)
    except Exception:
        logger.debug('提示浮窗不可用', exc_info=True)


def prewarm() -> None:
    """启动时先建好浮窗线程，避免第一次按录音键时卡一下。"""
    from core.ui.toast import ToastMessageManager
    threading.Thread(target=ToastMessageManager, daemon=True).start()


class _RecordingIndicator:
    def __init__(self) -> None:
        self._msg_id = None
        self._stop = threading.Event()

    def show(self, label) -> None:
        """label() 返回当前状态文字，如「🎤 录音」；计时由这里追加。"""
        from core.ui.toast import ToastMessageManager, ToastMessage
        self.hide()
        manager = ToastMessageManager()
        started = time.monotonic()

        def text():
            seconds = int(time.monotonic() - started)
            return f'{label()}  {seconds // 60}:{seconds % 60:02d}'

        msg_id = manager.add_message(ToastMessage(text=text(), bg=_OK, duration=0, **_STYLE))
        stop = threading.Event()
        self._msg_id, self._stop = msg_id, stop

        def tick():
            while not stop.wait(0.25):
                manager.update_label(msg_id, text())
        threading.Thread(target=tick, daemon=True, name='CapsWriter-indicator').start()

    def hide(self) -> None:
        self._stop.set()
        if self._msg_id:
            from core.ui.toast import ToastMessageManager
            ToastMessageManager().close_toast(self._msg_id)
            self._msg_id = None


indicator = _RecordingIndicator()
