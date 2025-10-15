from django.core.exceptions import ValidationError
from django.db import transaction
from foodmanagement.models import Food, Cart, OrderDetails, Wallet, WalletTransaction, DeliveryEarnings, DeliveryBoyProfile, CODSubmission
from core.decimal_utils import to_decimal, to_float, safe_add, safe_subtract, safe_multiply, is_amount_equal


def add_to_cart(user, food_id, quantity):
    """
    Adds the specified quantity of food to the user's cart.
    Raises ValidationError if not enough stock is available.
    """
    try:
        food = Food.objects.get(id=food_id)
    except Food.DoesNotExist:
        raise ValidationError("Food item does not exist.")

    if quantity > food.quantity:
        raise ValidationError(f"Only {food.quantity} items available.")

    # Add to cart (or update if already exists)
    cart_item, created = Cart.objects.get_or_create(user=user, food=food)
    if not created:
        cart_item.quantity += quantity
    else:
        cart_item.quantity = quantity
    cart_item.save()

    return cart_item


def remove_from_cart(user, food_id, quantity=None):
    """
    Removes the specified quantity of food from the user's cart.
    If quantity is None, removes the entire item from cart.
    Raises ValidationError if food item doesn't exist in cart.
    """
    try:
        food = Food.objects.get(id=food_id)
    except Food.DoesNotExist:
        raise ValidationError("Food item does not exist.")

    try:
        cart_item = Cart.objects.get(user=user, food=food)
    except Cart.DoesNotExist:
        raise ValidationError("Food item not found in cart.")

    if quantity is None:
        # Remove entire item from cart
        cart_item.delete()
        return None
    else:
        # Reduce quantity
        if quantity >= cart_item.quantity:
            # Remove entire item if quantity to remove is >= current quantity
            cart_item.delete()
            return None
        else:
            cart_item.quantity -= quantity
            cart_item.save()
            return cart_item


def get_user_cart(user):
    """
    Gets all cart items for a user.
    Returns a queryset of cart items.
    """
    return Cart.objects.filter(user=user)


def get_or_create_wallet(user):
    """
    Gets or creates a wallet for the user.
    Returns the wallet instance.
    """
    wallet, created = Wallet.objects.get_or_create(user=user)
    return wallet


def calculate_cart_total(user, delivery_charge=0, platform_fee_percentage=5):
    """
    Calculates the total amount for all items in user's cart.
    Returns a dictionary with subtotal, delivery_charge, platform_fee, and total.
    """
    cart_items = get_user_cart(user)
    subtotal = sum(safe_multiply(item.quantity, item.food.price) for item in cart_items)
    platform_fee = safe_multiply(subtotal, to_decimal(platform_fee_percentage)) / to_decimal(100)
    total = safe_add(subtotal, to_decimal(delivery_charge), platform_fee)

    return {
        "subtotal": to_float(subtotal),
        "delivery_charge": to_float(delivery_charge),
        "platform_fee": to_float(platform_fee),
        "total": to_float(total),
        "item_count": cart_items.count(),
    }


@transaction.atomic
def process_wallet_payment(user, amount, description="Order payment"):
    """
    Process payment using wallet.
    Returns True if successful, raises ValidationError if insufficient balance.
    """
    wallet = get_or_create_wallet(user)
    amount_decimal = to_decimal(amount)

    if wallet.balance < amount_decimal:
        raise ValidationError("Insufficient wallet balance")

    # Deduct amount from wallet
    wallet.deduct_money(amount_decimal)

    # Create transaction record
    WalletTransaction.objects.create(
        wallet=wallet, amount=amount_decimal, transaction_type="debit", description=description
    )

    return True


