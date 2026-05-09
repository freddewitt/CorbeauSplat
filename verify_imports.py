import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

try:
    print("Importing FourDGSEngine...")
    from app.core.four_dgs_engine import FourDGSEngine
    print("FourDGSEngine imported.")
    
    print("Importing FourDGSWorker...")
    from app.gui.workers import FourDGSWorker
    print("FourDGSWorker imported.")
    
    print("Importing FourDGSTab...")
    from app.gui.tabs.four_dgs_tab import FourDGSTab
    print("FourDGSTab imported.")
    
    print("\nAll imports successful.")
except Exception as e:
    print(f"\nFATAL ERROR: {e}")
    import traceback
    traceback.print_exc()
