# main.py
from pathlib import Path
from config import Config
from analysis import FilesAnalyzer, SystemMonitor
from classificator import LLMClassifier
from executor import Executor
from logger import CleanerLogger
from recuperator import Recuperator

class SmartCleaner:
    def __init__(self, mode='general'):
        """
        Modes: 'general' or 'deep'
        """
        self.mode = mode
        self.analyzer = FilesAnalyzer()
        self.monitor = SystemMonitor()
        self.logger = CleanerLogger()
        self.executor = Executor(self.logger)
        
        # LLM is optional (fallback if Ollama is not running)
        self.llm = LLMClassifier()
        self.llm_available = self.llm.verify_ollama()
        
        if not self.llm_available:
            print("[!] WARNING: Ollama is not running. LLM mode disabled.")
            print("    Only deterministic rules will be used.\n")
    
    def general_cleanup(self):
        """Quick cleanup: temp, logs, compressed files"""
        print("\n" + "="*60)
        print("GENERAL CLEANUP")
        print("="*60)
        
        # 1. Temporary files (deterministic rule)
        print("\n[1/3] Searching for temporary files...")
        temp_files = []
        
        for dir_temp in Config.TARGET_DIRS:
            if not dir_temp.exists():
                continue
            
            for file in dir_temp.rglob('*'):
                if not file.is_file():
                    continue
                
                if Config.is_in_whitelist(file):
                    continue
                
                # Obvious temporary files
                if file.suffix.lower() in Config.EXTENSIONS_TEMP:
                    temp_files.append(file)
        
        if temp_files:
            print(f"    Found: {len(temp_files)} temporary files")
            self.executor.delete_batch(temp_files, "temporary file")
        else:
            print("    No temporary files found")
        
        # 2. Compressed files (ZIP, RAR)
        print("\n[2/3] Searching for compressed files...")
        compressed = []
        
        # Focus on Downloads and Desktop (common places for forgotten compressed files)
        compressed_dirs = [
            Path.home() / 'Downloads',
            Path.home() / 'Desktop'
        ]
        
        for dir_base in compressed_dirs:
            if not dir_base.exists():
                continue
            
            for file in dir_base.rglob('*'):
                if not file.is_file():
                    continue
                
                if file.suffix.lower() in Config.EXTENSIONS_COMPRESSED:
                    # Delete only if > 30 days unused
                    import time
                    days_unused = (time.time() - file.stat().st_mtime) / 86400
                    
                    if days_unused > 30:
                        compressed.append(file)
        
        if compressed:
            print(f"    Found: {len(compressed)} old compressed files (>30 days)")
            response = input("    Delete them? [Y/n]: ").strip().lower()
            
            if response != 'n':
                self.executor.delete_batch(compressed, "old compressed file")
        else:
            print("    No old compressed files found")
        
        # 3. Background processes
        print("\n[3/3] Analyzing background processes...")
        diagnosis = self.monitor.diagnose()
        
        if diagnosis.get('problems'):
            print("\n    Problems detected:")
            for prob in diagnosis['problems']:
                print(f"    ⚠️  {prob['message']} (severity: {prob['severity']})")
            
            # Identifies candidate processes
            candidate_processes = []
            for proc in diagnosis['snapshot']['top_processes'][:10]:
                # Only processes with RAM > 5%
                if proc['ram'] > 5.0:
                    candidate_processes.append({
                        **proc,
                        'reason': 'excessive RAM consumption'
                    })
            
            if candidate_processes:
                self.executor.kill_batch_processes(candidate_processes, ask_confirmation=True)
        else:
            print("    ✓ System operating normally")
    
    def deep_cleanup(self):
        """Deep cleanup: duplicates, old files, full checkup"""
        print("\n" + "="*60)
        print("DEEP CLEANUP")
        print("="*60)
        
        # First do general cleanup
        self.general_cleanup()
        
        # 4. Duplicate files
        print("\n[4/6] Searching for duplicate files...")
        duplicates = self.analyzer.find_dup(Config.TARGET_DIRS)
        
        # 4a. Confirmed duplicates (100% certainty)
        if duplicates['confirmed']:
            print(f"\n    CONFIRMED duplicates: {len(duplicates['confirmed'])} groups")
            
            for group in duplicates['confirmed']:
                files = group['files']
                print(f"\n    Group ({len(files)} files, {group['size_mb']:.2f} MB each):")
                
                for file in files:
                    print(f"      - {file}")
                
                # Keep the most recent, delete the others
                most_recent = max(files, key=lambda a: a.stat().st_mtime)
                to_delete = [a for a in files if a != most_recent]
                
                print(f"    Keeping: {most_recent.name}")
                
                for file in to_delete:
                    self.executor.delete_file(file, f"duplicate of {most_recent.name}")
        
        # 4b. Suspect duplicates (uses LLM if available)
        if duplicates['suspect']:
            print(f"\n    SUSPECT duplicates: {len(duplicates['suspect'])} groups")
            
            if self.llm_available:
                print("    Analyzing with LLM...")
                
                for group in duplicates['suspect']:
                    should_delete, justification = self.llm.analyze_suspect_duplicate(
                        group['files'], 
                        group['confidence']
                    )
                    
                    print(f"\n    Confidence: {group['confidence']*100:.1f}%")
                    print(f"    LLM Decision: {'DELETE' if should_delete else 'KEEP'}")
                    print(f"    Reason: {justification}")
                    
                    if should_delete:
                        # Keep the most recent
                        files = group['files']
                        most_recent = max(files, key=lambda a: a.stat().st_mtime)
                        to_delete = [a for a in files if a != most_recent]
                        
                        for file in to_delete:
                            self.executor.delete_file(file, f"suspect duplicate (LLM): {justification}")
            else:
                print("    [!] LLM not available - suspect duplicates ignored")
                print("    Start Ollama for intelligent analysis")
        
        # 5. Unused files
        print("\n[5/6] Searching for unused files...")
        unused = self.analyzer.unused_files(Config.TARGET_DIRS)
        
        if unused:
            print(f"    Found: {len(unused)} file(s) unused for {Config.DAYS_OLD}+ days")
            
            # Sort by days unused (oldest first)
            unused.sort(key=lambda x: x['days_unused'], reverse=True)
            
            # Show top 10
            print("\n    Top 10 oldest:")
            for item in unused[:10]:
                print(f"      - {item['file'].name} ({item['days_unused']} days, {item['size_mb']:.2f} MB)")
            
            if self.llm_available:
                print("\n    Analyzing with LLM (may take a while)...")
                
                for item in unused:
                    should_delete, justification = self.llm.analyze_old_file(
                        item['file'],
                        item['days_unused']
                    )
                    
                    if should_delete:
                        self.executor.delete_file(
                            item['file'],
                            f"unused ({item['days_unused']} days): {justification}"
                        )
            else:
                # Without LLM: delete only safe extensions
                print("    [!] LLM not available - using basic rules")
                
                for item in unused:
                    if item['file'].suffix.lower() in Config.EXTENSIONS_TEMP:
                        self.executor.delete_file(
                            item['file'],
                            f"old temporary ({item['days_unused']} days)"
                        )
        
        # 6. Final system checkup
        print("\n[6/6] Final system checkup...")
        diagnosis = self.monitor.diagnose()
        
        print(f"\n    CPU: {diagnosis['snapshot']['cpu']['total']:.1f}%")
        print(f"    RAM: {diagnosis['snapshot']['ram']['percent']:.1f}% ({diagnosis['snapshot']['ram']['used_gb']:.2f} GB / {diagnosis['snapshot']['ram']['total_gb']:.2f} GB)")
        print(f"    Disk: {diagnosis['snapshot']['disk']['percent']:.1f}% ({diagnosis['snapshot']['disk']['free_gb']:.2f} GB free)")
        
        if diagnosis.get('problems'):
            print("\n    ⚠️  Problems detected:")
            for prob in diagnosis['problems']:
                print(f"       - {prob['message']}")
        else:
            print("\n    ✓ System healthy")
    
    def finalize(self):
        """Finalize cleanup and generate report"""
        # Save logs
        statistics = self.executor.get_statistics()
        log_file = self.logger.finalize(statistics)
        
        # Save LLM decisions
        if self.llm_available and self.llm.decisions_history:
            llm_log = log_file.parent / f"llm_decisions_{log_file.stem}.json"
            self.llm.save_history(llm_log)
            print(f"[+] LLM decisions saved to: {llm_log}")
        
        # Display summary
        self.logger.show_summary()
        
        # Recovery menu
        print("\n" + "="*60)
        response = input("\n[?] Review files in quarantine? [Y/n]: ").strip().lower()
        
        if response != 'n':
            recuperator = Recuperator(log_file)
            recuperator.interactive_menu()
        else:
            print("\n[*] Files remain in quarantine.")
            print(f"    To recover later: python recuperator.py {log_file}")

