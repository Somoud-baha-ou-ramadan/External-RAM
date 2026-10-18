"""
أدوات للتعامل مع النظام
"""

import psutil
import platform
import subprocess
import shutil


class SystemUtils:
    """أدوات مساعدة للنظام"""
    
    @staticmethod
    def is_process_running(pid):
        """التحقق من وجود عملية قيد التشغيل"""
        try:
            proc = psutil.Process(pid)
            return proc.is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    
    @staticmethod
    def get_system_info():
        """الحصول على معلومات النظام"""
        try:
            return {
                'os': platform.system(),
                'os_version': platform.version(),
                'processor': platform.processor(),
                'ram_total': psutil.virtual_memory().total,
                'ram_total_gb': psutil.virtual_memory().total / (1024**3),
                'cpu_count': psutil.cpu_count(),
                'python_version': platform.python_version()
            }
        except Exception as e:
            return {'error': str(e)}
    
    @staticmethod
    def get_disk_usage(path='/'):
        """الحصول على استخدام القرص"""
        try:
            usage = shutil.disk_usage(path)
            return {
                'total': usage.total,
                'used': usage.used,
                'free': usage.free,
                'percent': (usage.used / usage.total) * 100,
                'total_gb': usage.total / (1024**3),
                'used_gb': usage.used / (1024**3),
                'free_gb': usage.free / (1024**3)
            }
        except Exception:
            return None
    
    @staticmethod
    def kill_process(pid):
        """إنهاء عملية"""
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            # انتظر قليلاً لإنهاء العملية
            proc.wait(timeout=3)
            return True
        except psutil.TimeoutExpired:
            # إذا لم تنتهِ، قم بقتلها
            try:
                proc.kill()
                return True
            except:
                return False
        except Exception:
            return False