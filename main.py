#!/usr/bin/env python3
"""
نقطة البداية لتشغيل نظام Smart SSD Virtual RAM
"""

import time
import signal
import sys
import threading
from pathlib import Path

import psutil

# إضافة المسار الرئيسي للـ PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from config import settings
from core.memory_monitor import MemoryMonitor
from core.process_manager import ProcessManager
from core.cache_manager import CacheManager
from core.performance_logger import PerformanceLogger


class SmartSSDVirtualRAM:
    """الفئة الرئيسية للنظام"""
    
    def __init__(self):
        self.running = False
        self._stop_event = threading.Event()
        self.memory_monitor = MemoryMonitor()
        self.process_manager = ProcessManager()
        self.cache_manager = CacheManager()
        self.logger = PerformanceLogger()
        self.cached_processes = {}
        self.cache_count = 0
        self.last_cached_time = 0
        self._last_ram_print = 0.0
        self._last_ram_log = 0.0
        self._last_high_ram_log = 0.0
        
        # إعداد معالجة إشارات الإيقاف
        # (signal handlers only work in the main thread - the UI runs the engine in a worker thread)
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGINT, self.stop)
            signal.signal(signal.SIGTERM, self.stop)
        
    def start(self):
        """بدء تشغيل النظام"""
        self.running = True
        self.logger.log_event("SYSTEM_START", "بدء تشغيل النظام")
        print("🚀 Smart SSD Virtual RAM System Started")
        print(f"📊 Monitoring RAM every {settings.CHECK_INTERVAL_SECONDS} seconds")
        print(f"⚙️  RAM Threshold: {settings.RAM_THRESHOLD_PERCENT}%")
        print("-" * 50)
        
        try:
            while not self._stop_event.is_set():
                try:
                    self._monitoring_cycle()
                except Exception as e:
                    self.logger.log_event("CYCLE_ERROR", f"خطأ في دورة المراقبة: {str(e)}")
                    print(f"⚠️ خطأ في دورة المراقبة: {e}")
                
                self._stop_event.wait(settings.CHECK_INTERVAL_SECONDS)
                
        except KeyboardInterrupt:
            print("\n⚠️ تم استلام إشارة إيقاف")
        except Exception as e:
            self.logger.log_event("SYSTEM_ERROR", f"خطأ في النظام: {str(e)}")
            print(f"❌ خطأ في النظام: {e}")
        finally:
            self.cleanup()
    
    def _monitoring_cycle(self):
        """دورة المراقبة الرئيسية"""
        try:
            # التحقق من استخدام الرام
            ram_usage = self.memory_monitor.get_ram_usage()
            ram_details = self.memory_monitor.get_ram_details()
            
            # عرض معلومات الرام بشكل دوري
            now = time.time()
            if now - self._last_ram_print >= 10:
                self._last_ram_print = now
                print(f"📊 استخدام الرام: {ram_usage}% (مستخدم: {ram_details['used']/(1024**3):.1f}GB / {ram_details['total']/(1024**3):.1f}GB)")
            
            # تسجيل كل 5 دورات لتجنب كثافة السجلات
            if now - self._last_ram_log >= 30:
                self._last_ram_log = now
                self.logger.log_event("RAM_USAGE", f"استخدام الرام: {ram_usage}%")
            
            if ram_usage > settings.RAM_THRESHOLD_PERCENT:
                self._handle_high_ram_usage(ram_usage)
            else:
                self._check_and_restore_processes()
                
        except Exception as e:
            self.logger.log_event("MONITOR_ERROR", f"خطأ في المراقبة: {str(e)}")
            print(f"❌ خطأ في المراقبة: {e}")
    
    def _handle_high_ram_usage(self, ram_usage):
        """معالجة حالة ارتفاع استخدام الرام"""
        current_time = time.time()
        print(f"⚠️ ارتفاع استخدام الرام: {ram_usage}%")
        # Log at most once a minute (it used to log every 5 s: thousands of rows)
        if current_time - self._last_high_ram_log >= 60:
            self._last_high_ram_log = current_time
            self.logger.log_event("HIGH_RAM", f"ارتفاع في استخدام الرام: {ram_usage}%")
        
        # منع التخزين المتكرر لنفس العملية خلال فترة قصيرة
        if current_time - self.last_cached_time < settings.MIN_SECONDS_BETWEEN_CACHES:
            return
        
        # الحصول على العملية الأكثر استهلاكاً
        top_process = self.process_manager.get_top_memory_process()
        
        if top_process and top_process['pid'] not in self.cached_processes:
            memory_mb = top_process['memory_rss'] / (1024 * 1024)
            print(f"📦 تخزين العملية: {top_process['name']} (PID: {top_process['pid']}) - {memory_mb:.1f} MB")
            
            # التحقق من عدد العمليات المخزنة
            if len(self.cached_processes) >= settings.MAX_PROCESSES_TO_CACHE:
                print(f"⚠️ تم الوصول للحد الأقصى للعمليات المخزنة ({settings.MAX_PROCESSES_TO_CACHE})")
                # حذف أقدم عملية مخزنة
                oldest_pid = min(self.cached_processes.keys(), 
                                key=lambda p: self.cached_processes[p]['timestamp'])
                print(f"🗑️ حذف أقدم عملية: {oldest_pid}")
                self.cache_manager.cleanup_process_cache(oldest_pid)
                del self.cached_processes[oldest_pid]
            
            # نقل العملية إلى الكاش
            success = self.cache_manager.cache_process(top_process)
            
            if success:
                self.cached_processes[top_process['pid']] = {
                    'process': top_process,
                    'timestamp': current_time
                }
                self.cache_count += 1
                self.last_cached_time = current_time
                self.logger.log_event(
                    "PROCESS_CACHED", 
                    f"تم تخزين العملية {top_process['name']} (PID: {top_process['pid']}) - {memory_mb:.1f} MB"
                )
                print(f"✅ تم تخزين العملية بنجاح (المخزنة حالياً: {len(self.cached_processes)})")
                
                # عرض قائمة العمليات المخزنة
                self._show_cached_processes()
            else:
                print(f"❌ فشل في تخزين العملية")
        elif top_process:
            print(f"ℹ️ العملية {top_process['name']} (PID: {top_process['pid']}) مخزنة مسبقاً")
        else:
            print("ℹ️ لا توجد عمليات مناسبة للتخزين")
    
    def _show_cached_processes(self):
        """عرض العمليات المخزنة حالياً"""
        if self.cached_processes:
            print("\n📋 العمليات المخزنة حالياً:")
            for pid, info in self.cached_processes.items():
                proc = info['process']
                memory_mb = proc['memory_rss'] / (1024 * 1024)
                print(f"   - {proc['name']} (PID: {pid}) - {memory_mb:.1f} MB")
            print()
    
    def _check_and_restore_processes(self):
        """التحقق وإعادة العمليات المخزنة إذا كان هناك مساحة كافية"""
        ram_usage = self.memory_monitor.get_ram_usage()
        
        # إذا كان هناك مساحة كافية، حاول استعادة العمليات
        if ram_usage < (settings.RAM_THRESHOLD_PERCENT - 15):
            for pid, cache_info in list(self.cached_processes.items()):
                if not self._is_process_running(pid):
                    # العملية انتهت - تنظيف الكاش
                    print(f"🧹 تنظيف كاش العملية المنتهية: {cache_info['process']['name']} (PID: {pid})")
                    self.cache_manager.cleanup_process_cache(pid)
                    del self.cached_processes[pid]
                    self.logger.log_event("CACHE_CLEANUP", f"تنظيف كاش العملية المنتهية {pid}")
                else:
                    # محاولة استعادة العملية
                    print(f"🔄 استعادة العملية: {cache_info['process']['name']} (PID: {pid})")
                    self.cache_manager.restore_process(pid)
                    del self.cached_processes[pid]
                    print(f"✅ تم استعادة العملية")
    
    def _is_process_running(self, pid):
        """التحقق من وجود عملية"""
        try:
            return psutil.Process(pid).is_running()
        except psutil.Error:
            return False
    
    def stop(self, signum=None, frame=None):
        """إيقاف التشغيل"""
        if self._stop_event.is_set():
            return  # already stopping
        self._stop_event.set()
        print("\n🛑 جاري إيقاف النظام...")
        self.logger.log_event("SYSTEM_STOP", "إيقاف تشغيل النظام")
        self.running = False
    
    def cleanup(self):
        """تنظيف الموارد قبل الخروج"""
        print("🧹 جاري تنظيف الموارد...")
        if self.cached_processes:
            print(f"📦 عدد العمليات المخزنة: {len(self.cached_processes)}")
        self.cache_manager.cleanup_all()
        self.logger.close()
        print("✅ تم إيقاف النظام بنجاح")


if __name__ == "__main__":
    system = SmartSSDVirtualRAM()
    system.start()