@transaction.atomic
def create_order_from_cart(user, payment_method, delivery_charge=0, platform_fee_percentage=5, delivery_type='delivery'):
    """
    Creates a single OrderDetails with multiple OrderItems from cart items and clears the cart.
    Returns the created order.
    """
    from foodmanagement.models import OrderItem
    
    cart_items = get_user_cart(user)

    if not cart_items.exists():
        raise ValidationError("Cart is empty")

    # Calculate totals
    subtotal = sum(safe_multiply(item.quantity, item.food.price) for item in cart_items)
    platform_fee = safe_multiply(subtotal, to_decimal(platform_fee_percentage)) / to_decimal(100)
    total_amount = safe_add(subtotal, to_decimal(delivery_charge), platform_fee)

    # Check availability for all items first
    for cart_item in cart_items:
        if cart_item.food.quantity < cart_item.quantity:
            raise ValidationError(f"Insufficient quantity for {cart_item.food.name}. Available: {cart_item.food.quantity}, Requested: {cart_item.quantity}")

    # Create the main order
    order = OrderDetails.objects.create(
        user=user,
        subtotal=subtotal,
        delivery_charge=to_decimal(delivery_charge),
        platform_fee=platform_fee,
        total_amount=total_amount,
        payment_method=payment_method,
        delivery_type=delivery_type,
        payment_status="pending",  # All orders start as pending, COD gets paid when collected
    )

    # Create order items and reduce food quantities
    for cart_item in cart_items:
        # Create order item
        OrderItem.objects.create(
            order=order,
            food=cart_item.food,
            quantity=cart_item.quantity,
            price=cart_item.food.price,
        )
        
        # Reduce food quantity
        cart_item.food.quantity -= cart_item.quantity
        cart_item.food.save()

    # Clear cart
    cart_items.delete()
    
    return order


def process_online_payment(user, amount, payment_data):
    """
    Process online payment (placeholder for integration with payment gateway).
    In a real implementation, this would integrate with payment providers like Stripe, Razorpay, etc.
    """
    # This is a placeholder - in real implementation, integrate with payment gateway
    # For now, we'll simulate a successful payment
    return {
        "success": True,
        "transaction_id": f"TXN_{user.id}_{amount}_{payment_data.get('timestamp', 'now')}",
        "message": "Payment processed successfully",
    }


def get_or_create_delivery_profile(user):
    """
    Gets or creates a delivery profile for the user.
    Returns the delivery profile instance.
    """
    profile, created = DeliveryBoyProfile.objects.get_or_create(user=user)
    return profile


def get_available_orders():
    """
    Gets all orders that are pending and not assigned to any delivery boy.
    Returns a queryset of available orders.
    """
    return OrderDetails.objects.filter(
        delivery_status='pending',
        is_assigned=False
    ).order_by('ordered_at')


@transaction.atomic
def assign_order_to_delivery_boy(delivery_boy, order_id):
    """
    Assigns an order to a delivery boy.
    Returns the order if successful, raises ValidationError if not available.
    """
    from django.utils import timezone
    
    try:
        order = OrderDetails.objects.get(id=order_id)
    except OrderDetails.DoesNotExist:
        raise ValidationError("Order does not exist.")
    
    if order.is_assigned:
        raise ValidationError("Order is already assigned to another delivery boy.")
    
    if order.delivery_status != 'pending':
        raise ValidationError("Order is not available for delivery.")
    
    # Assign order to delivery boy
    order.delivered_by = delivery_boy
    order.is_assigned = True
    order.assigned_at = timezone.now()
    order.delivery_status = 'confirmed'
    order.save()
    
    return order


@transaction.atomic
def update_delivery_status(delivery_boy, order_id, new_status):
    """
    Updates the delivery status of an order.
    Returns the updated order.
    """
    try:
        order = OrderDetails.objects.get(id=order_id, delivered_by=delivery_boy)
    except OrderDetails.DoesNotExist:
        raise ValidationError("Order not found or not assigned to you.")
    
    valid_statuses = ['confirmed', 'preparing', 'out_for_delivery', 'delivered', 'cancelled']
    if new_status not in valid_statuses:
        raise ValidationError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
    
    order.delivery_status = new_status
    order.save()
    
    return order


