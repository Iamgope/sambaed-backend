from django.db import models
from django.contrib.auth.models import User

from users.constants import DeviceType

# Create your models here.
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    elo_rating = models.IntegerField(default=1200)
    total_debates = models.IntegerField(default=0)
    wins = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)
    
    # optional for later
    is_bot = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username


class UserDevice(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    device_id = models.CharField(max_length=255, unique=True)
    device_type = models.CharField(max_length=255, choices=DeviceType.choices)
    device_token = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
