from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from .models import User
import logging

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    """
    Register a new user with username, password, and user_type.
    """
    try:
        username = request.data.get('username')
        password = request.data.get('password')
        user_type = request.data.get('user_type', 'customer')
        email = request.data.get('email', '')
        first_name = request.data.get('first_name', '')
        last_name = request.data.get('last_name', '')
        
        # Validate required fields
        if not username or not password:
            return Response({
                'error': 'Username and password are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate user_type
        valid_user_types = ['customer', 'delivery']
        if user_type not in valid_user_types:
            return Response({
                'error': f'Invalid user_type. Must be one of: {", ".join(valid_user_types)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if username already exists
        if User.objects.filter(username=username).exists():
            return Response({
                'error': 'Username already exists'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create user
        user = User.objects.create_user(
            username=username,
            password=password,
            user_type=user_type,
            email=email,
            first_name=first_name,
            last_name=last_name
        )
        
        logger.info(f"New user registered: {username} ({user_type})")
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token
        
        return Response({
            'message': 'User registered successfully',
            'user': {
                'id': user.id,
                'username': user.username,
                'user_type': user.user_type,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'date_joined': user.date_joined,
            },
            'tokens': {
                'access': str(access_token),
                'refresh': str(refresh),
            }
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return Response({
            'error': 'Registration failed. Please try again.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def login_user(request):
    """
    Login user and return JWT tokens along with user information.
    """
    try:
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not username or not password:
            return Response({
                'error': 'Username and password are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Authenticate user
        user = authenticate(username=username, password=password)
        
        if user is None:
            return Response({
                'error': 'Invalid credentials'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token
        
        logger.info(f"User logged in: {username} ({user.user_type})")
        
        return Response({
            'message': 'Login successful',
            'user': {
                'id': user.id,
                'username': user.username,
                'user_type': user.user_type,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'date_joined': user.date_joined,
            },
            'tokens': {
                'access': str(access_token),
                'refresh': str(refresh),
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return Response({
            'error': 'Login failed. Please try again.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_user_profile(request):
    """
    Get current user's profile information.
    """
    try:
        user = request.user
        
        return Response({
            'user': {
                'id': user.id,
                'username': user.username,
                'user_type': user.user_type,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'date_joined': user.date_joined,
                'is_active': user.is_active,
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Get profile error: {str(e)}")
        return Response({
            'error': 'Failed to get user profile'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)