@transaction.atomic
def collect_cod_payment(delivery_boy, order_id, amount_collected):
    """
    Records COD payment collection by delivery boy.
    Creates delivery earnings record.
    """
    import logging
    from django.utils import timezone
    
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Starting COD collection for order {order_id}, amount: {amount_collected}, type: {type(amount_collected)}")
        
        order = OrderDetails.objects.get(
            id=order_id, 
            delivered_by=delivery_boy,
            payment_method='cod'
        )
        logger.info(f"Order found: {order.order_id}")
    except OrderDetails.DoesNotExist:
        logger.error(f"Order {order_id} not found for delivery boy {delivery_boy.username}")
        raise ValidationError("Order not found or not assigned to you.")
    
    if order.cod_amount_collected > 0:
        logger.warning(f"COD already collected for order {order.order_id}")
        raise ValidationError("COD amount already collected for this order.")
    
    # Convert amount_collected to Decimal using centralized utility
    amount_collected_decimal = to_decimal(amount_collected)
    logger.info(f"Amount converted to Decimal: {amount_collected_decimal}, type: {type(amount_collected_decimal)}")
    
    # The expected amount is just the total_amount (which already includes delivery charge and platform fee)
    expected_amount = order.total_amount
    logger.info(f"Expected amount: {expected_amount}, type: {type(expected_amount)}")
    
    # Check amount match with tolerance for floating point precision
    if not is_amount_equal(amount_collected_decimal, expected_amount):
        logger.error(f"Amount mismatch. Expected: {expected_amount}, Received: {amount_collected_decimal}")
        raise ValidationError(f"Amount mismatch. Expected: ${expected_amount}, Received: ${amount_collected_decimal}")
    
    # Update order with COD collection
    order.cod_amount_collected = amount_collected_decimal
    order.cod_collected_at = timezone.now()
    order.payment_status = 'paid'
    order.save()
    logger.info(f"Order updated with COD collection: {amount_collected_decimal}")
    
    # Create delivery earnings for delivery charge
    delivery_charge_decimal = to_decimal(order.delivery_charge)
    logger.info(f"Delivery charge converted: {delivery_charge_decimal}, type: {type(delivery_charge_decimal)}")
    
    if delivery_charge_decimal > 0:
        DeliveryEarnings.objects.create(
            delivery_boy=delivery_boy,
            order=order,
            amount=delivery_charge_decimal,
            earning_type='delivery_charge',
            description=f'Delivery charge for order {order.order_id}'
        )
        logger.info(f"Delivery earnings created: {delivery_charge_decimal}")
    
    # Update delivery boy profile using safe conversion
    profile = get_or_create_delivery_profile(delivery_boy)
    logger.info(f"Profile found/created. Current total_earnings: {profile.total_earnings}, type: {type(profile.total_earnings)}")
    
    # Keep everything as Decimal for database consistency
    current_earnings_decimal = to_decimal(profile.total_earnings)
    logger.info(f"Current earnings as Decimal: {current_earnings_decimal}, type: {type(current_earnings_decimal)}")
    
    try:
        # Use Decimal arithmetic for database field
        profile.total_earnings = safe_add(current_earnings_decimal, delivery_charge_decimal)
        logger.info(f"Profile total_earnings updated to: {profile.total_earnings}, type: {type(profile.total_earnings)}")
    except Exception as e:
        logger.error(f"Error updating profile total_earnings: {e}")
        logger.error(f"current_earnings_decimal type: {type(current_earnings_decimal)}")
        logger.error(f"delivery_charge_decimal type: {type(delivery_charge_decimal)}")
        raise
    
    profile.total_deliveries += 1
    profile.save()
    logger.info(f"Profile saved successfully")
    
    return order


