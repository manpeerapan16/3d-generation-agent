"""
Text to 3D model generation using free Hugging Face Spaces.
Combines text→image and image→3D for best results,
or uses direct text→3D models when available.

Pipelines:
1. Direct: Text → Shap-E → 3D (fast, lower quality)
2. Two-stage: Text → FLUX image → TripoSR 3D (slower, better quality)
"""

import sys
import time
from pathlib import Path

from gradio_client import Client, handle_file

# Add parent to path for utils
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.utils import get_output_dir, save_metadata, save_file, print_result, convert_mesh_formats
from scripts.text_to_image import text_to_image
from scripts.image_to_3d import image_to_3d


# Direct text-to-3D Spaces
SPACES = {
    "shap-e": {
        "space_id": "hysts/Shap-E",
        "description": "Shap-E (OpenAI) - Direct text to 3D",
        "output_format": "glb",
    },
}

DEFAULT_PIPELINE = "two-stage"  # Best quality


def text_to_3d_direct(
    prompt: str,
    space: str = "shap-e",
    seed: int = 0,
    num_steps: int = 64,
    guidance_scale: float = 15.0,
    project_name: str = None,
) -> Path:
    """
    Generate a 3D model directly from text using Shap-E.
    Faster but lower quality than the two-stage pipeline.

    Args:
        prompt: Text description of the 3D object.
        space: Which space to use.
        seed: Random seed (0 = random).
        num_steps: Number of inference steps.
        guidance_scale: How closely to follow the prompt.
        project_name: Optional project name for output folder.

    Returns:
        Path to the output directory containing the 3D model.
    """
    space_info = SPACES.get(space, SPACES["shap-e"])
    print(f"\n  Pipeline: Direct Text → 3D")
    print(f"  Using: {space_info['description']}")
    print(f"  Prompt: {prompt}")
    print(f"  Generating...")

    start_time = time.time()

    try:
        client = Client(space_info["space_id"])

        result = client.predict(
            prompt=prompt,
            seed=seed,
            guidance_scale=guidance_scale,
            num_inference_steps=num_steps,
            api_name="/text-to-3d",
        )

        # Shap-E returns the path to a .glb file
        if isinstance(result, tuple):
            model_path = result[0]
        else:
            model_path = result

        duration = time.time() - start_time

        # Save to output directory
        output_dir = get_output_dir(project_name or "text_to_3d")

        # Save 3D model in both .obj and .glb formats
        saved_formats = convert_mesh_formats(str(model_path), output_dir)

        # Save metadata
        save_metadata(output_dir, {
            "type": "text_to_3d_direct",
            "pipeline": "direct",
            "prompt": prompt,
            "space": space,
            "space_id": space_info["space_id"],
            "seed": seed,
            "num_steps": num_steps,
            "guidance_scale": guidance_scale,
            "output_formats": list(saved_formats.keys()),
            "duration_seconds": round(duration, 2),
            "output_files": {k: str(v) for k, v in saved_formats.items()},
        })

        print_result("Text → 3D (Direct) Complete", output_dir, duration)
        return output_dir

    except Exception as e:
        print(f"\n  Error with direct generation: {e}")
        print(f"  Falling back to two-stage pipeline...")
        return text_to_3d_twostage(prompt=prompt, project_name=project_name)


