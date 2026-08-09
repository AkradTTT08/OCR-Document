import requests
import json
import uuid

# Configuration
URL = "http://127.0.0.1:5000/api/mcp/submit_document"

def test_api():
    print("Testing /api/mcp/submit_document")
    
    payload = {
        "document_content": "This is a test document content. We need to check if it passes the criteria.",
        "document_type": "Requirement",
        "target_email": "test@example.com"
    }
    
    headers = {
        'Content-Type': 'application/json'
    }
    
    print(f"Sending first request...")
    response = requests.post(URL, json=payload, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        print("Response 1:", json.dumps(data, indent=2, ensure_ascii=False))
        
        session_id = data.get("session_id")
        if session_id:
            print(f"\nSending second request with session_id {session_id}...")
            payload["session_id"] = session_id
            response2 = requests.post(URL, json=payload, headers=headers)
            
            if response2.status_code == 200:
                print("Response 2:", json.dumps(response2.json(), indent=2, ensure_ascii=False))
            else:
                print("Error on second request:", response2.status_code, response2.text)
    else:
        print("Error on first request:", response.status_code, response.text)

if __name__ == "__main__":
    test_api()
