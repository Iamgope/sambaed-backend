from enum import Enum
from django.db import models


class DeviceType(models.TextChoices):
    ANDROID = 'ANDROID', 'Android'
    IOS = 'IOS', 'IOS'
    WEB = 'WEB', 'Web'


class FeedbackType(models.TextChoices):
    BUG = 'BUG', 'Bug Report'
    FEATURE_REQUEST = 'FEATURE_REQUEST', 'Feature Request'
    GENERAL = 'GENERAL', 'General'
    APP_REVIEW = 'APP_REVIEW', 'App Review'


class ApplicationConfigName(Enum):
    TEST = "TEST"
    DEBATE_JUDGE = "DEBATE_JUDGE"
