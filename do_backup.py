import shutil
import os

src = r'c:\Code\prediction-bot'
dst = r'c:\Code\prediction-bot-backup-20241214'

# Remove dst if exists
if os.path.exists(dst):
    shutil.rmtree(dst)

# Copy, ignoring backup script and __pycache__
shutil.copytree(src, dst, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'do_backup.py', 'prediction-bot-backup*', 'nul'))
print(f"Backed up to {dst}")
