from django.contrib import admin
from django.core.exceptions import ValidationError
from django.urls import path
from django.shortcuts import render
from django.db.models import Sum, Count, Q
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from datetime import datetime, timedelta
import calendar
from .models import Food, Cart, OrderDetails, OrderItem, Wallet, WalletTransaction, DeliveryEarnings, DeliveryBoyProfile, CODSubmission
from .fcm_models import FCMDevice
from core.helpers import get_financial_reports
from core.pdf_generator import generate_financial_report_pdf
from core.fcm_service_v1 import fcm_service_v1

@admin.register(Food)
class FoodAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Food._meta.fields]
    exclude = ('initial_quantity',)  # Hide initial_quantity from the admin form

    def save_model(self, request, obj, form, change):
        if obj.quantity < 0:
            raise ValidationError("Quantity cannot be negative.")
        if obj.price < 0:
            raise ValidationError("Price cannot be negative.")
        
        # Save the food item
        super().save_model(request, obj, form, change)
        
        # Send push notification to all customers when new food is added
        if not change:  # Only for new food items
            print("\n" + "=" * 80)
            print("🍕 NEW FOOD ADDED - Triggering push notification")
            print(f"   Food: {obj.name}")
            print(f"   Price: ₹{obj.price}")
            print(f"   Quantity: {obj.quantity}")
            print(f"   ID: {obj.id}")
            print("=" * 80)
            
            try:
                # Send notification via FCM v1 API (Firebase Admin SDK)
                print("📤 Calling fcm_service_v1.send_to_all_customers()...")
                
                fcm_result = fcm_service_v1.send_to_all_customers(
                    title="🍕 New Food Available!",
                    body=f"{obj.name} is now available for just ₹{obj.price}",
                    data={
                        "type": "new_food",
                        "food_id": str(obj.id),
                        "food_name": obj.name,
                        "price": str(obj.price),
                        "quantity": str(obj.quantity)
                    }
                )
                
                print("\n" + "=" * 80)
                print("📊 NOTIFICATION RESULT:")
                print(f"   FCM v1 result: {fcm_result}")
                
                if fcm_result:
                    print(f"   ✅ Success: {fcm_result.get('success_count', 0)} devices")
                    print(f"   ❌ Failure: {fcm_result.get('failure_count', 0)} devices")
                    print(f"   📱 Total: {fcm_result.get('total', 0)} devices")
                else:
                    print("   ⚠️ No result returned (check logs above for errors)")
                print("=" * 80 + "\n")
                
            except Exception as e:
                print("\n" + "=" * 80)
                print("❌ EXCEPTION in FoodAdmin.save_model()!")
                print(f"   Error: {str(e)}")
                print(f"   Type: {type(e).__name__}")
                import traceback
                print("   Traceback:")
                traceback.print_exc()
                print("=" * 80 + "\n")

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Cart._meta.fields]

    def save_model(self, request, obj, form, change):
        food = obj.food
        
        # Check if requested quantity is available
        if obj.quantity > food.quantity:
            raise ValidationError(f"Only {food.quantity} items available for {food.name}.")
        
        super().save_model(request, obj, form, change)

class CODSubmissionInline(admin.TabularInline):
    model = CODSubmission
    extra = 0
    readonly_fields = ['created_at', 'submitted_at', 'verified_at']
    fields = ['delivery_boy', 'amount_submitted', 'submission_method', 'status', 'submitted_at', 'verified_by', 'verified_at', 'verification_notes']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('delivery_boy', 'verified_by')

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['total_price']
    fields = ['food', 'quantity', 'price', 'total_price']

