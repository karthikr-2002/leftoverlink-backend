from django.urls import path
from .views import (
    get_foods_api, get_food_by_id_api, add_to_cart_api, remove_from_cart_api, get_cart_api, clear_cart_api,
    checkout_api, process_payment_api, get_wallet_api, add_money_to_wallet_api,
    get_orders_api, get_available_orders_api, assign_order_api, 
    update_delivery_status_api, collect_cod_payment_api, get_delivery_earnings_api,
    get_delivery_profile_api, update_delivery_profile_api, get_my_assigned_orders_api,
    submit_cod_payment_api, get_my_cod_submissions_api, get_pending_cod_submissions_api,
    verify_cod_submission_api, get_cod_verification_summary_api, get_financial_reports_api,
    get_quick_reports_api, get_delivery_performance_api, register_fcm_token_api,
    unregister_fcm_token_api, send_test_notification_api, register_expo_push_token_api,
    unregister_expo_push_token_api, send_local_notification_api
)

urlpatterns = [
    # Food APIs
    path('foods/', get_foods_api, name='get_foods'),
    path('foods/<int:food_id>/', get_food_by_id_api, name='get_food_by_id'),
    
    # Cart APIs
    path('food/<int:food_id>/add-to-cart/', add_to_cart_api, name='add_to_cart'),
    path('food/<int:food_id>/remove-from-cart/', remove_from_cart_api, name='remove_from_cart'),
    path('cart/', get_cart_api, name='get_cart'),
    path('cart/clear/', clear_cart_api, name='clear_cart'),
    
    # Checkout and Payment APIs
    path('checkout/', checkout_api, name='checkout'),
    path('payment/process/', process_payment_api, name='process_payment'),
    
    # Wallet APIs
    path('wallet/', get_wallet_api, name='get_wallet'),
    path('wallet/add-money/', add_money_to_wallet_api, name='add_money_to_wallet'),
    
    # Order APIs
    path('orders/', get_orders_api, name='get_orders'),
    
    # Delivery Boy APIs
    path('delivery/available-orders/', get_available_orders_api, name='get_available_orders'),
    path('delivery/my-orders/', get_my_assigned_orders_api, name='get_my_assigned_orders'),
    path('delivery/assign-order/', assign_order_api, name='assign_order'),
    path('delivery/update-status/', update_delivery_status_api, name='update_delivery_status'),
    path('delivery/collect-cod/', collect_cod_payment_api, name='collect_cod_payment'),
    path('delivery/earnings/', get_delivery_earnings_api, name='get_delivery_earnings'),
    path('delivery/profile/', get_delivery_profile_api, name='get_delivery_profile'),
    path('delivery/profile/update/', update_delivery_profile_api, name='update_delivery_profile'),
    
    # COD Submission APIs
    path('delivery/submit-cod/', submit_cod_payment_api, name='submit_cod_payment'),
    path('delivery/my-cod-submissions/', get_my_cod_submissions_api, name='get_my_cod_submissions'),
    path('admin/pending-cod-submissions/', get_pending_cod_submissions_api, name='get_pending_cod_submissions'),
    path('admin/verify-cod-submission/', verify_cod_submission_api, name='verify_cod_submission'),
    
    # Admin Reporting APIs
    path('admin/cod-verification-summary/', get_cod_verification_summary_api, name='get_cod_verification_summary'),
    path('admin/financial-reports/', get_financial_reports_api, name='get_financial_reports'),
    path('admin/quick-reports/', get_quick_reports_api, name='get_quick_reports'),
    path('admin/delivery-performance/', get_delivery_performance_api, name='get_delivery_performance'),
    
    # Local Notification APIs (works with Expo Go)
    path('local-notification/', send_local_notification_api, name='send_local_notification'),
    
    # Expo Push Notification APIs
    path('expo-push/register/', register_expo_push_token_api, name='register_expo_push_token'),
    path('expo-push/unregister/', unregister_expo_push_token_api, name='unregister_expo_push_token'),
    
    # FCM Push Notification APIs
    path('fcm/register/', register_fcm_token_api, name='register_fcm_token'),
    path('fcm/unregister/', unregister_fcm_token_api, name='unregister_fcm_token'),
    path('fcm/test/', send_test_notification_api, name='send_test_notification'),
    
]