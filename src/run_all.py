import os
import subprocess
import sys

def run_all():
    # Get the root directory (one level up from src)
    src_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(src_dir)
    
    # Find all 2-letter .py files (state abbreviations)
    state_files = [f for f in os.listdir(src_dir) if f.endswith('.py') and len(f) == 5]
    
    # Sort for consistent execution order
    state_files.sort()
    
    print(f"Found {len(state_files)} state files: {', '.join(state_files)}")
    
    for state_file in state_files:
        module_name = f"src.{state_file[:-3]}"
        print(f"\n{'='*60}")
        print(f"RUNNING: {module_name}")
        print(f"{'='*60}")
        
        # Run using uv run src/state.py with PYTHONPATH="."
        # This follows the guideline in CLAUDE.md
        try:
            # On Windows, we set the environment variable in the subprocess call
            env = os.environ.copy()
            env["PYTHONPATH"] = "."
            
            script_path = f"src/{state_file}"
            result = subprocess.run(
                ["uv", "run", script_path],
                cwd=root_dir,
                env=env,
                capture_output=False,
                text=True
            )
            if result.returncode == 0:
                print(f"SUCCESS: {module_name}")
            else:
                print(f"FAILED: {module_name} with return code {result.returncode}")
        except Exception as e:
            print(f"ERROR: Could not run {module_name}: {e}")

if __name__ == "__main__":
    run_all()
