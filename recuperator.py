# recovery.py
import json
import shutil
from pathlib import Path

class Recuperator:
    def __init__(self, log_file: Path):
        self.log_file = log_file
        
        with open(log_file, 'r', encoding='utf-8') as f:
            self.log_data = json.load(f)
    
    def list_recoverable_actions(self):
        """List only files that can be recovered"""
        recoverable = []
        
        for i, action in enumerate(self.log_data['actions']):
            if action['type'] == 'delete' and 'quarantine' in action:
                recoverable.append({
                    'index': i,
                    'original_file': action['file'],
                    'quarantine': action['quarantine'],
                    'size_mb': action['details'].get('size_mb', 0),
                    'reason': action['details'].get('reason', 'N/A')
                })
        
        return recoverable
    
    def interactive_menu(self):
        """Menu for user to choose what to recover"""
        recoverable = self.list_recoverable_actions()
        
        if not recoverable:
            print("\n[!] No files in quarantine to recover.")
            return
        
        print("\n" + "="*60)
        print("FILES IN QUARANTINE")
        print("="*60)
        
        for item in recoverable:
            print(f"\n[{item['index']}] {Path(item['original_file']).name}")
            print(f"    Path: {item['original_file']}")
            print(f"    Size: {item['size_mb']:.2f} MB")
            print(f"    Reason: {item['reason']}")
        
        print("\n" + "="*60)
        print("\nOptions:")
        print("  [A] Recover ALL files")
        print("  [N] Delete ALL permanently")
        print("  [numbers separated by comma] Ex: 0,3,5")
        
        choice = input("\nYour choice: ").strip().upper()
        
        if choice == 'A':
            indices = [item['index'] for item in recoverable]
        elif choice == 'N':
            return self.delete_permanently()
        else:
            try:
                indices = [int(x.strip()) for x in choice.split(',')]
            except:
                print("[!] Invalid input.")
                return
        
        # Recover selected files
        for idx in indices:
            item = next((x for x in recoverable if x['index'] == idx), None)
            if item:
                self.recover_file(item)
        
        # Non-recovered files are deleted
        not_recovered = [x for x in recoverable if x['index'] not in indices]
        if not_recovered:
            print(f"\n[*] Permanently deleting {len(not_recovered)} unselected file(s)...")
            for item in not_recovered:
                self.delete_file(item)
    
    def recover_file(self, item: dict):
        """Recover a file from quarantine"""
        quarantine = Path(item['quarantine'])
        original = Path(item['original_file'])
        
        if not quarantine.exists():
            print(f"[!] File not found in quarantine: {quarantine}")
            return False
        
        try:
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(quarantine), str(original))
            print(f"[+] Recovered: {original.name}")
            return True
        except Exception as e:
            print(f"[!] Error recovering {original.name}: {e}")
            return False
    
    def delete_file(self, item: dict):
        """Permanently delete a file from quarantine"""
        quarantine = Path(item['quarantine'])
        
        if quarantine.exists():
            try:
                quarantine.unlink()
            except Exception as e:
                print(f"[!] Error deleting {quarantine.name}: {e}")
    
    def delete_permanently(self):
        """Delete the ENTIRE quarantine"""
        confirm = input("\n  DELETE EVERYTHING PERMANENTLY? (type 'YES' to confirm): ")
        
        if confirm.upper() == 'YES':
            # Find first action with quarantine
            quarantine_path = None
            for action in self.log_data['actions']:
                if 'quarantine' in action:
                    quarantine_path = action['quarantine']
                    break
            
            if quarantine_path:
                quarantine = Path(quarantine_path).parent
                try:
                    shutil.rmtree(quarantine)
                    print(f"[+] Quarantine deleted: {quarantine}")
                except Exception as e:
                    print(f"[!] Error deleting quarantine: {e}")
            else:
                print("[!] No quarantine found in log")
        else:
            print("[*] Operation cancelled.")