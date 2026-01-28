# Fuzzy Logic Analysis Module
import hashlib
from pathlib import Path
from collections import defaultdict
import os
from config import Config

class FilesAnalyzer:
    def __init__(self):
        self.hash_cache = {}
    
    def fast_hash(self, file: Path, block_size=8192) -> str:
        """Hash only the beginning of the file """
        with open(file, 'rb') as f:
            return hashlib.md5(f.read(block_size)).hexdigest()
    
    def full_hash(self, file: Path) -> str:
        """ Full file hash """
        if file in self.hash_cache:
            return self.hash_cache[file]

        hasher = hashlib.md5()
        with open(file, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        
        result = hasher.hexdigest()
        self.hash_cache[file] = result
        return result
    
    def find_dup(self, directories: list[Path]) -> dict:
        """
        Algorithm in 3 phases:

        1. group by file size (O(n))
        2. group by fast hash for candidates(O(n))
        3. full hash for only big files (O(k), k << n)
        """

        print("[*] Starting duplicate file analysis...")
        print("[*] Phase 1: Grouping by file size...")

        by_size = defaultdict(list)
        for dir_base in directories:
            if not dir_base.exists():
                continue
            
            for file in dir_base.rglob('*'):
                if not file.is_file():
                    continue

                # Ignore whitelists
                if Config.is_in_whitelist(file):
                    continue

                try:
                    length = file.stat().st_size
                    if length > 0:
                        by_size[length].append(file)
                except (PermissionError, FileNotFoundError):
                    print(f"[!] Permission denied or file not found: {file}")
                    continue

        print(f"[*] Phase 1 complete: {len(by_size)} groups")
        print("[*] Phase 2: Grouping by fast hash...")

        dup_confirmed = []
        dup_suspect = []
        for length, files in by_size.items():
            if len(files) < 2:
                continue

            length_mb = length / (1024 * 1024)

            # Small end medium files: full hash directly
            if length_mb <= Config.MIN_DUP_FILE_SIZE_MB:
                hash_map = defaultdict(list)
                for file in files:
                    try:
                        h = self.full_hash(file)
                        hash_map[h].append(file)
                    except (PermissionError, FileNotFoundError):
                        print(f"[!] Permission denied or file not found: {file}")
                        continue

                for h, list_files in hash_map.items():
                    if len(list_files) > 1:
                        dup_confirmed.append({
                            'files': list_files,
                            'length_mb': length_mb,
                            'accuracy': 1.0,
                            'type': 'confirmed'
                        })
                
            # Large files: fast hash first    
            else:
                print(f"    [*] Analyzing {len(files)} large files ({length_mb:.2f} MB)...")
                fast_hash_map = defaultdict(list)

                for file in files:
                    try:
                        h = self.fast_hash(file)
                        fast_hash_map[h].append(file)
                    except (PermissionError, FileNotFoundError):
                        print(f"[!] Permission denied or file not found: {file}")
                        continue
                
                # Only candidates with same fast hash do full hash
                for fh, candidates in fast_hash_map.items():
                    if len(candidates) < 2:
                        continue

                    # Calculate accuracy based on: similar name + similar size + parcial hash
                    accuracy = self._calculate_accuracy_fuzzy(candidates)

                    if accuracy >= Config.ACCURACY_DUP:
                        # full hash to confirm
                        full_hash_map = defaultdict(list)
                        for file in candidates:
                            try:
                                h_full = self.full_hash(file)
                                full_hash_map[h_full].append(file)
                            except (PermissionError, FileNotFoundError):
                                print(f"[!] Permission denied or file not found: {file}")
                                continue

                        for h_full, list_files in full_hash_map.items():
                            if len(list_files) > 1:
                                dup_confirmed.append({
                                    'files': list_files,
                                    'length_mb': length_mb,
                                    'accuracy': 1.0,
                                    'type': 'confirmed'
                                })
                    else:
                        dup_suspect.append({
                            'files': candidates,
                            'length_mb': length_mb,
                            'accuracy': accuracy,
                            'type': 'suspect'
                        })
        print(f"[*] Duplicate analysis complete: {len(dup_confirmed)} confirmed groups, {len(dup_suspect)} suspect groups")
        return {'confirmed': dup_confirmed, 'suspect': dup_suspect}
    
    def _calculate_accuracy_fuzzy(self, files: list[Path]) -> float:
        """
        Fuzzy logic to calculate accuracy
        Considers: similar name + similar size + parcial hash
        """

        if len(files) < 2:
            return 0.0
        
        total_acc = 0.0
        comparations = 0

        for i, file1 in enumerate(files):
            for file2 in files[i+1:]:
                score = 0.0

                # Extension similarity: +20%
                if file1.suffix == file2.suffix:
                    score += 0.2

                # Name similarity (Simply Levenshtein): up to +40%
                name1 = file1.stem.lower()
                name2 = file2.stem.lower()

                if name1 == name2:
                    score += 0.4
                elif name1 in name2 or name2 in name1:
                    score += 0.3
                elif self._name_similarity(name1, name2) >= 0.7:
                    score += 0.2
                
                # Date modification similarity: up to +20%
                try:
                    dif_days = abs(file1.stat().st_mtime - file2.stat().st_mtime) / (24 * 3600)
                    if dif_days < 1:
                        score += 0.2
                    elif dif_days < 7:
                        score += 0.1
                except:
                    pass

                # Fast hash: +20%
                try:
                    if self.fast_hash(file1) == self.fast_hash(file2):
                        score += 0.2
                except:
                    pass

                total_acc += score
                comparations += 1
        
        return total_acc / comparations if comparations > 0 else 0.0
    
    def _name_similarity(self, s1: str, s2: str) -> float:
        """ Simple similarity between strings (0.0 to 1.0) """
        if not s1 or not s2:
            return 0.0
        
        # Remove common numbers (e.g., file1(1), file1(2), file(3), etc.)
        import re
        s1_clean = re.sub(r'\(\d+\)|\s+\d+$', '', s1)
        s2_clean = re.sub(r'\(\d+\)|\s+\d+$', '', s2)

        # Calculate words in common
        words1 = set(s1_clean.split())
        words2 = set(s2_clean.split())

        if not words1 or not words2:
            return 0.0
        
        # Here, the division of intersection and union gives a similarity score of set of words
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        return len(intersection) / len(union)
    
    def unused_files(self, directories: list[Path]) -> list:
        """ Find files not accessed in X days """
        import time

        cutoff = time.time() - (Config.DAYS_OLD * 24*3600)
        unused = []

        for dir_base in directories:
            if not dir_base.exists():
                continue
            
            for file in dir_base.rglob('*'):
                if not file.is_file():
                    continue

                # Ignore whitelists
                if Config.is_in_whitelist(file):
                    continue

                try:
                    last_access = max(file.stat().st_atime, file.stat().st_mtime)
                    if last_access < cutoff:
                        days_unused = (time.time() - last_access) / (24*3600)
                        unused.append({
                            'file': file,
                            'days_unused': int(days_unused),
                            'size_mb': file.stat().st_size / (1024*1024)
                        })
                except (PermissionError, FileNotFoundError):
                    print(f"[!] Permission denied or file not found: {file}")
                    continue
        
        return unused







# System Monitor Module
import psutil
from datetime import datetime

class SystemMonitor:
    def __init__(self):
        self.history = []

    def snapshot(self) -> dict:
        """Captura estado atual do sistema"""
        cpu_percent = psutil.cpu_percent(interval=1, percpu=False)
        cpu_per_core = psutil.cpu_percent(interval=1, percpu=True)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('C:/')
        
        # Processos top consumidores
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'exe']):
            try:
                info = proc.info
                
                # Ignora processos protegidos
                if Config.protected_process(info['name']):
                    continue
                
                # Ignora se está em whitelist de diretórios
                if info['exe']:
                    path = Path(info['exe'])
                    if Config.is_in_whitelist(path):
                        continue
                
                # Apenas processos relevantes
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
        Diagnóstico focado em uso anormal de recursos
        """
        if not self.history:
            return {}
        
        snapshot = self.history[-1]
        
        # Processos "peso pesado" (>10% RAM individual)
        heavy_processes = [
            p for p in snapshot['top_processes']
            if p['ram'] > 10.0
        ]
        
        # Múltiplos processos médios (5-10% RAM cada)
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
        
        # Processos individuais
        if heavy_processes:
            names = ', '.join([f"{p['name']} ({p['ram']:.1f}%)" for p in heavy_processes[:3]])
            problems.append({
                'type': 'heavy_processes',
                'message': f'{len(heavy_processes)} process(es) consuming >10% RAM: {names}',
                'severity': 'high'
            })
        
        # Muitos processos médios = possível leak ou acúmulo
        if len(medium_processes) >= 5:
            problems.append({
                'type': 'ram_fragmentation',
                'message': f'{len(medium_processes)} processes consuming 5-10% RAM each (possible fragmentation)',
                'severity': 'medium'
            })
        
        # Disco
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