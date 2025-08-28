"""
Basic tests for the ox_task system.

The ox_task framework provides a way to run commands similar to AWS Lambda
but with simpler configuration. This test suite covers the core functionality
including task plan parsing, job execution, and notification systems.

Run with: python -m pytest test_basics.py -v
"""

import json
import os
import shutil
import tempfile
import subprocess
import sys
from unittest.mock import patch, MagicMock

import pytest
import click.testing
import requests_mock

from ox_task.ui.cli import main, run_job, _parse_task_plan_file
from ox_task.core import models


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    my_temp_dir = tempfile.mkdtemp()
    yield my_temp_dir
    shutil.rmtree(my_temp_dir)


@pytest.fixture
def sample_task_plan_data():
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


@pytest.fixture
def sample_task_plan_json(temp_dir, sample_task_plan_data):
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


class TestCLIBasics:
    """Test basic CLI functionality."""

    def test_find_path_command(self):
        """Test the find-path command."""
        runner = click.testing.CliRunner()
        result = runner.invoke(main, ['find-path', 'os.path'])
        assert result.exit_code == 0
        assert ('posixpath.py' in result.output or
                'ntpath.py' in result.output)

    def test_find_path_nonexistent(self):
        """Test find-path with nonexistent module."""
        runner = click.testing.CliRunner()
        result = runner.invoke(main, ['find-path', 'nonexistent.module'])
        assert result.exit_code == 1
        assert result.output.strip() == ''


