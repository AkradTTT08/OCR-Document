import os
import logging
import threading
from typing import Tuple, Any

logger = logging.getLogger(__name__)

_LAST_MODEL_LOCAL = threading.local()


def _record_last_used_model(usage_metadata: Any, model_name: str):
    try:
        _LAST_MODEL_LOCAL.usage_id = id(usage_metadata) if usage_metadata is not None else None
        _LAST_MODEL_LOCAL.model_name = str(model_name or "").strip()
    except Exception:
        pass


def get_actual_model_for_usage(usage_metadata: Any, fallback_model: str = None) -> str:
    """Returns the exact model that produced usage_metadata if it came from call_gemini() fallback."""
    try:
        if (
            usage_metadata is not None
            and getattr(_LAST_MODEL_LOCAL, "usage_id", None) == id(usage_metadata)
            and getattr(_LAST_MODEL_LOCAL, "model_name", None)
        ):
            return _LAST_MODEL_LOCAL.model_name
    except Exception:
        pass
    return fallback_model or "gemini-2.5-flash"

def get_gemini_api_key():
    try:
        from ocr_engine import get_all_api_keys
        keys = get_all_api_keys()
        if keys:
            return keys[0]
    except Exception:
        pass
    raw = (
        os.environ.get("GEMINI_API_KEY") 
        or os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GOOGLE_API_KEYS")
        or os.environ.get("GOOGLE_API_KEY_1")
        or ""
    ).strip().strip('"').strip("'")
    if ',' in raw:
        keys = [k.strip() for k in raw.split(',') if k.strip()]
        return keys[0] if keys else ""
    return raw

def call_gemini(
    prompt: str, 
    model_name: str = None, 
    system_instruction: str = None,
    temperature: float = 0.2,
    max_output_tokens: int = 32768
) -> Tuple[str, Any]:
    """
    Calls Google Gemini using modern google-genai SDK with automatic fallback across models and legacy SDK.
    Returns (text_response, usage_metadata).
    """
    api_key = get_gemini_api_key()
    if not api_key:
        raise ValueError("ไม่พบ GEMINI_API_KEY หรือ GOOGLE_API_KEY ใน environment variables")

    preferred_model = model_name or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    raw_models = [preferred_model, "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-1.5-pro"]
    candidate_models = []
    for m in raw_models:
        if m and m not in ("gemini-3.1-pro-preview", "gemini-3.1-pro", "gemini-3.1-flash") and m not in candidate_models:
            candidate_models.append(m)

    last_error = None

    # 1. Try modern google-genai SDK across candidate models
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens
        )
        if system_instruction:
            config.system_instruction = system_instruction
        
        for m in candidate_models:
            try:
                response = client.models.generate_content(
                    model=m,
                    contents=prompt,
                    config=config
                )
                if response and (response.text or "").strip():
                    usage_meta = getattr(response, 'usage_metadata', None)
                    actual_model = getattr(response, 'model_version', None) or m
                    _record_last_used_model(usage_meta, actual_model)
                    return (response.text or "").strip(), usage_meta
            except Exception as m_err:
                last_error = m_err
                logger.warning(f"google-genai model '{m}' failed: {m_err}")
                continue
    except ImportError:
        pass
    except Exception as modern_err:
        last_error = modern_err
        logger.warning(f"google-genai setup failed ({modern_err}), attempting legacy fallback...")

    # 2. Fallback: Legacy google-generativeai SDK
    try:
        import google.generativeai as legacy_genai
        legacy_genai.configure(api_key=api_key)
        
        generation_config = {
            "temperature": temperature,
            "max_output_tokens": max_output_tokens
        }
        
        for m in candidate_models:
            try:
                if system_instruction:
                    model = legacy_genai.GenerativeModel(
                        model_name=m,
                        system_instruction=system_instruction,
                        generation_config=generation_config
                    )
                else:
                    model = legacy_genai.GenerativeModel(
                        model_name=m,
                        generation_config=generation_config
                    )
                    
                response = model.generate_content(prompt)
                if response and (response.text or "").strip():
                    usage_meta = getattr(response, 'usage_metadata', None)
                    actual_model = getattr(response, 'model_version', None) or m
                    _record_last_used_model(usage_meta, actual_model)
                    return (response.text or "").strip(), usage_meta
            except Exception as leg_m_err:
                last_error = leg_m_err
                logger.warning(f"legacy google.generativeai model '{m}' failed: {leg_m_err}")
                continue
    except ImportError:
        if last_error:
            raise last_error
        raise ImportError("ไม่พบ library 'google-genai' หรือ 'google-generativeai' กรุณารัน: pip install google-genai")

    if last_error:
        raise last_error
    raise RuntimeError("Gemini API call failed with all candidate models.")