def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║      INTELLIGENT DISK CLEANUP - Windows 11               ║
║                   Powered by Ollama                      ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    print("Available modes:")
    print("  [1] General Cleanup (fast)")
    print("  [2] Deep Cleanup (complete)")
    print("  [3] Only recover files from previous log")
    
    choice = input("\nChoose mode [1/2/3]: ").strip()
    
    if choice == '3':
        # Recovery mode
        log_dir = Path('data/logs')
        logs = sorted(log_dir.glob('cleaner_log_*.json'), reverse=True)
        
        if not logs:
            print("[!] No logs found.")
            return
        
        print("\nAvailable logs:")
        for i, log in enumerate(logs[:10], 1):
            print(f"  [{i}] {log.name}")
        
        idx = int(input("\nChoose log: ").strip()) - 1
        
        if 0 <= idx < len(logs):
            recuperator = Recuperator(logs[idx])
            recuperator.interactive_menu()
        return
    
    # Cleanup mode
    mode = 'deep' if choice == '2' else 'general'
    cleaner = SmartCleaner(mode=mode)
    
    try:
        if mode == 'general':
            cleaner.general_cleanup()
        else:
            cleaner.deep_cleanup()
        
        cleaner.finalize()
        
    except KeyboardInterrupt:
        print("\n\n[!] Interrupted by user")
        cleaner.finalize()
    except Exception as e:
        print(f"\n[!] Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()