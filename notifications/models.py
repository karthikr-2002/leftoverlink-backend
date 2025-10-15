from django.db import models
from django.conf import settings


class NotificationToken(models.Model):
    """Model to store Expo push notification tokens for users"""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_token')
    expo_push_token = models.CharField(max_length=200, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notification_tokens'

    def __str__(self):
        return f"{self.user.username} - {self.expo_push_token[:20]}..."


class NotificationSettings(models.Model):
    """Model to store user notification preferences"""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_settings')
    
    # Order notifications
    order_confirmed = models.BooleanField(default=True)
    order_preparing = models.BooleanField(default=True)
    order_ready = models.BooleanField(default=True)
    order_delivered = models.BooleanField(default=True)
    order_cancelled = models.BooleanField(default=True)
    
    # Delivery notifications (for delivery agents)
    new_order_available = models.BooleanField(default=True)
    order_assigned = models.BooleanField(default=True)
    order_picked_up = models.BooleanField(default=True)
    
    # Promotional notifications
    new_food_available = models.BooleanField(default=True)
    promotional_offers = models.BooleanField(default=True)
    
    # General settings
    push_notifications_enabled = models.BooleanField(default=True)
    email_notifications_enabled = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notification_settings'

    def __str__(self):
        return f"Settings for {self.user.username}"


class NotificationLog(models.Model):
    """Model to log sent notifications for debugging and analytics"""
    NOTIFICATION_TYPES = (
        ('order_confirmed', 'Order Confirmed'),
        ('order_preparing', 'Order Preparing'),
        ('order_ready', 'Order Ready'),
        ('order_delivered', 'Order Delivered'),
        ('order_cancelled', 'Order Cancelled'),
        ('new_order_available', 'New Order Available'),
        ('order_assigned', 'Order Assigned'),
        ('order_picked_up', 'Order Picked Up'),
        ('new_food_available', 'New Food Available'),
        ('promotional_offer', 'Promotional Offer'),
    )

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_logs')
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    body = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    expo_push_token = models.CharField(max_length=200, blank=True)
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notification_logs'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.notification_type} - {self.status}"
