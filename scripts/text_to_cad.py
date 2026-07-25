"""
Text to CAD 3D model generation using FreeCAD or CadQuery.

This module allows Kiro (LLM) to write Python CAD scripts that generate
precise, parametric 3D models. Perfect for mechanical parts, enclosures,
brackets, and any geometry that needs exact dimensions.

Backends:
1. CadQuery (preferred) - pip install, no external app needed
2. FreeCAD (alternative) - needs FreeCAD installed separately

Workflow:
1. User describes what they want ("a box for Raspberry Pi")
2. LLM generates a CadQuery/FreeCAD Python script
3. This module executes the script and exports STL/OBJ/STEP
"""

import sys
import os
import time
import json
import subprocess
import tempfile
from pathlib import Path

# Add parent to path for utils
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.utils import get_output_dir, save_metadata, save_file, print_result


# ============================================================
# Backend Detection
# ============================================================

def find_freecad() -> str | None:
    """Find FreeCAD installation path. Returns FreeCADCmd executable path or None."""
    import shutil

    # Check PATH first
    cmd = shutil.which("FreeCADCmd") or shutil.which("freecadcmd")
    if cmd:
        return cmd

    # Common Windows installation paths
    search_paths = [
        r"C:\Program Files\FreeCAD 1.0\bin\FreeCADCmd.exe",
        r"C:\Program Files\FreeCAD 0.21\bin\FreeCADCmd.exe",
        r"C:\Program Files\FreeCAD 0.22\bin\FreeCADCmd.exe",
        r"C:\Program Files (x86)\FreeCAD\bin\FreeCADCmd.exe",
    ]

    # Search by glob
    import glob
    search_paths += glob.glob(r"C:\Program Files\FreeCAD*\bin\FreeCADCmd.exe")
    search_paths += glob.glob(r"C:\Users\*\AppData\Local\Programs\FreeCAD*\bin\FreeCADCmd.exe")

    for path in search_paths:
        if os.path.isfile(path):
            return path

    return None


def check_cadquery() -> bool:
    """Check if CadQuery is available."""
    try:
        import cadquery  # noqa: F401
        return True
    except ImportError:
        return False


def get_available_backend() -> str:
    """Determine which CAD backend is available."""
    if check_cadquery():
        return "cadquery"
    if find_freecad():
        return "freecad"
    return "none"


# ============================================================
# Script Execution
# ============================================================

def execute_cadquery_script(script: str, output_dir: Path, filename: str = "model") -> Path:
    """
    Execute a CadQuery script and export the result.

    Args:
        script: Python source code using CadQuery.
        output_dir: Directory to save output files.
        filename: Base name for output files.

    Returns:
        Path to the exported STL file.
    """
    # Write script to temp file with export logic appended
    export_stl = output_dir / f"{filename}.stl"
    export_step = output_dir / f"{filename}.step"

    # Append export commands to the script
    export_code = f"""

# === Auto-appended export code ===
import cadquery as cq

# Find the result variable (last CadQuery Workplane object)
_result = None
for _name in reversed(list(dir())):
    _obj = eval(_name)
    if isinstance(_obj, cq.Workplane):
        _result = _obj
        break

if _result is not None:
    cq.exporters.export(_result, r"{export_stl}")
    try:
        cq.exporters.export(_result, r"{export_step}")
    except Exception:
        pass  # STEP export may fail in some cases
    print(f"EXPORT_SUCCESS: {{r'{export_stl}'}}")
else:
    print("EXPORT_FAILED: No CadQuery Workplane result found")
"""

    full_script = script + export_code

    # Write to temp file
    script_file = output_dir / f"{filename}_script.py"
    with open(script_file, "w", encoding="utf-8") as f:
        f.write(full_script)

    # Execute using project's Python (with cadquery installed)
    python_exe = str(Path(__file__).parent.parent / ".venv" / "Scripts" / "python.exe")

    result = subprocess.run(
        [python_exe, str(script_file)],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(output_dir),
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"CadQuery script failed:\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}"
        )

    if "EXPORT_SUCCESS" in result.stdout:
        return export_stl
    else:
        raise RuntimeError(
            f"Script ran but no model was exported.\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}"
        )


def execute_freecad_script(script: str, output_dir: Path, filename: str = "model") -> Path:
    """
    Execute a FreeCAD script using FreeCADCmd.

    Args:
        script: Python source code using FreeCAD API.
        output_dir: Directory to save output files.
        filename: Base name for output files.

    Returns:
        Path to the exported STL file.
    """
    freecad_cmd = find_freecad()
    if not freecad_cmd:
        raise RuntimeError("FreeCAD not found. Install from https://www.freecad.org/downloads.php")

    export_stl = output_dir / f"{filename}.stl"
    export_step = output_dir / f"{filename}.step"

    # Append export commands
    export_code = f"""

# === Auto-appended export code ===
import FreeCAD
import Mesh
import Part

doc = FreeCAD.ActiveDocument
if doc and doc.Objects:
    # Export STL
    objs = [obj for obj in doc.Objects if hasattr(obj, 'Shape')]
    if objs:
        Mesh.export(objs, r"{export_stl}")
        print(f"EXPORT_SUCCESS: {{r'{export_stl}'}}")
        # Try STEP export
        try:
            shapes = [obj.Shape for obj in objs]
            compound = Part.makeCompound(shapes)
            compound.exportStep(r"{export_step}")
        except Exception:
            pass
    else:
        print("EXPORT_FAILED: No objects with Shape found")
else:
    print("EXPORT_FAILED: No active document or objects")
"""

    full_script = script + export_code

    # Write to temp file
    script_file = output_dir / f"{filename}_script.py"
    with open(script_file, "w", encoding="utf-8") as f:
        f.write(full_script)

    # Execute using FreeCADCmd
    result = subprocess.run(
        [freecad_cmd, "--console", str(script_file)],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(output_dir),
    )

    if "EXPORT_SUCCESS" in result.stdout:
        return export_stl
    else:
        raise RuntimeError(
            f"FreeCAD script failed:\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}"
        )


