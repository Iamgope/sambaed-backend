from django.db import models
from debate.models import Topic

# Create your models here.
class TopicNews(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    content = models.TextField()
    pro_content = models.TextField()
    con_content = models.TextField()
