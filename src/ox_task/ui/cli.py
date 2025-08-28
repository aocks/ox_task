"""
Task runner script that executes job plans defined in JSON or Python files.
"""

from contextlib import ExitStack
import importlib
import importlib.util
import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from string import Template
from typing import Any, Dict, List, Union

import click
import requests

from ox_task.core import finders, models, noters, shell_tools, comm_utils


@click.group
def main():
    """The ox_task system helps you run automated tasks."""


@main.command
@click.argument("module")
def find_path(module):
    """Find and print the path to a Python module."""
    spec = importlib.util.find_spec(module)
    if spec and spec.origin:
        click.echo(spec.origin)
    return spec.origin


@main.command
@click.option('--url', required=True,
              help='URL for GitHub file to download.')
@click.option('--outfile', type=click.Path(), required=True,
              help='Path to where to store local copy of the file.')
@click.option('--timeout', type=float, default=30)
def github_file(url, outfile, timeout):
    """Download GitHub files from URLs.

    The --url can include a path to a branch like:
      https://github.com/python/cpython/blob/main/README.rst

    or can include a commit hash like:
      https://github.com/python/cpython/blob/a7715ccfba5b86ab09f42ae69d987a1260cba29c/README.rst
    """
    raw_url = url.replace("github.com", "raw.githubusercontent.com").replace(
        "/blob/", "/")

    response = requests.get(raw_url, timeout=timeout)
    response.raise_for_status()

    with open(outfile, 'wb') as f:
        f.write(response.content)


@main.command
@click.option('--github-url', help='URL for GitHub file to download.')
@click.option('--path', type=click.Path(),
              help='Path to where to store local copy of the file.')
@click.option('--timeout', type=float, default=30)
def pyscript(github_url, path, timeout):
    """Download and execute a Python script from GitHub or run a local script.
    """
    if not github_url and not path:
        raise click.BadParameter('Must provide github-url and/or path.')
    
    with ExitStack() as stack:
        if github_url:  # need to download file from github
            if not path:  # no path give so download to temporary file path
                tmpdir = stack.enter_context(tempfile.TemporaryDirectory())
                path = os.path.join(tmpdir, 'script.py')
            github_file.callback(url=github_url, outfile=path, timeout=timeout)
        cmd = [sys.executable, path]
        result = simple_run_command(cmd, capture_output=True, text=True,
                                    timeout=timeout)
    
    click.echo(f'Result of calling {cmd=}:\n{result}')
    if result['exit_code']:
        raise subprocess.CalledProcessError(
            cmd=cmd, returncode=result['exit_code'], output=result.get(
                'output', None), stderr=result.get('stderr', None))
    return result


def notify_result(task_plan: models.TaskPlan, noter_name: str,
                 job_results: Dict[str, Any], env_vars: Dict[str, str]) -> None:
    """Notify about job results using configured noter.

    Args:
        task_plan: The task plan containing noter configurations
        noter_name: Name of the noter to use
        job_results: Results from job execution
        env_vars: Environment variables for template substitution
    """
    if not noter_name:
        logging.warning('No TaskNote configured for task_plan %s; using %s',
                        task_plan, 'EchoNotifier')
        klass = finders.TaskNoteFinder.find_noter('EchoNotifier')
        kwargs = {}
    else:
        note_config = task_plan.notes.get(noter_name)
        if note_config is None:
            raise ValueError(f'No TaskNote named {noter_name}')

        klass = finders.TaskNoteFinder.find_noter(note_config.class_name)
        kwargs = {
            k: Template(v).safe_substitute(env_vars) if isinstance(v, str) else v
            for k, v in note_config.model_dump().items()
        }

    my_noter = klass(**kwargs)
    my_noter.notify_result(job_results)


def _create_virtual_environment(job_dir: str, env_config) -> None:
    """Create a virtual environment for the job."""
    runtime = env_config.runtime or "python3"
    venv_path = os.path.join(job_dir, "venv")

    subprocess.run(
        [runtime, "-m", "venv", venv_path],
        check=True,
        cwd=job_dir
    )


def _install_requirements(job_dir: str, env_config) -> None:
    """Install requirements in the virtual environment."""
    if not env_config.requirements:
        return

    venv_path = os.path.join(job_dir, "venv")
    if os.name == "nt":  # Windows
        pip_path = os.path.join(venv_path, "Scripts", "pip.exe")
    else:
        pip_path = os.path.join(venv_path, "bin", "pip")

    for requirement in env_config.requirements:
        subprocess.run(
            [pip_path, "install", requirement],
            check=True,
            cwd=job_dir
        )


