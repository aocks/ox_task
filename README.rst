Specification
=============

Task Plan
---------

A task plan consists of one or more task files. A task file can either
be a JSON file or a python module. In either case, there should be the
following top-level dictionaries:

-  envs: A dictionary of TaskEnv objects (see below).
-  notes: A dictionary of TaskNote objects (see below).
-  jobs: A dictionary of TaskJob objects (see below).

TaskEnv
~~~~~~~

A TaskEnv represents the environment to run a task. It should be a
dictionary with the following elements:

-  runtime: Optional string indicating python runtime environment (e.g,
   python3.11).
-  requirements: Optional list of strings indicating project
   dependencies in the same format of a python requirements file.
-  path: Optional path (relative to the main task runner root).
-  vars: Dictionary of environment variable names and values to define.

TaskNote
~~~~~~~~

A TaskNote represents how to log the task results and possibly notify
someone about them. It should be a dictionary with the following
elements:

-  class\ :sub:`name`: String indicating the Note class to use (e.g.,
   "SimpleFileLog").
-  Optional keywords and values passed as a dictionary to the class
   implementation the note.

TaskJob
~~~~~~~

A TaskJob represents how to run the job for a task. It should be a
dictionary with the following elements:

-  env: String name of a TaskEnv indicating environment to use in
   running the task.
-  note: String name of a TaskNote indicating how to track or notify
   someone about the task results.
-  command:
