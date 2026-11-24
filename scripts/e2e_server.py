import os
import subprocess
import sys
from pathlib import Path

manage = str(Path(__file__).resolve().parents[1] / 'backend' / 'manage.py')
subprocess.run([sys.executable, manage, 'prepare_e2e'], check=True)
worker = subprocess.Popen([sys.executable, manage, 'poll_gps', '--provider', 'simulation'])
try:
    subprocess.run([sys.executable, manage, 'runserver', '127.0.0.1:8000', '--noreload'], check=True)
finally:
    worker.terminate()
    worker.wait(timeout=10)
