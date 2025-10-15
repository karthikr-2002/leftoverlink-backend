from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import NotificationToken, NotificationSettings, NotificationLog
from .serializers import NotificationTokenSerializer, NotificationSettingsSerializer, NotificationLogSerializer
from .services import NotificationService


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def register_token(request):
    """Register or update user's Expo push notification token"""
    try:
        expo_push_token = request.data.get('expo_push_token')
        
        if not expo_push_token:
            return Response(
                {'error': 'expo_push_token is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get or create notification token
        token_obj, created = NotificationToken.objects.get_or_create(
            user=request.user,
            defaults={'expo_push_token': expo_push_token}
        )
        
        if not created:
            # Update existing token
            token_obj.expo_push_token = expo_push_token
            token_obj.is_active = True
            token_obj.save()

        # Create default notification settings if they don't exist
        NotificationSettings.objects.get_or_create(user=request.user)

        return Response({
            'message': 'Token registered successfully',
            'created': created
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def unregister_token(request):
    """Unregister user's Expo push notification token"""
    try:
        token_obj = get_object_or_404(NotificationToken, user=request.user)
        token_obj.is_active = False
        token_obj.save()
        
        return Response({
            'message': 'Token unregistered successfully'
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PUT'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def update_token(request):
    """Update user's Expo push notification token"""
    try:
        expo_push_token = request.data.get('expo_push_token')
        
        if not expo_push_token:
            return Response(
                {'error': 'expo_push_token is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        token_obj = get_object_or_404(NotificationToken, user=request.user)
        token_obj.expo_push_token = expo_push_token
        token_obj.is_active = True
        token_obj.save()

        return Response({
            'message': 'Token updated successfully'
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_settings(request):
    """Get user's notification settings"""
    try:
        settings, created = NotificationSettings.objects.get_or_create(user=request.user)
        serializer = NotificationSettingsSerializer(settings)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PUT'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def update_settings(request):
    """Update user's notification settings"""
    try:
        settings, created = NotificationSettings.objects.get_or_create(user=request.user)
        serializer = NotificationSettingsSerializer(settings, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_notification_history(request):
    """Get user's notification history"""
    try:
        notifications = NotificationLog.objects.filter(user=request.user)[:50]  # Last 50 notifications
        serializer = NotificationLogSerializer(notifications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def send_test_notification(request):
    """Send a test notification to the current user"""
    import asyncio
    
    try:
        notification_service = NotificationService()
        
        title = request.data.get('title', 'Test Notification')
        body = request.data.get('body', 'This is a test notification from LeftoverLink')
        
        # Run the async function in a new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success = loop.run_until_complete(
                notification_service.send_notification_to_user(
                    user=request.user,
                    title=title,
                    body=body,
                    notification_type='test',
                    data={'test': True}
                )
            )
        finally:
            loop.close()
        
        if success:
            return Response({
                'message': 'Test notification sent successfully'
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': 'Failed to send test notification'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