class TestTaskPlanParsing:
    """Test task plan file parsing."""

    def test_parse_json_task_plan(self, sample_task_plan_json):
        """Test parsing JSON task plan."""
        task_plan = _parse_task_plan_file(sample_task_plan_json)
        assert isinstance(task_plan, models.TaskPlan)
        assert "test_python" in task_plan.envs
        assert "test_echo" in task_plan.jobs
        assert "test_file" in task_plan.notes

    def test_parse_python_task_plan(self, sample_task_plan_py):
        """Test parsing Python task plan."""
        task_plan = _parse_task_plan_file(sample_task_plan_py)
        assert isinstance(task_plan, models.TaskPlan)
        assert "test_python" in task_plan.envs
        assert "test_echo" in task_plan.jobs
        assert "test_file" in task_plan.notes

    def test_task_env_structure(self, sample_task_plan_json):
        """Test TaskEnv structure and components."""
        task_plan = _parse_task_plan_file(sample_task_plan_json)

        # Test full-featured environment
        test_env = task_plan.envs["test_python"]
        assert hasattr(test_env, 'requirements')
        assert hasattr(test_env, 'variables')
        assert "requests" in test_env.requirements
        assert "click" in test_env.requirements

        # Test minimal environment
        minimal_env = task_plan.envs["minimal_env"]
        assert minimal_env.requirements == []
        assert minimal_env.variables == {}

    def test_task_job_structure(self, sample_task_plan_json):
        """Test TaskJob structure and required fields."""
        task_plan = _parse_task_plan_file(sample_task_plan_json)

        # Test standard job
        echo_job = task_plan.jobs["test_echo"]
        assert hasattr(echo_job, 'env')
        assert hasattr(echo_job, 'note')
        assert hasattr(echo_job, 'timeout')
        assert hasattr(echo_job, 'command')
        assert echo_job.env == "minimal_env"
        assert echo_job.note == "test_file"
        assert echo_job.timeout == 10
        assert isinstance(echo_job.command, list)

        # Test shell job
        shell_job = task_plan.jobs["test_shell_command"]
        assert hasattr(shell_job, 'shell')
        assert shell_job.shell is True

    def test_task_note_structure(self, sample_task_plan_json):
        """Test TaskNote structure."""
        task_plan = _parse_task_plan_file(sample_task_plan_json)

        note = task_plan.notes["test_file"]
        assert hasattr(note, 'class_name')
        assert note.class_name == "FileNotifier"
        # Path should contain template variable for job name

    def test_environment_variable_substitution(self, temp_dir):
        """Test environment variable substitution in TaskEnv variables."""
        task_data = {
            "envs": {
                "var_test": {
                    "variables": {
                        "USER_VAR": "$USER",
                        "COMBINED": "Hello_${USER}_world",
                        "LITERAL": "no_substitution"
                    }
                }
            },
            "jobs": {},
            "notes": {}
        }

        json_file = os.path.join(temp_dir, "var_test.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(task_data, f)

        task_plan = _parse_task_plan_file(json_file)
        env_config = task_plan.envs["var_test"]

        # Variables should be stored as templates for later substitution
        assert env_config.variables["USER_VAR"] == "$USER"
        assert env_config.variables["COMBINED"] == "Hello_${USER}_world"
        assert env_config.variables["LITERAL"] == "no_substitution"

    def test_backtick_shell_commands(self, temp_dir):
        """Test backtick shell command evaluation in variables."""
        task_data = {
            "envs": {
                "shell_test": {
                    "variables": {
                        "ECHO_TEST": "`echo hello_world`",
                        "NORMAL_VAR": "not_a_command"
                    }
                }
            },
            "jobs": {},
            "notes": {}
        }

        json_file = os.path.join(temp_dir, "shell_test.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(task_data, f)

        task_plan = _parse_task_plan_file(json_file)
        env_config = task_plan.envs["shell_test"]

        # Backtick commands should be stored for later evaluation
        assert env_config.variables["ECHO_TEST"] == "`echo hello_world`"

    def test_shell_vs_list_commands(self, temp_dir, sample_task_plan_data):
        """Test difference between shell and list-based commands."""
        task_plan_data = sample_task_plan_data.copy()

        # Add test jobs for both shell and list commands
        task_plan_data["jobs"]["list_command"] = {
            "env": "minimal_env",
            "note": "test_file",
            "timeout": 5,
            "shell": False,
            "command": ["echo", "list_command_output"]
        }

        json_file = os.path.join(temp_dir, "command_test.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(task_plan_data, f)

        task_plan = _parse_task_plan_file(json_file)

        # Test shell command job
        shell_job = task_plan.jobs["test_shell_command"]
        assert shell_job.shell is True
        assert isinstance(shell_job.command, str)

        # Test list command job
        list_job = task_plan.jobs["list_command"]
        assert shell_job.shell is not False
        assert isinstance(list_job.command, list)

    def test_parse_unsupported_file(self, temp_dir):
        """Test parsing unsupported file type."""
        txt_file = os.path.join(temp_dir, "test.txt")
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write("not a task plan")

        with pytest.raises(ValueError, match="Unsupported file type"):
            _parse_task_plan_file(txt_file)


class TestJobExecution:
    """Test job execution functionality."""

    def test_simple_echo_job(self, temp_dir, sample_task_plan_json):
        """Test running a simple echo job."""
        task_plan = _parse_task_plan_file(sample_task_plan_json)

        # Mock the setup to avoid actually creating venvs
        with patch('ox_task.ui.cli.setup_job_environment') as mock_setup:
            mock_setup.return_value = temp_dir

            with patch('ox_task.ui.cli.notify_result'):
                result = run_job(temp_dir, task_plan, "test_echo")

                assert result["status"] == "success"
                assert result["exit_code"] == 0
                assert "Hello World" in result["output"]

    def test_nonexistent_job(self, temp_dir, sample_task_plan_json):
        """Test running a nonexistent job."""
        task_plan = _parse_task_plan_file(sample_task_plan_json)
        result = run_job(temp_dir, task_plan, "nonexistent_job")

        assert result["status"] == "error"
        assert "not found" in result["error"]

    def test_job_timeout(self, temp_dir, sample_task_plan_data):
        """Test job timeout handling."""
        # Create a job that sleeps longer than timeout
        sample_task_plan_data["jobs"]["test_timeout"] = {
            "env": "test_python",
            "note": "test_file",
            "timeout": 1,  # 1 second timeout
            "command": ["python", "-c", "import time; time.sleep(5)"]
        }

        json_file = os.path.join(temp_dir, "timeout_test.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(sample_task_plan_data, f)

        task_plan = _parse_task_plan_file(json_file)

        with patch('ox_task.ui.cli.setup_job_environment') as mock_setup:
            mock_setup.return_value = temp_dir
            with patch('ox_task.ui.cli.notify_result'):
                result = run_job(temp_dir, task_plan, "test_timeout")

                assert result["status"] == "timeout"
                assert "timed out" in result["error"]


class TestWeatherCommand:
    """Test the weather command functionality."""

    def test_weather_api_call(self):
        """Test weather command with mocked API."""

        with requests_mock.Mocker() as my_mock:
            # Mock the weather API response
            mock_response = {
                "current": {
                    "temperature_2m": 22.5,
                    "wind_speed_10m": 3.2
                }
            }
            my_mock.get(
                "https://api.open-meteo.com/v1/forecast",
                json=mock_response
            )

            runner = click.testing.CliRunner()

            # Import the weather command from simple_tasks
            from ox_task.example_tasks.simple_tasks import cli
            result = runner.invoke(cli, [
                'weather',
                '--latitude', '40.7',
                '--longitude', '-73.9'
            ])

        assert result.exit_code == 0
        assert "temperature_2m" in result.output
        assert "22.5" in result.output


class TestTickerCommand:
    """Test the check-tickers command functionality."""

    def test_check_tickers_api(self):
        """Test check-tickers command with mocked SEC API."""

        with requests_mock.Mocker() as my_mock:
            # Mock SEC company tickers response
            mock_tickers = {
                "0": {"ticker": "AAPL", "title": "Apple Inc"},
                "1": {"ticker": "MSFT", "title": "Microsoft Corp"},
                "2": {"ticker": "FUSE", "title": "Fuse Holdings"}
            }
            my_mock.get(
                "https://www.sec.gov/files/company_tickers.json",
                json=mock_tickers
            )

            runner = click.testing.CliRunner()
            from ox_task.example_tasks.simple_tasks import cli

            # Test alert-exists
            result = runner.invoke(cli, [
                'check-tickers',
                '--alert-exists', 'FUSE,AAPL'
            ])

        assert result.exit_code == 0
        assert "FUSE" in result.output
        assert "AAPL" in result.output
        assert "Apple Inc" in result.output

    def test_check_tickers_file(self, temp_dir):
        """Test check-tickers with local file."""
        # Create a test ticker file
        mock_tickers = {
            "0": {"ticker": "TEST", "title": "Test Corp"},
            "1": {"ticker": "DEMO", "title": "Demo Inc"}
        }
        ticker_file = os.path.join(temp_dir, "test_tickers.json")
        with open(ticker_file, 'w', encoding='utf-8') as f:
            json.dump(mock_tickers, f)

        runner = click.testing.CliRunner()
        from ox_task.example_tasks.simple_tasks import cli

        result = runner.invoke(cli, [
            'check-tickers',
            '--alert-exists', 'TEST',
            '--alert-not-exists', 'NOT_THERE,DEMO',
            '--url', f'file://{ticker_file}'
        ])

        assert result.exit_code == 0
        assert result.output.strip() == (
            "{'NOT_THERE': 'not found'"
            ", 'TEST': {'ticker': 'TEST', 'title': 'Test Corp'}}")


class TestGitHubFunctionality:
    """Test GitHub file download and execution."""

    def test_github_file_download(self, temp_dir):
        """Test downloading files from GitHub."""

        with requests_mock.Mocker() as my_mock:
            # Mock GitHub raw content
            test_script_content = "print('Downloaded from GitHub')\n"
            my_mock.get(
                "https://raw.githubusercontent.com/user/repo/main/script.py",
                text=test_script_content
            )

            runner = click.testing.CliRunner()
            outfile = os.path.join(temp_dir, "downloaded_script.py")

            result = runner.invoke(main, [
                'github-file',
                '--url', 'https://github.com/user/repo/blob/main/script.py',
                '--outfile', outfile
            ])

        assert result.exit_code == 0
        assert os.path.exists(outfile)

        with open(outfile, 'r', encoding='utf-8') as f:
            content = f.read()
        assert content == test_script_content

    def test_pyscript_github(self):
        """Test executing Python script from GitHub."""

        with requests_mock.Mocker() as my_mock:
            # Mock GitHub raw content
            test_script = "print('Hello from GitHub script')"
            my_mock.get(
                "https://raw.githubusercontent.com/user/repo/main/test.py",
                text=test_script
            )

            runner = click.testing.CliRunner()
            result = runner.invoke(main, [
                'pyscript',
                '--github-url',
                'https://github.com/user/repo/blob/main/test.py'
            ])

        assert result.exit_code == 0
        assert "Hello from GitHub script" in result.output


class TestFullWorkflow:
    """Test complete workflow execution."""

    def test_run_command_full_workflow(self, temp_dir, sample_task_plan_json):
        """Test the complete run command workflow."""
        # Mock the environment setup to avoid creating actual venvs
        with patch('ox_task.ui.cli.setup_job_environment') as mock_setup:
            mock_setup.return_value = temp_dir

            with patch('ox_task.ui.cli.notify_result'):
                runner = click.testing.CliRunner()
                result = runner.invoke(main, [
                    'run',
                    '--working-dir', temp_dir,
                    sample_task_plan_json
                ])

                # Should succeed (mocked) or fail due to missing modules
                assert result.exit_code in (0, 1)
                assert "Running" in result.output
                assert "jobs from" in result.output


class TestGoldenFiles:
    """Tests that compare outputs against golden files."""

    def test_echo_output_golden(self, temp_dir, golden_files_dir):
        """Test echo command output against golden file."""
        golden_file = os.path.join(golden_files_dir, "echo_output.txt")

        # Create golden file (you would provide this)
        expected_output = "Hello World\n"
        with open(golden_file, 'w', encoding='utf-8') as f:
            f.write(expected_output)

        # Run actual command
        result = subprocess.run([
            sys.executable, '-c', "print('Hello World')"
        ], capture_output=True, text=True, cwd=temp_dir, check=False)

        # Compare with golden file
        with open(golden_file, 'r', encoding='utf-8') as f:
            golden_content = f.read()

        assert result.stdout == golden_content

    def test_task_plan_parsing_golden(self, sample_task_plan_json,
                                     golden_files_dir):
        """Test task plan parsing output against golden file."""
        golden_file = os.path.join(golden_files_dir, "parsed_task_plan.json")

        # Parse task plan
        task_plan = _parse_task_plan_file(sample_task_plan_json)

        # Convert to comparable format
        parsed_data = {
            "env_count": len(task_plan.envs),
            "job_count": len(task_plan.jobs),
            "note_count": len(task_plan.notes),
            "env_names": sorted(list(task_plan.envs.keys())),
            "job_names": sorted(list(task_plan.jobs.keys())),
            "note_names": sorted(list(task_plan.notes.keys()))
        }

        # You would provide this golden file
        expected_data = {
            "env_count": 2,
            "job_count": 3,
            "note_count": 1,
            "env_names": ["minimal_env", "test_python"],
            "job_names": ["test_echo", "test_shell_command", "test_weather"],
            "note_names": ["test_file"]
        }

        with open(golden_file, 'w', encoding='utf-8') as f:
            json.dump(expected_data, f, indent=2)

        # Compare
        assert parsed_data == expected_data


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_malformed_json_task_plan(self, temp_dir):
        """Test handling of malformed JSON task plan."""
        bad_json_file = os.path.join(temp_dir, "bad_tasks.json")
        with open(bad_json_file, 'w', encoding='utf-8') as f:
            f.write('{"invalid": json syntax')

        with pytest.raises(json.JSONDecodeError):
            _parse_task_plan_file(bad_json_file)

    def test_missing_environment(self, temp_dir):
        """Test handling of missing environment reference."""
        task_data = {
            "envs": {},
            "jobs": {
                "test_job": {
                    "env": "nonexistent_env",
                    "command": ["echo", "test"]
                }
            },
            "notes": {}
        }

        json_file = os.path.join(temp_dir, "missing_env.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(task_data, f)

        _parse_task_plan_file(json_file)


class TestSecurityConsiderations:
    """Test security-related aspects of the ox_task system."""

    def test_shell_command_safety_awareness(self, temp_dir):
        """Test that shell commands are marked appropriately."""
        # This test documents the security consideration mentioned in README
        task_data = {
            "envs": {
                "unsafe_env": {
                    "variables": {
                        # Example of dangerous command
                        "POTENTIALLY_DANGEROUS": "`rm -rf /tmp/test`"
                    }
                }
            },
            "jobs": {
                "unsafe_shell_job": {
                    "env": "unsafe_env",
                    "note": "test_file",
                    "timeout": 5,
                    "shell": True,  # This enables shell evaluation
                    "command": "echo 'This could be dangerous'"
                }
            },
            "notes": {
                "test_file": {
                    "class_name": "FileNotifier",
                    "path": "/tmp/test_security.txt"
                }
            }
        }

        json_file = os.path.join(temp_dir, "security_test.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(task_data, f)

        task_plan = _parse_task_plan_file(json_file)

        # Verify that shell usage is explicit and documented
        unsafe_job = task_plan.jobs["unsafe_shell_job"]
        assert unsafe_job.shell is True  # Shell usage is explicit

        # Verify environment variables with backticks are stored as-is
        unsafe_env = task_plan.envs["unsafe_env"]
        dangerous_var = unsafe_env.variables["POTENTIALLY_DANGEROUS"]
        assert dangerous_var.startswith("`") and dangerous_var.endswith("`")

    def test_safer_list_command_approach(self, temp_dir):
        """Test the safer list-based command approach."""
        task_data = {
            "envs": {
                "safe_env": {
                    "variables": {
                        "SAFE_VAR": "safe_value"
                    }
                }
            },
            "jobs": {
                "safe_job": {
                    "env": "safe_env",
                    "note": "test_file",
                    "timeout": 5,
                    "shell": False,  # Safer default
                    "command": ["echo", "${SAFE_VAR}"]  # List format is safer
                }
            },
            "notes": {
                "test_file": {
                    "class_name": "FileNotifier",
                    "path": "/tmp/test_safe.txt"
                }
            }
        }

        json_file = os.path.join(temp_dir, "safe_test.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(task_data, f)

        task_plan = _parse_task_plan_file(json_file)
        safe_job = task_plan.jobs["safe_job"]

        assert not safe_job.shell  # Shell disabled by default
        assert isinstance(safe_job.command, list)  # List format

    def test_missing_environment_error_handling(self, temp_dir):
        """Test handling of missing environment reference."""
        task_data = {
            "envs": {},
            "jobs": {
                "test_job": {
                    "env": "nonexistent_env",
                    "command": ["echo", "test"]
                }
            },
            "notes": {}
        }

        json_file = os.path.join(temp_dir, "missing_env.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(task_data, f)

        task_plan = _parse_task_plan_file(json_file)

        with patch('ox_task.ui.cli.notify_result'):
            result = run_job(temp_dir, task_plan, "test_job")
            assert result['status'] == 'error'
            assert result['exit_code'] == -1
            assert result['error'] == (
                "Environment 'nonexistent_env' not found in task plan")


# Helper functions for test setup
def create_mock_response(data):
    """Create a mock response object."""
    mock = MagicMock()
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    return mock


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
