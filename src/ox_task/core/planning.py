"""Module to represent a task plan.
"""

class TaskParsingError(Exception):
    pass

from ox_task.core.models import TaskEnv, TaskNote, TaskJob,
models.py

class TaskPlan:

    def __init__(self):
        self.jobs = {}
        self.envs = {}
        self.notes = {}

    def import_plan_from_file(self, fname):
        if fname.endswith('.json') or fname.endswith('.js'):
            with open(fname, 'r', encoding='utf8') as fdesc:
                text = fdesc.read()
                return self.import_plan_from_json(text)
        if fname.endswith('.py'):
            return self.import_plan_from_python_file(fname)
        raise TaskParsingError(f'Unsupported file type {fname}')
        
    def import_plan_from_json(self, text):
        data = json.loads(text)
        if not isinstance(text, dict):
            raise TaskParsingError(f'Text {text[:60]}... was not a dict')
        self.import_plan_from_dict(self, data)

    def import_plan_from_dict(self, data):
        ekeys = ['jobs', 'envs', 'notes']
        if list(sorted(data)) != ekeys:
            raise TaskParsingError(
                f'Got keys {list(sorted(data))}: expected {ekeys}')
        self.import_jobs(data['jobs'])
        self.import_envs(data['events'])
        self.import_notes(data['notes'])

    def import_jobs(self, job_dict):
        if not isinstance(job_dict, dict):
            raise JobParsingError(f'Expected dict but job_dict was {job_dict}')
        for name, info in job_dict.items():
            fixme