def get_delivery_boy_earnings(delivery_boy):
    """
    Gets all earnings for a delivery boy.
    Returns earnings summary.
    """
    earnings = DeliveryEarnings.objects.filter(delivery_boy=delivery_boy)
    total_earnings = sum(to_float(earning.amount) for earning in earnings)
    paid_earnings = sum(to_float(earning.amount) for earning in earnings if earning.is_paid)
    pending_earnings = total_earnings - paid_earnings
    
    return {
        'total_earnings': total_earnings,
        'paid_earnings': paid_earnings,
        'pending_earnings': pending_earnings,
        'total_deliveries': earnings.count(),
        'earnings_breakdown': [
            {
                'order_id': earning.order.order_id,
                'amount': to_float(earning.amount),
                'type': earning.earning_type,
                'description': earning.description,
                'date': earning.created_at,
                'is_paid': earning.is_paid
            }
            for earning in earnings.order_by('-created_at')
        ]
    }


@transaction.atomic
def submit_cod_payment(delivery_boy, order_id, amount_submitted, submission_method='cash', notes=''):
    """
    Submit COD payment collected by delivery boy to company.
    Returns the COD submission record.
    """
    from django.utils import timezone
    
    try:
        order = OrderDetails.objects.get(
            id=order_id, 
            delivered_by=delivery_boy,
            payment_method='cod'
        )
    except OrderDetails.DoesNotExist:
        raise ValidationError("Order not found or not assigned to you.")
    
    if order.cod_amount_collected == 0:
        raise ValidationError("No COD amount collected for this order yet.")
    
    # Check if already submitted
    existing_submission = CODSubmission.objects.filter(
        delivery_boy=delivery_boy,
        order=order,
        status__in=['pending', 'submitted', 'verified']
    ).first()
    
    if existing_submission:
        raise ValidationError("COD payment already submitted for this order.")
    
    amount_submitted_decimal = to_decimal(amount_submitted)
    expected_amount = to_decimal(order.cod_amount_collected)
    
    if not is_amount_equal(amount_submitted_decimal, expected_amount):
        raise ValidationError(f"Amount mismatch. Expected: ${expected_amount}, Submitted: ${amount_submitted_decimal}")
    
    # Create COD submission
    submission = CODSubmission.objects.create(
        delivery_boy=delivery_boy,
        order=order,
        amount_submitted=amount_submitted_decimal,
        submission_method=submission_method,
        submission_notes=notes,
        status='submitted',
        submitted_at=timezone.now()
    )
    
    return submission


def get_cod_submissions(delivery_boy):
    """
    Get all COD submissions for a delivery boy.
    Returns submissions summary.
    """
    submissions = CODSubmission.objects.filter(delivery_boy=delivery_boy).order_by('-created_at')
    
    total_submitted = sum(to_float(sub.amount_submitted) for sub in submissions)
    pending_submissions = submissions.filter(status='pending').count()
    submitted_submissions = submissions.filter(status='submitted').count()
    verified_submissions = submissions.filter(status='verified').count()
    rejected_submissions = submissions.filter(status='rejected').count()
    
    return {
        'total_submitted': total_submitted,
        'pending_submissions': pending_submissions,
        'submitted_submissions': submitted_submissions,
        'verified_submissions': verified_submissions,
        'rejected_submissions': rejected_submissions,
        'submissions': [
            {
                'id': sub.id,
                'order_id': sub.order.order_id,
                'amount_submitted': to_float(sub.amount_submitted),
                'submission_method': sub.submission_method,
                'status': sub.status,
                'submitted_at': sub.submitted_at,
                'verified_at': sub.verified_at,
                'verification_notes': sub.verification_notes,
                'created_at': sub.created_at
            }
            for sub in submissions
        ]
    }


def get_pending_cod_submissions():
    """
    Get all pending COD submissions for admin verification.
    Returns queryset of pending submissions.
    """
    return CODSubmission.objects.filter(status='submitted').order_by('submitted_at')


@transaction.atomic
def verify_cod_submission(admin_user, submission_id, status, verification_notes=''):
    """
    Verify a COD submission (admin function).
    Returns the updated submission.
    """
    from django.utils import timezone
    
    try:
        submission = CODSubmission.objects.get(id=submission_id)
    except CODSubmission.DoesNotExist:
        raise ValidationError("COD submission not found.")
    
    if submission.status != 'submitted':
        raise ValidationError("Only submitted COD payments can be verified.")
    
    if status not in ['verified', 'rejected']:
        raise ValidationError("Status must be 'verified' or 'rejected'.")
    
    submission.status = status
    submission.verified_by = admin_user
    submission.verified_at = timezone.now()
    submission.verification_notes = verification_notes
    submission.save()
    
    return submission


