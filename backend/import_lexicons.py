import csv
import os
import sys

def process_csv(file_path, column_name, output_path):
    print(f"Processing {file_path} for column {column_name}...")
    words = set()
    
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return

    try:
        # Using utf-8 as the file suggests telex-utf8
        with open(file_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                word = row.get(column_name)
                if word:
                    # Clean the word
                    word = word.strip()
                    if word:
                        words.add(word)
                        
        print(f"Found {len(words)} unique entries.")
        
        # Save to output file
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            for word in sorted(words):
                f.write(word + '\n')
        
        print(f"Successfully saved to {output_path}")
        
    except Exception as e:
        print(f"Error processing {file_path}: {e}")

if __name__ == "__main__":
    # Base directory
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, 'data')
    
    # Process telex-utf8.csv for Thai words
    telex_csv = os.path.join(data_dir, 'telex-utf8.csv')
    telex_out = os.path.join(data_dir, 'telex_th.txt')
    process_csv(telex_csv, 't-search', telex_out)
    
    # Process etlex-utf8.csv for English words
    etlex_csv = os.path.join(data_dir, 'etlex-utf8.csv')
    etlex_out = os.path.join(data_dir, 'etlex_en.txt')
    process_csv(etlex_csv, 'e-search', etlex_out)
