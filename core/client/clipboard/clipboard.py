# coding: utf-8
"""
剪贴板工具模块

提供统一的剪贴板操作接口，包括：
1. 安全读取剪贴板（支持多种编码）
2. 安全写入剪贴板
3. 剪贴板保存/恢复上下文管理器
4. 粘贴文本（模拟 Ctrl+V）
5. 读取选中文字（模拟 Ctrl+C）

Windows 下保存并恢复剪贴板的全部格式（含图片、文件），见 windows_clipboard。
"""
import asyncio
import platform
import time
from contextlib import contextmanager
import keyboard as typing_keyboard
import pyclip
from pynput import keyboard
from . import logger


# 支持的编码列表
CLIPBOARD_ENCODINGS = ['utf-8', 'gbk', 'utf-16', 'latin1']


def safe_paste() -> str:
    """
    安全地从剪贴板读取并解码文本

    尝试多种编码方式，确保能够正确读取

    Returns:
        解码后的文本字符串，失败返回空字符串
    """
    try:
        clipboard_data = pyclip.paste()

        # 尝试多种编码方式
        for encoding in CLIPBOARD_ENCODINGS:
            try:
                return clipboard_data.decode(encoding)
            except (UnicodeDecodeError, AttributeError):
                continue

        # 如果所有编码都失败，返回空字符串
        logger.debug(f"剪贴板解码失败，尝试了编码: {CLIPBOARD_ENCODINGS}")
        return ""

    except Exception as e:
        logger.warning(f"剪贴板读取失败: {e}")
        return ""


def safe_copy(content: str) -> bool:
    """
    安全地复制内容到剪贴板

    Args:
        content: 要复制的内容

    Returns:
        是否成功
    """
    if not content:
        return False

    try:
        pyclip.copy(content)
        logger.debug(f"剪贴板写入成功，长度: {len(content)}")
        return True
    except Exception as e:
        logger.warning(f"剪贴板写入失败: {e}")
        return False


def copy_to_clipboard(content: str):
    """
    复制内容到剪贴板（兼容旧 API）

    Args:
        content: 要复制的内容
    """
    safe_copy(content)


@contextmanager
def save_and_restore_clipboard():
    """
    剪贴板保存/恢复上下文管理器

    用法:
        with save_and_restore_clipboard():
            # 在这里操作剪贴板
            pyclip.copy("临时内容")
        # 退出后剪贴板恢复原内容
    """
    original = safe_paste()
    try:
        yield
    finally:
        if original:
            pyclip.copy(original)
            logger.debug("剪贴板已恢复")


async def paste_text(text: str, restore_clipboard: bool = True):
    """
    通过模拟 Ctrl+V 粘贴文本

    Args:
        text: 要粘贴的文本
        restore_clipboard: 粘贴后是否恢复原剪贴板内容
    """
    if platform.system() == 'Windows':
        return await _paste_windows(text, restore_clipboard)

    # 保存剪切板
    original = ''
    if restore_clipboard:
        try:
            original = safe_paste()
        except:
            pass

    # 复制要粘贴的文本
    pyclip.copy(text)
    logger.debug(f"已复制文本到剪贴板，长度: {len(text)}")

    _send_paste_key()

    # 还原剪贴板
    if restore_clipboard and original:
        await asyncio.sleep(0.1)
        pyclip.copy(original)
        logger.debug("剪贴板已恢复")


def _send_paste_key() -> None:
    """模拟 Ctrl+V（macOS 为 Command+V）"""
    controller = keyboard.Controller()
    modifier = keyboard.Key.cmd if platform.system() == 'Darwin' else keyboard.Key.ctrl
    with controller.pressed(modifier):
        controller.tap('v')
    logger.debug("已发送粘贴命令 (Ctrl+V)")


async def _paste_windows(text: str, restore_clipboard: bool) -> None:
    from .windows_clipboard import WindowsClipboard, ClipboardUnavailable
    with WindowsClipboard() as clip:
        try:
            if restore_clipboard:
                clip.save()
        except ClipboardUnavailable as exc:
            logger.warning(f"剪贴板内容无法安全保存，改为直接输入: {exc}")
            typing_keyboard.write(text)
            return
        clip.set_text(text)
        _send_paste_key()
        if restore_clipboard:
            await asyncio.sleep(0.1)  # 等目标程序读走再恢复
            clip.restore()
            logger.debug("剪贴板已恢复")


def copy_selected_text() -> str:
    """模拟 Ctrl+C 读取选中文字，读完恢复原剪贴板；没有选中内容时返回空字符串"""
    if platform.system() != 'Windows':
        original = safe_paste()
        typing_keyboard.press_and_release('ctrl+c')
        time.sleep(0.1)
        selected = safe_paste()
        pyclip.copy(original)
        return '' if selected == original else selected

    from .windows_clipboard import WindowsClipboard, ClipboardUnavailable
    with WindowsClipboard() as clip:
        try:
            clip.save()
        except ClipboardUnavailable as exc:
            logger.warning(f"剪贴板内容无法安全保存，本次不读取选中文字: {exc}")
            return ''
        typing_keyboard.press_and_release('ctrl+c')
        time.sleep(0.1)
        selected = clip.copied_text()
        clip.restore()
        return selected
