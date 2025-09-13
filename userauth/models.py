from django.db import models

from django.contrib.auth.models import AbstractUser

from django.contrib.auth.models import BaseUserManager

class UserManager(BaseUserManager):
    def create_user(self, username, password=None, user_type="customer", **extra_fields):
        if not username:
            raise ValueError("Users must have a username")
        user = self.model(username=username, user_type=user_type, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(username, password, user_type="admin", **extra_fields)

class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ("admin", "Admin"),
        ("customer", "Customer"),
        ("delivery", "Delivery Agent"),
    )
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default="customer")

    objects = UserManager()
