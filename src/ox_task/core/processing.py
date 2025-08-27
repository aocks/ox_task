"""Tools for processing tasks.
"""


class TaskProcessor:

    def __init__(self, task_plan):
        self.task_plan = task_plan

    def run(self, task_plan, results):
        for task_name, task_item in task_info.items():
            task_result = processing.run_task(task_name, task_item)
            assert task_name not in results
            results[task_name] = task_result
        click.echo(results)
