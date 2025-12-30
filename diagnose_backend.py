"""
Backend Diagnostic Script
Run this to find exactly what's wrong with the import
"""

import sys
import os

print("="*60)
print("HUGO BACKEND DIAGNOSTIC")
print("="*60)

# Step 1: Check file structure
print("\n1. CHECKING FILE STRUCTURE...")
current_dir = os.getcwd()
print(f"   Current directory: {current_dir}")

backend_path = os.path.join(current_dir, 'Backend')
print(f"   Backend path: {backend_path}")
print(f"   Backend exists: {os.path.exists(backend_path)}")

if os.path.exists(backend_path):
    print(f"\n   Files in backend/:")
    for item in os.listdir(backend_path):
        item_path = os.path.join(backend_path, item)
        if os.path.isfile(item_path):
            print(f"      📄 {item}")
        else:
            print(f"      📁 {item}/")
else:
    print("   ❌ BACKEND FOLDER NOT FOUND!")
    sys.exit(1)

# Step 2: Check main.py
print("\n2. CHECKING main.py...")
main_py = os.path.join(backend_path, 'main.py')
if os.path.exists(main_py):
    print(f"   ✅ main.py exists")
    with open(main_py, 'r') as f:
        content = f.read()
        if 'class HugoAgent' in content:
            print(f"   ✅ HugoAgent class found in main.py")
        else:
            print(f"   ❌ HugoAgent class NOT found in main.py")
else:
    print(f"   ❌ main.py does NOT exist")
    sys.exit(1)

# Step 3: Check required modules
print("\n3. CHECKING REQUIRED MODULES...")
required_modules = [
    'config/settings.py',
    'models/schemas.py',
    'services/email_ingestion.py',
    'services/delivery_detector.py',
    'services/erp_matcher.py',
    'services/vector_store.py',
    'services/risk_engine.py',
    'services/huggingface_llm.py',
    'utils/helpers.py'
]

missing_modules = []
for module in required_modules:
    module_path = os.path.join(backend_path, module)
    if os.path.exists(module_path):
        print(f"   ✅ {module}")
    else:
        print(f"   ❌ {module} MISSING")
        missing_modules.append(module)

if missing_modules:
    print(f"\n   ⚠️ WARNING: {len(missing_modules)} modules are missing!")
    print(f"   This will cause import errors.")

# Step 4: Test import with detailed error tracking
print("\n4. TESTING IMPORT...")
sys.path.insert(0, backend_path)

try:
    print("   Attempting: import main")
    import main
    print("   ✅ Module 'main' imported successfully")
    
    print(f"   Module location: {main.__file__}")
    
    # Check if HugoAgent exists
    if hasattr(main, 'HugoAgent'):
        print("   ✅ HugoAgent class found!")
        
        # Try to instantiate
        print("\n5. TESTING INITIALIZATION...")
        try:
            agent = main.HugoAgent()
            print("   ✅ HugoAgent initialized successfully!")
            print("\n" + "="*60)
            print("✅ ALL CHECKS PASSED - BACKEND IS WORKING!")
            print("="*60)
        except Exception as e:
            print(f"   ❌ Failed to initialize HugoAgent")
            print(f"   Error: {e}")
            print("\n   Full traceback:")
            import traceback
            traceback.print_exc()
    else:
        print("   ❌ HugoAgent class NOT found in main module")
        print(f"   Available items in main: {dir(main)}")
        
except Exception as e:
    print(f"   ❌ Import failed!")
    print(f"   Error: {e}")
    print("\n   Full traceback:")
    import traceback
    traceback.print_exc()
    
    # Try to identify the specific missing module
    error_str = str(e)
    if "No module named" in error_str:
        print(f"\n   💡 DIAGNOSIS: Missing Python module")
        print(f"   You may need to: pip install <missing-module>")
    elif "cannot import name" in error_str:
        print(f"\n   💡 DIAGNOSIS: Import structure issue")
        print(f"   Check if the required files exist in backend/")

print("\n" + "="*60)
print("DIAGNOSTIC COMPLETE")
print("="*60)