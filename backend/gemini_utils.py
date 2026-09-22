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
    Calls Google Gemini using the modern google-genai SDK (with automatic fallback to legacy google-generativeai).
    Returns (text_response, usage_metadata).
    """
    model_name = model_name or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    api_key = get_gemini_api_key()
    if not api_key:
        raise ValueError("ไม่พบ GEMINI_API_KEY หรือ GOOGLE_API_KEY ใน environment variables")

    # 1. Primary: Modern google-genai SDK
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
        
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config
        )
        return (response.text or "").strip(), getattr(response, 'usage_metadata', None)
    except ImportError:
        pass
    except Exception as modern_err:
        logger.warning(f"google-genai call failed ({modern_err}), attempting legacy fallback...")

    # 2. Fallback: Legacy google-generativeai SDK
    try:
        import google.generativeai as legacy_genai
        legacy_genai.configure(api_key=api_key)
        
        generation_config = {
            "temperature": temperature,
            "max_output_tokens": max_output_tokens
        }
        
        if system_instruction:
            model = legacy_genai.GenerativeModel(
                model_name=model_name,
                system_instruction=system_instruction,
                generation_config=generation_config
            )
        else:
            model = legacy_genai.GenerativeModel(
                model_name=model_name,
                generation_config=generation_config
            )
            
        response = model.generate_content(prompt)
        return (response.text or "").strip(), getattr(response, 'usage_metadata', None)
    except ImportError:
        raise ImportError("ไม่พบ library 'google-genai' หรือ 'google-generativeai' กรุณารัน: pip install google-genai")
