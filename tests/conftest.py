"""Provide some fixtures for tests.
"""

import os
import json
import tempfile
import shutil

import pytest


@pytest.fixture(name="temp_dir")
def make_temp_dir():
    """Create a temporary directory for tests."""
    my_temp_dir = tempfile.mkdtemp()
    yield my_temp_dir
    shutil.rmtree(my_temp_dir)


@pytest.fixture(name="sample_task_plan_data")
def make_sample_task_plan_data():
    """Sample task plan data for testing based on tasks.json example."""
    return {
        "envs": {
            "test_python": {
                "runtime": "python3",
                "requirements": ["requests", "click"],
                "variables": {
                    "TEST_VAR": "test_value",
                    "ST_PATH": "`echo /path/to/simple_tasks`"
                }
            },
            "minimal_env": {
                "requirements": [],
                "variables": {}
            }
        },
        "jobs": {
            "test_echo": {
                "description": ["Simple echo test job"],
                "env": "minimal_env",
                "note": "test_file",
                "timeout": 10,
                "shell": False,
                "command": ["python", "-c", "print('Hello World')"]
            },
            "test_weather": {
                "description": ["Test weather API call"],
                "env": "test_python",
                "note": "test_file",
                "timeout": 30,
                "shell": False,
                "command": [
                    "python", "-c",
                    "import sys; sys.path.insert(0, '.'); "
                    "from ox_task.example_tasks.simple_tasks import weather; "
                    "weather.callback(40.7, -73.9, 30)"
                ]
            },
            "test_shell_command": {
                "description": ["Test shell command execution"],
                "env": "minimal_env",
                "note": "test_file",
                "timeout": 5,
                "shell": True,
                "command": "echo 'Shell command test'"
            }
        },
        "notes": {
            "test_file": {
                "description": ["File-based notifier for testing"],
                "class_name": "FileNotifier",
                "path": "/tmp/ox_task_test_${OX_TASK_JOB_NAME}.txt"
            }
        }
    }


@pytest.fixture(name="sample_task_plan_json")
def make_sample_task_plan_json(temp_dir, sample_task_plan_data):
    """Create a sample task plan JSON file."""
    json_file = os.path.join(temp_dir, "test_tasks.json")
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(sample_task_plan_data, f, indent=2)
    return json_file


@pytest.fixture
def sample_task_plan_py(temp_dir, sample_task_plan_data):
    """Create a sample task plan Python file."""
    py_file = os.path.join(temp_dir, "test_tasks.py")
    with open(py_file, 'w', encoding='utf-8') as f:
        f.write(f"""
# Task plan as Python module
envs = {sample_task_plan_data['envs']!r}
jobs = {sample_task_plan_data['jobs']!r}
notes = {sample_task_plan_data['notes']!r}
""")
    return py_file


@pytest.fixture
def golden_files_dir(temp_dir):
    """Directory for golden test files."""
    golden_dir = os.path.join(temp_dir, "golden")
    os.makedirs(golden_dir)
    return golden_dir
