from celery import shared_task


@shared_task
def debug_ping() -> str:
    """Smoke-test task; replace or remove when real tasks are added."""
    return "pong"
