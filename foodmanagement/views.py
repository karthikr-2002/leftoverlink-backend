from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status, serializers
from rest_framework_simplejwt.authentication import JWTAuthentication
from core.helpers import (
    add_to_cart, remove_from_cart, get_user_cart, 
    calculate_cart_total, get_or_create_wallet, 
    process_wallet_payment, create_order_from_cart, 
    process_online_payment, get_or_create_delivery_profile,
    get_available_orders, assign_order_to_delivery_boy,
    update_delivery_status, collect_cod_payment,
    get_delivery_boy_earnings, submit_cod_payment,
    get_cod_submissions, get_pending_cod_submissions,
    verify_cod_submission, get_financial_reports
)
from core.fcm_service_v1 import fcm_service_v1
from foodmanagement.models import Food, Cart, OrderDetails, Wallet, WalletTransaction, DeliveryEarnings, DeliveryBoyProfile, CODSubmission
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from core.decimal_utils import to_decimal, to_float, convert_model_amounts_to_float


class FoodSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(max_digits=8, decimal_places=2, coerce_to_string=False)
    
    class Meta:
        model = Food
        fields = ['id', 'name', 'description', 'price', 'quantity', 'status', 'created_at', 'updated_at']

class CartSerializer(serializers.ModelSerializer):
    food_name = serializers.CharField(source='food.name', read_only=True)
    food_price = serializers.DecimalField(source='food.price', max_digits=8, decimal_places=2, read_only=True, coerce_to_string=False)
    total_price = serializers.SerializerMethodField()
    
    class Meta:
        model = Cart
        fields = ['id', 'food', 'food_name', 'food_price', 'quantity', 'total_price', 'added_at']
    
    def get_total_price(self, obj):
        return float(obj.quantity * obj.food.price)