def get_financial_reports(start_date, end_date, period_type='daily'):
    """
    Generate financial reports for platform fee, order amounts, and COD collections.
    Returns comprehensive financial data.
    """
    from django.db.models import Sum, Count, Avg
    from django.utils import timezone
    from datetime import datetime, timedelta
    
    # Convert string dates to datetime objects
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Get orders in date range
    orders = OrderDetails.objects.filter(
        ordered_at__date__range=[start_date, end_date]
    )
    
    # Calculate totals
    total_orders = orders.count()
    total_order_amount = orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    total_platform_fee = orders.aggregate(Sum('platform_fee'))['platform_fee__sum'] or 0
    total_delivery_charge = orders.aggregate(Sum('delivery_charge'))['delivery_charge__sum'] or 0
    
    # COD collections
    cod_orders = orders.filter(payment_method='cod')
    total_cod_collected = cod_orders.aggregate(Sum('cod_amount_collected'))['cod_amount_collected__sum'] or 0
    cod_submissions = CODSubmission.objects.filter(
        order__in=cod_orders,
        status='verified'
    )
    total_cod_submitted = cod_submissions.aggregate(Sum('amount_submitted'))['amount_submitted__sum'] or 0
    
    # Payment method breakdown
    payment_breakdown = {}
    for method in ['wallet', 'online', 'cod']:
        method_orders = orders.filter(payment_method=method)
        payment_breakdown[method] = {
            'count': method_orders.count(),
            'amount': float(method_orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0)
        }
    
    # Delivery status breakdown
    delivery_breakdown = {}
    for status in ['pending', 'confirmed', 'preparing', 'out_for_delivery', 'delivered', 'cancelled']:
        status_orders = orders.filter(delivery_status=status)
        delivery_breakdown[status] = {
            'count': status_orders.count(),
            'amount': float(status_orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0)
        }
    
    # Daily breakdown if period_type is daily
    daily_breakdown = []
    if period_type == 'daily':
        current_date = start_date
        while current_date <= end_date:
            day_orders = orders.filter(ordered_at__date=current_date)
            daily_breakdown.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'orders_count': day_orders.count(),
                'total_amount': float(day_orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0),
                'platform_fee': float(day_orders.aggregate(Sum('platform_fee'))['platform_fee__sum'] or 0),
                'delivery_charge': float(day_orders.aggregate(Sum('delivery_charge'))['delivery_charge__sum'] or 0),
                'cod_collected': float(day_orders.filter(payment_method='cod').aggregate(Sum('cod_amount_collected'))['cod_amount_collected__sum'] or 0)
            })
            current_date += timedelta(days=1)
    
    # Top delivery boys
    top_delivery_boys = DeliveryEarnings.objects.filter(
        order__in=orders,
        earning_type='delivery_charge'
    ).values('delivery_boy__username').annotate(
        total_earnings=Sum('amount'),
        delivery_count=Count('order')
    ).order_by('-total_earnings')[:10]
    
    return {
        'period': {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'type': period_type
        },
        'summary': {
            'total_orders': total_orders,
            'total_order_amount': float(total_order_amount),
            'total_platform_fee': float(total_platform_fee),
            'total_delivery_charge': float(total_delivery_charge),
            'total_cod_collected': float(total_cod_collected),
            'total_cod_submitted': float(total_cod_submitted),
            'pending_cod_amount': float(total_cod_collected - total_cod_submitted),
            'average_order_value': float(total_order_amount / total_orders) if total_orders > 0 else 0
        },
        'payment_breakdown': payment_breakdown,
        'delivery_breakdown': delivery_breakdown,
        'daily_breakdown': daily_breakdown,
        'top_delivery_boys': list(top_delivery_boys)
    }
