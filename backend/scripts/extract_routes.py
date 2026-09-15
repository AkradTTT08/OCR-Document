import sys

def main():
    with open('d:\\OCR-Github\\OCR-Document\\backend\\app.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    with open('d:\\OCR-Github\\OCR-Document\\backend\\routes.txt', 'w', encoding='utf-8') as out:
        for i, line in enumerate(lines):
            if "@app.route" in line:
                out.write(f"Line {i+1}: {line.strip()}\n")
                if i+1 < len(lines):
                    out.write(f"       {lines[i+1].strip()}\n")

if __name__ == '__main__':
    main()
