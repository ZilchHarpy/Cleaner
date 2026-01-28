# standalone_recovery.py
"""
Usage: python standalone_recovery.py [path_to_log.json]
"""
import sys
from pathlib import Path
from recuperator import Recuperator

def main():
    if len(sys.argv) < 2:
        # List available logs
        log_dir = Path('data/logs')
        logs = sorted(log_dir.glob('cleaner_log_*.json'), reverse=True)
        
        if not logs:
            print("No logs found in data/logs/")
            return
        
        print("Available logs:\n")
        for i, log in enumerate(logs, 1):
            print(f"  [{i}] {log.name}")
        
        choice = int(input("\nChoose log: ").strip()) - 1
        
        if 0 <= choice < len(logs):
            log_file = logs[choice]
        else:
            print("Invalid choice")
            return
    else:
        log_file = Path(sys.argv[1])
    
    if not log_file.exists():
        print(f"Log not found: {log_file}")
        return
    
    recuperator = Recuperator(log_file)
    recuperator.interactive_menu()

if __name__ == "__main__":
    main()