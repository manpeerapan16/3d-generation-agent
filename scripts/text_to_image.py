"""
Text to Image generation using free Hugging Face Spaces.
Generates reference images that can be fed into Image→3D pipeline.

Spaces used:
- stabilityai/stable-diffusion-3.5-large (primary)
- black-forest-labs/FLUX.1-schnell (fallback, fast)
"""

import sys
import time
from pathlib import Path

from gradio_client import Client, handle_file

# Add parent to path for utils
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.utils import get_output_dir, save_metadata, save_file, print_result


# Available free Spaces for text-to-image
SPACES = {
    "flux-schnell": {
        "space_id": "black-forest-labs/FLUX.1-schnell",
        "description": "FLUX.1 Schnell - Fast, high quality",
    },
    "sd-3.5": {
        "space_id": "stabilityai/stable-diffusion-3-5-large",
        "description": "Stable Diffusion 3.5 Large",
    },
    "sdxl": {
        "space_id": "KingNish/SDXL-Flash",
        "description": "SDXL Flash - Fast SDXL variant",
    },
}

DEFAULT_SPACE = "flux-schnell"


def text_to_image(
    prompt: str,
    negative_prompt: str = "",
    space: str = DEFAULT_SPACE,
    seed: int = 0,
    width: int = 1024,
    height: int = 1024,
    num_steps: int = 4,
    project_name: str = None,
) -> Path:
    """
    Generate an image from a text prompt using a free HF Space.

    Args:
        prompt: Text description of the image to generate.
        negative_prompt: Things to avoid in the generation.
        space: Which space to use (flux-schnell, sd-3.5, sdxl).
        seed: Random seed for reproducibility (0 = random).
        width: Image width in pixels.
        height: Image height in pixels.
        num_steps: Number of inference steps.
        project_name: Optional project name for output folder.

    Returns:
        Path to the output directory containing the generated image.
    """
    if space not in SPACES:
        print(f"Unknown space '{space}'. Available: {list(SPACES.keys())}")
        print(f"Falling back to {DEFAULT_SPACE}")
        space = DEFAULT_SPACE

    space_info = SPACES[space]
    print(f"\n  Using: {space_info['description']}")
    print(f"  Space: {space_info['space_id']}")
    print(f"  Prompt: {prompt}")
    print(f"  Generating...")

    start_time = time.time()

    try:
        client = Client(space_info["space_id"])

        # Different spaces have different API signatures
        if space == "flux-schnell":
            result = client.predict(
                prompt=prompt,
                seed=seed,
                randomize_seed=seed == 0,
                width=width,
                height=height,
                num_inference_steps=num_steps,
                api_name="/infer",
            )
            # FLUX returns (image_path, seed)
            if isinstance(result, tuple):
                image_path = result[0]
            else:
                image_path = result

        elif space == "sd-3.5":
            result = client.predict(
                prompt=prompt,
                negative_prompt=negative_prompt or "low quality, blurry, distorted",
                seed=seed,
                randomize_seed=seed == 0,
                width=width,
                height=height,
                num_inference_steps=num_steps if num_steps > 4 else 28,
                api_name="/infer",
            )
            if isinstance(result, tuple):
                image_path = result[0]
            else:
                image_path = result

        elif space == "sdxl":
            result = client.predict(
                prompt=prompt,
                negative_prompt=negative_prompt or "low quality, blurry",
                seed=seed,
                width=width,
                height=height,
                api_name="/predict",
            )
            if isinstance(result, tuple):
                image_path = result[0]
            else:
                image_path = result

        duration = time.time() - start_time

        # Save to output directory
        output_dir = get_output_dir(project_name or "text_to_image")

        # Determine filename
        saved_path = save_file(str(image_path), output_dir, "generated_image.png")

        # Save metadata
        save_metadata(output_dir, {
            "type": "text_to_image",
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "space": space,
            "space_id": space_info["space_id"],
            "seed": seed,
            "width": width,
            "height": height,
            "num_steps": num_steps,
            "duration_seconds": round(duration, 2),
            "output_file": str(saved_path),
        })

        print_result("Text → Image Complete", output_dir, duration)
        return output_dir

    except Exception as e:
        print(f"\n  Error with {space_info['space_id']}: {e}")

        # Try fallback
        if space != DEFAULT_SPACE:
            print(f"  Trying fallback: {DEFAULT_SPACE}...")
            return text_to_image(
                prompt=prompt,
                negative_prompt=negative_prompt,
                space=DEFAULT_SPACE,
                seed=seed,
                width=width,
                height=height,
                num_steps=num_steps,
                project_name=project_name,
            )
        else:
            print(f"  All spaces failed. Please try again later.")
            raise


def main():
    """CLI entry point for text_to_image."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate image from text prompt")
    parser.add_argument("prompt", help="Text description of the image")
    parser.add_argument("--negative", "-n", default="", help="Negative prompt")
    parser.add_argument("--space", "-s", default=DEFAULT_SPACE,
                        choices=list(SPACES.keys()), help="HF Space to use")
    parser.add_argument("--seed", type=int, default=0, help="Random seed (0=random)")
    parser.add_argument("--width", "-W", type=int, default=1024, help="Image width")
    parser.add_argument("--height", "-H", type=int, default=1024, help="Image height")
    parser.add_argument("--steps", type=int, default=4, help="Inference steps")
    parser.add_argument("--project", "-p", default=None, help="Project name")

    args = parser.parse_args()

    text_to_image(
        prompt=args.prompt,
        negative_prompt=args.negative,
        space=args.space,
        seed=args.seed,
        width=args.width,
        height=args.height,
        num_steps=args.steps,
        project_name=args.project,
    )


if __name__ == "__main__":
    main()
