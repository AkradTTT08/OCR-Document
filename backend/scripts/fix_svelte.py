import os

file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'svelte-app', 'src', 'lib', 'ResultsPanel.svelte'))

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Delete lines 318 to 512 (0-indexed: 317 to 512)
del lines[317:512]

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Fixed ResultsPanel.svelte")
