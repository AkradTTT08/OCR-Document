from backend.spell_checker import spellcheck_text

def test_en_context():
    texts = [
        "Welcome to your home.",
        "I hope your doing well.",
        "The dog lost its bone.",
        "its a beautiful day.",
        "they are there with their friends.",
        "There is no one there.",
        "their is a cat on the mat.",
        "your going to love it.",
    ]
    
    for text in texts:
        print(f"\nTesting: {text}")
        result = spellcheck_text(text)
        print(f"Tokens: {[t['token'] for t in result['tokens']]}")
        for token in result['tokens']:
            if not token['is_correct'] and token['error_type'] == 'semantic':
                print(f"  [SEMANTIC ERROR] {token['token']} -> {token['suggestions']}")
            elif not token['is_correct']:
                print(f"  [MISSPELL] {token['token']} -> {token['suggestions']}")

if __name__ == "__main__":
    test_en_context()
