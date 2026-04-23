from django.db import models
from django.contrib.auth.models import User

from debate.constants import MatchQueueStatus, RoundType, DebateStatus

# Create your models here.
class Topic(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class Debate(models.Model):

    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)

    user_pro = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pro_debates')
    user_con = models.ForeignKey(User, on_delete=models.CASCADE, related_name='con_debates')

    winner = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)

    status = models.CharField(max_length=20, choices=DebateStatus.label)

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class Round(models.Model):

    debate = models.ForeignKey(Debate, on_delete=models.CASCADE, related_name='rounds')
    round_type = models.CharField(max_length=20, choices=RoundType.label)
    order = models.IntegerField()  # 1, 2, 3

    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)


class Message(models.Model):
    debate = models.ForeignKey(Debate, on_delete=models.CASCADE)
    round = models.ForeignKey(Round, on_delete=models.CASCADE)

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField(max_length=1000)

    created_at = models.DateTimeField(auto_now_add=True)


class Judgement(models.Model):
    debate = models.OneToOneField(Debate, on_delete=models.CASCADE)

    winner = models.ForeignKey(User, on_delete=models.CASCADE)

    argument_score_pro = models.FloatField()
    rebuttal_score_pro = models.FloatField()
    clarity_score_pro = models.FloatField()
    persuasion_score_pro = models.FloatField()

    argument_score_con = models.FloatField()
    rebuttal_score_con = models.FloatField()
    clarity_score_con = models.FloatField()
    persuasion_score_con = models.FloatField()

    reasoning = models.TextField()
    strongest_moment = models.TextField()
    coaching_tip_pro = models.TextField()
    coaching_tip_con = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Judgement for {self.debate.id}"

class MatchQueue(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    matched = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=MatchQueueStatus.label)

    matched_at = models.DateTimeField(null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"MatchQueue for {self.user.username}"