def setup_job_environment(working_dir: str, job_name: str,
                         task_plan: models.TaskPlan,
                         env_name: str) -> str:
    """
    Set up the job environment including venv creation and requirements.

    Args:
        working_dir: Base working directory
        job_name: Name of the job (used for subdirectory)
        task_plan: Parsed task plan containing environment definitions
        env_name: Name of the environment to set up

    Returns:
        Path to the job directory
    """
    job_dir = os.path.join(working_dir, job_name)

    if not os.path.exists(job_dir):
        os.makedirs(job_dir)

        env_config = task_plan.envs.get(env_name)
        if not env_config:
            raise ValueError(f"Environment '{env_name}' not found in task plan")

        _create_virtual_environment(job_dir, env_config)
        _install_requirements(job_dir, env_config)

    return job_dir


def simple_run_command(command: List[str], **kwargs) -> Dict[str, Any]:
    """
    Run a command and return structured results.

    Args:
        command: Command to run as a list of strings
        **kwargs: Additional arguments to pass to subprocess.run

    Returns:
        Dictionary containing execution results
    """
    job_results = {'cwd': kwargs.get('cwd', os.getcwd())}
    try:
        result = subprocess.run(command, **kwargs)
        job_results.update(
            status="success" if result.returncode == 0 else "failed",
            exit_code=result.returncode,
            output=result.stdout, stderr=result.stderr,
            command=command)
        if job_results['exit_code'] != 0 and 'error' not in job_results:
            job_results['error'] = job_results.get('stderr', 'unknown')

    except subprocess.TimeoutExpired as e:
        job_results.update(
            status="timeout",
            exit_code=-1, error="Command timed out",
            output=e.stdout or "", stderr=e.stderr or "",
            command=command)
    except Exception as e:
        logging.exception('Unable to run command')
        job_results.update(
            status="error", exit_code=-1, error=str(e),
            output="", stderr="", command=command)

    return job_results


def _prepare_environment_variables(job_name, env_config) -> Dict[str, str]:
    """
    Prepare environment variables with shell command execution and templating.
    """
    env_vars = os.environ.copy()
    env_vars['OX_TASK_JOB_NAME'] = job_name
    if not env_config.variables:
        return env_vars

    for name, value in list(env_config.variables.items()):
        if value.startswith('`') and value.endswith('`'):
            value = shell_tools.run_shell_command(value[1:-1], env=env_vars)
        else:
            value = Template(value).safe_substitute(env_vars)
        env_vars[name] = value

    return env_vars


def run_job(working_dir: str, task_plan: models.TaskPlan,
            job_name: str, re_raise=True) -> Dict[str, Any]:
    """Run a single job from the task plan.

    Args:
        working_dir: Base working directory for job execution
        task_plan: Parsed task plan containing job definitions
        job_name: Name of the job to run

    Returns:
        Dictionary containing job execution results
    """
    # Get job configuration
    job_config = task_plan.jobs.get(job_name)
    if not job_config:
        return {
            "status": "error",
            "exit_code": -1,
            "error": f"Job '{job_name}' not found in task plan",
            "output": "",
            "stderr": ""
        }

    try:
        env_vars = {}
        # Set up job environment
        job_dir = setup_job_environment(
            working_dir, job_name, task_plan, job_config.env
        )

        # Get environment configuration for path and vars
        env_config = task_plan.envs[job_config.env]

        # Prepare command
        if isinstance(job_config.command, str):
            command = job_config.command.split()
        else:
            command = job_config.command
        if not isinstance(command, (list, tuple)):
            raise ValueError(f'Expected list or tuple for {command=}')

        # Set up environment variables
        env_vars = _prepare_environment_variables(job_name, env_config)

        # Add venv to PATH
        venv_bin = os.path.join(job_dir, "venv", "bin")
        if os.name == "nt":  # Windows
            venv_bin = os.path.join(job_dir, "venv", "Scripts")
        env_vars["PATH"] = f"{venv_bin}{os.pathsep}{env_vars.get('PATH', '')}"

        command = [Template(c).safe_substitute(env_vars) for c in command]

        # Set working directory for command execution
        cmd_working_dir = job_dir
        if env_config.path:
            cmd_working_dir = os.path.join(job_dir, env_config.path)

        job_results = simple_run_command(
            command, cwd=cmd_working_dir, env=env_vars, capture_output=True,
            text=True, shell=job_config.shell, timeout=job_config.timeout)
    except Exception as problem:
        logging.exception('Unable to run command')
        job_results = {
            "status": "error",
            "exit_code": -1,
            "error": str(problem),
            "output": "",
            "stderr": "",
            "command": []
        }

    notify_result(task_plan, job_config.note, job_results, env_vars)

    if job_results['exit_code']:
        logging.warning(
            'Job %s returned error code %s\n  output=%s\n  stderr=%s',
            job_name, job_results['exit_code'],
            job_results.get('output', None), job_results.get('stderr', None))
        if re_raise:
            raise subprocess.CalledProcessError(
                cmd=command, returncode=job_results['exit_code'],
                output=job_results.get('stdout', None),
                stderr=job_results.get('stderr', None))

    return job_results


