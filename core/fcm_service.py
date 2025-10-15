"""
Firebase Cloud Messaging Service for Push Notifications
"""
from pyfcm import FCMNotification
from django.conf import settings
from foodmanagement.fcm_models import FCMDevice
from userauth.models import User
import logging

logger = logging.getLogger(__name__)

class FCMService:
    def __init__(self):
        # You'll need to add your FCM server key to settings.py
        fcm_server_key = getattr(settings, 'FCM_SERVER_KEY', None)
        if fcm_server_key and fcm_server_key not in ["YOUR_FCM_SERVER_KEY_HERE", "YOUR_ACTUAL_FCM_SERVER_KEY_HERE"]:
            try:
                self.push_service = FCMNotification(api_key=fcm_server_key)
                logger.info("FCM service initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing FCM service: {str(e)}")
                self.push_service = None
        else:
            self.push_service = None
            logger.warning("FCM_SERVER_KEY not configured. Push notifications will be disabled.")
            logger.info("To enable FCM: Add your Firebase server key to settings.py")
            logger.info("You can find it in Firebase Console → Project Settings → Cloud Messaging")

    def send_to_all_customers(self, title, body, data=None):
        """Send notification to all customer devices"""
        if not self.push_service:
            logger.warning("FCM service not initialized. Cannot send push notification.")
            return None
            
        try:
            customer_devices = FCMDevice.objects.filter(
                user__user_type='customer',
                is_active=True
            )
            
            if not customer_devices.exists():
                logger.warning("No active customer devices found for push notification")
                return None
            
            tokens = [device.fcm_token for device in customer_devices]
            logger.info(f"Sending push notification to {len(tokens)} customer devices")
            
            result = self.push_service.notify_multiple_devices(
                registration_ids=tokens,
                message_title=title,
                message_body=body,
                data_message=data
            )
            
            logger.info(f"Push notification result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error sending push notification to all customers: {str(e)}")
            return None

    def send_to_user(self, user_id, title, body, data=None):
        """Send notification to specific user"""
        if not self.push_service:
            logger.warning("FCM service not initialized. Cannot send push notification.")
            return None
            
        try:
            devices = FCMDevice.objects.filter(user_id=user_id, is_active=True)
            tokens = [device.fcm_token for device in devices]
            
            if not tokens:
                logger.warning(f"No active devices found for user {user_id}")
                return None
            
            result = self.push_service.notify_multiple_devices(
                registration_ids=tokens,
                message_title=title,
                message_body=body,
                data_message=data
            )
            
            logger.info(f"Push notification sent to user {user_id}: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error sending push notification to user {user_id}: {str(e)}")
            return None

    def register_device(self, user_id, fcm_token, device_type='android'):
        """Register or update FCM device"""
        try:
            device, created = FCMDevice.objects.update_or_create(
                fcm_token=fcm_token,
                defaults={
                    'user_id': user_id,
                    'device_type': device_type,
                    'is_active': True
                }
            )
            
            action = "created" if created else "updated"
            logger.info(f"FCM device {action} for user {user_id}: {device}")
            return device
            
        except Exception as e:
            logger.error(f"Error registering FCM device for user {user_id}: {str(e)}")
            return None

    def deactivate_device(self, fcm_token):
        """Deactivate FCM device"""
        try:
            device = FCMDevice.objects.get(fcm_token=fcm_token)
            device.is_active = False
            device.save()
            logger.info(f"FCM device deactivated: {device}")
            return device
        except FCMDevice.DoesNotExist:
            logger.warning(f"FCM device not found for token: {fcm_token}")
            return None
        except Exception as e:
            logger.error(f"Error deactivating FCM device: {str(e)}")
            return None

# Create a global instance
fcm_service = FCMService()
