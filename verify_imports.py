import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

try:
    print("Importing FourDGSEngine...")
    print("FourDGSEngine imported.")

    print("Importing FourDGSWorker...")
    print("FourDGSWorker imported.")

    print("Importing FourDGSTab...")
    print("FourDGSTab imported.")

    print("\nAll imports successful.")
except Exception as e:
    print(f"\nFATAL ERROR: {e}")
    import traceback
    traceback.print_exc()
