import os
import logging
from typing import Tuple, Any

logger = logging.getLogger(__name__)

def get_gemini_api_key():
    return (
        os.environ.get("GEMINI_API_KEY") 
        or os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GOOGLE_API_KEY_1")
    )

def call_gemini(
    prompt: str, 
    model_name: str = None, 
    system_instruction: str = None,
    temperature: float = 0.2,
    max_output_tokens: int = 8192
) -> Tuple[str, Any]:
    """
    Calls Google Gemini using modern google-genai SDK with automatic fallback across models and legacy SDK.
    Returns (text_response, usage_metadata).
    """
    api_key = get_gemini_api_key()
    if not api_key:
        raise ValueError("ไม่พบ GEMINI_API_KEY หรือ GOOGLE_API_KEY ใน environment variables")

    preferred_model = model_name or os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    candidate_models = [preferred_model]
    for fallback in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.5-flash"]:
        if fallback not in candidate_models:
            candidate_models.append(fallback)

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
                    return (response.text or "").strip(), getattr(response, 'usage_metadata', None)
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
                    return (response.text or "").strip(), getattr(response, 'usage_metadata', None)
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
