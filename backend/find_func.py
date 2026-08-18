import sys

def main():
    with open('d:\\OCR-Github\\OCR-Document\\backend\\db_ingestion.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    for i, line in enumerate(lines):
        if "def ingest_markdown_document" in line:
            print(f"Line {i+1}: {line.strip()}")
            # Print a few lines after
            for j in range(1, 20):
                if i+j < len(lines):
                    print(f"       {lines[i+j].strip()}")

if __name__ == '__main__':
    main()
