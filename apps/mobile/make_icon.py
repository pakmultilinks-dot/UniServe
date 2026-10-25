"""Compatibility entry point: rasterize the existing UniServe SVG using make_icon.cjs.
No UI reference image is used. Set UNISERVE_SHARP_MODULE if sharp is installed outside the workspace.
"""
from pathlib import Path
import subprocess
subprocess.run(["node", str(Path(__file__).with_suffix(".cjs"))], check=True)