def text_to_3d_twostage(
    prompt: str,
    image_space: str = "flux-schnell",
    model_space: str = "triposg",
    seed: int = 0,
    project_name: str = None,
) -> Path:
    """
    Generate a 3D model from text using a two-stage pipeline:
    1. Text → Image (using FLUX/SD)
    2. Image → 3D (using TripoSG)

    Better quality than direct methods.

    Args:
        prompt: Text description of the 3D object.
        image_space: Space for image generation.
        model_space: Space for 3D generation.
        seed: Random seed.
        project_name: Optional project name.

    Returns:
        Path to the output directory containing the 3D model.
    """
    print(f"\n  Pipeline: Two-Stage (Text → Image → 3D)")
    print(f"  Prompt: {prompt}")

    start_time = time.time()

    # Enhance prompt for 3D-friendly image generation
    enhanced_prompt = _enhance_prompt_for_3d(prompt)
    print(f"  Enhanced prompt: {enhanced_prompt}")

    # Stage 1: Text → Image
    print(f"\n  [Stage 1/2] Generating reference image...")
    image_dir = text_to_image(
        prompt=enhanced_prompt,
        negative_prompt="multiple objects, text, watermark, blurry, low quality, background clutter",
        space=image_space,
        seed=seed,
        width=1024,
        height=1024,
        project_name=None,  # Temp, we'll reorganize
    )

    # Find the generated image
    image_file = None
    for f in image_dir.iterdir():
        if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            image_file = f
            break

    if not image_file:
        raise RuntimeError("Image generation failed - no image file produced")

    # Stage 2: Image → 3D
    print(f"\n  [Stage 2/2] Converting image to 3D model...")
    model_dir = image_to_3d(
        image_path=str(image_file),
        space=model_space,
        project_name=None,  # Temp
    )

    duration = time.time() - start_time

    # Consolidate output into one folder
    final_dir = get_output_dir(project_name or "text_to_3d_twostage")

    # Copy reference image
    for f in image_dir.iterdir():
        if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            save_file(str(f), final_dir, "reference_image.png")
            break

    # Copy all model formats (.obj and .glb) from model_dir
    for f in model_dir.iterdir():
        if f.suffix.lower() in (".obj", ".glb", ".fbx", ".stl", ".ply"):
            save_file(str(f), final_dir, f"model{f.suffix}")

    # Save combined metadata
    save_metadata(final_dir, {
        "type": "text_to_3d_twostage",
        "pipeline": "two-stage",
        "prompt": prompt,
        "enhanced_prompt": enhanced_prompt,
        "image_space": image_space,
        "model_space": model_space,
        "seed": seed,
        "duration_seconds": round(duration, 2),
    })

    print_result("Text → 3D (Two-Stage) Complete", final_dir, duration)
    return final_dir


def _enhance_prompt_for_3d(prompt: str) -> str:
    """
    Enhance a text prompt to produce better images for 3D conversion.
    Adds keywords that help produce clean, single-object images.
    """
    # Check if prompt already has 3D-friendly terms
    lower = prompt.lower()
    additions = []

    if "3d" not in lower and "render" not in lower:
        additions.append("3d render")

    if "white background" not in lower and "clean background" not in lower:
        additions.append("white background")

    if "single" not in lower and "isolated" not in lower:
        additions.append("single object, centered")

    if "studio" not in lower:
        additions.append("studio lighting")

    if additions:
        return f"{prompt}, {', '.join(additions)}"
    return prompt


def text_to_3d(
    prompt: str,
    pipeline: str = DEFAULT_PIPELINE,
    seed: int = 0,
    project_name: str = None,
    **kwargs,
) -> Path:
    """
    Main entry point for text to 3D generation.

    Args:
        prompt: Text description of the 3D object to generate.
        pipeline: "direct" (Shap-E, fast) or "two-stage" (FLUX+TripoSR, better).
        seed: Random seed.
        project_name: Optional project name.

    Returns:
        Path to the output directory.
    """
    if pipeline == "direct":
        return text_to_3d_direct(
            prompt=prompt,
            seed=seed,
            project_name=project_name,
            **kwargs,
        )
    else:
        return text_to_3d_twostage(
            prompt=prompt,
            seed=seed,
            project_name=project_name,
            **kwargs,
        )


def main():
    """CLI entry point for text_to_3d."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate 3D model from text")
    parser.add_argument("prompt", help="Text description of the 3D object")
    parser.add_argument("--pipeline", choices=["direct", "two-stage"],
                        default=DEFAULT_PIPELINE,
                        help="Generation pipeline (default: two-stage)")
    parser.add_argument("--seed", type=int, default=0, help="Random seed (0=random)")
    parser.add_argument("--project", "-p", default=None, help="Project name")

    args = parser.parse_args()

    text_to_3d(
        prompt=args.prompt,
        pipeline=args.pipeline,
        seed=args.seed,
        project_name=args.project,
    )


if __name__ == "__main__":
    main()