@admin.register(OrderDetails)
class OrderDetailsAdmin(admin.ModelAdmin):
    list_display = ['order_id', 'user', 'items_summary', 'subtotal', 'total_amount', 'delivery_charge', 'platform_fee', 'payment_status', 'delivery_status', 'payment_method', 'is_assigned', 'delivered_by', 'cod_collection_status', 'cod_submission_status', 'ordered_at']
    list_filter = ['payment_status', 'delivery_status', 'payment_method', 'is_assigned', 'ordered_at']
    search_fields = ['order_id', 'user__username', 'items__food__name', 'delivered_by__username']
    inlines = [OrderItemInline, CODSubmissionInline]
    readonly_fields = ['order_id', 'ordered_at', 'assigned_at', 'cod_collected_at']
    actions = ['generate_daily_report', 'generate_weekly_report', 'generate_monthly_report', 'view_financial_reports']
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order_id', 'user', 'ordered_at')
        }),
        ('Payment Details', {
            'fields': ('subtotal', 'delivery_charge', 'platform_fee', 'total_amount', 'payment_method', 'payment_status')
        }),
        ('Delivery Information', {
            'fields': ('delivery_status', 'is_assigned', 'delivered_by', 'assigned_at')
        }),
        ('COD Information', {
            'fields': ('cod_amount_collected', 'cod_collected_at'),
            'classes': ('collapse',)
        }),
    )
    
    def items_summary(self, obj):
        """Show a summary of items in the order"""
        items = obj.items.all()
        if not items:
            return "No items"
        
        item_names = [f"{item.food.name} x{item.quantity}" for item in items]
        summary = ", ".join(item_names)
        if len(summary) > 50:
            summary = summary[:47] + "..."
        return summary
    items_summary.short_description = 'Items'
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['reports_url'] = 'financial-reports/'
        extra_context['show_reports_link'] = True
        return super().changelist_view(request, extra_context=extra_context)
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('financial-reports/', self.admin_site.admin_view(self.financial_reports_view), name='financial_reports'),
            path('financial-reports/daily/', self.admin_site.admin_view(self.daily_report_view), name='daily_report'),
            path('financial-reports/weekly/', self.admin_site.admin_view(self.weekly_report_view), name='weekly_report'),
            path('financial-reports/monthly/', self.admin_site.admin_view(self.monthly_report_view), name='monthly_report'),
            path('financial-reports/custom/', self.admin_site.admin_view(self.custom_report_view), name='custom_report'),
            # PDF Download endpoints
            path('financial-reports/daily/pdf/', self.admin_site.admin_view(self.daily_report_pdf), name='daily_report_pdf'),
            path('financial-reports/weekly/pdf/', self.admin_site.admin_view(self.weekly_report_pdf), name='weekly_report_pdf'),
            path('financial-reports/monthly/pdf/', self.admin_site.admin_view(self.monthly_report_pdf), name='monthly_report_pdf'),
            path('financial-reports/custom/pdf/', self.admin_site.admin_view(self.custom_report_pdf), name='custom_report_pdf'),
        ]
        return custom_urls + urls
    
    def cod_collection_status(self, obj):
        """Show COD collection status"""
        if obj.payment_method != 'cod':
            return '-'
        if obj.cod_amount_collected > 0:
            return f'✅ Collected (₹{obj.cod_amount_collected})'
        else:
            return '⏳ Not Collected'
    cod_collection_status.short_description = 'COD Collection'
    cod_collection_status.admin_order_field = 'cod_amount_collected'
    
    def cod_submission_status(self, obj):
        """Show COD submission status"""
        if obj.payment_method != 'cod' or obj.cod_amount_collected == 0:
            return '-'
        
        # Get the latest COD submission for this order
        latest_submission = obj.cod_submissions.order_by('-created_at').first()
        if not latest_submission:
            return '📤 Not Submitted'
        
        status_icons = {
            'pending': '⏳ Pending',
            'submitted': '📋 Submitted',
            'verified': '✅ Verified',
            'rejected': '❌ Rejected'
        }
        return status_icons.get(latest_submission.status, '❓ Unknown')
    cod_submission_status.short_description = 'COD Submission'
    cod_submission_status.admin_order_field = 'cod_submissions__status'
    
    def financial_reports_view(self, request):
        """Main financial reports dashboard"""
        today = timezone.now().date()
        
        # Get quick summary data
        today_report = get_financial_reports(today, today, 'daily')
        
        # This week's report
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        week_report = get_financial_reports(week_start, week_end, 'daily')
        
        # This month's report
        month_start = today.replace(day=1)
        last_day = calendar.monthrange(today.year, today.month)[1]
        month_end = today.replace(day=last_day)
        month_report = get_financial_reports(month_start, month_end, 'daily')
        
        context = {
            'title': 'Financial Reports Dashboard',
            'today': {
                'date': today.strftime('%Y-%m-%d'),
                'summary': today_report['summary']
            },
            'this_week': {
                'start_date': week_start.strftime('%Y-%m-%d'),
                'end_date': week_end.strftime('%Y-%m-%d'),
                'summary': week_report['summary']
            },
            'this_month': {
                'start_date': month_start.strftime('%Y-%m-%d'),
                'end_date': month_end.strftime('%Y-%m-%d'),
                'summary': month_report['summary']
            },
            'opts': self.model._meta,
            'has_view_permission': True,
        }
        
        return render(request, 'admin/foodmanagement/orderdetails/financial_reports.html', context)
    
    def daily_report_view(self, request):
        """Daily financial report"""
        date_str = request.GET.get('date')
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                target_date = timezone.now().date()
        else:
            target_date = timezone.now().date()
        
        report = get_financial_reports(target_date, target_date, 'daily')
        
        context = {
            'title': f'Daily Report - {target_date.strftime("%Y-%m-%d")}',
            'report_type': 'daily',
            'date': target_date.strftime('%Y-%m-%d'),
            'data': report,
            'opts': self.model._meta,
            'has_view_permission': True,
        }
        
        return render(request, 'admin/foodmanagement/orderdetails/report_detail.html', context)
    
    def weekly_report_view(self, request):
        """Weekly financial report"""
        week_str = request.GET.get('week')
        if week_str:
            try:
                year, week = week_str.split('-W')
                year = int(year)
                week = int(week)
                start_date = datetime.strptime(f'{year}-W{week:02d}-1', '%Y-W%W-%w').date()
                end_date = start_date + timedelta(days=6)
            except ValueError:
                today = timezone.now().date()
                start_date = today - timedelta(days=today.weekday())
                end_date = start_date + timedelta(days=6)
        else:
            today = timezone.now().date()
            start_date = today - timedelta(days=today.weekday())
            end_date = start_date + timedelta(days=6)
        
        report = get_financial_reports(start_date, end_date, 'daily')
        
        context = {
            'title': f'Weekly Report - Week {start_date.isocalendar()[1]} of {start_date.year}',
            'report_type': 'weekly',
            'week': f"{start_date.year}-W{start_date.isocalendar()[1]:02d}",
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'data': report,
            'opts': self.model._meta,
            'has_view_permission': True,
        }
        
        return render(request, 'admin/foodmanagement/orderdetails/report_detail.html', context)
    
    def monthly_report_view(self, request):
        """Monthly financial report"""
        month_str = request.GET.get('month')
        if month_str:
            try:
                year, month = month_str.split('-')
                year = int(year)
                month = int(month)
                start_date = datetime(year, month, 1).date()
                last_day = calendar.monthrange(year, month)[1]
                end_date = datetime(year, month, last_day).date()
            except ValueError:
                today = timezone.now().date()
                start_date = today.replace(day=1)
                last_day = calendar.monthrange(today.year, today.month)[1]
                end_date = today.replace(day=last_day)
        else:
            today = timezone.now().date()
            start_date = today.replace(day=1)
            last_day = calendar.monthrange(today.year, today.month)[1]
            end_date = today.replace(day=last_day)
        
        report = get_financial_reports(start_date, end_date, 'daily')
        
        context = {
            'title': f'Monthly Report - {start_date.strftime("%B %Y")}',
            'report_type': 'monthly',
            'month': f"{start_date.year}-{start_date.month:02d}",
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'data': report,
            'opts': self.model._meta,
            'has_view_permission': True,
        }
        
        return render(request, 'admin/foodmanagement/orderdetails/report_detail.html', context)
    
    def custom_report_view(self, request):
        """Custom date range financial report"""
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        
        if not start_date_str or not end_date_str:
            # Default to last 30 days
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=30)
        else:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                end_date = timezone.now().date()
                start_date = end_date - timedelta(days=30)
        
        if start_date > end_date:
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=30)
        
        report = get_financial_reports(start_date, end_date, 'daily')
        
        context = {
            'title': f'Custom Report - {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}',
            'report_type': 'custom',
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'data': report,
            'opts': self.model._meta,
            'has_view_permission': True,
        }
        
        return render(request, 'admin/foodmanagement/orderdetails/report_detail.html', context)
    
    def daily_report_pdf(self, request):
        """Generate PDF for daily report"""
        date_str = request.GET.get('date')
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                target_date = timezone.now().date()
        else:
            target_date = timezone.now().date()
        
        report = get_financial_reports(target_date, target_date, 'daily')
        
        title = f"Daily Financial Report - {target_date.strftime('%Y-%m-%d')}"
        pdf = generate_financial_report_pdf(
            report, 
            title, 
            'daily',
            target_date.strftime('%Y-%m-%d'),
            target_date.strftime('%Y-%m-%d')
        )
        
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="daily_report_{target_date.strftime("%Y%m%d")}.pdf"'
        return response
    
    def weekly_report_pdf(self, request):
        """Generate PDF for weekly report"""
        week_str = request.GET.get('week')
        if week_str:
            try:
                year, week = week_str.split('-W')
                year = int(year)
                week = int(week)
                start_date = datetime.strptime(f'{year}-W{week:02d}-1', '%Y-W%W-%w').date()
                end_date = start_date + timedelta(days=6)
            except ValueError:
                today = timezone.now().date()
                start_date = today - timedelta(days=today.weekday())
                end_date = start_date + timedelta(days=6)
        else:
            today = timezone.now().date()
            start_date = today - timedelta(days=today.weekday())
            end_date = start_date + timedelta(days=6)
        
        report = get_financial_reports(start_date, end_date, 'daily')
        
        title = f"Weekly Financial Report - Week {start_date.isocalendar()[1]} of {start_date.year}"
        pdf = generate_financial_report_pdf(
            report, 
            title, 
            'weekly',
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )
        
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="weekly_report_{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}.pdf"'
        return response
    
    def monthly_report_pdf(self, request):
        """Generate PDF for monthly report"""
        month_str = request.GET.get('month')
        if month_str:
            try:
                year, month = month_str.split('-')
                year = int(year)
                month = int(month)
                start_date = datetime(year, month, 1).date()
                last_day = calendar.monthrange(year, month)[1]
                end_date = datetime(year, month, last_day).date()
            except ValueError:
                today = timezone.now().date()
                start_date = today.replace(day=1)
                last_day = calendar.monthrange(today.year, today.month)[1]
                end_date = today.replace(day=last_day)
        else:
            today = timezone.now().date()
            start_date = today.replace(day=1)
            last_day = calendar.monthrange(today.year, today.month)[1]
            end_date = today.replace(day=last_day)
        
        report = get_financial_reports(start_date, end_date, 'daily')
        
        title = f"Monthly Financial Report - {start_date.strftime('%B %Y')}"
        pdf = generate_financial_report_pdf(
            report, 
            title, 
            'monthly',
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )
        
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="monthly_report_{start_date.strftime("%Y%m")}.pdf"'
        return response
    
    def custom_report_pdf(self, request):
        """Generate PDF for custom date range report"""
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        
        if not start_date_str or not end_date_str:
            # Default to last 30 days
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=30)
        else:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                end_date = timezone.now().date()
                start_date = end_date - timedelta(days=30)
        
        if start_date > end_date:
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=30)
        
        report = get_financial_reports(start_date, end_date, 'daily')
        
        title = f"Custom Financial Report - {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
        pdf = generate_financial_report_pdf(
            report, 
            title, 
            'custom',
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )
        
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="custom_report_{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}.pdf"'
        return response
    
    def generate_daily_report(self, request, queryset):
        """Admin action to generate daily report for selected orders"""
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        
        # Get the date range from selected orders
        if queryset.exists():
            dates = queryset.values_list('ordered_at__date', flat=True).distinct()
            if dates:
                # Use the most recent date
                target_date = max(dates)
                url = reverse('admin:daily_report') + f'?date={target_date}'
                return HttpResponseRedirect(url)
        
        # Default to today if no orders selected
        today = timezone.now().date()
        url = reverse('admin:daily_report') + f'?date={today}'
        return HttpResponseRedirect(url)
    generate_daily_report.short_description = 'Generate daily report for selected orders'
    
    def generate_weekly_report(self, request, queryset):
        """Admin action to generate weekly report for selected orders"""
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        
        # Get the date range from selected orders
        if queryset.exists():
            dates = queryset.values_list('ordered_at__date', flat=True).distinct()
            if dates:
                # Use the most recent date to determine the week
                target_date = max(dates)
                week_start = target_date - timedelta(days=target_date.weekday())
                week_str = f"{week_start.year}-W{week_start.isocalendar()[1]:02d}"
                url = reverse('admin:weekly_report') + f'?week={week_str}'
                return HttpResponseRedirect(url)
        
        # Default to current week if no orders selected
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        week_str = f"{week_start.year}-W{week_start.isocalendar()[1]:02d}"
        url = reverse('admin:weekly_report') + f'?week={week_str}'
        return HttpResponseRedirect(url)
    generate_weekly_report.short_description = 'Generate weekly report for selected orders'
    
    def generate_monthly_report(self, request, queryset):
        """Admin action to generate monthly report for selected orders"""
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        
        # Get the date range from selected orders
        if queryset.exists():
            dates = queryset.values_list('ordered_at__date', flat=True).distinct()
            if dates:
                # Use the most recent date to determine the month
                target_date = max(dates)
                month_str = f"{target_date.year}-{target_date.month:02d}"
                url = reverse('admin:monthly_report') + f'?month={month_str}'
                return HttpResponseRedirect(url)
        
        # Default to current month if no orders selected
        today = timezone.now().date()
        month_str = f"{today.year}-{today.month:02d}"
        url = reverse('admin:monthly_report') + f'?month={month_str}'
        return HttpResponseRedirect(url)
    generate_monthly_report.short_description = 'Generate monthly report for selected orders'
    
    def view_financial_reports(self, request, queryset):
        """Admin action to view financial reports dashboard"""
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        
        url = reverse('admin:financial_reports')
        return HttpResponseRedirect(url)
    view_financial_reports.short_description = '📊 View Financial Reports Dashboard'


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