# ==================== FOOD APIs ====================

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_foods_api(request):
    """Get list of all available foods with quantity > 0"""
    foods = Food.objects.filter(status='available', quantity__gt=0).order_by('-created_at')
    serializer = FoodSerializer(foods, many=True)
    return Response({
        "foods": serializer.data,
        "total_foods": foods.count()
    }, status=status.HTTP_200_OK)

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_food_by_id_api(request, food_id):
    """Get specific food details by ID"""
    try:
        food = Food.objects.get(id=food_id, status='available')
        serializer = FoodSerializer(food)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Food.DoesNotExist:
        return Response({"detail": "Food not found or not available"}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def add_to_cart_api(request, food_id):
    quantity = int(request.data.get('quantity', 1))
    try:
        add_to_cart(request.user, food_id, quantity)
        return Response({"detail": "Added to cart!"}, status=status.HTTP_200_OK)
    except ValidationError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def remove_from_cart_api(request, food_id):
    quantity = request.data.get('quantity')
    if quantity is not None:
        quantity = int(quantity)
    
    try:
        result = remove_from_cart(request.user, food_id, quantity)
        if result is None:
            return Response({"detail": "Item removed from cart!"}, status=status.HTTP_200_OK)
        else:
            return Response({"detail": f"Quantity reduced! Remaining: {result.quantity}"}, status=status.HTTP_200_OK)
    except ValidationError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_cart_api(request):
    """Get all items in the user's cart"""
    cart_items = get_user_cart(request.user)
    serializer = CartSerializer(cart_items, many=True)
    
    # Calculate total cart value
    total_value = sum(item.quantity * item.food.price for item in cart_items)
    
    return Response({
        "cart_items": serializer.data,
        "total_items": cart_items.count(),
        "total_value": float(total_value)
    }, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def clear_cart_api(request):
    """Clear all items from the user's cart"""
    cart_items = get_user_cart(request.user)
    count = cart_items.count()
    cart_items.delete()
    
    return Response({
        "detail": f"Cart cleared! Removed {count} items."
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def checkout_api(request):
    """Get checkout summary with total amount and payment options"""
    from decimal import Decimal
    from core.location_utils import calculate_delivery_charge, validate_coordinates
    
    # Get delivery type and location parameters
    delivery_type = request.GET.get('delivery_type', 'delivery')
    user_lat = request.GET.get('latitude')
    user_lon = request.GET.get('longitude')
    
    # Calculate delivery charge based on location if delivery type is 'delivery'
    if delivery_type == 'delivery':
        if user_lat and user_lon and validate_coordinates(user_lat, user_lon):
            delivery_charge = calculate_delivery_charge(user_lat, user_lon)
        else:
            # No delivery charge if no valid coordinates provided
            delivery_charge = Decimal('0')
    else:
        # No delivery charge for takeaway
        delivery_charge = Decimal('0')
    
    platform_fee_percentage = float(request.GET.get('platform_fee_percentage', 5))
    
    # Calculate cart total
    cart_summary = calculate_cart_total(request.user, float(delivery_charge), platform_fee_percentage)
    
    # Get user's wallet balance
    wallet = get_or_create_wallet(request.user)
    
    return Response({
        "cart_summary": cart_summary,
        "wallet_balance": float(wallet.balance),
        "delivery_charge": float(delivery_charge),
        "delivery_type": delivery_type,
        "payment_methods": [
            {"value": "wallet", "label": "Wallet"},
            {"value": "online", "label": "Online Payment"},
            {"value": "cod", "label": "Cash on Delivery"}
        ]
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def process_payment_api(request):
    """Process payment and create order"""
    from decimal import Decimal
    
    payment_method = request.data.get('payment_method')
    delivery_type = request.data.get('delivery_type', 'delivery')
    delivery_charge = float(request.data.get('delivery_charge', 0))
    platform_fee_percentage = float(request.data.get('platform_fee_percentage', 5))
    
    if payment_method not in ['wallet', 'online', 'cod']:
        return Response({"detail": "Invalid payment method"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Calculate total amount
        cart_summary = calculate_cart_total(request.user, delivery_charge, platform_fee_percentage)
        total_amount = cart_summary['total']
        
        # Create order from cart (starts as pending)
        order = create_order_from_cart(request.user, payment_method, delivery_charge, platform_fee_percentage, delivery_type)
        
        # Process payment based on method
        if payment_method == 'wallet':
            # Process wallet payment and update order status
            process_wallet_payment(request.user, total_amount, "Order payment")
            order.payment_status = 'paid'
            order.save()
            
        elif payment_method == 'online':
            # Process online payment
            payment_data = request.data.get('payment_data', {})
            payment_result = process_online_payment(request.user, total_amount, payment_data)
            
            if not payment_result['success']:
                order.payment_status = 'failed'
                order.save()
                return Response({"detail": "Payment failed"}, status=status.HTTP_400_BAD_REQUEST)
            else:
                order.payment_status = 'paid'
                order.save()
        
        # For COD, order remains pending until delivery boy collects payment
        
        return Response({
            "detail": "Order placed successfully!",
            "order_id": order.order_id,
            "total_amount": float(order.total_amount),
            "payment_method": payment_method,
            "payment_status": "paid" if payment_method in ['wallet', 'online'] else "pending"
        }, status=status.HTTP_201_CREATED)
        
    except ValidationError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_wallet_api(request):
    """Get user's wallet information"""
    wallet = get_or_create_wallet(request.user)
    
    return Response({
        "balance": float(wallet.balance),
        "created_at": wallet.created_at,
        "updated_at": wallet.updated_at
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def add_money_to_wallet_api(request):
    """Add money to user's wallet"""
    from decimal import Decimal
    
    amount = Decimal(str(request.data.get('amount', 0)))
    
    if amount <= 0:
        return Response({"detail": "Amount must be positive"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        wallet = get_or_create_wallet(request.user)
        wallet.add_money(amount)
        
        # Create transaction record
        WalletTransaction.objects.create(
            wallet=wallet,
            amount=amount,
            transaction_type='credit',
            description=request.data.get('description', 'Wallet top-up')
        )
        
        return Response({
            "detail": f"₹{amount} added to wallet successfully!",
            "new_balance": float(wallet.balance)
        }, status=status.HTTP_200_OK)
        
    except ValueError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_orders_api(request):
    """Get user's order history"""
    orders = OrderDetails.objects.filter(user=request.user).order_by('-ordered_at')
    
    order_data = []
    for order in orders:
        # Get all items in this order
        items = []
        for item in order.items.all():
            items.append({
                'food_name': item.food.name if item.food else 'Item no longer available',
                'quantity': item.quantity,
                'price': float(item.price),
                'total_price': float(item.total_price)
            })
        
        order_data.append({
            'order_id': order.order_id,
            'items': items,
            'subtotal': float(order.subtotal),
            'delivery_charge': float(order.delivery_charge),
            'platform_fee': float(order.platform_fee),
            'total_amount': float(order.total_amount),
            'payment_method': order.payment_method,
            'delivery_type': order.delivery_type,
            'payment_status': order.payment_status,
            'delivery_status': order.delivery_status,
            'ordered_at': order.ordered_at,
            'delivered_by': order.delivered_by.username if order.delivered_by else None
        })
    
    return Response({
        "orders": order_data,
        "total_orders": orders.count()
    }, status=status.HTTP_200_OK)


# ==================== DELIVERY BOY APIs ====================

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_available_orders_api(request):
    """Get all available orders for delivery boys"""
    # Check if user is a delivery boy
    if request.user.user_type != 'delivery':
        return Response({"detail": "Access denied. Only delivery boys can view this."}, status=status.HTTP_403_FORBIDDEN)
    
    orders = get_available_orders()
    
    order_data = []
    for order in orders:
        # Get all items in this order
        items = []
        for item in order.items.all():
            items.append({
                'food_name': item.food.name if item.food else 'Item no longer available',
                'quantity': item.quantity,
                'price': float(item.price),
                'total_price': float(item.total_price)
            })
        
        order_data.append({
            'id': order.id,
            'order_id': order.order_id,
            'customer_name': order.user.username,
            'items': items,
            'subtotal': float(order.subtotal),
            'total_amount': float(order.total_amount),
            'delivery_charge': float(order.delivery_charge),
            'platform_fee': float(order.platform_fee),
            'payment_method': order.payment_method,
            'delivery_type': order.delivery_type,
            'delivery_status': order.delivery_status,
            'ordered_at': order.ordered_at,
            'address': getattr(order.user, 'address', 'Address not provided')
        })
    
    return Response({
        "available_orders": order_data,
        "total_available": orders.count()
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def assign_order_api(request):
    """Assign an order to a delivery boy"""
    # Check if user is a delivery boy
    if request.user.user_type != 'delivery':
        return Response({"detail": "Access denied. Only delivery boys can assign orders."}, status=status.HTTP_403_FORBIDDEN)
    
    order_id = request.data.get('order_id')
    if not order_id:
        return Response({"detail": "Order ID is required"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        order = assign_order_to_delivery_boy(request.user, order_id)
        
        # Get all items in this order
        items = []
        for item in order.items.all():
            items.append({
                'food_name': item.food.name if item.food else 'Item no longer available',
                'quantity': item.quantity,
                'price': float(item.price),
                'total_price': float(item.total_price)
            })
        
        return Response({
            "detail": f"Order {order.order_id} assigned successfully!",
            "order": {
                'id': order.id,
                'order_id': order.order_id,
                'customer_name': order.user.username,
                'items': items,
                'subtotal': float(order.subtotal),
                'total_amount': float(order.total_amount),
                'delivery_charge': float(order.delivery_charge),
                'platform_fee': float(order.platform_fee),
                'payment_method': order.payment_method,
                'delivery_status': order.delivery_status,
                'assigned_at': order.assigned_at
            }
        }, status=status.HTTP_200_OK)
        
    except ValidationError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def update_delivery_status_api(request):
    """Update delivery status of an order"""
    # Check if user is a delivery boy
    if request.user.user_type != 'delivery':
        return Response({"detail": "Access denied. Only delivery boys can update status."}, status=status.HTTP_403_FORBIDDEN)
    
    order_id = request.data.get('order_id')
    new_status = request.data.get('status')
    
    if not order_id or not new_status:
        return Response({"detail": "Order ID and status are required"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        order = update_delivery_status(request.user, order_id, new_status)
        
        # Get order items
        order_items = order.items.all()
        items_data = []
        for item in order_items:
            items_data.append({
                'id': item.id,
                'food_name': item.food.name,
                'quantity': item.quantity,
                'price': to_float(item.price),
                'total_price': to_float(item.total_price)
            })
        
        return Response({
            "detail": f"Order status updated to {new_status}",
            "order": {
                'id': order.id,
                'order_id': order.order_id,
                'delivery_status': order.delivery_status,
                'delivery_type': order.delivery_type,
                'total_amount': to_float(order.total_amount),
                'delivery_charge': to_float(order.delivery_charge),
                'platform_fee': to_float(order.platform_fee),
                'payment_method': order.payment_method,
                'payment_status': order.payment_status,
                'cod_amount_collected': to_float(order.cod_amount_collected),
                'items': items_data,
                'updated_at': order.assigned_at
            }
        }, status=status.HTTP_200_OK)
        
    except ValidationError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def collect_cod_payment_api(request):
    """Collect COD payment from customer"""
    import logging
    from decimal import Decimal
    
    logger = logging.getLogger(__name__)
    
    # Check if user is a delivery boy
    if request.user.user_type != 'delivery':
        return Response({"detail": "Access denied. Only delivery boys can collect payments."}, status=status.HTTP_403_FORBIDDEN)
    
    order_id = request.data.get('order_id')
    raw_amount = request.data.get('amount_collected', 0)
    
    logger.info(f"API received - order_id: {order_id}, raw_amount: {raw_amount}, type: {type(raw_amount)}")
    
    # Use centralized utility instead of direct Decimal conversion
    amount_collected = to_decimal(raw_amount)
    logger.info(f"Amount converted using to_decimal: {amount_collected}, type: {type(amount_collected)}")
    
    if not order_id or amount_collected <= 0:
        return Response({"detail": "Order ID and valid amount are required"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        logger.info(f"Calling collect_cod_payment with order_id: {order_id}, amount: {amount_collected}")
        order = collect_cod_payment(request.user, order_id, amount_collected)
        
        return Response({
            "detail": f"COD payment of ₹{amount_collected} collected successfully!",
            "order": {
                'id': order.id,
                'order_id': order.order_id,
                'amount_collected': to_float(order.cod_amount_collected),
                'collected_at': order.cod_collected_at,
                'payment_status': order.payment_status
            }
        }, status=status.HTTP_200_OK)
        
    except ValidationError as e:
        logger.error(f"Validation error in collect_cod_payment_api: {e}")
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Unexpected error in collect_cod_payment_api: {e}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return Response({"detail": f"Error collecting COD: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_delivery_earnings_api(request):
    """Get delivery boy earnings"""
    # Check if user is a delivery boy
    if request.user.user_type != 'delivery':
        return Response({"detail": "Access denied. Only delivery boys can view earnings."}, status=status.HTTP_403_FORBIDDEN)
    
    earnings = get_delivery_boy_earnings(request.user)
    
    return Response(earnings, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_my_assigned_orders_api(request):
    """Get delivery boy's assigned/taken orders"""
    # Check if user is a delivery boy
    if request.user.user_type != 'delivery':
        return Response({"detail": "Access denied. Only delivery boys can view assigned orders."}, status=status.HTTP_403_FORBIDDEN)
    
    # Get all orders assigned to this delivery boy
    assigned_orders = OrderDetails.objects.filter(
        delivered_by=request.user,
        is_assigned=True
    ).order_by('-assigned_at')
    
    order_data = []
    for order in assigned_orders:
        # Check COD submission status
        cod_submission_status = None
        if order.payment_method == 'cod' and order.cod_amount_collected > 0:
            cod_submission = order.cod_submissions.filter(
                delivery_boy=request.user
            ).first()
            if cod_submission:
                cod_submission_status = cod_submission.status
        
        # Get all items in this order
        items = []
        for item in order.items.all():
            items.append({
                'food_name': item.food.name if item.food else 'Item no longer available',
                'quantity': item.quantity,
                'price': float(item.price),
                'total_price': float(item.total_price)
            })
        
        # Convert order data using centralized utilities
        order_dict = {
            'id': order.id,
            'order_id': order.order_id,
            'customer_name': order.user.username,
            'items': items,
            'subtotal': order.subtotal,
            'total_amount': order.total_amount,
            'delivery_charge': order.delivery_charge,
            'platform_fee': order.platform_fee,
            'payment_method': order.payment_method,
            'delivery_type': order.delivery_type,
            'payment_status': order.payment_status,
            'delivery_status': order.delivery_status,
            'ordered_at': order.ordered_at,
            'assigned_at': order.assigned_at,
            'cod_amount_collected': order.cod_amount_collected,
            'cod_collected_at': order.cod_collected_at,
            'cod_submission_status': cod_submission_status,
            'address': getattr(order.user, 'address', 'Address not provided'),
            'customer_phone': getattr(order.user, 'phone_number', 'Phone not provided')
        }
        
        # Convert amount fields to float for API response
        order_data.append(convert_model_amounts_to_float(order_dict))
    
    return Response({
        "assigned_orders": order_data,
        "total_assigned": assigned_orders.count(),
        "delivery_boy": request.user.username
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_delivery_profile_api(request):
    """Get delivery boy profile"""
    # Check if user is a delivery boy
    if request.user.user_type != 'delivery':
        return Response({"detail": "Access denied. Only delivery boys can view profile."}, status=status.HTTP_403_FORBIDDEN)
    
    profile = get_or_create_delivery_profile(request.user)
    
    return Response({
        'user': request.user.username,
        'is_available': profile.is_available,
        'total_earnings': float(profile.total_earnings),
        'total_deliveries': profile.total_deliveries,
        'rating': float(profile.rating),
        'phone_number': profile.phone_number,
        'vehicle_type': profile.vehicle_type,
        'license_number': profile.license_number,
        'created_at': profile.created_at,
        'updated_at': profile.updated_at
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def update_delivery_profile_api(request):
    """Update delivery boy profile"""
    # Check if user is a delivery boy
    if request.user.user_type != 'delivery':
        return Response({"detail": "Access denied. Only delivery boys can update profile."}, status=status.HTTP_403_FORBIDDEN)
    
    profile = get_or_create_delivery_profile(request.user)
    
    # Update available fields
    if 'is_available' in request.data:
        profile.is_available = request.data['is_available']
    if 'phone_number' in request.data:
        profile.phone_number = request.data['phone_number']
    if 'vehicle_type' in request.data:
        profile.vehicle_type = request.data['vehicle_type']
    if 'license_number' in request.data:
        profile.license_number = request.data['license_number']
    
    profile.save()
    
    return Response({
        "detail": "Profile updated successfully!",
        "profile": {
            'user': request.user.username,
            'is_available': profile.is_available,
            'phone_number': profile.phone_number,
            'vehicle_type': profile.vehicle_type,
            'license_number': profile.license_number
        }
    }, status=status.HTTP_200_OK)


# ==================== COD SUBMISSION APIs ====================

@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def submit_cod_payment_api(request):
    """Submit COD payment collected by delivery boy to company"""
    from decimal import Decimal
    
    # Check if user is a delivery boy
    if request.user.user_type != 'delivery':
        return Response({"detail": "Access denied. Only delivery boys can submit COD payments."}, status=status.HTTP_403_FORBIDDEN)
    
    order_id = request.data.get('order_id')
    amount_submitted = float(request.data.get('amount_submitted', 0))
    submission_method = request.data.get('submission_method', 'cash')
    notes = request.data.get('notes', '')
    
    if not order_id or amount_submitted <= 0:
        return Response({"detail": "Order ID and valid amount are required"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        submission = submit_cod_payment(
            request.user, 
            order_id, 
            amount_submitted, 
            submission_method, 
            notes
        )
        
        return Response({
            "detail": f"COD payment of ₹{amount_submitted} submitted successfully!",
            "submission": {
                'id': submission.id,
                'order_id': submission.order.order_id,
                'amount_submitted': float(submission.amount_submitted),
                'submission_method': submission.submission_method,
                'status': submission.status,
                'submitted_at': submission.submitted_at
            }
        }, status=status.HTTP_201_CREATED)
        
    except ValidationError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_my_cod_submissions_api(request):
    """Get delivery boy's COD submissions"""
    # Check if user is a delivery boy
    if request.user.user_type != 'delivery':
        return Response({"detail": "Access denied. Only delivery boys can view COD submissions."}, status=status.HTTP_403_FORBIDDEN)
    
    submissions = get_cod_submissions(request.user)
    
    return Response(submissions, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_pending_cod_submissions_api(request):
    """Get all pending COD submissions (Admin only)"""
    # Check if user is admin
    if not request.user.is_staff:
        return Response({"detail": "Access denied. Only admins can view pending submissions."}, status=status.HTTP_403_FORBIDDEN)
    
    submissions = get_pending_cod_submissions()
    
    submission_data = []
    for submission in submissions:
        submission_data.append({
            'id': submission.id,
            'delivery_boy': submission.delivery_boy.username,
            'order_id': submission.order.order_id,
            'amount_submitted': float(submission.amount_submitted),
            'submission_method': submission.submission_method,
            'submission_notes': submission.submission_notes,
            'status': submission.status,
            'submitted_at': submission.submitted_at,
            'created_at': submission.created_at
        })
    
    return Response({
        "pending_submissions": submission_data,
        "total_pending": submissions.count()
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def verify_cod_submission_api(request):
    """Verify a COD submission (Admin only)"""
    # Check if user is admin
    if not request.user.is_staff:
        return Response({"detail": "Access denied. Only admins can verify submissions."}, status=status.HTTP_403_FORBIDDEN)
    
    submission_id = request.data.get('submission_id')
    status = request.data.get('status')
    verification_notes = request.data.get('verification_notes', '')
    
    if not submission_id or not status:
        return Response({"detail": "Submission ID and status are required"}, status=status.HTTP_400_BAD_REQUEST)
    
    if status not in ['verified', 'rejected']:
        return Response({"detail": "Status must be 'verified' or 'rejected'"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        submission = verify_cod_submission(request.user, submission_id, status, verification_notes)
        
        return Response({
            "detail": f"COD submission {status} successfully!",
            "submission": {
                'id': submission.id,
                'delivery_boy': submission.delivery_boy.username,
                'order_id': submission.order.order_id,
                'amount_submitted': float(submission.amount_submitted),
                'status': submission.status,
                'verified_by': submission.verified_by.username if submission.verified_by else None,
                'verified_at': submission.verified_at,
                'verification_notes': submission.verification_notes
            }
        }, status=status.HTTP_200_OK)
        
    except ValidationError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ==================== ADMIN VERIFICATION & REPORTING APIs ====================

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_cod_verification_summary_api(request):
    """Get COD verification summary for admin dashboard"""
    # Check if user is admin
    if not request.user.is_staff:
        return Response({"detail": "Access denied. Only admins can view verification summary."}, status=status.HTTP_403_FORBIDDEN)
    
    from django.db.models import Sum, Count
    
    # Get all COD submissions
    all_submissions = CODSubmission.objects.all()
    
    # Calculate summary statistics
    total_submitted = all_submissions.aggregate(Sum('amount_submitted'))['amount_submitted__sum'] or 0
    verified_submissions = all_submissions.filter(status='verified')
    pending_submissions = all_submissions.filter(status='submitted')
    rejected_submissions = all_submissions.filter(status='rejected')
    
    total_verified = verified_submissions.aggregate(Sum('amount_submitted'))['amount_submitted__sum'] or 0
    total_pending = pending_submissions.aggregate(Sum('amount_submitted'))['amount_submitted__sum'] or 0
    total_rejected = rejected_submissions.aggregate(Sum('amount_submitted'))['amount_submitted__sum'] or 0
    
    # Get recent submissions
    recent_submissions = all_submissions.order_by('-submitted_at')[:10]
    
    recent_data = []
    for submission in recent_submissions:
        recent_data.append({
            'id': submission.id,
            'delivery_boy': submission.delivery_boy.username,
            'order_id': submission.order.order_id,
            'amount_submitted': float(submission.amount_submitted),
            'submission_method': submission.submission_method,
            'status': submission.status,
            'submitted_at': submission.submitted_at,
            'verified_at': submission.verified_at,
            'verified_by': submission.verified_by.username if submission.verified_by else None
        })
    
    return Response({
        'summary': {
            'total_submitted_amount': float(total_submitted),
            'total_verified_amount': float(total_verified),
            'total_pending_amount': float(total_pending),
            'total_rejected_amount': float(total_rejected),
            'verification_rate': float(total_verified / total_submitted * 100) if total_submitted > 0 else 0,
            'pending_count': pending_submissions.count(),
            'verified_count': verified_submissions.count(),
            'rejected_count': rejected_submissions.count()
        },
        'recent_submissions': recent_data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_financial_reports_api(request):
    """Get financial reports for admin dashboard"""
    # Check if user is admin
    if not request.user.is_staff:
        return Response({"detail": "Access denied. Only admins can view financial reports."}, status=status.HTTP_403_FORBIDDEN)
    
    from datetime import datetime, timedelta
    
    # Get date parameters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    period_type = request.GET.get('period_type', 'daily')
    
    # Default to last 30 days if no dates provided
    if not start_date or not end_date:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)
    
    try:
        reports = get_financial_reports(start_date, end_date, period_type)
        return Response(reports, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({"detail": f"Invalid date format: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_quick_reports_api(request):
    """Get quick financial reports (today, this week, this month, this year)"""
    # Check if user is admin
    if not request.user.is_staff:
        return Response({"detail": "Access denied. Only admins can view reports."}, status=status.HTTP_403_FORBIDDEN)
    
    from datetime import datetime, timedelta
    
    today = datetime.now().date()
    
    # Today's report
    today_report = get_financial_reports(today, today, 'daily')
    
    # This week's report
    week_start = today - timedelta(days=today.weekday())
    week_report = get_financial_reports(week_start, today, 'daily')
    
    # This month's report
    month_start = today.replace(day=1)
    month_report = get_financial_reports(month_start, today, 'daily')
    
    # This year's report
    year_start = today.replace(month=1, day=1)
    year_report = get_financial_reports(year_start, today, 'monthly')
    
    return Response({
        'today': today_report['summary'],
        'this_week': week_report['summary'],
        'this_month': month_report['summary'],
        'this_year': year_report['summary'],
        'daily_breakdown': week_report['daily_breakdown'][-7:],  # Last 7 days
        'top_delivery_boys': week_report['top_delivery_boys']
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_delivery_performance_api(request):
    """Get delivery boy performance report"""
    # Check if user is admin
    if not request.user.is_staff:
        return Response({"detail": "Access denied. Only admins can view performance reports."}, status=status.HTTP_403_FORBIDDEN)
    
    from django.db.models import Sum, Count, Avg, Q
    from datetime import datetime, timedelta
    
    # Get date range
    days = int(request.GET.get('days', 30))
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    
    # Get delivery boy performance
    performance = DeliveryEarnings.objects.filter(
        created_at__date__range=[start_date, end_date],
        earning_type='delivery_charge'
    ).values('delivery_boy__username').annotate(
        total_earnings=Sum('amount'),
        delivery_count=Count('order'),
        avg_earning_per_delivery=Avg('amount')
    ).order_by('-total_earnings')
    
    # Get COD submission performance
    cod_performance = CODSubmission.objects.filter(
        created_at__date__range=[start_date, end_date]
    ).values('delivery_boy__username').annotate(
        total_submitted=Sum('amount_submitted'),
        submission_count=Count('id'),
        verified_count=Count('id', filter=Q(status='verified')),
        pending_count=Count('id', filter=Q(status='submitted'))
    ).order_by('-total_submitted')
    
    performance_data = []
    for perf in performance:
        cod_data = next((item for item in cod_performance if item['delivery_boy__username'] == perf['delivery_boy__username']), {})
        
        performance_data.append({
            'delivery_boy': perf['delivery_boy__username'],
            'total_earnings': float(perf['total_earnings']),
            'delivery_count': perf['delivery_count'],
            'avg_earning_per_delivery': float(perf['avg_earning_per_delivery']),
            'total_cod_submitted': float(cod_data.get('total_submitted', 0)),
            'submission_count': cod_data.get('submission_count', 0),
            'verified_count': cod_data.get('verified_count', 0),
            'pending_count': cod_data.get('pending_count', 0),
            'verification_rate': float(cod_data.get('verified_count', 0) / cod_data.get('submission_count', 1) * 100) if cod_data.get('submission_count', 0) > 0 else 0
        })
    
    return Response({
        'period': {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'days': days
        },
        'performance_data': performance_data
    }, status=status.HTTP_200_OK)


# ==================== EXPO PUSH NOTIFICATION APIs ====================

@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def register_expo_push_token_api(request):
    """Register Expo push token for push notifications"""
    expo_push_token = request.data.get('expo_push_token')
    device_type = request.data.get('device_type', 'android')
    
    if not expo_push_token:
        return Response({"detail": "Expo push token is required"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        device = fcm_service_v1.register_device(
            user_id=request.user.id,
            fcm_token=expo_push_token,
            device_type=device_type
        )
        
        if device:
            return Response({
                "detail": "Expo push token registered successfully",
                "device_id": device.id
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                "detail": "Failed to register token"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        return Response({
            "detail": f"Error registering token: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def unregister_expo_push_token_api(request):
    """Unregister Expo push token"""
    expo_push_token = request.data.get('expo_push_token')
    
    if not expo_push_token:
        return Response({"detail": "Expo push token is required"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        device = fcm_service_v1.deactivate_device(expo_push_token)
        
        return Response({
            "detail": "Expo push token unregistered successfully"
        }, status=status.HTTP_200_OK)
        
    except FCMDevice.DoesNotExist:
        return Response({
            "detail": "Expo push token not found"
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            "detail": f"Error unregistering token: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== FCM PUSH NOTIFICATION APIs ====================

@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def register_fcm_token_api(request):
    """Register FCM token for push notifications"""
    fcm_token = request.data.get('fcm_token')
    device_type = request.data.get('device_type', 'android')
    
    if not fcm_token:
        return Response({"detail": "FCM token is required"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        device = fcm_service_v1.register_device(
            user_id=request.user.id,
            fcm_token=fcm_token,
            device_type=device_type
        )
        
        if device:
            return Response({
                "detail": "FCM token registered successfully",
                "device_id": device.id
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                "detail": "Failed to register FCM token"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        return Response({
            "detail": f"Error registering token: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def unregister_fcm_token_api(request):
    """Unregister FCM token"""
    fcm_token = request.data.get('fcm_token')
    
    if not fcm_token:
        return Response({"detail": "FCM token is required"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        device = fcm_service_v1.deactivate_device(fcm_token)
        
        if device:
            return Response({
                "detail": "FCM token unregistered successfully"
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                "detail": "FCM token not found"
            }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        return Response({
            "detail": f"Error unregistering token: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def send_local_notification_api(request):
    """Send local notification to current user (for testing with Expo Go)"""
    title = request.data.get('title', 'Test Notification')
    body = request.data.get('body', 'This is a test notification from LeftoverLink')
    
    try:
        # For Expo Go, we'll just return success and let the frontend handle it
        return Response({
            "detail": "Local notification triggered successfully",
            "title": title,
            "body": body,
            "data": {
                "type": "test",
                "timestamp": str(timezone.now())
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            "detail": f"Error triggering local notification: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def send_test_notification_api(request):
    """Send test notification to current user (for testing purposes)"""
    if not request.user.is_staff:
        return Response({
            "detail": "Access denied. Only staff can send test notifications."
        }, status=status.HTTP_403_FORBIDDEN)
    
    title = request.data.get('title', 'Test Notification')
    body = request.data.get('body', 'This is a test notification from LeftoverLink')
    
    try:
        result = fcm_service_v1.send_to_user(
            user_id=request.user.id,
            title=title,
            body=body,
            data={'type': 'test', 'timestamp': str(timezone.now())}
        )
        
        if result:
            return Response({
                "detail": "Test notification sent successfully",
                "result": result
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                "detail": "Failed to send test notification"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        return Response({
            "detail": f"Error sending test notification: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

