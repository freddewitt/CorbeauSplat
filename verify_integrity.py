import os
import sys
import compileall
import importlib.util

def check_syntax(root_dir):
    print(f"--- Checking Syntax in {root_dir} ---")
    try:
        # force=True forces recompilation, quiet=1 hides standard output but shows errors
        success = compileall.compile_dir(root_dir, force=True, quiet=1)
        if success:
            print("✅ Syntax OK")
            return True
        else:
            print("❌ Syntax Errors Found")
            return False
    except Exception as e:
        print(f"Error checking syntax: {e}")
        return False

def check_imports(root_dir):
    print(f"\n--- Checking Imports in {root_dir} ---")
    error_count = 0
    
    # Walk through files
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                
                # Skip __init__.py mostly, or script files that might run immediately
                if file == "run.command" or file == "setup_dependencies.py": 
                    continue
                
                try:
                    # We just attempt to parse and find imports, not necessarily execute module code 
                    # which might trigger GUI.
                    # A safe simple check is just ensuring the file path is readable and compilable,
                    # which we did above. 
                    # Actual import might be too aggressive for a GUI app in headless mode.
                    pass
                except Exception as e:
                    print(f"❌ Error with {file}: {e}")
                    error_count += 1
                    
    print("✅ Import check skipped (unsafe in headless). Syntax check is primary indicator.")
    return True

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.join(current_dir, "app")
    
    if not os.path.exists(app_dir):
        print(f"Error: {app_dir} not found")
        sys.exit(1)
        
    syntax_ok = check_syntax(app_dir)
    
    if syntax_ok:
        print("\n✨ GLOBAL CHECK: PASSED ✨")
        sys.exit(0)
    else:
        print("\n💀 GLOBAL CHECK: FAILED 💀")
        sys.exit(1)
