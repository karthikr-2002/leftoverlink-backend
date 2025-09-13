from django.contrib import admin
from django.core.exceptions import ValidationError
from .models import Food, Cart, OrderDetails, Wallet, WalletTransaction, DeliveryEarnings, DeliveryBoyProfile, CODSubmission

@admin.register(Food)
class FoodAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Food._meta.fields]
    exclude = ('initial_quantity',)  # Hide initial_quantity from the admin form

    def save_model(self, request, obj, form, change):
        if obj.quantity < 0:
            raise ValidationError("Quantity cannot be negative.")
        if obj.price < 0:
            raise ValidationError("Price cannot be negative.")
        super().save_model(request, obj, form, change)

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Cart._meta.fields]

    def save_model(self, request, obj, form, change):
        food = obj.food
        
        # Check if requested quantity is available
        if obj.quantity > food.quantity:
            raise ValidationError(f"Only {food.quantity} items available for {food.name}.")
        
        super().save_model(request, obj, form, change)

@admin.register(OrderDetails)
class OrderDetailsAdmin(admin.ModelAdmin):
    list_display = ['order_id', 'user', 'food', 'quantity', 'total_amount', 'delivery_charge', 'platform_fee', 'payment_status', 'delivery_status', 'payment_method', 'is_assigned', 'delivered_by', 'ordered_at']
    list_filter = ['payment_status', 'delivery_status', 'payment_method', 'is_assigned', 'ordered_at']
    search_fields = ['order_id', 'user__username', 'food__name', 'delivered_by__username']


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['user', 'balance', 'created_at', 'updated_at']
    search_fields = ['user__username']


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ['wallet', 'amount', 'transaction_type', 'description', 'created_at']
    list_filter = ['transaction_type', 'created_at']
    search_fields = ['wallet__user__username', 'description']


@admin.register(DeliveryEarnings)
class DeliveryEarningsAdmin(admin.ModelAdmin):
    list_display = ['delivery_boy', 'order', 'amount', 'earning_type', 'is_paid', 'created_at']
    list_filter = ['earning_type', 'is_paid', 'created_at']
    search_fields = ['delivery_boy__username', 'order__order_id']


@admin.register(DeliveryBoyProfile)
class DeliveryBoyProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'is_available', 'total_earnings', 'total_deliveries', 'rating', 'phone_number', 'vehicle_type']
    list_filter = ['is_available', 'vehicle_type', 'created_at']
    search_fields = ['user__username', 'phone_number', 'license_number']


@admin.register(CODSubmission)
class CODSubmissionAdmin(admin.ModelAdmin):
    list_display = ['delivery_boy', 'order', 'amount_submitted', 'submission_method', 'status', 'submitted_at', 'verified_by']
    list_filter = ['status', 'submission_method', 'submitted_at', 'created_at']
    search_fields = ['delivery_boy__username', 'order__order_id', 'verification_notes']
    readonly_fields = ['created_at', 'submitted_at', 'verified_at']