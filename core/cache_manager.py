"""
إدارة الكاش على SSD مع التنظيف التلقائي وأسماء حقيقية للملفات
"""

import os
import shutil
import json
import time
import threading
import re
import sys
from pathlib import Path
from datetime import datetime, timedelta
from config import settings


class CacheManager:
    """إدارة تخزين العمليات على SSD مع التنظيف التلقائي وأسماء حقيقية"""
    
    def __init__(self):
        self.cache_dir = settings.CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.active_caches = {}
        # RLock: cleanup is called while the lock is already held (was a deadlock with Lock)
        self.lock = threading.RLock()
        self._stop_event = threading.Event()
        
        # تحميل معلومات الكاش السابقة عند بدء التشغيل (before the thread starts)
        self._load_existing_cache_info()

        # بدء خلفية التنظيف التلقائي
        self.cleanup_thread = threading.Thread(target=self._auto_cleanup_loop, daemon=True)
        self.cleanup_thread.start()
    
    def _sanitize_filename(self, name):
        """
        تنظيف اسم الملف ليكون صالحاً لأنظمة الملفات
        
        Args:
            name: اسم العملية الأصلي
            
        Returns:
            str: اسم صالح للملف
        """
        # استبدال المسافات والرموز غير الصالحة بشرطة سفلية
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
        sanitized = re.sub(r'\s+', '_', sanitized)
        # إزالة أي رموز غير مرغوب فيها
        sanitized = ''.join(c for c in sanitized if c.isalnum() or c in '._-')
        # التأكد من أن الاسم ليس فارغاً
        if not sanitized:
            sanitized = "unknown_process"
        # الحد من طول الاسم
        return sanitized[:100]
    
    def _get_process_folder_name(self, pid, process_name, timestamp):
        """
        إنشاء اسم مجلد مناسب للعملية
        
        Args:
            pid: معرف العملية
            process_name: اسم العملية الحقيقي
            timestamp: الطابع الزمني
            
        Returns:
            str: اسم المجلد (مثلاً: Blender_PID_1234_20240315_143022)
        """
        safe_name = self._sanitize_filename(process_name)
        time_str = datetime.fromtimestamp(timestamp).strftime("%Y%m%d_%H%M%S")
        
        # صيغة: اسم_العملية_PID_الرقم_التاريخ
        return f"{safe_name}_PID_{pid}_{time_str}"
    
    def _extract_process_info_from_folder(self, folder_name):
        """
        استخراج معلومات العملية من اسم المجلد
        
        Args:
            folder_name: اسم المجلد
            
        Returns:
            dict: معلومات مستخرجة أو None
        """
        try:
            # نمط البحث: اسم_PID_رقم_تاريخ
            pattern = r'(.+)_PID_(\d+)_(\d{8}_\d{6})'
            match = re.match(pattern, folder_name)
            
            if match:
                process_name = match.group(1)
                pid = int(match.group(2))
                timestamp_str = match.group(3)
                timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S").timestamp()
                
                return {
                    'name': process_name,
                    'pid': pid,
                    'timestamp': timestamp,
                    'folder_name': folder_name
                }
        except:
            pass
        return None
    
    def _load_existing_cache_info(self):
        """تحميل معلومات الكاش الموجود. Only folders created by this tool are touched."""
        try:
            for process_dir in self.cache_dir.glob("*_PID_*"):
                if not process_dir.is_dir():
                    continue
                folder_info = self._extract_process_info_from_folder(process_dir.name)
                info_file = process_dir / "process_info.json"
                if not folder_info or not info_file.exists():
                    # Not ours (or a leftover from an older version): leave it alone.
                    continue
                try:
                    with open(info_file, 'r', encoding='utf-8') as f:
                        json.load(f)
                except (OSError, ValueError):
                    print(f"⚠️ ملف تالف، يتم حذفه: {process_dir.name}")
                    shutil.rmtree(process_dir, ignore_errors=True)
                    continue
                with self.lock:
                    self.active_caches[folder_info['pid']] = {
                        'path': process_dir,
                        'timestamp': folder_info['timestamp'],
                        'size': self._get_dir_size(process_dir),
                        'process_name': folder_info['name'],
                        'auto_cleanup': True,
                        'folder_name': process_dir.name,
                    }
                print(f"✅ تم تحميل كاش: {process_dir.name}")
        except Exception as e:
            print(f"خطأ في تحميل معلومات الكاش: {e}")

    def _auto_cleanup_loop(self):
        """حلقة التنظيف التلقائي في الخلفية"""
        while not self._stop_event.is_set():
            try:
                self._cleanup_orphaned_caches()
                self._cleanup_old_caches(settings.CACHE_MAX_AGE_HOURS)
            except Exception as e:
                print(f"خطأ في دورة التنظيف التلقائي: {e}")
            self._stop_event.wait(60)  # فحص كل دقيقة
    
    def _cleanup_orphaned_caches(self):
        """تنظيف الكاش للعمليات المنتهية"""
        import psutil
        
        # عمل نسخة من المفاتيح لتجنب مشاكل التعديل أثناء التكرار
        with self.lock:
            pids = list(self.active_caches.keys())
        
        for pid in pids:
            try:
                # التحقق إذا كانت العملية لا تزال موجودة
                proc = psutil.Process(pid)
                if not proc.is_running():
                    self._cleanup_process_cache(pid, reason="انتهت العملية")
            except psutil.NoSuchProcess:
                # العملية غير موجودة - نظف الكاش
                self._cleanup_process_cache(pid, reason="انتهت العملية")
            except psutil.AccessDenied:
                # Process exists but is protected: it is still alive, keep its cache
                continue
            except Exception as e:
                print(f"خطأ في فحص العملية {pid}: {e}")
    
    def _cleanup_old_caches(self, max_age_hours=24):
        """
        تنظيف الكاش القديم (أقدم من 24 ساعة)
        
        Args:
            max_age_hours: أقصى عمر مسموح للكاش بالساعات
        """
        cutoff_time = time.time() - (max_age_hours * 3600)
        
        with self.lock:
            pids = list(self.active_caches.keys())
            
        for pid in pids:
            with self.lock:
                cache_info = self.active_caches.get(pid)
            if cache_info and cache_info['timestamp'] < cutoff_time:
                process_name = cache_info.get('process_name', 'unknown')
                self._cleanup_process_cache(pid, reason=f"انتهت صلاحية الكاش (أكثر من {max_age_hours} ساعة)")
    
    def cache_process(self, process_info):
        """
        تخزين بيانات عملية على SSD
        
        Args:
            process_info: معلومات العملية
            
        Returns:
            bool: نجاح أو فشل العملية
        """
        try:
            pid = process_info['pid']
            process_name = process_info['name']
            timestamp = time.time()
            
            # إذا كان هناك كاش سابق لنفس العملية، احذفه أولاً
            if pid in self.active_caches:
                self._cleanup_process_cache(pid, reason="تحديث الكاش")

            
            # إنشاء اسم مجلد وصفي
            folder_name = self._get_process_folder_name(pid, process_name, timestamp)
            process_dir = self.cache_dir / folder_name
            process_dir.mkdir(parents=True, exist_ok=True)
            
            # تخزين معلومات العملية (JSON, not pickle: loading pickle from disk can run code)
            info_file = process_dir / "process_info.json"
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(process_info, f, ensure_ascii=False, indent=2, default=str)
            
            # إنشاء ملف تعريف يحتوي على وقت الإنشاء ومدة الصلاحية
            metadata = {
                'pid': pid,
                'process_name': process_name,
                'created_at': timestamp,
                'expires_at': timestamp + (settings.CACHE_MAX_AGE_HOURS * 3600),
                'last_accessed': timestamp,
                'folder_name': folder_name
            }
            
            meta_file = process_dir / "metadata.json"
            with open(meta_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            # إنشاء ملف README مع معلومات مفيدة
            self._create_readme_file(process_dir, process_info, metadata)
            
            # محاكاة نقل بيانات العملية
            self._simulate_data_transfer(process_dir, process_info)
            
            with self.lock:
                self.active_caches[pid] = {
                    'path': process_dir,
                    'timestamp': timestamp,
                    'size': self._get_dir_size(process_dir),
                    'process_name': process_name,
                    'auto_cleanup': True,
                    'metadata': metadata,
                    'folder_name': folder_name
                }
            
            # Enforce the global size cap now that the new dump is counted
            self._enforce_size_cap()

            # تسجيل العملية في ملف منفصل للتتبع
            self._log_cache_operation("CACHE_CREATED", pid, process_name, folder_name)
            
            print(f"✅ تم تخزين: {folder_name}")
            
            return True
            
        except Exception as e:
            print(f"❌ خطأ في تخزين العملية: {e}")
            return False
    
    def _create_readme_file(self, process_dir, process_info, metadata):
        """
        إنشاء ملف README مع معلومات مفيدة عن العملية المخزنة
        
        Args:
            process_dir: مجلد العملية
            process_info: معلومات العملية
            metadata: البيانات الوصفية
        """
        try:
            readme_path = process_dir / "README.txt"
            created_time = datetime.fromtimestamp(metadata['created_at']).strftime("%Y-%m-%d %H:%M:%S")
            expires_time = datetime.fromtimestamp(metadata['expires_at']).strftime("%Y-%m-%d %H:%M:%S")
            
            content = f"""
==================================================
معلومات العملية المخزنة في Smart SSD Virtual RAM
==================================================

اسم العملية: {process_info['name']}
معرف العملية (PID): {process_info['pid']}
تاريخ التخزين: {created_time}
تاريخ انتهاء الصلاحية: {expires_time}

معلومات إضافية:
- حجم الذاكرة المستخدمة: {process_info.get('memory_rss', 0) / (1024*1024):.2f} MB
- نسبة استخدام الذاكرة من الرام: {process_info.get('memory_percent', 0):.2f}%

ملاحظات:
- هذا المجلد يحتوي على بيانات مؤقتة للعملية
- سيتم حذفه تلقائياً عند انتهاء العملية أو بعد 24 ساعة
- لا تقم بحذف هذا المجلد يدوياً إلا إذا كنت متأكداً

--------------------------------------------------
تم إنشاؤه بواسطة Smart SSD Virtual RAM
"""
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            print(f"⚠️ خطأ في إنشاء README: {e}")
    
    def _enforce_size_cap(self):
        """Delete the oldest caches until the folder fits MAX_CACHE_SIZE_MB."""
        limit = settings.MAX_CACHE_SIZE_MB * 1024 * 1024
        while True:
            with self.lock:
                total = sum(c['size'] for c in self.active_caches.values())
                if total <= limit or not self.active_caches:
                    return
                oldest = min(self.active_caches, key=lambda p: self.active_caches[p]['timestamp'])
            self._cleanup_process_cache(oldest, reason="تجاوز الحد الأقصى لحجم الكاش")

    def _cleanup_process_cache(self, pid, reason="غير محدد"):
        """تنظيف داخلي لكاش عملية محددة"""
        with self.lock:
            if pid not in self.active_caches:
                return
            
            cache_info = self.active_caches[pid]
            cache_path = cache_info['path']
            process_name = cache_info.get('process_name', 'unknown')
            folder_name = cache_info.get('folder_name', 'unknown')
            
            try:
                if cache_path.exists():
                    # تسجيل عملية التنظيف قبل الحذف
                    self._log_cache_operation("CACHE_CLEANED", pid, process_name, folder_name, reason)
                    
                    # حذف المجلد بالكامل
                    shutil.rmtree(cache_path, ignore_errors=True)
                    print(f"🧹 تم تنظيف: {folder_name} - السبب: {reason}")
                
                del self.active_caches[pid]
                
            except Exception as e:
                print(f"⚠️ خطأ في تنظيف كاش العملية {pid}: {e}")
    
    def cleanup_process_cache(self, pid):
        """واجهة عامة لتنظيف كاش عملية محددة"""
        self._cleanup_process_cache(pid, reason="طلب يدوي")
    
    def _log_cache_operation(self, operation, pid, process_name, folder_name="", reason=""):
        """تسجيل عمليات الكاش في ملف منفصل"""
        try:
            log_file = settings.LOGS_DIR / "cache_operations.log"
            settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            log_entry = f"[{timestamp}] {operation} - PID: {pid}, Name: {process_name}"
            if folder_name:
                log_entry += f", Folder: {folder_name}"
            if reason:
                log_entry += f", Reason: {reason}"
            log_entry += "\n"
            
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except Exception as e:
            print(f"⚠️ خطأ في تسجيل العملية: {e}")
    
    def _simulate_data_transfer(self, process_dir, process_info):
        """محاكاة نقل البيانات"""
        memory_bytes = process_info.get('memory_rss', 100 * 1024 * 1024)
        data_size_mb = memory_bytes / (1024 * 1024)
        
        # تحديد حجم الملف (حد أقصى 10 ميجابايت لتجنب استهلاك مساحة كبيرة)
        max_size_bytes = settings.MAX_DUMP_SIZE_MB * 1024 * 1024
        data_size_bytes = int(min(memory_bytes, max_size_bytes))
        
        # إنشاء ملف بيانات مع اسم واضح
        data_file = process_dir / f"memory_dump_{int(time.time())}.bin"
        try:
            with open(data_file, 'wb') as f:
                # NOTE: prototype - writes placeholder bytes, it does not copy real process memory.
                block = settings.CACHE_BLOCK_SIZE_KB * 1024
                remaining = data_size_bytes
                while remaining > 0:
                    chunk = min(block, remaining)
                    f.write(os.urandom(chunk))
                    remaining -= chunk
        except Exception as e:
            print(f"⚠️ خطأ في محاكاة نقل البيانات: {e}")
    
    def restore_process(self, pid):
        """
        استعادة عملية من الكاش
        
        Returns:
            bool: نجاح أو فشل الاستعادة
        """
        with self.lock:
            if pid not in self.active_caches:
                return False
            
            cache_info = self.active_caches[pid]
            process_dir = cache_info['path']
            process_name = cache_info.get('process_name', 'unknown')
            folder_name = cache_info.get('folder_name', 'unknown')
        
        try:
            # تحديث وقت آخر وصول
            meta_file = process_dir / "metadata.json"
            if meta_file.exists():
                with open(meta_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                metadata['last_accessed'] = time.time()
                with open(meta_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2)
            
            self._log_cache_operation("PROCESS_RESTORED", pid, process_name, folder_name)
            print(f"🔄 تمت استعادة: {folder_name}")
            # Once restored, the cached copy is no longer needed
            self._cleanup_process_cache(pid, reason="تمت الاستعادة")
            
            return True
            
        except Exception as e:
            print(f"❌ خطأ في استعادة العملية: {e}")
            return False
    
    def list_cached_processes(self):
        """
        عرض قائمة بالعمليات المخزنة بشكل مقروء
        
        Returns:
            list: قائمة بالعمليات المخزنة مع معلوماتها
        """
        processes = []
        with self.lock:
            for pid, info in self.active_caches.items():
                processes.append({
                    'pid': pid,
                    'name': info.get('process_name', 'unknown'),
                    'folder': info.get('folder_name', 'unknown'),
                    'size': info.get('size', 0),
                    'size_readable': self._get_size_readable(info.get('size', 0)),
                    'cached_since': datetime.fromtimestamp(info.get('timestamp', 0)).strftime("%Y-%m-%d %H:%M:%S")
                })
        
        # ترتيب حسب الاسم
        return sorted(processes, key=lambda x: x['name'])
    
    def _get_size_readable(self, size_bytes):
        """تحويل الحجم إلى صيغة مقروءة"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = float(size_bytes)
        while size >= 1024.0 and i < len(size_names) - 1:
            size /= 1024.0
            i += 1
        
        return f"{size:.1f} {size_names[i]}"
    
    def cleanup_all(self):
        """تنظيف كل الكاش (للاستخدام عند إيقاف التشغيل)"""
        print("\n🧹 جاري تنظيف جميع ملفات الكاش...")
        
        # عرض قائمة بما سيتم حذفه
        processes = self.list_cached_processes()
        if processes:
            print("العمليات التي سيتم حذفها:")
            for p in processes:
                print(f"  - {p['folder']} ({p['size_readable']})")
        
        # عمل نسخة من المفاتيح للتكرار
        with self.lock:
            pids = list(self.active_caches.keys())
        
        for pid in pids:
            self._cleanup_process_cache(pid, reason="إيقاف النظام")
        
        # Stop the background thread; never wipe the whole folder (it may hold unrelated files)
        self._stop_event.set()
        print(f"✅ تم تنظيف الكاش الخاص بالبرنامج في: {self.cache_dir}")

    def get_orphaned_caches(self):
        """الحصول على قائمة الكاش اليتيم (بدون عمليات نشطة)"""
        import psutil
        orphaned = []
        
        with self.lock:
            for pid, cache_info in self.active_caches.items():
                try:
                    proc = psutil.Process(pid)
                    if not proc.is_running():
                        orphaned.append((pid, cache_info))
                except psutil.NoSuchProcess:
                    orphaned.append((pid, cache_info))
                except psutil.AccessDenied:
                    continue
        
        return orphaned
    
    def _get_dir_size(self, path):
        """حساب حجم المجلد"""
        total = 0
        try:
            for entry in path.rglob('*'):
                if entry.is_file():
                    try:
                        total += entry.stat().st_size
                    except:
                        pass
        except Exception as e:
            print(f"خطأ في حساب حجم المجلد: {e}")
        return total
    
    def get_total_size(self):
        """Cheap total cache size in bytes (used by the UI every refresh)."""
        with self.lock:
            return sum(c['size'] for c in self.active_caches.values())

    def get_cache_info(self):
        """الحصول على معلومات الكاش"""
        orphaned = self.get_orphaned_caches()
        processes = self.list_cached_processes()
        
        with self.lock:
            total_size = sum(c['size'] for c in self.active_caches.values())
        
        return {
            'total_cached': len(processes),
            'total_size': total_size,
            'total_size_readable': self._get_size_readable(total_size),
            'cached_processes': processes,
            'orphaned_count': len(orphaned),
            'orphaned_details': [{'pid': p[0], 'name': p[1].get('process_name'), 'folder': p[1].get('folder_name')} 
                                for p in orphaned],
            'cache_directory': str(self.cache_dir),
            'auto_cleanup_active': True
        }
    
    def manual_cleanup_orphaned(self):
        """تنظيف يدوي للكاش اليتيم"""
        orphaned = self.get_orphaned_caches()
        count = 0
        
        if orphaned:
            print(f"\n🧹 جاري تنظيف {len(orphaned)} كاش يتيم...")
            for pid, cache_info in orphaned:
                folder_name = cache_info.get('folder_name', 'unknown')
                self._cleanup_process_cache(pid, reason="تنظيف يدوي للكاش اليتيم")
                count += 1
            print(f"✅ تم تنظيف {count} كاش يتيم")
        
        return count