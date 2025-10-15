import math
from decimal import Decimal


def calculate_distance_haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    Returns distance in kilometers
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Radius of earth in kilometers
    r = 6371
    
    return c * r


def calculate_delivery_charge(user_lat, user_lon, restaurant_lat=10.231380, restaurant_lon=76.408872, 
                            per_km_charge=5):
    """
    Calculate delivery charge based on distance from restaurant
    Args:
        user_lat: User's latitude
        user_lon: User's longitude
        restaurant_lat: Restaurant's latitude (default: hostel canteen)
        restaurant_lon: Restaurant's longitude (default: hostel canteen)
        per_km_charge: Charge per kilometer (default: 5)
    
    Returns:
        Delivery charge as Decimal
    """
    if not user_lat or not user_lon:
        return Decimal('0')
    
    try:
        # Calculate distance in kilometers
        distance = calculate_distance_haversine(user_lat, user_lon, restaurant_lat, restaurant_lon)
        
        # Calculate charge: distance * per_km_charge (no minimum charge)
        charge = distance * per_km_charge
        
        # Round to nearest rupee
        charge = round(charge)
        
        return Decimal(str(charge))
        
    except (ValueError, TypeError) as e:
        # If calculation fails, return 0 charge
        return Decimal('0')


def validate_coordinates(lat, lon):
    """
    Validate if coordinates are within reasonable bounds
    """
    try:
        lat = float(lat)
        lon = float(lon)
        
        # Check if coordinates are within valid ranges
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return True
        return False
    except (ValueError, TypeError):
        return False
