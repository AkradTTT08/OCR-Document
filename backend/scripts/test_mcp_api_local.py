import json
from app import app

def test_api():
    print("Testing /api/mcp/submit_document using Flask Test Client")
    
    # Create test client
    client = app.test_client()
    
    payload = {
        "document_content": "This is a test document content. We need to check if it passes the criteria.",
        "document_type": "Requirement",
        "target_email": "test@example.com"
    }
    
    print(f"\n--- [Attempt 1: New Session] ---")
    response1 = client.post('/api/mcp/submit_document', json=payload)
    
    if response1.status_code == 200:
        data1 = response1.get_json()
        print("Response 1:", json.dumps(data1, indent=2, ensure_ascii=False))
        
        session_id = data1.get("session_id")
        if session_id:
            print(f"\n--- [Attempt 2: Reuse Session {session_id}] ---")
            payload["session_id"] = session_id
            response2 = client.post('/api/mcp/submit_document', json=payload)
            
            if response2.status_code == 200:
                print("Response 2:", json.dumps(response2.get_json(), indent=2, ensure_ascii=False))
                
                print(f"\n--- [Attempt 3: Reuse Session {session_id}] ---")
                response3 = client.post('/api/mcp/submit_document', json=payload)
                if response3.status_code == 200:
                    print("Response 3:", json.dumps(response3.get_json(), indent=2, ensure_ascii=False))
                    
                    print(f"\n--- [Attempt 4: Hit Circuit Breaker for {session_id}] ---")
                    response4 = client.post('/api/mcp/submit_document', json=payload)
                    if response4.status_code == 200:
                        print("Response 4:", json.dumps(response4.get_json(), indent=2, ensure_ascii=False))
                    else:
                        print("Error on Attempt 4:", response4.status_code, response4.data.decode('utf-8'))
                else:
                    print("Error on Attempt 3:", response3.status_code, response3.data.decode('utf-8'))
            else:
                print("Error on Attempt 2:", response2.status_code, response2.data.decode('utf-8'))
    else:
        print("Error on Attempt 1:", response1.status_code, response1.data.decode('utf-8'))

if __name__ == "__main__":
    test_api()
