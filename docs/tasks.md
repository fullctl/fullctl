# Task classes

## Definition

### Needs to be registered

Task models need to be decorated with `fullctl.django.tasks.register`

### Need to be proxy

All task models should be proxy models of `fullctl.django.models.Task`

### Need to set HandleRef tag

Task models use the handle ref tag to uniquely identify their type / model
when it comes to converting from Task to the proxy model.

### Config through TaskMeta

The TaskMeta meta class can be used to specified task limits and task qualifiers
for each task model individually.

```py
from fullctl.django.models import Task
from fullctl.django.tasks import register

@register
class SumTask(Task):

    # required
    class Meta:
        proxy = True

    # required
    class HandleRef:
        tag = "task_sum"

    # optional
    class TaskMeta:
        limit = 1
        result_type = str
        qualifiers = [qualifiers.Setting('IMPORTANT_SETTING', True),]

    # required
    def run(self, a, b, *args, **kwargs):
        return (a,b)
```

### Needs to be imported

Don't forget to make sure your task models are imported through your django app's `models.py`

### Task Qualifiers

The fullctl task queue allows you to limit which pollers are allowed to work on which tasks through the `qualifiers` system.

If qualifiers are set on your task, only the pollers that meet the requirements will be able to poll and claim those tasks.

#### Settings Qualifier

This qualifier allows you to require certain conditions to exist within the django project settings.

##### Example

```py
from fullctl.django.tasks import qualifiers
class MyTask(Task):

    class Meta:
        proxy = True

    class HandleRef:
        tag = "task_my"

    class TaskMeta:
        qualifiers = [
            # require settings.IMPORTANT_SETTING to be True
            qualifiers.Settings('IMPORTANT_SETTING', True),

            # require value 'xyz' to exist in settings.IMPORTANT_LIST
            qualifiers.Settings(
                'IMPORTANT_LIST',
                lambda v: 'xyz' in v
            )
        ]
```

### Task Limits

You may want to limit how many pending instances can exist of a task model.

This is done through the `TaskMeta` limit property and the task model's `limit_id` property.

#### Examples

Allow a maximum of 1 pending instances to be up for the task.

```py
class MyTask(Task):
    class Meta:
        proxy = True

    class HandleRef:
        tag = "task_my"

    class TaskMeta:
        limit = 1


MyTask.create_task() # ok
MyTask.create_task() # raises TaskLimitError
```

Allow 1 pending instances to be up for each variation of task as specified
by the first task argument

```py
class MyTask(Task):
    class Meta:
        proxy = True

    class HandleRef:
        tag = "task_my"

    class TaskMeta:
        limit = 1

    @property
    def generate_limit_id(self):
        return self.param["args"][0]

MyTask.create_task("first") # ok
MyTask.create_task("second") # ok
MyTask.create_task("first") # raises TaskLimitError
```

### Migrations

Django still wants to make migrations for proxy models and will do so at the next
`makemigrations` call. However it does not seem to be mandatory for normal operation. Just be aware that such migrations will be made.


# Creating task instances

Tasks are spawned by creating object instances of the task.

This should be done through the models `create_task` class method.

```py
MyTask.create_task()
```

## Execution

Execution logic should be overridden in the model's `run` method.

### Task arguments

Any arguments and keyword arguments passed to create task (excl `parent` and `timeout`) will be also passed to the tasks `run` method.

### Task results

A task wont have any result value until its processed. You can wait for the results by calling the `wait` method on the task. If `async` context you can also use `async_wait` instead.

#### Result type

You can specify a result type for the task in `TaskMeta` with the `result_type` property

### Example

```py
class SumTask(Task):
    class Meta:
        proxy = True

    class HandleRef:
        tag = "task_sum"

    class TaskMeta:
        result_type = int

    def run(self, a, b, *args, **kwargs):
        return (a+b)

task = SumTask.create_task(2,3)

# wait for task to be processed
task.wait(timeout=10)

assert task.result == 5
```

## Chaining tasks

You can chain tasks, requiring the parent task to be processed succesfully before processing the child task

This is done by specifying the `parent` parameter in `create_task`

```py
first_task = MyTask.create_task()
next_task = MyTask.create_task(parent=first_task)
```

The `child` task will not be processed until the parent task is processed.

## Timeouts

You can give a task a maximum execution time via the timeout parameter in `create_task`

```py
task = MyTask.create_task(timeout=600) # 10 minutes max. execution time

task.wait(timeout=10) # separate timeout for waiting for a result
```

# Django settings

- `TASK_ORM_WORKER_ID`: specifies how the environment is identified when spawning or processing a task. if not specified this will default to "{hostname}:{pid}"

# Django admin

Task state and listing can be accessed from `/admin/django_fullctl/task`

- source: hostname and process id that spawned the task
- queue_id: hostname and process id that claimed the task for processing
- parent: parent task
- status: task status (pending, running, completed, failed, cancelled)
- param: task parameters
- time: task completion time

# Queue a fullctl django command

All fullctl django commands have a `-Q` paramenter that allows you to send the command execution to the queue.

## Example

```sh
manage.py fullctl_promote_user vegu -Q
```

# Process tasks

Fetch and process tasks in the task queue using the `fullctl_poll_tasks` command

## Workers

```sh
manage.py fullctl_poll_tasks --workers 4
```

