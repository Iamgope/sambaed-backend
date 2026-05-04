from django.db import models

class DeviceType(models.TextChoices):
    ANDROID = 'ANDROID', 'Android'
    IOS = 'IOS', 'IOS'
    WEB = 'WEB', 'Web'
