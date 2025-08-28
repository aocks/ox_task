"""Tools for doing shell operations.
"""

import subprocess


def run_shell_command(command, env, shell=True):
    """Execute a shell command and return the result"""
    result = subprocess.run(command, shell=shell,
                            capture_output=True, text=True, check=True,
                            env=env)
    return result.stdout.strip()
