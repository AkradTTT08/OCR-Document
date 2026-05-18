import requests
import base64
import os
import json

ollama_url = 'http://localhost:11434/api/chat'
model_name = 'qwen2.5vl:3b-4k'

# Create a dummy 1x1 white pixel image in base64
dummy_img_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII="

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
        "num_ctx": 4096
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
