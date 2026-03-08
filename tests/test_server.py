import tempfile
import unittest
from pathlib import Path
import sys
import types
from unittest.mock import MagicMock, patch

from PIL import Image

sys.modules.setdefault(
    "rembg",
    types.SimpleNamespace(
        remove=lambda image, session=None: image,
        new_session=lambda model=None: object(),
    ),
)

import server


class GenerateImageTests(unittest.TestCase):
    def test_generate_image_uses_text_prompt_without_reference(self):
        fake_image = Image.new("RGBA", (4, 4), (255, 0, 0, 255))
        fake_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        try:
            fake_image.save(fake_file.name, "PNG")
            image_bytes = Path(fake_file.name).read_bytes()
        finally:
            Path(fake_file.name).unlink(missing_ok=True)

        client = MagicMock()
        client.models.generate_content.return_value = MagicMock(
            candidates=[
                MagicMock(
                    content=MagicMock(
                        parts=[
                            MagicMock(
                                inline_data=MagicMock(data=image_bytes)
                            )
                        ]
                    )
                )
            ]
        )

        with patch.object(server, "_get_client", return_value=client):
            result = server._generate_image("test prompt")

        self.assertEqual(result.size, (4, 4))
        kwargs = client.models.generate_content.call_args.kwargs
        self.assertEqual(kwargs["contents"], "test prompt")

    def test_generate_image_includes_reference_part(self):
        reference_image = Image.new("RGB", (2, 2), (0, 0, 255))
        output_image = Image.new("RGBA", (4, 4), (255, 0, 0, 255))

        with tempfile.TemporaryDirectory() as directory:
            reference_path = Path(directory) / "reference.png"
            output_path = Path(directory) / "output.png"
            reference_image.save(reference_path, "PNG")
            output_image.save(output_path, "PNG")
            image_bytes = output_path.read_bytes()

            client = MagicMock()
            client.models.generate_content.return_value = MagicMock(
                candidates=[
                    MagicMock(
                        content=MagicMock(
                            parts=[
                                MagicMock(
                                    inline_data=MagicMock(data=image_bytes)
                                )
                            ]
                        )
                    )
                ]
            )

            with patch.object(server, "_get_client", return_value=client):
                result = server._generate_image(
                    "keep the same person",
                    reference_image_path=str(reference_path),
                )

        self.assertEqual(result.size, (4, 4))
        kwargs = client.models.generate_content.call_args.kwargs
        contents = kwargs["contents"]
        self.assertIsInstance(contents, list)
        self.assertEqual(len(contents), 2)
        self.assertIn("reference image", contents[0].text)
        self.assertEqual(contents[1].inline_data.mime_type, "image/png")

    def test_batch_background_forwards_reference_image_path(self):
        items_json = (
            '[{"prompt": "p1", "output_path": "/tmp/o1.png", '
            '"reference_image_path": "/tmp/r1.png"}]'
        )
        fake_image = Image.new("RGBA", (3, 5), (1, 2, 3, 255))

        with patch.object(
            server, "_generate_image", return_value=fake_image
        ) as mock_generate:
            with patch.object(
                server, "_ensure_directory", return_value=Path("/tmp/o1.png")
            ):
                result = server.batch_generate_background_images(items_json)

        self.assertIn("OK", result)
        mock_generate.assert_called_once_with("p1", "/tmp/r1.png")


if __name__ == "__main__":
    unittest.main()
