"""Gemini Image Generation MCP Server.

Provides tools for single and batch image generation:
- generate_background_image: Single image generation
- generate_transparent_image: Single image with background removal
- batch_generate_background_images: Batch image generation
- batch_generate_transparent_images: Batch images with background removal
"""

import io
import json
import mimetypes
import os
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types
from mcp.server.fastmcp import FastMCP
from PIL import Image
from rembg import remove, new_session

load_dotenv(Path(__file__).parent / ".env")

mcp = FastMCP("gemini-image")

def _get_client() -> genai.Client:
    """Create a Gemini API client from environment variable."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY environment variable is not set. "
            "Please set it to your Gemini API key."
        )
    return genai.Client(api_key=api_key)


def _get_reference_part(reference_image_path: str) -> types.Part:
    """Create an inline Gemini image part from a local file path."""
    path = Path(reference_image_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Reference image not found: {path}")

    mime_type, _ = mimetypes.guess_type(path.name)
    return types.Part.from_bytes(
        data=path.read_bytes(),
        mime_type=mime_type or "image/png",
    )


def _build_contents(
    prompt: str,
    reference_image_path: str | None = None,
) -> str | list[types.Part]:
    """Build Gemini contents with optional text + reference image."""
    if not reference_image_path:
        return prompt

    reference_prompt = (
        "Use the attached reference image as the visual anchor. Preserve the "
        "same subject, style, proportions, and overall composition unless the "
        f"prompt explicitly asks for a change.\n\n{prompt}"
    )
    return [
        types.Part.from_text(text=reference_prompt),
        _get_reference_part(reference_image_path),
    ]


def _generate_image(
    prompt: str,
    reference_image_path: str | None = None,
) -> Image.Image:
    """Call Gemini API to generate an image and return it as a PIL Image."""
    client = _get_client()
    response = client.models.generate_content(
        model="gemini-2.5-flash-image",
        contents=_build_contents(prompt, reference_image_path),
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
        ),
    )

    if not response.candidates:
        raise RuntimeError("Gemini API returned no candidates.")

    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            image_bytes = part.inline_data.data
            return Image.open(io.BytesIO(image_bytes))

    raise RuntimeError(
        "Gemini API response did not contain an image. "
        "The model may have returned text instead."
    )


_rembg_session = None


def _get_rembg_session():
    """Lazily initialize rembg session to avoid slow MCP startup."""
    global _rembg_session
    if _rembg_session is None:
        _rembg_session = new_session("birefnet-general")
    return _rembg_session


def _remove_background(image: Image.Image) -> Image.Image:
    """Remove background from an image using rembg (birefnet-general)."""
    result = remove(image, session=_get_rembg_session())
    return _trim_transparent(result)


def _trim_transparent(image: Image.Image) -> Image.Image:
    """Crop the image to the bounding box of non-transparent pixels."""
    if image.mode != "RGBA":
        return image
    alpha = np.array(image.split()[3])
    rows = np.any(alpha > 0, axis=1)
    cols = np.any(alpha > 0, axis=0)
    if not rows.any():
        return image
    y_min, y_max = int(np.argmax(rows)), int(len(rows) - np.argmax(rows[::-1]))
    x_min, x_max = int(np.argmax(cols)), int(len(cols) - np.argmax(cols[::-1]))
    return image.crop((x_min, y_min, x_max, y_max))


def _ensure_directory(file_path: str) -> Path:
    """Ensure the parent directory exists and return the resolved Path."""
    path = Path(file_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _save_raw(image: Image.Image, output_path: Path) -> Path:
    """Save the raw Gemini output alongside the processed file.

    For an output_path like /a/b/image.png, the raw image is saved
    as /a/b/image_raw.png.
    """
    raw_path = output_path.with_stem(output_path.stem + "_raw")
    image.save(str(raw_path), "PNG")
    return raw_path


@mcp.tool()
def generate_background_image(
    prompt: str,
    output_path: str,
    reference_image_path: str | None = None,
) -> str:
    """Generate an image using Gemini API and save as PNG.

    IMPORTANT: Each API call costs money. Before calling this tool,
    you MUST confirm with the user exactly how many images to generate.

    Args:
        prompt: Text description of the image to generate.
        output_path: File path where the PNG image will be saved.
        reference_image_path: Optional local image path to preserve as a
            visual reference while applying prompt changes. When generating
            a variant of an existing character, always use the character's
            raw base image here if one exists.

    Returns:
        A message indicating success and the saved file path.
    """
    image = _generate_image(prompt, reference_image_path)
    path = _ensure_directory(output_path)
    image.save(str(path), "PNG")
    return f"Image saved to {path} ({image.width}x{image.height})"


_WHITE_BG_SUFFIX = " The subject must be on a plain solid white background."


@mcp.tool()
def generate_transparent_image(
    prompt: str,
    output_path: str,
    reference_image_path: str | None = None,
) -> str:
    """Generate an image using Gemini API with background removal.

    The generated image has its background removed using rembg
    (u2net model), producing a transparent PNG.
    A white background instruction is automatically appended to
    the prompt for cleaner background removal results.

    IMPORTANT: Each API call costs money. Before calling this tool,
    you MUST confirm with the user exactly how many images to generate.

    Args:
        prompt: Text description of the image to generate.
        output_path: File path where the transparent PNG will be saved.
        reference_image_path: Optional local image path to preserve as a
            visual reference while applying prompt changes. When generating
            a variant of an existing character, always use the character's
            raw base image here if one exists.

    Returns:
        A message indicating success and the saved file path.
    """
    image = _generate_image(
        prompt + _WHITE_BG_SUFFIX,
        reference_image_path,
    )
    path = _ensure_directory(output_path)
    raw_path = _save_raw(image, path)
    transparent = _remove_background(image)
    transparent.save(str(path), "PNG")
    return f"Transparent image saved to {path} ({transparent.width}x{transparent.height}), raw: {raw_path}"


@mcp.tool()
def batch_generate_background_images(items_json: str) -> str:
    """Generate multiple images in one call.

    Each item produces a PNG file.
    Processing is sequential. Failures on individual items are reported
    but do not stop the remaining items.

    IMPORTANT: Each image in the batch costs money. Before calling this
    tool, you MUST confirm with the user exactly how many images to
    generate and list all prompts for approval.

    Args:
        items_json: A JSON array of objects, each with "prompt" and
            "output_path" keys. When generating a variant of an
            existing character, each item should use the character's
            raw base image as reference_image_path if one exists.
            Example: [
              {"prompt": "a castle on a hill", "output_path": "/tmp/castle.png"},
              {"prompt": "a forest at dawn", "output_path": "/tmp/forest.png"}
            ]

    Returns:
        A summary of results for each item.
    """
    items = json.loads(items_json)
    results: list[str] = []
    for i, item in enumerate(items, 1):
        prompt = item["prompt"]
        output_path = item["output_path"]
        reference_image_path = item.get("reference_image_path")
        try:
            image = _generate_image(prompt, reference_image_path)
            path = _ensure_directory(output_path)
            image.save(str(path), "PNG")
            results.append(
                f"[{i}/{len(items)}] OK: {path} "
                f"({image.width}x{image.height})"
            )
        except Exception as e:
            results.append(f"[{i}/{len(items)}] FAIL: {output_path} - {e}")
    return "\n".join(results)


@mcp.tool()
def batch_generate_transparent_images(items_json: str) -> str:
    """Generate multiple transparent-background images in one call.

    Each item produces a PNG with the background removed via rembg.
    Processing is sequential. Failures on individual items are reported
    but do not stop the remaining items.

    IMPORTANT: Each image in the batch costs money. Before calling this
    tool, you MUST confirm with the user exactly how many images to
    generate and list all prompts for approval.

    Args:
        items_json: A JSON array of objects, each with "prompt" and
            "output_path" keys. When generating a variant of an
            existing character, each item should use the character's
            raw base image as reference_image_path if one exists.
            Example: [
              {"prompt": "a warrior holding a sword", "output_path": "/tmp/warrior.png"},
              {"prompt": "an archer drawing a bow", "output_path": "/tmp/archer.png"}
            ]

    Returns:
        A summary of results for each item.
    """
    items = json.loads(items_json)
    results: list[str] = []
    for i, item in enumerate(items, 1):
        prompt = item["prompt"]
        output_path = item["output_path"]
        reference_image_path = item.get("reference_image_path")
        try:
            image = _generate_image(
                prompt + _WHITE_BG_SUFFIX,
                reference_image_path,
            )
            path = _ensure_directory(output_path)
            raw_path = _save_raw(image, path)
            transparent = _remove_background(image)
            transparent.save(str(path), "PNG")
            results.append(
                f"[{i}/{len(items)}] OK: {path} "
                f"({transparent.width}x{transparent.height}), raw: {raw_path}"
            )
        except Exception as e:
            results.append(f"[{i}/{len(items)}] FAIL: {output_path} - {e}")
    return "\n".join(results)


if __name__ == "__main__":
    mcp.run()
