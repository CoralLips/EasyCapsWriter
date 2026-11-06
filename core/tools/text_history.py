"""文字记录容量上限：年/月/ 目录下的听写与 LLM 记录总量超限时，删掉最旧的文件。"""
import re
from pathlib import Path

_YEAR = re.compile(r'\d{4}')
_MONTH = re.compile(r'0[1-9]|1[0-2]')
_RECORD = re.compile(r'\d{2}(-.+)?\.md')   # 日记 DD.md，LLM 记录 DD-角色.md


def enforce_limit(base_dir, max_bytes: int) -> None:
    files = [f for year in Path(base_dir).iterdir() if year.is_dir() and _YEAR.fullmatch(year.name)
             for month in year.iterdir() if month.is_dir() and _MONTH.fullmatch(month.name)
             for f in month.iterdir() if f.is_file() and _RECORD.fullmatch(f.name)]
    files.sort(key=lambda f: f.stat().st_mtime)
    total = sum(f.stat().st_size for f in files)
    while total > max_bytes and len(files) > 1:
        oldest = files.pop(0)
        total -= oldest.stat().st_size
        oldest.unlink()
    if files and total > max_bytes:
        # 只剩当天一个文件仍超限：保留末尾部分
        tail = files[0].read_bytes()[-max_bytes:]
        files[0].write_bytes(tail.decode('utf-8', errors='ignore').encode('utf-8'))
