# 3D Generation Agent

AI-powered 3D model generation using free Hugging Face Spaces. No API keys, no payments, no GPU required.

Built with [Kiro](https://kiro.dev) steering skills inspired by [Meshy AI](https://github.com/meshy-dev/meshy-3d-agent) workflow patterns.

## Features

- **Text → 3D**: Generate 3D models from text descriptions
- **Image → 3D**: Convert any image into a 3D mesh
- **Text → Image**: Generate reference images for 3D conversion
- **Auto-fallback**: If one Space is down, automatically tries alternatives
- **Organized output**: Timestamped folders with metadata tracking

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Generate a 3D model from text

```bash
python scripts/text_to_3d.py "a cute robot toy"
```

### 3. Convert an image to 3D

```bash
python scripts/image_to_3d.py path/to/your/image.png
```

## Pipelines

| Pipeline | Command | Speed | Quality |
|----------|---------|-------|---------|
| Two-Stage (recommended) | `python scripts/text_to_3d.py "prompt" --pipeline two-stage` | ~2-5 min | High |
| Direct | `python scripts/text_to_3d.py "prompt" --pipeline direct` | ~30s-1min | Basic |
| Image → 3D | `python scripts/image_to_3d.py image.png` | ~30s-2min | Good |
| Text → Image only | `python scripts/text_to_image.py "prompt"` | ~10-30s | High |

## How It Works

```
Text → [FLUX.1 Schnell] → Image → [TripoSR] → 3D Model (.obj/.glb)
              ↑                          ↑
     Hugging Face Space          Hugging Face Space
          (free)                      (free)
```

All processing happens on Hugging Face's infrastructure via their free Gradio API. Your machine only sends requests and downloads results.

## Available Spaces

### Text → Image
- **FLUX.1 Schnell** (default) - Fast, high quality
- **Stable Diffusion 3.5 Large** - High quality, slower
- **SDXL Flash** - Fast fallback

### Image → 3D
- **TripoSR** (default) - Fast single-image to 3D by Stability AI
- **InstantMesh** - Higher quality multi-view reconstruction

### Text → 3D (Direct)
- **Shap-E** - OpenAI's direct text-to-3D model

## Output

Generated files are saved to `output/` with this structure:

```
output/
└── text_to_3d_twostage_20250725_143022/
    ├── reference_image.png    # Generated reference image
    ├── model.obj              # 3D model file
    └── metadata.json          # Generation parameters & timing
```

## Usage with Kiro

This project includes a Kiro steering file (`.kiro/steering/3d-generation.md`) that teaches Kiro how to use these scripts. Simply ask Kiro in natural language:

- "สร้างโมเดล 3D แมวให้หน่อย"
- "แปลงรูปนี้เป็น 3D"
- "สร้างรูป concept ดาบวิเศษ"

Kiro will automatically choose the right pipeline and execute it.

## CLI Options

### text_to_3d.py

```
python scripts/text_to_3d.py "prompt" [options]

Options:
  --pipeline {direct,two-stage}  Generation pipeline (default: two-stage)
  --seed INT                     Random seed (0=random)
  --project, -p NAME             Project name for output folder
```

### image_to_3d.py

```
python scripts/image_to_3d.py image_path [options]

Options:
  --space, -s {triposr,instantmesh}  HF Space to use
  --foreground-ratio, -f FLOAT       Object framing (0.0-1.0, default: 0.85)
  --resolution, -r INT               Mesh resolution (default: 256)
  --project, -p NAME                 Project name for output folder
```

### text_to_image.py

```
python scripts/text_to_image.py "prompt" [options]

Options:
  --space, -s {flux-schnell,sd-3.5,sdxl}  HF Space to use
  --negative, -n TEXT                      Negative prompt
  --seed INT                               Random seed (0=random)
  --width, -W INT                          Image width (default: 1024)
  --height, -H INT                         Image height (default: 1024)
  --steps INT                              Inference steps (default: 4)
  --project, -p NAME                       Project name for output folder
```

## Requirements

- Python 3.8+
- Internet connection
- No GPU needed
- No API keys needed

## Limitations

- Queue times vary (30s - 5min) depending on Space load
- No rigging/animation (use Blender or Mixamo separately)
- Spaces may sleep if unused — first request may take longer
- Heavy usage may trigger Hugging Face rate limits

## License

MIT
