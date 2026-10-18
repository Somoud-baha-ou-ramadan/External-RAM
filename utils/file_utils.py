"""
أدوات للتعامل مع الملفات والمجلدات
"""

import os
import shutil
import hashlib
from pathlib import Path


def ensure_dir(directory):
    """التأكد من وجود المجلد، وإنشائه إذا لم يكن موجوداً"""
    Path(directory).mkdir(parents=True, exist_ok=True)
    return directory


def safe_delete(path):
    """حذف آمن لملف أو مجلد"""
    try:
        if os.path.isfile(path):
            os.remove(path)
        elif os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        return True
    except Exception as e:
        print(f"خطأ في حذف {path}: {e}")
        return False


def get_file_hash(filepath, blocksize=65536):
    """الحصول على هاش SHA256 للملف"""
    sha256 = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            for block in iter(lambda: f.read(blocksize), b''):
                sha256.update(block)
        return sha256.hexdigest()
    except Exception:
        return None


def get_size_format(size_bytes):
    """تحويل حجم البايت إلى صيغة مقروءة"""
    if size_bytes == 0:
        return "0B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    while size >= 1024 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.2f} {size_names[i]}"