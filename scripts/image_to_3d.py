"""
Image to 3D model generation using free Hugging Face Spaces.
Converts a 2D image into a 3D mesh (.glb/.obj).

Spaces (ordered by quality):
- VAST-AI/TripoSG (default - best quality, with texture support)
- stabilityai/TripoSR (fallback - fast, lower quality)
- TencentARC/InstantMesh (alternative - multi-view)
"""

import sys
import time
from pathlib import Path

from gradio_client import Client, handle_file

# Add parent to path for utils
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.utils import (
    get_output_dir,
    save_metadata,
    save_file,
    print_result,
    validate_image,
    convert_mesh_formats,
)


# Available free Spaces for image-to-3D (ordered by quality)
SPACES = {
    "triposg": {
        "space_id": "https://vast-ai-triposg.hf.space",
        "description": "TripoSG - High-fidelity 3D generation (VAST AI, best quality)",
        "output_format": "glb",
        "has_texture": True,
    },
    "triposr": {
        "space_id": "stabilityai/TripoSR",
        "description": "TripoSR - Fast single-image to 3D (Stability AI)",
        "output_format": "obj",
        "has_texture": False,
    },
    "instantmesh": {
        "space_id": "TencentARC/InstantMesh",
        "description": "InstantMesh - Multi-view reconstruction",
        "output_format": "obj",
        "has_texture": False,
    },
}

DEFAULT_SPACE = "triposg"


def image_to_3d(
    image_path: str,
    space: str = DEFAULT_SPACE,
    foreground_ratio: float = 0.85,
    resolution: int = 256,
    num_inference_steps: int = 50,
    guidance_scale: float = 7.0,
    texture: bool = True,
    target_face_num: int = 100000,
    project_name: str = None,
) -> Path:
    """
    Convert an image to a 3D model using a free HF Space.

    Args:
        image_path: Path to the input image file.
        space: Which space to use (triposg, triposr, instantmesh).
        foreground_ratio: How much of the frame the object fills (0.0-1.0).
        resolution: Marching cubes resolution (triposr only).
        num_inference_steps: Diffusion steps (triposg only, 20-100).
        guidance_scale: Guidance scale (triposg only, 1-20).
        texture: Whether to apply texture (triposg only).
        target_face_num: Target face count for mesh (triposg only).
        project_name: Optional project name for output folder.

    Returns:
        Path to the output directory containing the 3D model.
    """
    # Validate input
    image_path = str(Path(image_path).resolve())

    if not Path(image_path).exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    if not validate_image(image_path):
        raise ValueError(f"Invalid image file: {image_path}")

    if space not in SPACES:
        print(f"Unknown space '{space}'. Available: {list(SPACES.keys())}")
        print(f"Falling back to {DEFAULT_SPACE}")
        space = DEFAULT_SPACE

    space_info = SPACES[space]
    print(f"\n  Using: {space_info['description']}")
    print(f"  Space: {space_info['space_id']}")
    print(f"  Input: {image_path}")
    print(f"  Texture: {'Yes' if (texture and space_info.get('has_texture')) else 'No'}")
    print(f"  Converting to 3D...")

    start_time = time.time()

    try:
        client = Client(space_info["space_id"])

        if space == "triposg":
            # TripoSG pipeline:
            # 1. Segment foreground
            # 2. Generate 3D mesh (.glb)
            # 3. Optionally apply texture

            # Step 1: Segment
            print(f"    [1/{'3' if texture else '2'}] Segmenting foreground...")
            segmented = client.predict(
                handle_file(image_path),
                api_name="/run_segmentation",
            )

            # Step 2: Generate 3D
            print(f"    [2/{'3' if texture else '2'}] Generating 3D mesh...")
            mesh_path = client.predict(
                handle_file(segmented),      # segmented image
                0,                           # seed
                num_inference_steps,         # num_inference_steps (50)
                guidance_scale,              # guidance_scale (7.0)
                True,                        # simplify
                target_face_num,             # target_face_num (100000)
                api_name="/image_to_3d",
            )

            model_path = mesh_path

            # Step 3: Apply texture (optional)
            if texture:
                print(f"    [3/3] Applying texture...")
                try:
                    textured_path = client.predict(
                        handle_file(segmented),  # original segmented image
                        handle_file(mesh_path),  # generated mesh
                        0,                       # seed
                        api_name="/run_texture",
                    )
                    model_path = textured_path
                except Exception as tex_err:
                    print(f"    Texture failed ({tex_err}), using untextured mesh")

        elif space == "triposr":
            # TripoSR pipeline:
            # 1. Preprocess (remove background)
            # 2. Generate 3D model
            preprocessed = client.predict(
                handle_file(image_path),
                True,                     # remove_background
                foreground_ratio,         # foreground_ratio (0.5-1.0)
                api_name="/preprocess",
            )

            result = client.predict(
                handle_file(preprocessed),
                resolution,               # marching_cubes_resolution (32-320)
                api_name="/generate",
            )

            if isinstance(result, tuple):
                model_path = result[0]
            else:
                model_path = result

        elif space == "instantmesh":
            # InstantMesh pipeline:
            # 1. Preprocess
            # 2. Generate multi-view
            # 3. Reconstruct 3D
            preprocessed = client.predict(
                handle_file(image_path),
                True,
                api_name="/preprocess",
            )

            client.predict(
                handle_file(preprocessed),
                75,    # sample_steps
                42,    # sample_seed
                api_name="/generate_mvs",
            )

            result = client.predict(
                api_name="/make3d",
            )

            if isinstance(result, tuple):
                model_path = result[0] if result[0] else result[1]
            else:
                model_path = result

        duration = time.time() - start_time

        # Save to output directory
        output_dir = get_output_dir(project_name or "image_to_3d")

        # Copy input image
        save_file(image_path, output_dir, "input_image.png")

        # Save 3D model in both .obj and .glb formats
        model_ext = space_info["output_format"]
        saved_formats = convert_mesh_formats(str(model_path), output_dir)

        # Save metadata
        save_metadata(output_dir, {
            "type": "image_to_3d",
            "input_image": image_path,
            "space": space,
            "space_id": space_info["space_id"],
            "has_texture": texture and space_info.get("has_texture", False),
            "num_inference_steps": num_inference_steps if space == "triposg" else None,
            "guidance_scale": guidance_scale if space == "triposg" else None,
            "target_face_num": target_face_num if space == "triposg" else None,
            "foreground_ratio": foreground_ratio if space == "triposr" else None,
            "resolution": resolution if space == "triposr" else None,
            "output_formats": list(saved_formats.keys()),
            "duration_seconds": round(duration, 2),
            "output_files": {k: str(v) for k, v in saved_formats.items()},
        })

        print_result("Image → 3D Complete", output_dir, duration)
        return output_dir

    except Exception as e:
        print(f"\n  Error with {space_info['space_id']}: {e}")

        # Try fallback chain: triposg -> triposr
        if space == "triposg":
            print(f"  Trying fallback: triposr...")
            return image_to_3d(
                image_path=image_path,
                space="triposr",
                foreground_ratio=foreground_ratio,
                resolution=resolution,
                project_name=project_name,
            )
        elif space == "instantmesh":
            print(f"  Trying fallback: triposr...")
            return image_to_3d(
                image_path=image_path,
                space="triposr",
                foreground_ratio=foreground_ratio,
                resolution=resolution,
                project_name=project_name,
            )
        else:
            print(f"  Generation failed. The Space might be sleeping or overloaded.")
            print(f"  Try again in a few minutes.")
            raise


