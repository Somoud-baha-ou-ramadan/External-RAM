"""
إدارة العمليات وتحديد الأعلى استهلاكاً
"""

import os

import psutil


class ProcessManager:
    """إدارة عمليات النظام"""
    
    def __init__(self):
        self.tracked_processes = {}
    
    def get_top_memory_process(self):
        """
        الحصول على العملية الأكثر استهلاكاً للرام
        مع استثناء عمليات النظام الأساسية
        
        Returns:
            dict: معلومات العملية أو None إذا لم يتم العثور على عملية
        """
        processes = []
        
        # قائمة العمليات التي يجب استثناؤها
        excluded_names = [
            'system', 'kernel', 'idle', 'system idle process', 
            'svchost.exe', 'services.exe', 'lsass.exe', 'wininit.exe',
            'csrss.exe', 'winlogon.exe', 'smss.exe', 'fontdrvhost.exe',
            'dwm.exe', 'explorer.exe', 'taskhostw.exe', 'sihost.exe',
            'memcompression', 'registry', 'vmmem', 'securityhealthservice.exe',
            'msmpeng.exe', 'python.exe', 'pythonw.exe', 'python3', 'python'
        ]
        own_pid = os.getpid()
        
        # استثناء عمليات النظام المهمة
        excluded_lower = [name.lower() for name in excluded_names]
        
        for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'memory_percent']):
            try:
                # التحقق من صحة البيانات
                if not proc.info['name'] or proc.info['pid'] == own_pid:
                    continue
                    
                process_name = proc.info['name'].lower()
                
                # استثناء العمليات المستبعدة
                if process_name in excluded_lower:
                    continue
                
                # استثناء العمليات ذات الذاكرة المنخفضة
                if proc.info['memory_info'] is None:
                    continue
                
                memory_rss = proc.info['memory_info'].rss
                memory_mb = memory_rss / (1024 * 1024)
                
                # تجاهل العمليات التي تستهلك أقل من 50 ميجابايت
                if memory_mb < 50:
                    continue
                
                processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'memory_rss': memory_rss,
                    'memory_percent': proc.info['memory_percent'] or 0,
                    'memory_mb': memory_mb
                })
                
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            except Exception as e:
                print(f"خطأ في معالجة العملية: {e}")
                continue
        
        if processes:
            # ترتيب العمليات حسب استهلاك الرام
            top_process = max(processes, key=lambda x: x['memory_rss'])
            print(f"🔍 العملية الأكثر استهلاكاً: {top_process['name']} (PID: {top_process['pid']}) - {top_process['memory_mb']:.1f} MB")
            return top_process
        
        print("⚠️ لم يتم العثور على عمليات مناسبة للتخزين")
        return None
    
    def get_all_processes_by_memory(self, limit=10, exclude_system=True):
        """
        الحصول على قائمة بجميع العمليات مرتبة حسب استهلاك الذاكرة
        
        Args:
            limit: عدد العمليات المطلوبة
            exclude_system: استبعاد عمليات النظام
            
        Returns:
            list: قائمة العمليات
        """
        processes = []
        
        excluded_names = [
            'system', 'kernel', 'idle', 'system idle process', 
            'svchost.exe', 'services.exe', 'lsass.exe'
        ]
        excluded_lower = [name.lower() for name in excluded_names]
        
        for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'memory_percent']):
            try:
                if not proc.info['name']:
                    continue
                
                if exclude_system and proc.info['name'].lower() in excluded_lower:
                    continue
                
                if proc.info['memory_info']:
                    memory_mb = proc.info['memory_info'].rss / (1024 * 1024)
                    
                    # تجاهل العمليات ذات الاستهلاك المنخفض جداً
                    if memory_mb < 10:
                        continue
                    
                    processes.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'memory_mb': memory_mb,
                        'memory_percent': proc.info['memory_percent'] or 0
                    })
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # ترتيب حسب استهلاك الذاكرة
        processes.sort(key=lambda x: x['memory_mb'], reverse=True)
        return processes[:limit]
    
    def get_process_details(self, pid):
        """
        الحصول على تفاصيل عملية محددة
        
        Args:
            pid: معرف العملية
            
        Returns:
            dict: تفاصيل العملية أو None
        """
        try:
            proc = psutil.Process(pid)
            mem_info = proc.memory_info()
            
            return {
                'pid': pid,
                'name': proc.name(),
                'status': proc.status(),
                'cpu_percent': proc.cpu_percent(interval=0.1),
                'memory_rss': mem_info.rss,
                'memory_mb': mem_info.rss / (1024 * 1024),
                'memory_percent': proc.memory_percent(),
                'create_time': proc.create_time(),
                'num_threads': proc.num_threads()
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None
        except Exception as e:
            print(f"خطأ في الحصول على تفاصيل العملية {pid}: {e}")
            return None
    
    def suspend_process(self, pid):
        """Suspend a whole process (psutil handles Windows, Linux and macOS)."""
        try:
            psutil.Process(pid).suspend()
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
        except Exception as e:
            print(f"خطأ في تعليق العملية {pid}: {e}")
            return False

    def resume_process(self, pid):
        """Resume a suspended process."""
        try:
            psutil.Process(pid).resume()
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
        except Exception as e:
            print(f"خطأ في استئناف العملية {pid}: {e}")
            return False

    def get_processes_by_memory(self, limit=10):
        """
        الحصول على قائمة العمليات مرتبة حسب استهلاك الذاكرة
        
        Args:
            limit: عدد العمليات المطلوبة
            
        Returns:
            list: قائمة العمليات
        """
        return self.get_all_processes_by_memory(limit, exclude_system=False)