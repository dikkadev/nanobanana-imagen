# nanobanana-imagen

A lightweight CLI tool for generating images using the Google Gemini 3 Pro Image API.

## Features

- 🎨 Generate high-quality 2K images from text prompts
- 📷 Support for input images (image-to-image transformations)
- 🔄 Generate multiple images in parallel from the same prompt
- 🖼️ Automatic grid creation when generating multiple images
- 📄 Load prompts from text files for complex/reusable prompts

## Requirements

- Python 3.13+
- A Google Gemini API key with access to the `gemini-3-pro-image-preview` model

## Installation

This script uses inline script metadata ([PEP 723](https://peps.python.org/pep-0723/)), so you can run it directly with [uv](https://github.com/astral-sh/uv):

```bash
uv run img.py --help
```

Or install dependencies manually:

```bash
pip install requests pillow
```

## Setup

Set your Gemini API key as an environment variable:

```bash
export GEMINI_API_KEY="your-api-key-here"
```

## Usage

### Basic Usage

Generate an image from a text prompt:

```bash
uv run img.py -p "a cheeseburger working in an office"
```

### Using a Prompt File

For complex prompts, save them to a file:

```bash
uv run img.py -f prompt.txt -o my-image.png
```

### Image-to-Image Generation

Use input images for reference or transformation:

```bash
uv run img.py -p "Make this photo look like a painting" -i photo.jpg -o painting.png
```

Multiple input images are supported:

```bash
uv run img.py -p "Combine these photos" -i image1.jpg -i image2.png -o combined.png
```

Or use shell globs:

```bash
uv run img.py -p "Create a collage" -i photos/* -o collage.png
```

### Generate Multiple Images

Generate multiple variations from the same prompt:

```bash
uv run img.py -p "a sunset over mountains" -n 4 -o sunset.png
```

This creates:
- `sunset-1.png`, `sunset-2.png`, `sunset-3.png`, `sunset-4.png` (individual images)
- `sunset.png` (a grid combining all images)

## CLI Options

| Option | Description |
|--------|-------------|
| `-p`, `--prompt` | Text prompt for image generation |
| `-f`, `--prompt-file` | Path to a file containing the prompt |
| `-i`, `--input` | Input image path(s) for reference |
| `-o`, `--out` | Output filename (default: `output.png`) |
| `-n`, `--num-images` | Number of images to generate (default: `1`) |

## Example Prompt Files

### Simple Prompt

```text
a cheeseburger working in an office
```

### Detailed Portrait Prompt

```text
Keep the facial features of the person in the uploaded image exactly consistent. Style : A cinematic, emotional portrait shot on Kodak Portra 400 film . Setting : An urban street coffee shop window at Golden Hour (sunset) . Warm, nostalgic lighting hitting the side of the face. Atmosphere : Apply a subtle film grain and soft focus to create a dreamy, storytelling vibe. Action : The subject is looking very slightly away from the camera by having his head turned, his body is facing toward the camera, holding a coffee cup, with a relaxed, candid expression. Details : High quality, depth of field, bokeh background of city lights. Beautiful.
```

## Image Specifications

- **Resolution**: 2K
- **Aspect Ratio**: 1:1
- **Format**: PNG
- **Supported Input Formats**: JPEG, PNG

## License

MIT
