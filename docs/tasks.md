# Task classes

## Spawning tasks

## Chaining tasks

## Task qualifiers

# Queue a fullctl django command

All fullctl django commands have a `-Q` paramenter that allows you to send the command
execution to the queue.

## Example

```sh
manage.py fullctl_promote_user vegu -Q
```

# Process tasks

Fetch and process tasks in the task queue using the `fullctl_poll_tasks` command

```sh
manage.py fullctl_poll_tasks --workers 4
```

This will run forever and automatically fetch and process tasks that the environment is qualified
to handle.
