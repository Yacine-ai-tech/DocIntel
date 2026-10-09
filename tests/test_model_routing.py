import pytest
import os
from unittest.mock import AsyncMock, patch, MagicMock

from core.config import settings
from services.vision_extractor import _vision_call_route_a
from services.surya_extractor import _enabled as surya_enabled
from services.ocr_extractor import extract_text_from_image


@pytest.mark.asyncio
async def test_route_a_env_driven_model_selection():
    """Verify Route A uses the configured model without hardcoded provider lists."""
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = '{"vendor": "Test Corp"}'

    with patch("services.vision_extractor.acompletion", new=AsyncMock(return_value=mock_resp)) as mock_acompletion:
        # 1. Custom Gemini model passed from env or caller
        content, _ = await _vision_call_route_a("gemini/gemini-3.8-flash", "extract", [b"fake_image"])
        assert content == '{"vendor": "Test Corp"}'
        assert mock_acompletion.call_args[1]["model"] == "gemini/gemini-3.8-flash"

        # 2. Default Sonnet model
        content, _ = await _vision_call_route_a("anthropic/claude-sonnet-4-6", "extract", [b"fake_image"])
        assert mock_acompletion.call_args[1]["model"] == "anthropic/claude-sonnet-4-6"


@pytest.mark.asyncio
async def test_route_a_configured_fallback():
    """Verify Route A attempts configured fallback only if set via LLM_VISION_ROUTE_A_FALLBACK."""
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = '{"vendor": "Fallback Corp"}'

    called_models = []

    async def mock_call(**kwargs):
        model = kwargs.get("model")
        called_models.append(model)
        if model == "anthropic/claude-sonnet-4-6":
            raise RuntimeError("Primary model auth error")
        return mock_resp

    with patch("services.vision_extractor.acompletion", side_effect=mock_call):
        with patch.dict(os.environ, {"LLM_VISION_ROUTE_A_FALLBACK": "gemini/gemini-3.5-flash"}):
            content, _ = await _vision_call_route_a("anthropic/claude-sonnet-4-6", "extract", [b"fake_image"])
            assert content == '{"vendor": "Fallback Corp"}'
            assert called_models == ["anthropic/claude-sonnet-4-6", "gemini/gemini-3.5-flash"]


def test_surya_enabled_by_default():
    """Verify Surya OCR is enabled by default in configuration."""
    with patch.dict(os.environ, {}, clear=True):
        # When SURYA_ENABLED is unset, it should default to True
        assert surya_enabled() is True

    with patch.dict(os.environ, {"SURYA_ENABLED": "false"}):
        assert surya_enabled() is False


def test_route_c_surya_fallback_to_tesseract():
    """Verify Route C falls back to Tesseract if Surya raises an error."""
    mock_tesseract = MagicMock()
    mock_tesseract.image_to_string.return_value = "Tesseract Extracted Text"
    
    with patch("services.surya_extractor.SuryaExtractor.extract", side_effect=Exception("llama-server missing")):
        with patch.dict("sys.modules", {"pytesseract": mock_tesseract}):
            with patch("services.ocr_extractor._TESSERACT", True):
                with patch("services.ocr_extractor.pytesseract", mock_tesseract, create=True):
                    # Create a small valid 50x50 PNG
                    from PIL import Image
                    import io
                    img = Image.new("RGB", (50, 50), color="white")
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    png_bytes = buf.getvalue()

                    text = extract_text_from_image(png_bytes)
                    assert "Tesseract Extracted Text" in text
