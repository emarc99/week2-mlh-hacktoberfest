"""Streamlit Community Cloud entrypoint (share.streamlit.io defaults to this file)."""

from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).resolve().parent / "app.py"), run_name="__main__")
