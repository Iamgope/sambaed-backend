from django.db import models


class DebateStatus(models.TextChoices):
    MATCHED = 'MATCHED', 'Matched'
    ONGOING = 'ONGOING', 'Ongoing'
    JUDGING = 'JUDGING', 'Judging'
    COMPLETED = 'COMPLETED', 'Completed'
    DISPUTED = 'DISPUTED', 'Disputed'


class RoundType(models.TextChoices):
    OPENING = 'OPENING', 'Opening'
    REBUTTAL = 'REBUTTAL', 'Rebuttal'
    CLOSING = 'CLOSING', 'Closing'


class MatchQueueStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    MATCHED = 'MATCHED', 'Matched'
    CANCELLED = 'CANCELLED', 'Cancelled'


class ProOrCon(models.TextChoices):
    PRO = 'PRO', 'Pro'
    CON = 'CON', 'Con'
    


MAX_MESSAGE_LENGTH = 400