# ============================================================
# Main Entry Point
# ============================================================

def text_to_cad(
    script: str,
    backend: str = "auto",
    project_name: str = None,
    filename: str = "model",
    description: str = "",
) -> Path:
    """
    Execute a CAD script and save the output.

    Args:
        script: Python CAD script (CadQuery or FreeCAD syntax).
        backend: "cadquery", "freecad", or "auto" (detect best available).
        project_name: Optional project name for output folder.
        filename: Base filename for exports.
        description: Human description of what was generated.

    Returns:
        Path to the output directory.
    """
    # Auto-detect backend
    if backend == "auto":
        backend = get_available_backend()
        if backend == "none":
            print("\n  No CAD backend available!")
            print("  Install CadQuery (recommended):")
            print("    uv pip install cadquery")
            print("  Or install FreeCAD:")
            print("    https://www.freecad.org/downloads.php")
            raise RuntimeError("No CAD backend available. Install cadquery or FreeCAD.")

    print(f"\n  Backend: {backend}")
    print(f"  Generating CAD model...")

    start_time = time.time()
    output_dir = get_output_dir(project_name or "cad_model")

    # Save the source script
    script_path = output_dir / f"{filename}_script.py"
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)

    # Execute
    if backend == "cadquery":
        stl_path = execute_cadquery_script(script, output_dir, filename)
    elif backend == "freecad":
        stl_path = execute_freecad_script(script, output_dir, filename)
    else:
        raise ValueError(f"Unknown backend: {backend}")

    duration = time.time() - start_time

    # Save metadata
    save_metadata(output_dir, {
        "type": "text_to_cad",
        "backend": backend,
        "description": description,
        "duration_seconds": round(duration, 2),
        "output_file": str(stl_path),
        "script_file": str(script_path),
    })

    print_result("CAD Model Generated", output_dir, duration)
    return output_dir


def setup_cadquery():
    """Install CadQuery into the project's virtual environment."""
    print("Installing CadQuery...")
    python_exe = str(Path(__file__).parent.parent / ".venv" / "Scripts" / "python.exe")

    result = subprocess.run(
        [python_exe, "-m", "pip", "install", "cadquery"],
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode == 0:
        print("  CadQuery installed successfully!")
        return True
    else:
        print(f"  Installation failed: {result.stderr}")
        # Try with uv
        import shutil
        uv = shutil.which("uv")
        if uv:
            result = subprocess.run(
                [uv, "pip", "install", "cadquery"],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(Path(__file__).parent.parent),
            )
            if result.returncode == 0:
                print("  CadQuery installed with uv!")
                return True

        print("  Failed to install CadQuery.")
        print("  Try manually: uv pip install cadquery")
        return False


def status():
    """Print the current CAD backend status."""
    print("\n  CAD Backend Status:")
    print(f"  {'='*40}")

    # CadQuery
    cq_available = check_cadquery()
    print(f"  CadQuery: {'Available' if cq_available else 'Not installed'}")
    if not cq_available:
        print(f"    Install: uv pip install cadquery")

    # FreeCAD
    freecad_path = find_freecad()
    print(f"  FreeCAD:  {'Available' if freecad_path else 'Not installed'}")
    if freecad_path:
        print(f"    Path: {freecad_path}")
    else:
        print(f"    Install: https://www.freecad.org/downloads.php")

    active = get_available_backend()
    print(f"\n  Active backend: {active}")
    print(f"  {'='*40}\n")


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Execute CAD script to generate 3D model")
    subparsers = parser.add_subparsers(dest="command")

    # Status command
    subparsers.add_parser("status", help="Show CAD backend status")

    # Setup command
    subparsers.add_parser("setup", help="Install CadQuery")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run a CAD script file")
    run_parser.add_argument("script_file", help="Path to Python CAD script")
    run_parser.add_argument("--backend", "-b", default="auto",
                            choices=["auto", "cadquery", "freecad"])
    run_parser.add_argument("--project", "-p", default=None)
    run_parser.add_argument("--filename", "-f", default="model")

    args = parser.parse_args()

    if args.command == "status":
        status()
    elif args.command == "setup":
        setup_cadquery()
    elif args.command == "run":
        with open(args.script_file, "r", encoding="utf-8") as f:
            script = f.read()
        text_to_cad(
            script=script,
            backend=args.backend,
            project_name=args.project,
            filename=args.filename,
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
