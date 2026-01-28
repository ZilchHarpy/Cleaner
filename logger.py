import json
import shutil
from pathlib import Path
from datetime import datetime

class CleanerLogger:
    def __init__(self, logs_dir='data/logs'):
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self.quarantine_dir = self.logs_dir / 'quarantine'
        self.quarantine_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_file = self.logs_dir / f'cleaner_log_{timestamp}.json'

        self.log_data = {
            'timestamp_start': timestamp,
            'actions': [],
            'statistics': {}
        }
    def add_action(self, action_type: str, file: Path, details: dict):
        """ Register a clean action """
        action = {
            'type': action_type, # 'delete', 'move', 'process_kill', etc.
            'file': str(file),
            'details': details,
            'timestamp': datetime.now().isoformat()
        }

        # If delete file, move to quarantine first
        if action_type == 'delete':
            try:
                # Preserve directories structure
                rel_path = file.relative_to(file.anchor)
                destination = self.quarantine_dir / rel_path
                destination.parent.mkdir(parents=True, exist_ok=True)

                shutil.move(str(file), str(destination))
                action['quarantine'] = str(destination)
                action['status'] = 'moved to quarantine'
            except Exception as e:
                action['status'] = 'error'
                action['error'] = str(e)
        self.log_data['actions'].append(action)

    def finalize(self, statistics: dict):
        """ Save final log to file """
        self.log_data['timestamp_end'] = datetime.now().isoformat()
        self.log_data['statistics'] = statistics

        with open(self.log_file, 'w', encoding='utf-8') as f:
            json.dump(self.log_data, f, indent=4)
        
        print(f'Log saved to {self.log_file}')
        return self.log_file

    def show_summary(self):
        """ Show a formatted summary of actions """
        print("\n" + "="*60)
        print("Clean Summary")
        print("="*60)

        total_files = len([a for a in self.log_data['actions'] if a['type'] == 'delete'])
        total_processes = len([a for a in self.log_data['actions'] if a['type'] == 'process_kill'])

        cleared_size = sum(
            a['details'].get('size_mb', 0)
            for a in self.log_data['actions']
            if a['type'] == 'delete'
        )

        print(f"Files moved to quarantine: {total_files}")
        print(f"Processes killed: {total_processes}")
        print(f"Total space cleared: {cleared_size:.2f} MB")

        print(f"\nComplete log: {self.log_file}")
        print(f"Quarantine: {self.quarantine_dir}")