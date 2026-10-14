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


def test_route_c_reports_surya_failure_instead_of_switching_engine():
    """A Surya failure is an error: there is no lower-accuracy OCR engine to fall back to."""
    import io
    import pytest
    from PIL import Image
    from services.ocr_extractor import OcrUnavailable

    with patch("services.surya_extractor.SuryaExtractor.extract",
               return_value={"text": "", "lines": [], "error": "llama-server missing"}):
        img = Image.new("RGB", (50, 50), color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        with pytest.raises(OcrUnavailable):
            extract_text_from_image(buf.getvalue())
