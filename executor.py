# executor.py
import psutil
from pathlib import Path
from typing import List
import os

class Executor:
    def __init__(self, logger, dry_run=False):
        self.logger = logger
        self.dry_run = dry_run
        self.statistics = {
            'files_deleted': 0,
            'space_freed_mb': 0,
            'processes_killed': 0,
            'errors': []
        }
    
    def delete_file(self, file: Path, reason: str) -> bool:
        """Move file to quarantine (via logger)"""
        if self.dry_run:
            print(f"[DRY RUN] Would delete file: {file}")
            return True

        if not file.exists():
            self.statistics['errors'].append(f"File does not exist: {file}")
            return False
        
        try:
            size_mb = file.stat().st_size / (1024 * 1024)
            
            self.logger.add_action(
                action_type='delete',
                file=file,
                details={
                    'reason': reason,
                    'size_mb': round(size_mb, 2)
                }
            )
            
            self.statistics['files_deleted'] += 1
            self.statistics['space_freed_mb'] += size_mb
            
            return True
            
        except Exception as e:
            error = f"Error deleting {file.name}: {e}"
            self.statistics['errors'].append(error)
            return False
    
    def delete_batch(self, files: List[Path], reason: str):
        """Delete multiple files"""
        total = len(files)
        success = 0
        
        print(f"\n[*] Deleting {total} file(s)...")
        
        for i, file in enumerate(files, 1):
            if self.delete_file(file, reason):
                success += 1
            
            # Progress bar
            if i % 10 == 0 or i == total:
                print(f"    Progress: {i}/{total} ({success} ok)", end='\r')
        
        print(f"\n[+] Done: {success}/{total} files moved to quarantine")
    
    def kill_process(self, pid: int, name: str, reason: str) -> bool:
        """Kill a process"""
        try:
            proc = psutil.Process(pid)
            
            # Confirms it's the correct process
            if proc.name().lower() != name.lower():
                self.statistics['errors'].append(f"PID {pid} does not match {name}")
                return False
            
            # Try graceful termination first
            proc.terminate()
            
            # Wait up to 3 seconds
            try:
                proc.wait(timeout=3)
            except psutil.TimeoutExpired:
                # If it didn't terminate, force it
                proc.kill()
            
            self.logger.add_action(
                action_type='process_killed',
                file=Path(name),  # uses name as placeholder
                details={
                    'pid': pid,
                    'reason': reason
                }
            )
            
            self.statistics['processes_killed'] += 1
            return True
            
        except psutil.NoSuchProcess:
            self.statistics['errors'].append(f"Process {name} (PID {pid}) no longer exists")
            return False
        except psutil.AccessDenied:
            self.statistics['errors'].append(f"No permission to kill {name} (PID {pid})")
            return False
        except Exception as e:
            self.statistics['errors'].append(f"Error killing {name}: {e}")
            return False
    
    def kill_batch_processes(self, processes: List[dict], ask_confirmation=True):
        """Kill multiple processes"""
        if not processes:
            return
        
        print(f"\n[!] {len(processes)} process(es) candidates to kill:")
        for proc in processes:
            print(f"    - {proc['name']} (PID {proc['pid']}) - RAM: {proc['ram']}%")
        
        if ask_confirmation:
            response = input("\n[?] Do you want to kill ALL these processes? [Y/N]: ").strip().lower()
            if response != 'y':
                print("[*] Process kill cancelled.")
                return
        
        print("\n[*] Killing processes...")
        success = 0
        
        for proc in processes:
            if self.kill_process(proc['pid'], proc['name'], proc.get('reason', 'excessive consumption')):
                success += 1
                print(f"    [+] {proc['name']} killed")
            else:
                print(f"    [!] Failed to kill {proc['name']}")
        
        print(f"\n[+] {success}/{len(processes)} processes killed")
    
    def get_statistics(self) -> dict:
        """Return execution statistics"""
        return self.statistics
    