def main():
    """CLI entry point for image_to_3d."""
    import argparse

    parser = argparse.ArgumentParser(description="Convert image to 3D model")
    parser.add_argument("image", help="Path to input image")
    parser.add_argument("--space", "-s", default=DEFAULT_SPACE,
                        choices=list(SPACES.keys()), help="HF Space to use")
    parser.add_argument("--foreground-ratio", "-f", type=float, default=0.85,
                        help="Foreground ratio (0.0-1.0, triposr only)")
    parser.add_argument("--resolution", "-r", type=int, default=256,
                        help="Mesh resolution (triposr only)")
    parser.add_argument("--steps", type=int, default=50,
                        help="Inference steps (triposg only, 20-100)")
    parser.add_argument("--guidance", "-g", type=float, default=7.0,
                        help="Guidance scale (triposg only, 1-20)")
    parser.add_argument("--no-texture", action="store_true",
                        help="Skip texture generation (triposg only)")
    parser.add_argument("--faces", type=int, default=100000,
                        help="Target face count (triposg only)")
    parser.add_argument("--project", "-p", default=None, help="Project name")

    args = parser.parse_args()

    image_to_3d(
        image_path=args.image,
        space=args.space,
        foreground_ratio=args.foreground_ratio,
        resolution=args.resolution,
        num_inference_steps=args.steps,
        guidance_scale=args.guidance,
        texture=not args.no_texture,
        target_face_num=args.faces,
        project_name=args.project,
    )


if __name__ == "__main__":
    main()
