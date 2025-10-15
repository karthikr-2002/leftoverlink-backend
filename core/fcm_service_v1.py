"""
Firebase Cloud Messaging Service (v1 API) using Firebase Admin SDK
Modern implementation replacing legacy pyfcm
"""
import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings
from foodmanagement.fcm_models import FCMDevice
from userauth.models import User
import logging
import os

logger = logging.getLogger(__name__)

class FCMServiceV1:
    def __init__(self):
        """Initialize Firebase Admin SDK with service account"""
        try:
            # Check if already initialized
            if firebase_admin._apps:
                logger.info("Firebase Admin SDK already initialized")
                self.initialized = True
                return
            
            # Path to service account key file
            service_account_path = getattr(settings, 'FIREBASE_SERVICE_ACCOUNT_KEY', None)
            
            if service_account_path and os.path.exists(service_account_path):
                cred = credentials.Certificate(service_account_path)
                firebase_admin.initialize_app(cred)
                logger.info("✅ Firebase Admin SDK initialized successfully with FCM v1 API")
                self.initialized = True
            else:
                logger.warning("⚠️ Firebase service account key not found.")
                logger.warning("To enable FCM v1 API:")
                logger.warning("1. Go to Firebase Console → Project Settings → Service Accounts")
                logger.warning("2. Click 'Generate New Private Key'")
                logger.warning("3. Save as 'serviceAccountKey.json' in project root")
                logger.warning("4. Add path to settings.py: FIREBASE_SERVICE_ACCOUNT_KEY")
                self.initialized = False
                
        except Exception as e:
            logger.error(f"❌ Error initializing Firebase Admin SDK: {str(e)}")
            self.initialized = False

    def send_to_all_customers(self, title, body, data=None):
        """Send notification to all customer devices using FCM v1 API"""
        print("=" * 80)
        print("🔔 FCM v1 - send_to_all_customers() called")
        print(f"   Title: {title}")
        print(f"   Body: {body}")
        print(f"   Data: {data}")
        print("=" * 80)
        
        if not self.initialized:
            print("❌ FCM v1 service NOT initialized!")
            logger.warning("FCM v1 service not initialized. Cannot send push notification.")
            return None
        
        print("✅ FCM v1 service is initialized")
            
        try:
            print("📊 Querying database for customer devices...")
            customer_devices = FCMDevice.objects.filter(
                user__user_type='customer',
                is_active=True
            )
            
            device_count = customer_devices.count()
            print(f"📊 Found {device_count} active customer devices")
            
            if not customer_devices.exists():
                print("❌ No active customer devices found!")
                logger.warning("No active customer devices found for push notification")
                return None
            
            # Log device details
            for idx, device in enumerate(customer_devices, 1):
                print(f"   Device {idx}: User={device.user.username}, Token={device.fcm_token[:20]}..., Active={device.is_active}")
            
            tokens = [device.fcm_token for device in customer_devices]
            print(f"✅ Prepared {len(tokens)} tokens for sending")
            logger.info(f"Sending push notification to {len(tokens)} customer devices via FCM v1")
            
            # Send to each device individually (more reliable than multicast)
            print("📤 Sending notifications individually to each device...")
            
            success_count = 0
            failure_count = 0
            failed_tokens = []
            
            for idx, token in enumerate(tokens, 1):
                try:
                    print(f"📡 Sending to device {idx}/{len(tokens)}...")
                    
                    # Create individual message
                    message = messaging.Message(
                        notification=messaging.Notification(
                            title=title,
                            body=body,
                        ),
                        data=data or {},
                        token=token,
                        android=messaging.AndroidConfig(
                            priority='high',
                            notification=messaging.AndroidNotification(
                                sound='default',
                                channel_id='default',
                            ),
                        ),
                    )
                    
                    # Send individual message
                    response = messaging.send(message)
                    print(f"   ✅ Success! Message ID: {response}")
                    success_count += 1
                    
                except Exception as e:
                    print(f"   ❌ Failed! Error: {str(e)}")
                    failure_count += 1
                    failed_tokens.append(token)
                    logger.error(f"Failed to send to token {token[:20]}...: {str(e)}")
            
            print(f"\n📊 Final Results:")
            print(f"   ✅ Success: {success_count}")
            print(f"   ❌ Failure: {failure_count}")
            
            logger.info(f"✅ FCM v1 notifications sent")
            logger.info(f"   Success: {success_count}")
            logger.info(f"   Failure: {failure_count}")
            
            # Deactivate failed tokens
            if failed_tokens:
                print(f"   🔧 Deactivating {len(failed_tokens)} failed tokens...")
                FCMDevice.objects.filter(fcm_token__in=failed_tokens).update(is_active=False)
            
            result = {
                'success_count': success_count,
                'failure_count': failure_count,
                'total': len(tokens)
            }
            
            print("=" * 80)
            print(f"✅ FCM v1 send_to_all_customers() completed")
            print(f"   Result: {result}")
            print("=" * 80)
            
            return result
            
        except Exception as e:
            print("=" * 80)
            print(f"❌ EXCEPTION in send_to_all_customers()!")
            print(f"   Error: {str(e)}")
            print(f"   Type: {type(e).__name__}")
            import traceback
            print(f"   Traceback:")
            traceback.print_exc()
            print("=" * 80)
            logger.error(f"❌ Error sending push notification to all customers: {str(e)}")
            return None

    def send_to_user(self, user_id, title, body, data=None):
        """Send notification to specific user using FCM v1 API"""
        if not self.initialized:
            logger.warning("FCM v1 service not initialized. Cannot send push notification.")
            return None
            
        try:
            devices = FCMDevice.objects.filter(user_id=user_id, is_active=True)
            
            if not devices.exists():
                logger.warning(f"No active devices found for user {user_id}")
                return None
            
            tokens = [device.fcm_token for device in devices]
            logger.info(f"Sending push notification to user {user_id} via FCM v1")
            
            success_count = 0
            failure_count = 0
            
            for token in tokens:
                try:
                    message = messaging.Message(
                        notification=messaging.Notification(
                            title=title,
                            body=body,
                        ),
                        data=data or {},
                        token=token,
                        android=messaging.AndroidConfig(
                            priority='high',
                            notification=messaging.AndroidNotification(
                                sound='default',
                            ),
                        ),
                    )
                    
                    response = messaging.send(message)
                    success_count += 1
                    logger.info(f"✅ Sent to user {user_id}: {response}")
                    
                except Exception as e:
                    failure_count += 1
                    logger.error(f"Failed to send to user {user_id} token: {str(e)}")
            
            logger.info(f"✅ Push notification sent to user {user_id}")
            logger.info(f"   Success: {success_count}, Failure: {failure_count}")
            
            return {
                'success_count': success_count,
                'failure_count': failure_count
            }
            
        except Exception as e:
            logger.error(f"❌ Error sending push notification to user {user_id}: {str(e)}")
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
            logger.info(f"FCM device {action} for user {user_id}")
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
            logger.info(f"FCM device deactivated")
            return device
        except FCMDevice.DoesNotExist:
            logger.warning(f"FCM device not found for token")
            return None
        except Exception as e:
            logger.error(f"Error deactivating FCM device: {str(e)}")
            return None

# Create a global instance
fcm_service_v1 = FCMServiceV1()

