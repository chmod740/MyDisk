from django.db import models

# Create your models here.
class User(models.Model):
    username = models.CharField(max_length=30)
    password = models.CharField(max_length=30)
    email = models.CharField(max_length=30, blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True, null=True)
    def __str__(self):
        return 'username: ' + self.username + ' password: ' + self.password
