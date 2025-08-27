from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field


class TaskEnv(BaseModel):
    """
    Represents the environment to run a task.
    """
    runtime: Optional[str] = Field(
        None,
        description="Python runtime environment (e.g., python3.11)"
    )
    requirements: Optional[List[str]] = Field(
        None,
        description=(
            "List of project dependencies in requirements file format"
        )
    )
    path: Optional[str] = Field(
        None,
        description="Path relative to the main task runner root"
    )
    variables: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="Dictionary of environment variable names and values"
    )


class TaskNote(BaseModel):
    """
    Represents how to log task results and possibly notify someone.
    """
    class_name: str = Field(
        description=(
            "String indicating the Note class to use "
            "(e.g., 'SimpleFileLog')"
        )
    )
    
    # Allow additional fields for optional keywords passed to the class
    class Config:
        extra = "allow"  # Allows additional fields beyond defined ones


class TaskJob(BaseModel):
    """
    Represents how to run the job for a task.
    """
    env: str = Field(
        description="String name of a TaskEnv indicating environment to use"
    )
    note: str = Field(
        description="String name of a TaskNote indicating how to track"
    )
    command: Union[str, List[str]] = Field(
        description="Command to execute - can be a string or list of strings"
    )
    timeout: Optional[float] = Field(
        default=300)
    shell: Optional[bool] = Field(
        description=('Whether to use shell in invoking command. See docs for'
                     'passing True for shell in subprocess as it can behave'
                     'in unexpected ways.'), default=False)
    


class TaskPlan(BaseModel):
    """
    Root model representing a complete task plan.
    Contains dictionaries of environments, notes, and jobs.
    """
    envs: Dict[str, TaskEnv] = Field(
        default_factory=dict,
        description="Dictionary of TaskEnv objects"
    )
    notes: Dict[str, TaskNote] = Field(
        default_factory=dict,
        description="Dictionary of TaskNote objects"
    )
    jobs: Dict[str, TaskJob] = Field(
        default_factory=dict,
        description="Dictionary of TaskJob objects"
    )


# Example usage and validation
if __name__ == "__main__":
    # Example JSON data based on your specification
    example_data = {
        "envs": {
            "simple_python": {
                "requirements": ["requests"]
            }
        },
        "jobs": {
            "check_tickers": {
                "env": "simple_python",
                "note": "simple_file_log",
                "command": [
                    "python3", "src/ox_task/example_tasks/check_tickers.py",
                    "--alert-exists", "FUSE",
                    "--alert-not-exists", "CSLM"
                ]
            }
        },
        "notes": {
            "simple_file_log": {
                "class_name": "SimpleFileLog",
                "filename": "results.log.txt"
            }
        }
    }
    
    # Parse and validate the data
    try:
        task_plan = TaskPlan(**example_data)
        import pdb; pdb.set_trace()#FIXME        
        print("✓ Task plan parsed successfully!")
        print(f"Found {len(task_plan.envs)} environments, "
              f"{len(task_plan.jobs)} jobs, {len(task_plan.notes)} notes")
        
        # Access specific elements
        simple_python_env = task_plan.envs["simple_python"]
        print(f"Simple python env requirements: "
              f"{simple_python_env.requirements}")
        
        check_tickers_job = task_plan.jobs["check_tickers"]
        print(f"Check tickers command: {check_tickers_job.command}")
        
        simple_file_log = task_plan.notes["simple_file_log"]
        print(f"Log class: {simple_file_log.class_name}")

    except Exception as e:
        print(f"✗ Validation failed: {e}")
