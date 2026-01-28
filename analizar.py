# Compatibility module - imports from Analysis.py
# This file is deprecated, use Analysis.py instead

from Analysis import SystemMonitor
from config import Config

class SystemMonitor:
    """Alias for backward compatibility with old naming"""
    def __init__(self):
        self.history = []
    
    def snapshot(self) -> dict:
        """Capture current system state"""
        import psutil
        from datetime import datetime
        
        cpu_percent = psutil.cpu_percent(interval=1, percpu=False)
        cpu_per_core = psutil.cpu_percent(interval=1, percpu=True)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('C:/')
        
        # Top consuming processes
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'exe']):
            try:
                info = proc.info
                
                # Ignore protected processes
                if Config.protected_process(info['name']):
                    continue
                
                # Ignore if in whitelisted directories
                if info['exe']:
                    from pathlib import Path
                    path = Path(info['exe'])
                    if Config.is_in_whitelist(path):
                        continue
                
                # Only relevant processes
                if info['memory_percent'] > 2.0 or info['cpu_percent'] > 5.0:
                    processes.append({
                        'pid': info['pid'],
                        'name': info['name'],
                        'cpu': round(info['cpu_percent'], 2),
                        'ram': round(info['memory_percent'], 2),
                        'path': info['exe']
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        processes.sort(key=lambda x: x['ram'], reverse=True)
        
        snapshot = {
            'timestamp': datetime.now().isoformat(),
            'cpu': {
                'total': cpu_percent,
                'per_core': cpu_per_core
            },
            'ram': {
                'percent': ram.percent,
                'used_gb': ram.used / (1024**3),
                'total_gb': ram.total / (1024**3)
            },
            'disk': {
                'percent': disk.percent,
                'free_gb': disk.free / (1024**3),
                'total_gb': disk.total / (1024**3)
            },
            'top_processes': processes[:20]
        }
        
        self.history.append(snapshot)
        return snapshot
    
    def diagnose(self) -> dict:
        """
        Diagnosis focused on abnormal resource usage
        """
        if not self.history:
            return {}
        
        snapshot = self.history[-1]
        
        # Heavy processes (>10% RAM individual)
        heavy_processes = [
            p for p in snapshot['top_processes']
            if p['ram'] > 10.0
        ]
        
        # Multiple medium processes (5-10% RAM each)
        medium_processes = [
            p for p in snapshot['top_processes']
            if 5.0 < p['ram'] <= 10.0
        ]
        
        problems = []
        
        # RAM
        if snapshot['ram']['percent'] > 85:
            problems.append({
                'type': 'ram_critical',
                'message': f'RAM at {snapshot["ram"]["percent"]:.1f}% usage ({snapshot["ram"]["used_gb"]:.1f}/{snapshot["ram"]["total_gb"]:.1f} GB)',
                'severity': 'critical'
            })
        elif snapshot['ram']['percent'] > 70:
            problems.append({
                'type': 'ram_high',
                'message': f'RAM at {snapshot["ram"]["percent"]:.1f}% usage',
                'severity': 'medium'
            })
        
        # CPU
        if snapshot['cpu']['total'] > 80:
            top_cpu = max(snapshot['top_processes'], key=lambda x: x['cpu'], default={'name': 'unknown', 'cpu': 0})
            problems.append({
                'type': 'cpu_high',
                'message': f'CPU at {snapshot["cpu"]["total"]:.1f}% usage (top: {top_cpu["name"]} with {top_cpu["cpu"]:.1f}%)',
                'severity': 'medium'
            })
        
        # Individual processes
        if heavy_processes:
            names = ', '.join([f"{p['name']} ({p['ram']:.1f}%)" for p in heavy_processes[:3]])
            problems.append({
                'type': 'heavy_processes',
                'message': f'{len(heavy_processes)} process(es) consuming >10% RAM: {names}',
                'severity': 'high'
            })
        
        # Many medium processes = possible leak or accumulation
        if len(medium_processes) >= 5:
            problems.append({
                'type': 'ram_fragmentation',
                'message': f'{len(medium_processes)} processes consuming 5-10% RAM each (possible fragmentation)',
                'severity': 'medium'
            })
        
        # Disk
        if snapshot['disk']['percent'] > 90:
            problems.append({
                'type': 'disk_critical',
                'message': f'Disk at {snapshot["disk"]["percent"]:.1f}% usage (only {snapshot["disk"]["free_gb"]:.1f} GB free)',
                'severity': 'critical'
            })
        
        return {
            'snapshot': snapshot,
            'heavy_processes': heavy_processes,
            'medium_processes': medium_processes,
            'problems': problems
        }

__all__ = ['SystemMonitor']