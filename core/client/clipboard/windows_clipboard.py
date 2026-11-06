"""
Windows 剪贴板快照

粘贴识别结果或读取选中文字前，保存剪贴板里的全部格式（文字、图片、文件等），
用完原样放回。无法无损保存的格式会抛 ClipboardUnavailable，调用方改用直接输入。
用户在这期间自己复制了新内容时，不覆盖它。
"""
import win32clipboard as wcb
import win32con
import win32gui

CF_BITMAP, CF_DIB, CF_UNICODETEXT, CF_DIBV5 = 2, 8, 13, 17
# 这些格式在 pywin32 里是句柄或结构指针，按字节写回无法还原
_HANDLE_FORMATS = {2, 3, 9, 14, 15, 0x80, 0x82, 0x83, 0x8E}


class ClipboardUnavailable(RuntimeError):
    pass


class WindowsClipboard:
    def __init__(self):
        # 写剪贴板需要一个所属窗口；这是不可见的消息窗口
        self._hwnd = win32gui.CreateWindowEx(
            0, 'STATIC', 'CapsWriter Clipboard', 0, 0, 0, 0, 0,
            win32con.HWND_MESSAGE, 0, 0, None)
        self._saved = None
        self._sequence = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        win32gui.DestroyWindow(self._hwnd)

    def _open(self):
        wcb.OpenClipboard(self._hwnd)

    def _snapshot(self):
        formats, current = [], 0
        while current := wcb.EnumClipboardFormats(current):
            formats.append(current)
        saved = {}
        if CF_BITMAP in formats:
            # 位图句柄清空后失效；存自包含的 DIB，系统会据此重新合成位图
            dib = next((f for f in (CF_DIBV5, CF_DIB) if f in formats), None)
            if dib is None:
                raise ClipboardUnavailable('位图无法安全保存')
            saved[dib] = wcb.GetClipboardData(dib)
        for fmt in formats:
            if fmt in saved or fmt == CF_BITMAP:
                continue
            if fmt in _HANDLE_FORMATS or 0x200 <= fmt <= 0x2FF:
                raise ClipboardUnavailable(f'剪贴板格式 {fmt} 无法安全保存')
            data = wcb.GetClipboardData(fmt)
            if not isinstance(data, (bytes, str)):
                raise ClipboardUnavailable(f'剪贴板格式 {fmt} 无法安全保存')
            saved[fmt] = data
        return saved

    def save(self):
        """保存当前剪贴板，并记下序号用于判断之后是否被改动"""
        self._open()
        try:
            self._saved = self._snapshot()
            self._sequence = wcb.GetClipboardSequenceNumber()
        finally:
            wcb.CloseClipboard()

    def set_text(self, text):
        self._open()
        try:
            wcb.EmptyClipboard()
            wcb.SetClipboardData(CF_UNICODETEXT, text)
        finally:
            wcb.CloseClipboard()
        # 关闭时系统会补出其他文字格式，序号要在关闭之后读
        self._sequence = wcb.GetClipboardSequenceNumber()

    def copied_text(self):
        """读取 Ctrl+C 之后的文字；剪贴板没变化说明没有选中内容"""
        self._open()
        try:
            sequence = wcb.GetClipboardSequenceNumber()
            if sequence == self._sequence:
                return ''
            self._sequence = sequence
            if not wcb.IsClipboardFormatAvailable(CF_UNICODETEXT):
                return ''
            return wcb.GetClipboardData(CF_UNICODETEXT)
        finally:
            wcb.CloseClipboard()

    def restore(self):
        """剪贴板仍是本程序写入的内容时，放回原内容"""
        if self._saved is None:
            return
        self._open()
        try:
            if wcb.GetClipboardSequenceNumber() == self._sequence:
                wcb.EmptyClipboard()
                for fmt, data in self._saved.items():
                    wcb.SetClipboardData(fmt, data)
        finally:
            wcb.CloseClipboard()
