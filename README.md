# Nano Banana 2

Single-file CLI for generating images with Google's Gemini 3.1 Flash model. Supports text-to-image, image-to-image, batch generation with parallel API calls, and automatic grid composition.

## Setup

Requires Python 3.13+ and a [Gemini API key](https://aistudio.google.com/apikey).

```bash
export GEMINI_API_KEY="your-key-here"
```

Dependencies (`requests`, `pillow`) are declared inline via [PEP 723](https://peps.python.org/pep-0723/) — `uv run` handles them automatically.

## Usage

```bash
# text-to-image
uv run img.py -p "a cat wearing sunglasses"

# prompt from file
uv run img.py -f my-prompt.prompt -o portrait.png

# image-to-image with reference photos
uv run img.py -p "oil painting style" -i photo.jpg -o painting.png

# multiple reference images (shell glob)
uv run img.py -p "blend these" -i in_photos/* -o blended.png

# batch: generate 4 variations in parallel, get a grid
uv run img.py -p "sunset landscape" -n 4 -s 2K -a 16:9 -o sunset.png
# → sunset-1.png, sunset-2.png, sunset-3.png, sunset-4.png, sunset.png (grid)
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `-p, --prompt` | Prompt text | — |
| `-f, --prompt-file` | Read prompt from file | — |
| `-i, --input` | Reference image(s), repeatable | none |
| `-o, --out` | Output filename | `output.png` |
| `-n, --num-images` | Number of images to generate in parallel | `1` |
| `-s, --size` | Resolution: `512px`, `1K`, `2K`, `4K` | `1K` |
| `-a, --aspect-ratio` | Aspect ratio (e.g. `16:9`, `3:2`, `9:16`) | API default |

## Batch output

When `-n` is greater than 1, individual images are written as `<name>-1.png`, `<name>-2.png`, etc. A grid image combining all results is saved to the base output name. The grid uses shelf-packing at original resolution — no resizing or cropping.

## Viewer

Open `viewer.html` in a browser to live-monitor generation progress. It auto-refreshes and displays output images in a grid.
