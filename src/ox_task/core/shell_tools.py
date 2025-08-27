"""Tools for doing shell operations.
"""

import os
import re
import subprocess

_varprog = None
_varprogb = None

def run_shell_command(command, env, shell=True, reraise=True):
    """Execute a shell command and return the result"""
    try:
        result = subprocess.run(command, shell=shell, 
                                capture_output=True, text=True, check=True,
                                env=env)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Command failed with return code {e.returncode}")
        print(f"Error output: {e.stderr}")
        if reraise:
            raise
        return None