def _parse_task_plan_file(task_plan_file: str) -> models.TaskPlan:
    """Parse task plan file and return TaskPlan object."""
    task_plan_path = Path(task_plan_file)

    if task_plan_path.suffix.lower() == ".json":
        # Parse JSON file
        with open(task_plan_path, 'r') as f:
            task_data = json.load(f)
    elif task_plan_path.suffix.lower() == ".py":
        # Parse Python module
        spec = importlib.util.spec_from_file_location(
            "task_plan", task_plan_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Extract task plan data from module
        task_data = {
            "envs": getattr(module, "envs", {}),
            "notes": getattr(module, "notes", {}),
            "jobs": getattr(module, "jobs", {})
        }
    else:
        raise ValueError(
            f"Unsupported file type: {task_plan_path.suffix}. "
            "Use .json or .py files."
        )

    return models.TaskPlan(**task_data)


@main.command()
@click.option(
    "--working-dir",
    default=None,
    help="Working directory for job execution (default: system temp dir)"
)
@click.option(
    "--re-raise/--no-re-raise", default=False, help=(
        'If --re-raise is provided we raise an Exception if a job fails.'))
@click.argument("task_plan_file", type=click.Path(exists=True))
def run(working_dir: str, task_plan_file: str, re_raise: bool) -> None:
    """Run all jobs defined in a task plan file.

    TASK_PLAN_FILE: Path to JSON or Python file containing task definitions

If you provide --re-raise, then an Exception will be raised if any job
fails. This can be helpful if you want to debug or if you just want to
stop execution of all tasks if any task fails.    
    """
    # Set default working directory
    if working_dir is None:
        working_dir = tempfile.gettempdir()

    # Ensure working directory exists
    os.makedirs(working_dir, exist_ok=True)

    # Parse task plan file
    try:
        task_plan = _parse_task_plan_file(task_plan_file)
    except Exception as e:
        click.echo(f"Error parsing task plan file: {e}", err=True)
        sys.exit(1)

    # Run all jobs and collect results
    all_results = {}

    click.echo(f"Running {len(task_plan.jobs)} jobs from {task_plan_file}")
    click.echo(f"Working directory: {working_dir}")
    click.echo("-" * 60)

    for job_name in task_plan.jobs:
        click.echo(f"Running job: {job_name}")

        job_result = run_job(working_dir, task_plan, job_name, re_raise)
        all_results[job_name] = job_result

        # Print job status
        status_color = "green" if job_result["status"] == "success" else "red"
        click.echo(
            f"  Status: {click.style(job_result['status'], fg=status_color)}"
        )
        short_msg = comm_utils.shorten_msg(
            job_result.get('output', 'unknown'), max_len=(
                400 if job_result['exit_code'] == 0 else 2000))
        click.echo(f"  Output: {click.style(short_msg, fg=status_color)}")
        if job_result.get("exit_code") is not None:
            click.echo(f"  Exit Code: {job_result['exit_code']}")

        if job_result.get("error"):
            click.echo(f"  Error: {job_result['error']}")
            click.echo(f"  stdout: {job_result.get('stdout', 'None')}")
            click.echo(f"  stderr: {job_result['stderr']}")

        click.echo()

    # Summary
    successful = sum(1 for r in all_results.values()
                    if r["status"] == "success")
    total = len(all_results)

    click.echo("-" * 60)
    click.echo(f"Completed: {successful}/{total} jobs successful")

    # Exit with error code if any jobs failed
    if successful < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
