#!/usr/bin/env python3
"""
أداة لتصحيح أخطاء وعرض جميع العمليات
"""

import psutil
import time

def show_top_processes(limit=10):
    """عرض العمليات الأكثر استهلاكاً للذاكرة"""
    print("\n" + "="*80)
    print(f"{'PID':<8} {'الاسم':<30} {'الذاكرة (MB)':<15} {'النسبة %':<10}")
    print("="*80)
    
    total_ram = psutil.virtual_memory().total
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
        try:
            if proc.info['memory_info']:
                memory_mb = proc.info['memory_info'].rss / (1024 * 1024)
                if memory_mb > 10:  # فقط العمليات التي تستهلك أكثر من 10 ميجابايت
                    processes.append({
                        'pid': proc.info['pid'],
                        'name': (proc.info['name'] or '?')[:30],
                        'memory_mb': memory_mb
                    })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    # ترتيب حسب الاستهلاك
    processes.sort(key=lambda x: x['memory_mb'], reverse=True)
    
    for p in processes[:limit]:
        print(f"{p['pid']:<8} {p['name']:<30} {p['memory_mb']:<15.1f} {(p['memory_mb'] * 1024 * 1024 * 100 / total_ram):<10.1f}")
    
    print("="*80)

def monitor_ram():
    """مراقبة الرام بشكل مستمر"""
    print("مراقبة الرام - اضغط Ctrl+C للإيقاف")
    print("-"*60)
    
    try:
        while True:
            memory = psutil.virtual_memory()
            print(f"\rالرام: {memory.percent}% | مستخدم: {memory.used/(1024**3):.1f}GB / {memory.total/(1024**3):.1f}GB | حر: {memory.available/(1024**3):.1f}GB", end="")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nتم إيقاف المراقبة")

if __name__ == "__main__":
    print("اختر الخيار:")
    print("1 - عرض العمليات الأكثر استهلاكاً")
    print("2 - مراقبة الرام")
    
    choice = input("اختر (1/2): ").strip()
    
    if choice == "1":
        show_top_processes(20)
    elif choice == "2":
        monitor_ram()
    else:
        show_top_processes(20)