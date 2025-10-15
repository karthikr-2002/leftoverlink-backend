import logging
import json
import time
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse

# Create a logger for API calls
logger = logging.getLogger('api_calls')

class APILoggingMiddleware(MiddlewareMixin):
    """
    Middleware to log all API calls with request/response details
    """
    
    def process_request(self, request):
        """Log incoming request details"""
        # Store start time for response time calculation
        request._start_time = time.time()
        
        # Get request data
        request_data = {
            'method': request.method,
            'path': request.path,
            'query_params': dict(request.GET),
            'headers': dict(request.headers),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'remote_addr': request.META.get('REMOTE_ADDR', ''),
            'content_type': request.content_type,
        }
        
        # Log request body for POST/PUT/PATCH requests
        if request.method in ['POST', 'PUT', 'PATCH']:
            try:
                if request.content_type == 'application/json':
                    body = json.loads(request.body.decode('utf-8'))
                    request_data['body'] = body
                elif request.content_type == 'application/x-www-form-urlencoded':
                    # Parse form data
                    body = request.POST.dict()
                    request_data['body'] = body
                else:
                    request_data['body'] = request.body.decode('utf-8', errors='ignore')
            except Exception as e:
                request_data['body_error'] = str(e)
                request_data['raw_body'] = request.body.decode('utf-8', errors='ignore')
        
        # Log the request
        logger.info(f"API REQUEST: {request.method} {request.path}")
        logger.info(f"Request Data: {json.dumps(request_data, indent=2, default=str)}")
        
        return None
    
    def process_response(self, request, response):
        """Log response details"""
        # Calculate response time
        response_time = time.time() - getattr(request, '_start_time', 0)
        
        # Get response data
        response_data = {
            'status_code': response.status_code,
            'content_type': response.get('Content-Type', ''),
            'response_time': f"{response_time:.3f}s",
        }
        
        # Log response body for error responses or if it's JSON
        if response.status_code >= 400 or 'application/json' in response.get('Content-Type', ''):
            try:
                if hasattr(response, 'content'):
                    content = response.content.decode('utf-8')
                    if content:
                        try:
                            response_data['body'] = json.loads(content)
                        except json.JSONDecodeError:
                            response_data['body'] = content[:500]  # Limit to 500 chars
            except Exception as e:
                response_data['body_error'] = str(e)
        
        # Log the response
        logger.info(f"API RESPONSE: {request.method} {request.path} - {response.status_code}")
        logger.info(f"Response Data: {json.dumps(response_data, indent=2, default=str)}")
        
        return response
    
    def process_exception(self, request, exception):
        """Log exceptions"""
        response_time = time.time() - getattr(request, '_start_time', 0)
        
        exception_data = {
            'exception_type': type(exception).__name__,
            'exception_message': str(exception),
            'response_time': f"{response_time:.3f}s",
        }
        
        logger.error(f"API EXCEPTION: {request.method} {request.path}")
        logger.error(f"Exception Data: {json.dumps(exception_data, indent=2, default=str)}")
        
        return None
