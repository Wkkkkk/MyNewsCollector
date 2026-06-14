import sys
from pathlib import Path

# Make the repo root importable so `import news_collect...` works under pytest.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
