"""
مراقبة استخدام الرام
"""

import psutil


class MemoryMonitor:
    """مراقبة استخدام الذاكرة"""
    
    def __init__(self):
        self.previous_usage = 0
    
    def get_ram_usage(self):
        """
        الحصول على نسبة استخدام الرام
        
        Returns:
            float: نسبة استخدام الرام (0-100)
        """
        memory = psutil.virtual_memory()
        self.previous_usage = memory.percent
        return memory.percent
    
    def get_ram_details(self):
        """
        الحصول على تفاصيل استخدام الرام
        
        Returns:
            dict: تفاصيل الرام
        """
        memory = psutil.virtual_memory()
        return {
            'total': memory.total,
            'available': memory.available,
            'percent': memory.percent,
            'used': memory.used,
            'free': memory.free
        }
    
    def get_swap_usage(self):
        """الحصول على استخدام الـ Swap"""
        swap = psutil.swap_memory()
        return {
            'total': swap.total,
            'used': swap.used,
            'percent': swap.percent
        }