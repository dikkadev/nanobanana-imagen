# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "requests",
#     "pillow",
# ]
# ///
# //
import argparse
import base64
import json
import math
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from PIL import Image


GEMINI_MODEL = "gemini-3.1-flash-image-preview"
GEMINI_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)


def log(msg: str) -> None:
    """Lightweight informational logging to stderr."""
    print(msg, file=sys.stderr)


def read_prompt(args: argparse.Namespace) -> str:
    if args.prompt and args.prompt_file:
        print("Use either -p/--prompt or -f/--prompt-file, not both.", file=sys.stderr)
        sys.exit(1)

    if args.prompt:
        return args.prompt

    if args.prompt_file:
        path = Path(args.prompt_file)
        if not path.is_file():
            print(f"Prompt file not found: {path}", file=sys.stderr)
            sys.exit(1)
        return path.read_text(encoding="utf-8")

    print("You must provide -p/--prompt or -f/--prompt-file.", file=sys.stderr)
    sys.exit(1)


def encode_image(path: str) -> dict:
    p = Path(path)
    if not p.is_file():
        print(f"Input image not found: {p}", file=sys.stderr)
        sys.exit(1)

    data = base64.b64encode(p.read_bytes()).decode("utf-8")

    suffix = p.suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        mime = "image/jpeg"
    elif suffix == ".png":
        mime = "image/png"
    else:
        print(f"Unsupported image type for: {p}", file=sys.stderr)
        sys.exit(1)

    return {
        "inline_data": {
            "mime_type": mime,
            "data": data,
        }
    }


VALID_IMAGE_SIZES = ("512px", "1K", "2K", "4K")
VALID_ASPECT_RATIOS = (
    "1:1", "1:4", "1:8", "2:3", "3:2", "3:4", "4:1",
    "4:3", "4:5", "5:4", "8:1", "9:16", "16:9", "21:9",
)


def build_request_body(
    prompt: str,
    input_images: list[str] | None,
    *,
    image_size: str = "1K",
    aspect_ratio: str | None = None,
) -> dict:
    parts: list[dict] = [{"text": prompt}]

    if input_images:
        for img_path in input_images:
            parts.append(encode_image(img_path))

    image_config: dict = {"imageSize": image_size}
    if aspect_ratio:
        image_config["aspectRatio"] = aspect_ratio

    return {
        "contents": [
            {
                "parts": parts
            }
        ],
        "generationConfig": {
            "imageConfig": image_config,
        },
    }


def explain_block(response_json: dict) -> str:
    pf = response_json.get("promptFeedback") or {}
    block_reason = pf.get("blockReason")
    if not block_reason:
        return ""

    msg = f"Model did not return any image. Block reason: {block_reason}."
    safety_ratings = pf.get("safetyRatings") or []
    if safety_ratings:
        categories = ", ".join(
            f"{r.get('category','?')}={r.get('probability','?')}"
            for r in safety_ratings
        )
        msg += f" Safety ratings: {categories}."

    msg += (
        " This usually means the prompt and/or input image triggered safety filters. "
        "You cannot disable moderation; adjust the content or wording."
    )
    return msg


def extract_image_bytes(response_json: dict) -> bytes:
    candidates = response_json.get("candidates") or []
    if not candidates:
        block_msg = explain_block(response_json)
        if block_msg:
            raise RuntimeError(block_msg)

        raise RuntimeError(
            "Model did not return any candidates. Raw response (truncated):\n"
            + json.dumps(response_json, indent=2)[:2000]
        )

    try:
        parts = candidates[0]["content"]["parts"]
        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and "data" in inline:
                return base64.b64decode(inline["data"])
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Failed to extract image bytes from model response."
        ) from exc

    raise RuntimeError(
        "No inline image data found in model response. Raw response (truncated):\n"
        + json.dumps(response_json, indent=2)[:2000]
    )


def ensure_png_suffix(path: Path) -> Path:
    """Ensure the output path has a .png suffix."""
    if path.suffix:
        return path
    return path.with_suffix(".png")


