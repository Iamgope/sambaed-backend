from django.db import models

MAX_MESSAGE_LENGTH = 400


class DebateStatus(models.TextChoices):
    MATCHED = "MATCHED", "Matched"
    ONGOING = "ONGOING", "Ongoing"
    JUDGING = "JUDGING", "Judging"
    COMPLETED = "COMPLETED", "Completed"
    DISPUTED = "DISPUTED", "Disputed"
    ABANDONED = "ABANDONED", "Abandoned"


class RoundType(models.TextChoices):
    OPENING = "OPENING", "Opening"
    REBUTTAL = "REBUTTAL", "Rebuttal"
    CLOSING = "CLOSING", "Closing"


class MatchQueueStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    MATCHED = "MATCHED", "Matched"
    CANCELLED = "CANCELLED", "Cancelled"
    ABANDONED = "ABANDONED", "Abandoned"


class ProOrCon(models.TextChoices):
    PRO = "PRO", "Pro"
    CON = "CON", "Con"


class DebateViewerStatus(models.TextChoices):
    JOINED = "JOINED", "Joined"
    LEFT = "LEFT", "Left"
    DISCONNECTED = "DISCONNECTED", "Disconnected"
    KICKED = "KICKED", "Kicked"
    MUTED = "MUTED", "Muted"
    UNMUTED = "UNMUTED", "Unmuted"
    BANNED = "BANNED", "Banned"


class ViewerReactionType(models.TextChoices):
    LIKE = "LIKE", "Like"
    DISLIKE = "DISLIKE", "Dislike"
    LOVE = "LOVE", "Love"
    SUPPORT = "SUPPORT", "Support"
    OPPOSE = "OPPOSE", "Oppose"
    THUMBS_DOWN = "THUMBS_DOWN", "Thumbs Down"
    THUMBS_UP = "THUMBS_UP", "Thumbs Up"
