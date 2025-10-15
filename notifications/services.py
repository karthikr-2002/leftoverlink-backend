import requests
import json
from django.conf import settings
from .models import NotificationToken, NotificationSettings, NotificationLog


class NotificationService:
    """Service class for handling push notifications"""
    
    EXPO_PUSH_URL = 'https://exp.host/--/api/v2/push/send'
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'Accept-encoding': 'gzip, deflate',
            'Content-Type': 'application/json',
        })

    async def send_notification_to_user(self, user, title, body, notification_type='general', data=None):
        """Send a push notification to a specific user"""
        try:
            # Get user's notification token
            token_obj = NotificationToken.objects.filter(
                user=user, 
                is_active=True
            ).first()
            
            if not token_obj:
                print(f"No active notification token found for user {user.username}")
                return False

            # Check if user has notifications enabled
            settings_obj = NotificationSettings.objects.filter(user=user).first()
            if settings_obj and not settings_obj.push_notifications_enabled:
                print(f"Push notifications disabled for user {user.username}")
                return False

            # Check specific notification type setting
            if not self._is_notification_type_enabled(settings_obj, notification_type):
                print(f"Notification type {notification_type} disabled for user {user.username}")
                return False

            # Create notification log entry
            log_entry = NotificationLog.objects.create(
                user=user,
                notification_type=notification_type,
                title=title,
                body=body,
                data=data or {},
                expo_push_token=token_obj.expo_push_token,
                status='pending'
            )

            # Prepare notification payload
            payload = {
                'to': token_obj.expo_push_token,
                'title': title,
                'body': body,
                'data': data or {},
                'sound': 'default',
                'badge': 1,
            }

            # Send notification
            response = self.session.post(self.EXPO_PUSH_URL, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('data', [{}])[0].get('status') == 'ok':
                    log_entry.status = 'sent'
                    log_entry.save()
                    print(f"Notification sent successfully to {user.username}")
                    return True
                else:
                    error_message = result.get('data', [{}])[0].get('message', 'Unknown error')
                    log_entry.status = 'failed'
                    log_entry.error_message = error_message
                    log_entry.save()
                    print(f"Failed to send notification to {user.username}: {error_message}")
                    return False
            else:
                log_entry.status = 'failed'
                log_entry.error_message = f"HTTP {response.status_code}: {response.text}"
                log_entry.save()
                print(f"HTTP error sending notification to {user.username}: {response.status_code}")
                return False

        except Exception as e:
            print(f"Error sending notification to {user.username}: {str(e)}")
            if 'log_entry' in locals():
                log_entry.status = 'failed'
                log_entry.error_message = str(e)
                log_entry.save()
            return False

    def _is_notification_type_enabled(self, settings_obj, notification_type):
        """Check if a specific notification type is enabled for the user"""
        if not settings_obj:
            return True  # Default to enabled if no settings found

        notification_type_mapping = {
            'order_confirmed': settings_obj.order_confirmed,
            'order_preparing': settings_obj.order_preparing,
            'order_ready': settings_obj.order_ready,
            'order_delivered': settings_obj.order_delivered,
            'order_cancelled': settings_obj.order_cancelled,
            'new_order_available': settings_obj.new_order_available,
            'order_assigned': settings_obj.order_assigned,
            'order_picked_up': settings_obj.order_picked_up,
            'new_food_available': settings_obj.new_food_available,
            'promotional_offer': settings_obj.promotional_offers,
        }

        return notification_type_mapping.get(notification_type, True)

    async def send_notification_to_multiple_users(self, users, title, body, notification_type='general', data=None):
        """Send a push notification to multiple users"""
        results = []
        for user in users:
            result = await self.send_notification_to_user(user, title, body, notification_type, data)
            results.append({'user': user.username, 'success': result})
        return results

    async def send_order_notification(self, order, notification_type, custom_title=None, custom_body=None):
        """Send order-related notification"""
        user = order.user
        
        # Default messages based on notification type
        default_messages = {
            'order_confirmed': {
                'title': 'Order Confirmed! 🎉',
                'body': f'Your order #{order.order_id} has been confirmed and is being prepared.'
            },
            'order_preparing': {
                'title': 'Order Being Prepared 👨‍🍳',
                'body': f'Your order #{order.order_id} is now being prepared in the kitchen.'
            },
            'order_ready': {
                'title': 'Order Ready! 🍽️',
                'body': f'Your order #{order.order_id} is ready for {"pickup" if order.delivery_type == "takeaway" else "delivery"}.'
            },
            'order_delivered': {
                'title': 'Order Delivered! ✅',
                'body': f'Your order #{order.order_id} has been delivered. Enjoy your meal!'
            },
            'order_cancelled': {
                'title': 'Order Cancelled ❌',
                'body': f'Your order #{order.order_id} has been cancelled.'
            }
        }

        message = default_messages.get(notification_type, {
            'title': 'Order Update',
            'body': f'Update for your order #{order.order_id}'
        })

        title = custom_title or message['title']
        body = custom_body or message['body']

        data = {
            'order_id': order.order_id,
            'order_type': order.delivery_type,
            'total_amount': str(order.total_amount),
        }

        return await self.send_notification_to_user(user, title, body, notification_type, data)

    async def send_delivery_notification(self, order, notification_type, custom_title=None, custom_body=None):
        """Send delivery-related notification to delivery agents"""
        # Get all active delivery agents
        User = settings.AUTH_USER_MODEL
        delivery_agents = User.objects.filter(
            user_type='delivery',
            notification_token__is_active=True
        )

        # Default messages for delivery agents
        default_messages = {
            'new_order_available': {
                'title': 'New Order Available! 📦',
                'body': f'New order #{order.order_id} is available for delivery.'
            },
            'order_assigned': {
                'title': 'Order Assigned! 🚚',
                'body': f'Order #{order.order_id} has been assigned to you.'
            },
            'order_picked_up': {
                'title': 'Order Picked Up! 📦',
                'body': f'Order #{order.order_id} has been picked up and is ready for delivery.'
            }
        }

        message = default_messages.get(notification_type, {
            'title': 'Delivery Update',
            'body': f'Update for order #{order.order_id}'
        })

        title = custom_title or message['title']
        body = custom_body or message['body']

        data = {
            'order_id': order.order_id,
            'customer_name': order.user.username,
            'delivery_type': order.delivery_type,
            'total_amount': str(order.total_amount),
        }

        if notification_type == 'new_order_available':
            # Send to all delivery agents
            return await self.send_notification_to_multiple_users(
                delivery_agents, title, body, notification_type, data
            )
        else:
            # Send to assigned delivery agent
            if order.delivered_by:
                return await self.send_notification_to_user(
                    order.delivered_by, title, body, notification_type, data
                )
            return False

    async def send_promotional_notification(self, users, title, body, data=None):
        """Send promotional notification to multiple users"""
        return await self.send_notification_to_multiple_users(
            users, title, body, 'promotional_offer', data
        )