def make_grid(image_paths: list[Path], out_path: Path) -> None:
    """Create a compact-ish grid from images WITHOUT resizing or cropping.

    Uses a simple 'shelf packing' algorithm:
    - Keep original image sizes.
    - Compute a target width from total area.
    - Fill rows left→right until adding another image would exceed target width,
      then start a new row.
    """
    if not image_paths:
        raise ValueError("Cannot make a grid from an empty image list.")

    images: list[Image.Image] = []
    try:
        for p in image_paths:
            img = Image.open(p)
            images.append(img.convert("RGBA"))

        sizes = [img.size for img in images]
        widths, heights = zip(*sizes)

        total_area = sum(w * h for w, h in sizes)
        # Target width ~ sqrt(total area) gives roughly square-ish result.
        target_width = int(math.sqrt(total_area))
        if target_width <= 0:
            target_width = max(widths)

        rows: list[list[int]] = []
        row_widths: list[int] = []
        row_heights: list[int] = []

        current_row: list[int] = []
        cur_w = 0
        cur_h = 0

        for idx, (w, h) in enumerate(sizes):
            if current_row and cur_w + w > target_width:
                rows.append(current_row)
                row_widths.append(cur_w)
                row_heights.append(cur_h)
                current_row = []
                cur_w = 0
                cur_h = 0

            current_row.append(idx)
            cur_w += w
            cur_h = max(cur_h, h)

        if current_row:
            rows.append(current_row)
            row_widths.append(cur_w)
            row_heights.append(cur_h)

        grid_w = max(row_widths)
        grid_h = sum(row_heights)

        grid = Image.new("RGBA", (grid_w, grid_h))
        y = 0
        for row_indices, row_h in zip(rows, row_heights):
            x = 0
            for idx in row_indices:
                img = images[idx]
                grid.paste(img, (x, y))
                x += img.size[0]
            y += row_h

        out_path = ensure_png_suffix(out_path)
        grid.save(out_path)
    finally:
        for img in images:
            try:
                img.close()
            except Exception:
                pass


