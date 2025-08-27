"""Command line interface for ox_task project.
"""

import json

import click

from ox_task.core import models
from ox_task.core import noters

import click

@click.group()
def cli():
    """Main commands for ox_task.
    """

@click.option('--task-file', required=True, type=click.Path(exists=True))
@cli.command
def run(task_file):
    results = {}
    click.echo(f'Processing task-file {task_file}')
    task_plan = plan.TaskPlan()
    for tf in task_file:
        task_plan.import_plan_from_file(tf)
    task_processor = processing.TaskProcessor(task_plan)
    task_processor.run(results)


if __name__ == '__main__':
    cli()
