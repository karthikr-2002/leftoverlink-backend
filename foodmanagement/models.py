from django.db import models
from userauth.models import User

class Food(models.Model):
    STATUS_CHOICES = (
        ('available', 'Available'),
        ('not_available', 'Not Available'),
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    quantity = models.PositiveIntegerField()
    initial_quantity = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='available'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    added_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="foods_added",
    )

    def save(self, *args, **kwargs):
        if not self.pk:  # Only set on creation
            self.initial_quantity = self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cart")
    food = models.ForeignKey(Food, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.food.name} ({self.quantity})"


class OrderDetails(models.Model):
    PAYMENT_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )
    
    DELIVERY_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('preparing', 'Preparing'),
        ('out_for_delivery', 'Out for Delivery'),
        ('ready_for_pickup', 'Ready for Pickup'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    )
    
    PAYMENT_METHOD_CHOICES = (
        ('wallet', 'Wallet'),
        ('online', 'Online Payment'),
        ('cod', 'Cash on Delivery'),
    )
    
    DELIVERY_TYPE_CHOICES = (
        ('delivery', 'Delivery'),
        ('takeaway', 'Take Away'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    ordered_at = models.DateTimeField(auto_now_add=True)
    delivered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deliveries",
    )
    payment_status = models.CharField(
        max_length=10,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending'
    )
    delivery_status = models.CharField(
        max_length=20,
        choices=DELIVERY_STATUS_CHOICES,
        default='pending'
    )
    delivery_charge = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    platform_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    payment_method = models.CharField(
        max_length=10,
        choices=PAYMENT_METHOD_CHOICES,
        default='cod'
    )
    delivery_type = models.CharField(
        max_length=10,
        choices=DELIVERY_TYPE_CHOICES,
        default='delivery'
    )
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    order_id = models.CharField(max_length=50, unique=True, blank=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    is_assigned = models.BooleanField(default=False)
    cod_amount_collected = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    cod_collected_at = models.DateTimeField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.order_id:
            import uuid
            self.order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order {self.order_id} by {self.user.username} on {self.ordered_at}"


class OrderItem(models.Model):
    """Individual items within an order"""
    order = models.ForeignKey(OrderDetails, on_delete=models.CASCADE, related_name="items")
    food = models.ForeignKey(Food, on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=8, decimal_places=2)  # Price at time of order
    total_price = models.DecimalField(max_digits=10, decimal_places=2)  # quantity * price
    
    def save(self, *args, **kwargs):
        # Calculate total price
        self.total_price = self.quantity * self.price
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.food.name} x{self.quantity} in Order {self.order.order_id}"


class Wallet(models.Model):
    TRANSACTION_TYPE_CHOICES = (
        ('credit', 'Credit'),
        ('debit', 'Debit'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="wallet")
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Wallet for {self.user.username} - ₹{self.balance}"
    
    def add_money(self, amount):
        """Add money to wallet"""
        from decimal import Decimal
        
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Amount must be positive")
        self.balance += amount
        self.save()
        return self.balance
    
    def deduct_money(self, amount):
        """Deduct money from wallet"""
        from decimal import Decimal
        
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Amount must be positive")
        if self.balance < amount:
            raise ValueError("Insufficient balance")
        self.balance -= amount
        self.save()
        return self.balance


class WalletTransaction(models.Model):
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="transactions")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=Wallet.TRANSACTION_TYPE_CHOICES)
    description = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.transaction_type.title()} of ₹{self.amount} for {self.wallet.user.username}"


class DeliveryEarnings(models.Model):
    EARNING_TYPE_CHOICES = (
        ('delivery_charge', 'Delivery Charge'),
        ('cod_collection', 'COD Collection'),
        ('bonus', 'Bonus'),
    )
    
    delivery_boy = models.ForeignKey(User, on_delete=models.CASCADE, related_name="delivery_earnings")
    order = models.ForeignKey(OrderDetails, on_delete=models.CASCADE, related_name="delivery_earnings")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    earning_type = models.CharField(max_length=20, choices=EARNING_TYPE_CHOICES)
    description = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.delivery_boy.username} - {self.earning_type} - ₹{self.amount}"


class CODSubmission(models.Model):
    SUBMISSION_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('submitted', 'Submitted'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    )
    
    delivery_boy = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cod_submissions")
    order = models.ForeignKey(OrderDetails, on_delete=models.CASCADE, related_name="cod_submissions")
    amount_submitted = models.DecimalField(max_digits=10, decimal_places=2)
    submission_method = models.CharField(max_length=50, default='cash')  # cash, bank_transfer, etc.
    submission_notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=SUBMISSION_STATUS_CHOICES, default='pending')
    submitted_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="verified_cod_submissions"
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"COD Submission - {self.delivery_boy.username} - Order {self.order.order_id} - ₹{self.amount_submitted}"


class DeliveryBoyProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="delivery_profile")
    is_available = models.BooleanField(default=True)
    total_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_deliveries = models.PositiveIntegerField(default=0)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    phone_number = models.CharField(max_length=15, blank=True)
    vehicle_type = models.CharField(max_length=50, blank=True)
    license_number = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Delivery Profile for {self.user.username}"
