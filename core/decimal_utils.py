"""
Centralized utility functions for handling Decimal and float conversions
to prevent type mismatch errors throughout the project.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Union, Any


def to_decimal(value: Union[str, int, float, Decimal, None], default: Decimal = Decimal('0')) -> Decimal:
    """
    Safely convert any value to Decimal.
    
    Args:
        value: The value to convert (str, int, float, Decimal, or None)
        default: Default value if conversion fails (default: Decimal('0'))
    
    Returns:
        Decimal: The converted value or default
    """
    if value is None:
        return default
    
    if isinstance(value, Decimal):
        return value
    
    try:
        return Decimal(str(value))
    except (ValueError, TypeError, ArithmeticError):
        return default


def to_float(value: Union[str, int, float, Decimal, None], default: float = 0.0) -> float:
    """
    Safely convert any value to float.
    
    Args:
        value: The value to convert (str, int, float, Decimal, or None)
        default: Default value if conversion fails (default: 0.0)
    
    Returns:
        float: The converted value or default
    """
    if value is None:
        return default
    
    if isinstance(value, float):
        return value
    
    if isinstance(value, Decimal):
        return float(value)
    
    try:
        return float(str(value))
    except (ValueError, TypeError, ArithmeticError):
        return default


def safe_add(*values: Union[str, int, float, Decimal, None]) -> Decimal:
    """
    Safely add multiple values together, handling type conversions.
    
    Args:
        *values: Variable number of values to add
    
    Returns:
        Decimal: The sum of all values
    """
    result = Decimal('0')
    for value in values:
        result += to_decimal(value)
    return result


def safe_subtract(minuend: Union[str, int, float, Decimal, None], 
                 subtrahend: Union[str, int, float, Decimal, None]) -> Decimal:
    """
    Safely subtract two values, handling type conversions.
    
    Args:
        minuend: The value to subtract from
        subtrahend: The value to subtract
    
    Returns:
        Decimal: The difference
    """
    return to_decimal(minuend) - to_decimal(subtrahend)


def safe_multiply(*values: Union[str, int, float, Decimal, None]) -> Decimal:
    """
    Safely multiply multiple values together, handling type conversions.
    
    Args:
        *values: Variable number of values to multiply
    
    Returns:
        Decimal: The product of all values
    """
    result = Decimal('1')
    for value in values:
        result *= to_decimal(value)
    return result


def safe_divide(dividend: Union[str, int, float, Decimal, None], 
               divisor: Union[str, int, float, Decimal, None], 
               default: Decimal = Decimal('0')) -> Decimal:
    """
    Safely divide two values, handling type conversions and division by zero.
    
    Args:
        dividend: The value to divide
        divisor: The value to divide by
        default: Default value if division by zero (default: Decimal('0'))
    
    Returns:
        Decimal: The quotient or default
    """
    dividend_decimal = to_decimal(dividend)
    divisor_decimal = to_decimal(divisor)
    
    if divisor_decimal == 0:
        return default
    
    return dividend_decimal / divisor_decimal


def format_currency(value: Union[str, int, float, Decimal, None], 
                   decimal_places: int = 2) -> str:
    """
    Format a value as currency string.
    
    Args:
        value: The value to format
        decimal_places: Number of decimal places (default: 2)
    
    Returns:
        str: Formatted currency string
    """
    decimal_value = to_decimal(value)
    return f"${decimal_value:.{decimal_places}f}"


def is_amount_equal(amount1: Union[str, int, float, Decimal, None], 
                   amount2: Union[str, int, float, Decimal, None], 
                   tolerance: Decimal = Decimal('0.01')) -> bool:
    """
    Check if two amounts are equal within a tolerance (for floating point precision).
    
    Args:
        amount1: First amount to compare
        amount2: Second amount to compare
        tolerance: Tolerance for comparison (default: Decimal('0.01'))
    
    Returns:
        bool: True if amounts are equal within tolerance
    """
    diff = abs(to_decimal(amount1) - to_decimal(amount2))
    return diff <= tolerance


def round_decimal(value: Union[str, int, float, Decimal, None], 
                 decimal_places: int = 2) -> Decimal:
    """
    Round a decimal value to specified decimal places.
    
    Args:
        value: The value to round
        decimal_places: Number of decimal places (default: 2)
    
    Returns:
        Decimal: Rounded value
    """
    decimal_value = to_decimal(value)
    return decimal_value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def convert_model_amounts_to_decimal(data: dict) -> dict:
    """
    Convert all amount-related fields in a dictionary to Decimal.
    Useful for processing model data before calculations.
    
    Args:
        data: Dictionary containing model data
    
    Returns:
        dict: Dictionary with amount fields converted to Decimal
    """
    amount_fields = [
        'total_amount', 'delivery_charge', 'platform_fee', 'cod_amount_collected',
        'amount', 'balance', 'amount_submitted', 'price'
    ]
    
    result = data.copy()
    for field in amount_fields:
        if field in result:
            result[field] = to_decimal(result[field])
    
    return result


def convert_model_amounts_to_float(data: dict) -> dict:
    """
    Convert all amount-related fields in a dictionary to float.
    Useful for API responses and frontend compatibility.
    
    Args:
        data: Dictionary containing model data
    
    Returns:
        dict: Dictionary with amount fields converted to float
    """
    amount_fields = [
        'total_amount', 'delivery_charge', 'platform_fee', 'cod_amount_collected',
        'amount', 'balance', 'amount_submitted', 'price'
    ]
    
    result = data.copy()
    for field in amount_fields:
        if field in result:
            result[field] = to_float(result[field])
    
    return result
