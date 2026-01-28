# classifier.py
import requests
import json
from pathlib import Path
from typing import Tuple

class LLMClassifier:
    def __init__(self, model="llama3.2:3b", url="http://localhost:11434"):
        self.model = model
        self.url = url
        self.decisions_history = []
    
    def verify_ollama(self) -> bool:
        """Check if Ollama is running"""
        try:
            response = requests.get(f"{self.url}/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def consult(self, prompt: str, temperature=0.3) -> str:
        """Consult the Ollama model"""
        endpoint = f"{self.url}/api/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": 200  # limit response to be fast
            }
        }
        
        try:
            response = requests.post(endpoint, json=payload, timeout=30)
            response.raise_for_status()
            return json.loads(response.text)['response']
        except Exception as e:
            print(f"[!] Error consulting Ollama: {e}")
            return ""
    
    def analyze_suspect_duplicate(self, files: list[Path], confidence: float) -> Tuple[bool, str]:
        """
        Analyze suspect duplicates (confidence < 1.0) using LLM
        Returns: (should_delete, justification)
        """
        # Prepare context
        infos = []
        for file in files:
            try:
                stat = file.stat()
                infos.append({
                    'name': file.name,
                    'path': str(file.parent),
                    'size_kb': stat.st_size / 1024,
                    'modified': stat.st_mtime
                })
            except:
                continue
        
        prompt = f"""You are an expert assistant specialized in analyzing duplicate files.

CONTEXT:
- Duplication confidence (fuzzy analysis): {confidence*100:.1f}%
- Candidate files: {len(infos)}

FILE DETAILS:
{json.dumps(infos, indent=2)}

TASK:
Analyze if these files are probably duplicates considering:
1. Name similarity
2. Modification date difference
3. Exact same size
4. Location (Downloads, Desktop, etc can have accidental duplicates)

Answer ONLY in the format:
DECISION: [YES/NO]
CONFIDENCE: [0-100]%
KEEP: [filename to keep, if applicable]
JUSTIFICATION: [one line explaining the reasoning]
"""
        
        response = self.consult(prompt, temperature=0.2)
        
        # Parse response
        should_delete = "DECISION: YES" in response.upper()
        
        # Extract justification
        lines = response.split('\n')
        justification = ""
        for line in lines:
            if "JUSTIFICATION:" in line.upper():
                justification = line.split(':', 1)[1].strip()
                break
        
        if not justification:
            justification = response[:200]  # gets start if not found
        
        # Register decision
        self.decisions_history.append({
            'type': 'suspect_duplicate',
            'files': [str(f) for f in files],
            'initial_confidence': confidence,
            'decision': should_delete,
            'justification': justification
        })
        
        return should_delete, justification
    
    def analyze_old_file(self, file: Path, days_unused: int) -> Tuple[bool, str]:
        """
        Analyze if old file should be deleted
        Returns: (should_delete, justification)
        """
        try:
            stat = file.stat()
            size_mb = stat.st_size / (1024 * 1024)
        except:
            return False, "Error accessing file"
        
        prompt = f"""You are an assistant specialized in file management.

FILE:
- Name: {file.name}
- Extension: {file.suffix}
- Path: {file.parent}
- Size: {size_mb:.2f} MB
- Days unused: {days_unused}

TASK:
Determine if it's safe to delete this file considering:
1. Extension (temporary, logs = safe; documents, code = caution)
2. Location (Downloads, Temp = safer; Documents = more caution)
3. Time unused (>180 days = probable garbage; <180 days = evaluate)
4. Name indicates backup, important document, or system file?

Answer ONLY in the format:
DECISION: [YES/NO]
RISK: [LOW/MEDIUM/HIGH]
JUSTIFICATION: [one line]
"""
        
        response = self.consult(prompt, temperature=0.3)
        
        should_delete = "DECISION: YES" in response.upper()
        
        # Parse response
        lines = response.split('\n')
        justification = ""
        risk = "MEDIUM"
        
        for line in lines:
            if "JUSTIFICATION:" in line.upper():
                justification = line.split(':', 1)[1].strip()
            elif "RISK:" in line.upper():
                risk = line.split(':', 1)[1].strip().split()[0]
        
        # If risk is HIGH, don't delete automatically
        if "HIGH" in risk.upper():
            should_delete = False
            justification += " [HIGH RISK - requires manual confirmation]"
        
        self.decisions_history.append({
            'type': 'old_file',
            'file': str(file),
            'days_unused': days_unused,
            'decision': should_delete,
            'risk': risk,
            'justification': justification
        })
        
        return should_delete, justification
    
    def analyze_process(self, process: dict) -> Tuple[bool, str]:
        """
        Analyze if background process should be killed
        Returns: (should_kill, justification)
        """
        prompt = f"""You are an assistant specialized in Windows processes.

PROCESS:
- Name: {process['name']}
- PID: {process['pid']}
- CPU: {process['cpu']}%
- RAM: {process['ram']}%
- Path: {process.get('path', 'unknown')}

TASK:
Determine if it's safe to kill this process considering:
1. Name indicates Windows critical service? (don't kill)
2. Excessive consumption without justification?
3. Common application process vs system service?
4. Suspicious location (outside Program Files)?

Answer ONLY in the format:
DECISION: [YES/NO]
SAFETY: [SAFE/CAUTION/DANGEROUS]
JUSTIFICATION: [one line]
"""
        
        response = self.consult(prompt, temperature=0.2)
        
        should_kill = "DECISION: YES" in response.upper()
        
        # Parse
        lines = response.split('\n')
        justification = ""
        safety = "CAUTION"
        
        for line in lines:
            if "JUSTIFICATION:" in line.upper():
                justification = line.split(':', 1)[1].strip()
            elif "SAFETY:" in line.upper():
                safety = line.split(':', 1)[1].strip().split()[0]
        
        # If it's DANGEROUS, don't kill
        if "DANGEROUS" in safety.upper():
            should_kill = False
            justification += " [DANGEROUS - will not be killed]"
        
        self.decisions_history.append({
            'type': 'process',
            'process': process['name'],
            'pid': process['pid'],
            'decision': should_kill,
            'safety': safety,
            'justification': justification
        })
        
        return should_kill, justification
    
    def save_history(self, path: Path):
        """Save LLM decisions history"""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.decisions_history, f, indent=2, ensure_ascii=False)