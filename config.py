from pathlib import Path
import os

class Config:
    # This whitelist is for you NEVER delete these directories
    WHITELISTED_DIRS = [
        # Boot, kernel, system, etc. DONT TOUCH THIS
        Path("C:/Windows"),

        # Program Files (x86) Files DONT TOUCH THIS too
        Path("C:/Program Files (x86)"),
        Path("C:/Program Files"),

        # Roaming
        Path(os.getenv('APPDATA') or ''),
        Path(os.getenv('LOCALAPPDATA') or '') / 'Packages',

        # More important system folders
        Path("C:/3DP"),
        Path("C:/AMD"),
        Path("C:/Autodesk"),
        Path("C:/PerfLogs")
    ]

    # This one is for processes you NEVER kill
    WHITELIST_PROCESSES = {
        'system', 'registry', 'smss.exe', 'csrss.exe', 'wininit.exe',
        'services.exe', 'lsass.exe', 'svchost.exe', 'explorer.exe',
        'dwm.exe', 'winlogon.exe', 'taskmgr.exe', 'sihost.exe',
        'ctfmon.exe', 'runtimebroker.exe', 'searchindexer.exe',
        'nvcontainer.exe', 'nvdisplay.container.exe'
    }

    # Save extensions to delete
    EXTENSIONS_TEMP = {'.tmp', '.temp', '.log', '.bak', '.old', '.cache', '.dmp'}
    EXTENSIONS_COMPRESSED = {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz'}

    # Thresholds
    DAYS_OLD = 90
    MIN_DUP_FILE_SIZE_MB = 50 # Files larger than 50 MB go to deep analysis
    ACCURACY_DUP = 0.6 # 60%

    # Targets to clean
    TARGET_DIRS = [
        Path(os.getenv('TEMP') or ''),
        Path(os.getenv('TMP') or ''),
        Path.home() / 'Downloads',
        Path.home() / 'Documents',
        Path.home() / 'Desktop'
    ]

    @staticmethod
    def is_in_whitelist(path: Path) -> bool:
        """Check if the path is protected by the whitelist"""
        path = path.resolve()
        for protected_dir in Config.WHITELISTED_DIRS:
            try:
                path.relative_to(protected_dir.resolve())
                return True
            except ValueError:
                continue
        return False
    
    @staticmethod
    def protected_process(process_name: str) -> bool:
        """Check if the process is protected by the whitelist"""
        return process_name.lower() in Config.WHITELIST_PROCESSES