import os
import re
import sys

def patch_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # 1. Ensure imports exist
    # Find insertion point
    lines = content.splitlines()
    insert_idx = 0
    found_future = False
    
    # Check if we already have the imports
    has_union = "from typing import Union" in content or ", Union" in content or "Union," in content or " Union" in content
    has_optional = "from typing import Optional" in content or ", Optional" in content or "Optional," in content or " Optional" in content
    
    # Find last __future__ import
    for i, line in enumerate(lines):
        if line.strip().startswith("from __future__"):
            insert_idx = i + 1
            found_future = True
        elif not found_future and (line.startswith("import ") or line.startswith("from ")):
            # If no future import found yet, and we hit normal imports, this is potentially a spot, 
            # but we keep searching in case future imports are further down (unlikely valid python but safely)
            if insert_idx == 0: insert_idx = i
            
    # Normalize if insert_idx is still 0 (start of file or after docstring?)
    # If 0, we might be before docstring. Let's find first non-comment/empty line if no imports?
    # Actually, safely inserting after last __future__ is best. 
    # If no __future__, use previous logic (first import)
    
    if not found_future:
         for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                insert_idx = i
                break
    
    # Prepare import line
    needed = []
    if "Union" not in content: needed.append("Union")
    if "Optional" not in content: needed.append("Optional")
    
    if needed:
         lines.insert(insert_idx, f"from typing import {', '.join(needed)}")
         content = "\n".join(lines)

    # 2. Replace Type | None -> Optional[Type] (Naive regex)
    # Recursively apply replacements until no change to handle A | B | C
    
    # Matches:  : Type | None  or  = Type | None
    # We used a regex that captures the preceding word. 
    # Warning: simple regex like (\w+) \| None captures "str | None" but fails on "list[int] | None" matches only "int] | None"
    
    # Better approach might be purely line-based string replacement for simple cases
    # or using LibCST/AST for robustness. Given constraints, let's try regexes for common patterns.
    
    # Pattern 1: Simple types:  str | None -> Optional[str]
    content = re.sub(r"(\b\w+)\s*\|\s*None", r"Optional[\1]", content)
    content = re.sub(r"None\s*\|\s*(\b\w+)", r"Optional[\1]", content)
    
    # Pattern 2: Generic types: list[int] | None -> Optional[list[int]]
    # This matches balanced brackets somewhat? No regex for balanced brackets.
    # Let's hope complex types are rare or we handle specific ones.
    
    # Pattern 3: Union: A | B -> Union[A, B]
    # We loop this one because A | B | C -> Union[A, B] | C -> Union[Union[A,B], C] (valid but ugly) or Union[A, B, C]
    # Let's do simple A | B first.
    
    # Loop to handle chaining
    prev_content = ""
    while content != prev_content:
        prev_content = content
        # Replace:  (TypeA) | (TypeB)  -> Union[\1, \2]
        # We need to be careful not to match inside string literals (simplified usage here)
        # Matches alphanumeric+brackets+dot logic?
        
        # Regex for valid type tokens: [\w\.\[\], "']+
        # Captures "int", "float", "list[str]", "sharp.Type"
        # pattern = r"([\w\.\[\]\"']+)\s*\|\s*([\w\.\[\]\"']+)"
        # replacement = r"Union[\1, \2]"
        # content = re.sub(pattern, replacement, content)
        
        # Let's target specific failures seen: str | None, int | float
        pass 
        
    # Manual common replacements based on grep intuition
    # int | float -> Union[int, float]
    content = re.sub(r"\bint\s*\|\s*float\b", "Union[int, float]", content)
    content = re.sub(r"\bfloat\s*\|\s*int\b", "Union[float, int]", content)
    content = re.sub(r"\bstr\s*\|\s*pathlib\.Path\b", "Union[str, pathlib.Path]", content)
    
    # Catch-all simple unions: Word | Word (that isn't None)
    # ([a-zA-Z0-9_.]+) \| ([a-zA-Z0-9_.]+)
    # Avoid matching inside Union[...] itself?
    # Actually, Python 3.9 supports `Union` so `Union[A, B]` is fine. 
    # But `|` operator is 3.10.
    
    # Robust method:
    # Find all usages of `|` not inside strings.
    # If it looks like type hint...
    
    # Let's stick to simple replacements for now, checking changes.
    
    if content != original_content:
        print(f"Patching {filepath}")
        with open(filepath, 'w') as f:
            f.write(content)

def main():
    target_dir = sys.argv[1]
    for root, dirs, files in os.walk(target_dir):
        for file in files:
            if file.endswith(".py"):
                patch_file(os.path.join(root, file))

if __name__ == "__main__":
    main()
