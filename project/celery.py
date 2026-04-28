import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")

app = Celery("project", broker=os.getenv("CELERY_BROKER_URL", "amqp://guest:guest@127.0.0.1:5672//"))
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