This will run forever and automatically fetch and process tasks that the environment is qualified to handle.

## Self selecting workers

```sh
manage.py fullctl_poll_tasks --processes 4
```

The difference between `--workers` and `--processes` is that `--processes` will spawn worker processes immediately that will poll for tasks themselves. While --workers will maintain a queue of busy and idle workers and assign tasks to them, spawning processes as tasks are assigned.

`--processes` is faster and will likely replace `--workers` in the future.

When using `--processes`, the `--workers` parameter is automatically set to 0, so you don't need to specify it manually.

### Limiting tasks per worker process

You can specify a maximum number of tasks a self-selecting worker process should handle before it exits and gets respawned. This helps prevent memory leaks or resource issues in long-running worker processes.

```sh
manage.py fullctl_poll_tasks --processes 4 --max-tasks-per-process 100
```

Or using the short-form parameter:

```sh
manage.py fullctl_poll_tasks -p 4 -t 100
```

This will cause each worker process to automatically exit after processing 100 tasks, and a new worker process will be spawned to replace it. If not specified or set to 0, worker processes will continue running indefinitely.


# Pruning old tasks

The `fullctl_manage_tasks prune` command removes old tasks from the database. Nothing is deleted without `--commit` (dry-run by default).

## Basic usage

```bash
# Dry-run: see how many tasks would be pruned
python manage.py fullctl_manage_tasks prune --age 30

# Actually delete completed/failed/cancelled tasks older than 30 days
python manage.py fullctl_manage_tasks prune --age 30 --commit
```

## Filtering by limit_id

Use `--include` or `--exclude` (mutually exclusive) to filter tasks by their `limit_id` using regex patterns.

```bash
# Prune only high-volume task types, keeping last 30 days
python manage.py fullctl_manage_tasks prune --include ".*(traffic|config/liveness|bgp/stats).*" --age 30 --commit

# Prune everything except liveness tasks
python manage.py fullctl_manage_tasks prune --exclude ".*/config/liveness/.*" --age 30 --commit
```

Patterns are full regex, with a glob-style shorthand layered on top: `**` is
always expanded to `.*`, and a single `*` is expanded to `.*` only where a
regex quantifier cannot appear — at the start of the pattern, or directly
after `(`, `|` or `/`. Everywhere else `*` keeps its regex meaning, so
`\d*`, `[a-z]*` and `(foo)*` match what they say.

## Cascade behavior

Tasks can have child tasks (`Task.parent`), and the FK cascades. Pruning a
task therefore also deletes its descendant tasks — including descendants that
do not match `--age`, `--status` or the pattern filters — along with their
heartbeat and claim rows. Dry-run counts cover only the directly matched
tasks, so the committed run can delete more rows than the dry run reported.

## Pruning specific statuses

By default only `completed`, `failed`, and `cancelled` tasks are pruned. Use `--status` to override.

```bash
# Prune all statuses including pending and running
python manage.py fullctl_manage_tasks prune --status pending running completed failed cancelled --age 30 --commit
```

## Settings

| Setting | Description | Default |
|---|---|---|
| `TASK_DEFAULT_PRUNE_AGE` | Default max age in days | 30 |
| `TASK_DEFAULT_PRUNE_STATUS` | Default statuses to prune | `completed`, `failed`, `cancelled` |
| `TASK_DEFAULT_PRUNE_EXCLUDE` | List of `limit_id` patterns always excluded from pruning, even when `--include` is used | `[]` |
| `TASK_PRUNE_BATCH_SIZE` | Rows deleted per batch | 10000 |

!!! warning "Upgrading to 1.16"

    `--exclude` now takes a single `limit_id` regex; it previously took a list
    of task op names (`--exclude op_a op_b`), which will now fail argparse.
    `TASK_DEFAULT_PRUNE_EXCLUDE` changed the same way — a value carried over
    from an earlier release is read as `limit_id` patterns and will silently
    stop protecting the ops it names. Rewrite the setting and any prune cron
    invocations before upgrading.

## All options

| Option | Description |
|---|---|
| `--age` | Maximum age in days for tasks to retain (default: `TASK_DEFAULT_PRUNE_AGE`) |
| `--status` | List of task statuses to prune (default: `TASK_DEFAULT_PRUNE_STATUS`) |
| `--include` | Only prune tasks whose `limit_id` matches this regex |
| `--exclude` | Only prune tasks whose `limit_id` does NOT match this regex |
| `--commit` | Actually delete (omit for dry-run) |

## Combined pruning with auditctl

In auditctl, the `auditctl_prune` command can prune both events and tasks in one shot using `--tasks`:

```bash
# Prune events AND tasks for high-volume patterns, keeping last 30 days
python manage.py auditctl_prune --include ".*(traffic|config/liveness|bgp/stats).*" --tasks --max-age 30 --commit
```

See the [auditctl pruning docs](../service/auditctl/docs/pruning.md) for full details.

# Task tracking

In `CommandInterface` there is a function `before_run` that runs before the command is run

In the worker `Command` a separate thread is created to track the task processing to avoid blocking the main thread for the command worker

The function of this thread is to update the TaskHeartbeart while the task is running

This is done at intervals of the specified - env var `TASK_TRACK_INTERVAL_SECONDS`

The `timestamp` field in the `TaskHeartbeat` model is used to check if the task is still running and not dead.

This is always checked for all tasks when `/health` is visited
