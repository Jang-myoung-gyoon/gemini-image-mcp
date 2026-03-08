# Gemini Image MCP Server

A Model Context Protocol (MCP) server for generating images using Google's Gemini API with optional background removal.

## Features

- **generate_background_image**: Generate a single image from a text prompt
- **generate_transparent_image**: Generate an image with automatic background removal (using rembg/birefnet)
- **batch_generate_background_images**: Generate multiple images in one call
- **batch_generate_transparent_images**: Generate multiple transparent images in one call
- Optional local reference image input for preserving a character, style, or
  composition while applying prompt changes

## Requirements

- Python 3.10+
- Google Gemini API key

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/gemini-image-mcp.git
cd gemini-image-mcp
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file with your Gemini API key:
```bash
cp .env.example .env
# Edit .env and add your API key
```

## Configuration

Create a `.env` file in the project root:

```
GEMINI_API_KEY=your_api_key_here
```

Get your API key from [Google AI Studio](https://aistudio.google.com/app/apikey).

## Usage with Claude Code

Add to your `.mcp.json` configuration:

```json
{
  "mcpServers": {
    "gemini-image": {
      "command": "/path/to/gemini-image-mcp/.venv/bin/python",
      "args": ["/path/to/gemini-image-mcp/server.py"]
    }
  }
}
```

## Tool Examples

### generate_background_image
```
Generate a fantasy castle on a mountain at sunset
Output: /path/to/castle.png
```

With a reference image:

```python
generate_background_image(
    prompt="Keep the same manager character, but change the expression to a big smile.",
    output_path="/path/to/manager_smile.png",
    reference_image_path="/path/to/manager_base.png",
)
```

### generate_transparent_image
```
A warrior in golden armor holding a sword
Output: /path/to/warrior.png (with transparent background)
```

With a reference image:

```python
generate_transparent_image(
    prompt="Use the same character and pose, but make the expression neutral.",
    output_path="/path/to/manager_neutral.png",
    reference_image_path="/path/to/manager_base.png",
)
```

### batch_generate_background_images
```json
[
  {"prompt": "a forest at dawn", "output_path": "/tmp/forest.png"},
  {"prompt": "a desert oasis", "output_path": "/tmp/desert.png"},
  {
    "prompt": "Keep the same fighter portrait, but add sunglasses",
    "output_path": "/tmp/fighter_sunglasses.png",
    "reference_image_path": "/tmp/fighter_base.png"
  }
]
```

## Notes

- Each API call costs money. The tools will remind you to confirm before generating.
- `reference_image_path` is optional on single-image tools and on each batch
  item.
- Transparent image generation uses the birefnet-general model for background removal.
- The raw Gemini output is saved alongside transparent images (as `*_raw.png`).

## License

MIT License
