import requests
import base64
import os
import io
import json
from PIL import Image

ollama_url = 'http://127.0.0.1:11434/api/chat'
model_name = 'qwen2.5vl-opt'

# Create a 64x64 white image (qwen2.5vl requires images larger than 28x28)
dummy_img = Image.new('RGB', (64, 64), color='white')
buffered = io.BytesIO()
dummy_img.save(buffered, format='PNG')
dummy_img_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

payload = {
    "model": model_name,
    "messages": [
        {
            "role": "user",
            "content": "What is in this image?",
            "images": [dummy_img_b64]
        }
    ],
    "stream": False,
    "options": {
        "num_ctx": 3072,
        "num_predict": 64,
        "num_batch": 8
    }
}

print(f"Testing Ollama API with model {model_name}...")
try:
    response = requests.post(ollama_url, json=payload)
    print(f"Status Code: {response.status_code}")
    if response.status_code != 200:
        print("Error Response Body:")
        print(response.text)
    else:
        print("Success! Response:")
        print(response.json()['message']['content'])
except Exception as e:
    print(f"Failed to connect: {e}")
