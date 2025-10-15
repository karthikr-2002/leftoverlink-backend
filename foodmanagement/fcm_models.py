from django.db import models
from userauth.models import User

class FCMDevice(models.Model):
    """Model to store FCM device tokens for push notifications"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fcm_devices')
    fcm_token = models.TextField(unique=True)
    device_type = models.CharField(max_length=10, choices=[('ios', 'iOS'), ('android', 'Android')], default='android')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "FCM Device"
        verbose_name_plural = "FCM Devices"

    def __str__(self):
        return f"{self.user.username} - {self.device_type} ({'Active' if self.is_active else 'Inactive'})"

