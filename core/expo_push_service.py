"""
Expo Push Notification Service
"""
import requests
import json
from django.conf import settings
from foodmanagement.fcm_models import FCMDevice
from userauth.models import User
import logging

logger = logging.getLogger(__name__)

class ExpoPushService:
    def __init__(self):
        self.expo_push_url = "https://exp.host/--/api/v2/push/send"
        
    def send_to_all_customers(self, title, body, data=None):
        """Send notification to all customer devices"""
        try:
            customer_devices = FCMDevice.objects.filter(
                user__user_type='customer',
                is_active=True
            )
            
            if not customer_devices.exists():
                logger.warning("No active customer devices found for push notification")
                return None
            
            # Prepare messages for all devices
            messages = []
            for device in customer_devices:
                message = {
                    "to": device.fcm_token,  # Using fcm_token field to store expo token
                    "title": title,
                    "body": body,
                    "data": data or {}
                }
                messages.append(message)
            
            logger.info(f"Sending push notification to {len(messages)} customer devices")
            
            # Send notifications in batches (Expo allows up to 100 messages per request)
            batch_size = 100
            results = []
            
            for i in range(0, len(messages), batch_size):
                batch = messages[i:i + batch_size]
                result = self._send_batch(batch)
                if result:
                    results.append(result)
            
            logger.info(f"Push notification results: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Error sending push notification to all customers: {str(e)}")
            return None

    def send_to_user(self, user_id, title, body, data=None):
        """Send notification to specific user"""
        try:
            devices = FCMDevice.objects.filter(user_id=user_id, is_active=True)
            
            if not devices.exists():
                logger.warning(f"No active devices found for user {user_id}")
                return None
            
            # Prepare messages for user's devices
            messages = []
            for device in devices:
                message = {
                    "to": device.fcm_token,  # Using fcm_token field to store expo token
                    "title": title,
                    "body": body,
                    "data": data or {}
                }
                messages.append(message)
            
            logger.info(f"Sending push notification to user {user_id}: {len(messages)} devices")
            
            result = self._send_batch(messages)
            logger.info(f"Push notification sent to user {user_id}: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error sending push notification to user {user_id}: {str(e)}")
            return None

    def _send_batch(self, messages):
        """Send a batch of messages to Expo push service"""
        try:
            headers = {
                'Accept': 'application/json',
                'Accept-encoding': 'gzip, deflate',
                'Content-Type': 'application/json',
            }
            
            response = requests.post(
                self.expo_push_url,
                data=json.dumps(messages),
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Expo push response: {result}")
                return result
            else:
                logger.error(f"Expo push error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error sending batch to Expo: {str(e)}")
            return None

# Create a global instance
expo_push_service = ExpoPushService()

