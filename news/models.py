from django.db import models
from debate.models import Topic

# Create your models here.
class TopicNews(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    content = models.TextField()
    pro_content = models.TextField()
    con_content = models.TextField()


class Perspective(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_DROPPED = "dropped"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_DROPPED, "Dropped"),
    ]

    # Source article snapshot — captured at generation time so the read
    # endpoint can return article + context + perspective in one query
    # without re-fetching from the original source.
    event_title = models.TextField(blank=True)
    event_context = models.TextField(blank=True)
    event_source = models.CharField(max_length=64, blank=True)
    event_date = models.CharField(max_length=10, blank=True)

    # LLM-derived perspective fields
    question = models.TextField(blank=True)
    context_2line = models.TextField(blank=True)
    view_1_label = models.CharField(max_length=64, blank=True)
    view_1_text = models.TextField(blank=True)
    view_2_label = models.CharField(max_length=64, blank=True)
    view_2_text = models.TextField(blank=True)
    debatable = models.BooleanField()
    drop_reason = models.TextField(blank=True)
    source_event_url = models.URLField(max_length=1024)
    image_url = models.URLField(max_length=1024, blank=True, default="")
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.question or self.drop_reason or f"Perspective {self.pk}"
