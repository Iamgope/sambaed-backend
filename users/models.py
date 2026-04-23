from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class UserProfile(User):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    elo_rating = models.IntegerField(default=1200)
    total_debates = models.IntegerField(default=0)
    wins = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)
    
    # optional for later
    is_bot = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username