@admin.register(FCMDevice)
class FCMDeviceAdmin(admin.ModelAdmin):
    list_display = ['user', 'device_type', 'is_active', 'token_preview', 'created_at', 'updated_at']
    list_filter = ['is_active', 'device_type', 'created_at']
    search_fields = ['user__username', 'fcm_token']
    readonly_fields = ['fcm_token', 'created_at', 'updated_at', 'full_token_display']
    list_per_page = 20
    
    fieldsets = (
        ('Device Information', {
            'fields': ('user', 'device_type', 'is_active')
        }),
        ('FCM Token', {
            'fields': ('full_token_display',),
            'description': 'Copy this token for testing notifications'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def token_preview(self, obj):
        """Show first 20 characters of token"""
        if obj.fcm_token:
            token_start = obj.fcm_token[:20]
            token_end = obj.fcm_token[-10:]
            return f"{token_start}...{token_end}"
        return "No token"
    token_preview.short_description = 'Token Preview'
    
    def full_token_display(self, obj):
        """Display full token for copying"""
        if obj.fcm_token:
            return f"{obj.fcm_token}"
        return "No token"
    full_token_display.short_description = 'Full FCM Token (Copy This)'
    
    def get_queryset(self, request):
        """Order by most recently updated"""
        qs = super().get_queryset(request)
        return qs.select_related('user').order_by('-updated_at')
    
    actions = ['activate_devices', 'deactivate_devices', 'test_send_notification']
    
    def activate_devices(self, request, queryset):
        """Activate selected devices"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} devices activated successfully.')
    activate_devices.short_description = '✅ Activate selected devices'
    
    def deactivate_devices(self, request, queryset):
        """Deactivate selected devices"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} devices deactivated successfully.')
    deactivate_devices.short_description = '❌ Deactivate selected devices'
    
    def test_send_notification(self, request, queryset):
        """Send test notification to selected devices"""
        from core.fcm_service_v1 import fcm_service_v1
        
        active_devices = queryset.filter(is_active=True)
        if not active_devices.exists():
            self.message_user(request, 'No active devices selected!', level='warning')
            return
        
        tokens = [device.fcm_token for device in active_devices]
        
        try:
            from firebase_admin import messaging
            
            success_count = 0
            failure_count = 0
            
            # Send to each device individually
            for token in tokens:
                try:
                    message = messaging.Message(
                        notification=messaging.Notification(
                            title="🔔 Test Notification",
                            body="This is a test notification from LeftoverLink Admin",
                        ),
                        data={'type': 'test', 'source': 'admin'},
                        token=token,
                    )
                    
                    messaging.send(message)
                    success_count += 1
                except Exception as e:
                    failure_count += 1
                    print(f"Failed to send to token: {str(e)}")
            
            self.message_user(
                request, 
                f'Test notification sent! Success: {success_count}, Failed: {failure_count}'
            )
        except Exception as e:
            self.message_user(request, f'Error sending notification: {str(e)}', level='error')
    test_send_notification.short_description = '📤 Send test notification to selected devices'


@admin.register(CODSubmission)
class CODSubmissionAdmin(admin.ModelAdmin):
    list_display = ['delivery_boy', 'order', 'amount_submitted', 'submission_method', 'status', 'submitted_at', 'verified_by', 'verification_status']
    list_filter = ['status', 'submission_method', 'submitted_at', 'created_at', 'verified_at']
    search_fields = ['delivery_boy__username', 'order__order_id', 'verification_notes', 'submission_notes']
    readonly_fields = ['created_at', 'submitted_at', 'verified_at']
    
    fieldsets = (
        ('Submission Details', {
            'fields': ('delivery_boy', 'order', 'amount_submitted', 'submission_method', 'submission_notes', 'status')
        }),
        ('Verification Details', {
            'fields': ('verified_by', 'verified_at', 'verification_notes'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'submitted_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['verify_submissions', 'reject_submissions']
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['cod_summary_url'] = 'cod-summary/'
        return super().changelist_view(request, extra_context=extra_context)
    
    def verification_status(self, obj):
        """Show verification status with icons"""
        if obj.status == 'verified':
            return '✅ Verified'
        elif obj.status == 'rejected':
            return '❌ Rejected'
        elif obj.status == 'submitted':
            return '⏳ Pending Verification'
        else:
            return '📋 Submitted'
    verification_status.short_description = 'Verification Status'
    verification_status.admin_order_field = 'status'
    
    def verify_submissions(self, request, queryset):
        """Admin action to verify COD submissions"""
        from django.utils import timezone
        updated = queryset.filter(status='submitted').update(
            status='verified',
            verified_by=request.user,
            verified_at=timezone.now(),
            verification_notes='Verified by admin'
        )
        self.message_user(request, f'{updated} COD submissions verified successfully.')
    verify_submissions.short_description = 'Verify selected COD submissions'
    
    def reject_submissions(self, request, queryset):
        """Admin action to reject COD submissions"""
        updated = queryset.filter(status='submitted').update(
            status='rejected',
            verified_by=request.user,
            verified_at=timezone.now(),
            verification_notes='Rejected by admin'
        )
        self.message_user(request, f'{updated} COD submissions rejected.')
    reject_submissions.short_description = 'Reject selected COD submissions'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('cod-summary/', self.admin_site.admin_view(self.cod_summary_view), name='cod_submission_summary'),
        ]
        return custom_urls + urls
    
    def cod_summary_view(self, request):
        """Custom admin view for COD submission summary"""
        # Get COD submission statistics
        total_submissions = CODSubmission.objects.count()
        pending_submissions = CODSubmission.objects.filter(status='submitted').count()
        verified_submissions = CODSubmission.objects.filter(status='verified').count()
        rejected_submissions = CODSubmission.objects.filter(status='rejected').count()
        
        # Get total amounts
        total_amount_submitted = CODSubmission.objects.aggregate(
            total=Sum('amount_submitted')
        )['total'] or 0
        
        total_amount_verified = CODSubmission.objects.filter(status='verified').aggregate(
            total=Sum('amount_submitted')
        )['total'] or 0
        
        # Get recent submissions
        recent_submissions = CODSubmission.objects.select_related(
            'delivery_boy', 'order', 'verified_by'
        ).order_by('-submitted_at')[:10]
        
        # Get pending submissions for quick action
        pending_for_verification = CODSubmission.objects.filter(
            status='submitted'
        ).select_related('delivery_boy', 'order').order_by('submitted_at')
        
        context = {
            'title': 'COD Submission Summary',
            'total_submissions': total_submissions,
            'pending_submissions': pending_submissions,
            'verified_submissions': verified_submissions,
            'rejected_submissions': rejected_submissions,
            'total_amount_submitted': total_amount_submitted,
            'total_amount_verified': total_amount_verified,
            'recent_submissions': recent_submissions,
            'pending_for_verification': pending_for_verification,
        }
        
        return render(request, 'admin/foodmanagement/codsubmission/summary.html', context)