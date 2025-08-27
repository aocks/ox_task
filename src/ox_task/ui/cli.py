"""
Task runner script that executes job plans defined in JSON or Python files.
"""

import importlib
import json
import logging
import os
from string import Template
import subprocess
import tempfile
import sys
from pathlib import Path
from typing import Dict, Any

import click

from ox_task.core import models, noters, shell_tools


@click.group
def main():
    """The ox_task system helps you run automated tasks.
    """

@main.command
@click.argument("module")
def find_path(module):
    spec = importlib.util.find_spec(module)
    if spec and spec.origin:
        click.echo(spec.origin)
    return spec.origin
    



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
    
    # Create job directory if it doesn't exist
    if not os.path.exists(job_dir):
        os.makedirs(job_dir)
        
        # Get environment configuration
        env_config = task_plan.envs.get(env_name)
        if not env_config:
            raise ValueError(f"Environment '{env_name}' not found in task plan")
        
        # Determine python runtime
        runtime = env_config.runtime or "python3"
        
        # Create virtual environment
        venv_path = os.path.join(job_dir, "venv")
        subprocess.run(
            [runtime, "-m", "venv", venv_path], 
            check=True,
            cwd=job_dir
        )
        
        # Install requirements if specified
        if env_config.requirements:
            pip_path = os.path.join(venv_path, "bin", "pip")
            if os.name == "nt":  # Windows
                pip_path = os.path.join(venv_path, "Scripts", "pip.exe")
            
            for requirement in env_config.requirements:
                subprocess.run(
                    [pip_path, "install", requirement],
                    check=True,
                    cwd=job_dir
                )
    
    return job_dir


def run_job(working_dir: str, task_plan: models.TaskPlan, 
            job_name: str) -> Dict[str, Any]:
    """
    Run a single job from the task plan.
    
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
        env_vars = os.environ.copy()
        if env_config.variables:
            for name, value in list(env_config.variables.items()):
                if value[0] == '`' and value[-1] == '`':
                    value = shell_tools.run_shell_command(value[1:-1],
                                                          env=env_vars)
                else:
                    value = Template(value).safe_substitute(env_vars)
                env_vars[name] = value
        
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
        
        # Execute command
        import pdb; pdb.set_trace()#FIXME
        result = subprocess.run(
            command,
            cwd=cmd_working_dir,
            env=env_vars,
            capture_output=True,
            text=True,
            shell=job_config.shell,
            timeout=job_config.timeout
        )
        import pdb; pdb.set_trace()#FIXME
        # Prepare results
        job_results = {
            "status": "success" if result.returncode == 0 else "failed",
            "exit_code": result.returncode,
            "output": result.stdout,
            "stderr": result.stderr,
            "command": command,
            "working_dir": cmd_working_dir
        }
        if job_results['exit_code'] != 0 and 'error' not in job_results:
            job_results['error'] = job_results.get('stderr', 'unknown')
        
    except subprocess.TimeoutExpired as e:
        job_results = {
            "status": "timeout",
            "exit_code": -1,
            "error": f"Command timed out",
            "output": e.stdout or "",
            "stderr": e.stderr or "",
            "command": command
        }
    except Exception as e:
        logging.exception('Unable to run command')
        job_results = {
            "status": "error",
            "exit_code": -1,
            "error": str(e),
            "output": "",
            "stderr": "",
            "command": getattr(locals().get('command'), 'command', [])
        }
    
    # Handle notification
    try:
        note_config = task_plan.notes.get(job_config.note)
        if note_config:
            # Get notifier class
            notifier_class = getattr(noters, note_config.class_name)
            
            # Extract additional kwargs (excluding class_name)
            note_kwargs = {
                k: v for k, v in note_config.dict().items() 
                if k != "class_name"
            }
            
            # Instantiate and call notifier
            notifier = notifier_class(**note_kwargs)
            notifier(job_results)
            
    except Exception as e:
        # Don't fail the job if notification fails
        job_results["notification_error"] = str(e)
    
    return job_results


@main.command()
@click.option(
    "--working-dir", 
    default=None,
    help="Working directory for job execution (default: system temp dir)"
)
@click.argument("task_plan_file", type=click.Path(exists=True))
def run(working_dir: str, task_plan_file: str) -> None:
    """
    Run all jobs defined in a task plan file.
    
    TASK_PLAN_FILE: Path to JSON or Python file containing task definitions
    """
    # Set default working directory
    if working_dir is None:
        working_dir = tempfile.gettempdir()
    
    # Ensure working directory exists
    os.makedirs(working_dir, exist_ok=True)
    
    # Parse task plan file
    try:
        task_plan_path = Path(task_plan_file)
        
        if task_plan_path.suffix.lower() == ".json":
            # Parse JSON file
            with open(task_plan_path, 'r') as f:
                task_data = json.load(f)
        elif task_plan_path.suffix.lower() == ".py":
            # Parse Python module
            import importlib.util
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
        
        # Create TaskPlan object
        task_plan = models.TaskPlan(**task_data)
        
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
        
        job_result = run_job(working_dir, task_plan, job_name)
        all_results[job_name] = job_result
        
        # Print job status
        status_color = "green" if job_result["status"] == "success" else "red"
        click.echo(
            f"  Status: {click.style(job_result['status'], fg=status_color)}"
        )
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
