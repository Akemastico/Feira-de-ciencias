import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Nunca carregar Whisper/Kokoro durante os testes, e não escrever log em disco.
os.environ["BMO_PRELOAD"] = "0"
os.environ["LOG_TO_FILE"] = "0"
os.environ["LOG_LEVEL"] = "WARNING"
