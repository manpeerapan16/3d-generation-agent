"""
Utility functions for the 3D Generation Agent.
Handles file management, output organization, and common helpers.
"""

import os
import json
import shutil
from datetime import datetime
from pathlib import Path


# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"


def get_output_dir(project_name: str = None) -> Path:
    """
    Get or create an output directory for generated files.
    Organizes by project name and timestamp.

    Args:
        project_name: Optional name for the project subfolder.
                      If None, uses timestamp only.

    Returns:
        Path to the output directory.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if project_name:
        # Sanitize project name
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in project_name)
        folder_name = f"{safe_name}_{timestamp}"
    else:
        folder_name = timestamp

    output_path = OUTPUT_DIR / folder_name
    output_path.mkdir(parents=True, exist_ok=True)

    return output_path


def save_metadata(output_path: Path, metadata: dict) -> Path:
    """
    Save generation metadata as JSON alongside the output file.

    Args:
        output_path: Directory where metadata will be saved.
        metadata: Dictionary with generation parameters and results.

    Returns:
        Path to the metadata file.
    """
    meta_file = output_path / "metadata.json"

    # Add timestamp
    metadata["generated_at"] = datetime.now().isoformat()

    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    return meta_file


def save_file(source_path: str, output_dir: Path, filename: str = None) -> Path:
    """
    Copy a generated file to the output directory.

    Args:
        source_path: Path to the source file (from Gradio temp).
        output_dir: Target output directory.
        filename: Optional custom filename. If None, uses original name.

    Returns:
        Path to the saved file.
    """
    source = Path(source_path)

    if filename:
        dest = output_dir / filename
    else:
        dest = output_dir / source.name

    shutil.copy2(str(source), str(dest))
    return dest


def format_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}m {secs:.1f}s"


def print_result(title: str, output_path: Path, duration: float = None):
    """Print a formatted result summary."""
    print(f"\n{'='*50}")
    print(f"  {title}")
    print(f"{'='*50}")
    print(f"  Output: {output_path}")

    if duration:
        print(f"  Duration: {format_duration(duration)}")

    # List generated files
    if output_path.is_dir():
        files = [f for f in output_path.iterdir() if f.name != "metadata.json"]
        if files:
            print(f"  Files:")
            for f in files:
                size = f.stat().st_size
                size_str = f"{size/1024:.1f}KB" if size < 1024*1024 else f"{size/1024/1024:.1f}MB"
                print(f"    - {f.name} ({size_str})")

    print(f"{'='*50}\n")


def validate_image(image_path: str) -> bool:
    """
    Validate that a file is a readable image.

    Args:
        image_path: Path to the image file.

    Returns:
        True if valid image, False otherwise.
    """
    try:
        from PIL import Image
        img = Image.open(image_path)
        img.verify()
        return True
    except Exception:
        return False


def list_outputs() -> list:
    """
    List all generated outputs with their metadata.

    Returns:
        List of dicts with output info.
    """
    results = []

    if not OUTPUT_DIR.exists():
        return results

    for folder in sorted(OUTPUT_DIR.iterdir(), reverse=True):
        if not folder.is_dir() or folder.name.startswith("."):
            continue

        info = {"path": str(folder), "name": folder.name, "files": []}

        # Read metadata if available
        meta_file = folder / "metadata.json"
        if meta_file.exists():
            with open(meta_file, "r", encoding="utf-8") as f:
                info["metadata"] = json.load(f)

        # List files
        for f in folder.iterdir():
            if f.name != "metadata.json" and not f.name.startswith("."):
                info["files"].append({
                    "name": f.name,
                    "size": f.stat().st_size
                })

        results.append(info)

    return results