def call_gemini(
    prompt: str,
    input_images: list[str],
    api_key: str,
    *,
    image_size: str = "1K",
    aspect_ratio: str | None = None,
) -> bytes:
    """Single API call that returns image bytes or raises."""
    log("Building request body...")
    body = build_request_body(
        prompt, input_images, image_size=image_size, aspect_ratio=aspect_ratio,
    )

    log("Calling Gemini API...")
    resp = requests.post(
        GEMINI_ENDPOINT,
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        json=body,
        timeout=120,
    )
    log(f"API response status: {resp.status_code}")

    if resp.status_code != 200:
        try:
            err_json = resp.json()
            msg = err_json.get("error", {}).get("message") or resp.text
        except Exception:  # noqa: BLE001
            msg = resp.text

        print("HTTP error from API:", file=sys.stderr)
        print(msg, file=sys.stderr)

        try:
            truncated = json.dumps(resp.json(), indent=2)[:2000]
            print("\nError JSON (truncated):", file=sys.stderr)
            print(truncated, file=sys.stderr)
        except Exception:
            pass

        sys.exit(1)

    try:
        response_json = resp.json()
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to parse JSON response: {exc}", file=sys.stderr)
        print(resp.text[:2000], file=sys.stderr)
        sys.exit(1)

    try:
        img_bytes = extract_image_bytes(response_json)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    return img_bytes


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate images with Nano Banana 2 (Gemini 3.1 Flash Image)."
    )
    parser.add_argument("-p", "--prompt", help="Prompt text.")
    parser.add_argument("-f", "--prompt-file", help="File containing the prompt.")
    parser.add_argument(
        "-i",
        "--input",
        dest="input_images",
        nargs="+",
        action="extend",
        metavar="IMG",
        help=(
            "Input image path(s). "
            "Supports globs via the shell, e.g. -i me/*, and can be repeated."
        ),
    )
    parser.add_argument(
        "-o",
        "--out",
        default="output.png",
        help="Output image filename (PNG). Default: output.png",
    )
    parser.add_argument(
        "-n",
        "--num-images",
        type=int,
        default=1,
        help="Number of images to generate from the same prompt and input. Default: 1",
    )
    parser.add_argument(
        "-s",
        "--size",
        default="1K",
        choices=VALID_IMAGE_SIZES,
        help="Image resolution. Default: 1K",
    )
    parser.add_argument(
        "-a",
        "--aspect-ratio",
        default=None,
        choices=VALID_ASPECT_RATIOS,
        help="Aspect ratio. Omitted by default (API decides).",
    )

    args = parser.parse_args()
    prompt = read_prompt(args)

    if args.num_images < 1:
        print("--num-images must be >= 1.", file=sys.stderr)
        sys.exit(1)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Env var GEMINI_API_KEY is required.", file=sys.stderr)
        sys.exit(1)

    # --- Informational logs ---
    log(f"Model: {GEMINI_MODEL}")
    log(f"Endpoint: {GEMINI_ENDPOINT}")
    prompt_len = len(prompt)
    prompt_preview = prompt.strip().replace("\n", " ")
    if len(prompt_preview) > 80:
        prompt_preview = prompt_preview[:77] + "..."
    log(f"Prompt length: {prompt_len} characters")
    log(f"Prompt preview: {prompt_preview!r}")
    log(f"Image size: {args.size}")
    if args.aspect_ratio:
        log(f"Aspect ratio: {args.aspect_ratio}")
    log(f"Number of images to generate: {args.num_images}")

    input_images = args.input_images or []
    if input_images:
        log(f"Number of input images: {len(input_images)}")
        for img in input_images:
            p = Path(img)
            try:
                size = p.stat().st_size
                log(f"  - {p} ({size / 1024:.1f} KiB)")
            except FileNotFoundError:
                log(f"  - {p} (missing)")
    else:
        log("No input images provided.")

    base_out_path = ensure_png_suffix(Path(args.out))

    # Determine individual output filenames.
    if args.num_images == 1:
        individual_paths = [base_out_path]
        grid_out_path: Path | None = None
    else:
        stem = base_out_path.stem
        suffix = base_out_path.suffix or ".png"
        individual_paths = [
            base_out_path.with_name(f"{stem}-{i}{suffix}")
            for i in range(1, args.num_images + 1)
        ]
        grid_out_path = base_out_path  # bare name for the grid

    # --- Parallel generation of images ---
    def generate_and_save(idx: int, out_path: Path) -> Path:
        log(f"--- Generating image {idx}/{len(individual_paths)} ---")
        img_bytes = call_gemini(
            prompt, input_images, api_key,
            image_size=args.size, aspect_ratio=args.aspect_ratio,
        )
        out_path.write_bytes(img_bytes)
        try:
            size = out_path.stat().st_size
            log(f"Wrote image → {out_path} ({size / 1024:.1f} KiB)")
        except Exception:
            log(f"Wrote image → {out_path}")
        return out_path

    written_paths: list[Path | None] = [None] * len(individual_paths)
    max_workers = min(len(individual_paths), 8)  # keep it sane

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {
            executor.submit(generate_and_save, idx, out_path): idx - 1
            for idx, out_path in enumerate(individual_paths, start=1)
        }
        for fut in as_completed(future_to_index):
            i = future_to_index[fut]
            written_paths[i] = fut.result()

    written_paths_clean = [p for p in written_paths if p is not None]

    # Create grid/montage if we generated multiple images
    if grid_out_path is not None and len(written_paths_clean) > 1:
        log("Creating grid image from generated images (no resizing/cropping)...")
        try:
            make_grid(written_paths_clean, grid_out_path)
            try:
                size = grid_out_path.stat().st_size
                log(f"Wrote grid image → {grid_out_path} ({size / 1024:.1f} KiB)")
            except Exception:
                log(f"Wrote grid image → {grid_out_path}")
        except Exception as exc:  # noqa: BLE001
            log(f"Failed to create grid image: {exc!r}")


if __name__ == "__main__":
    main()
