TASK_MODELS = {}


def register(cls):
    TASK_MODELS[cls.HandleRef.tag] = cls
    return cls


def specify_task(task):
    return TASK_MODELS[task.op].objects.get(id=task.id)
