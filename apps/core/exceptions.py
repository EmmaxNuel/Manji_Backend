from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    """
    Wrap DRF exceptions in a consistent response shape:
    {
        "success": false,
        "error": { "code": ..., "message": ..., "details": ... }
    }
    """
    response = exception_handler(exc, context)

    if response is not None:
        response.data = {
            "success": False,
            "error": {
                "code": response.status_code,
                "message": _get_message(response.data),
                "details": response.data,
            },
        }
    return response


def _get_message(data):
    if isinstance(data, dict):
        # Use 'detail' key if present, otherwise first value
        detail = data.get("detail", None)
        if detail:
            return str(detail)
        first = next(iter(data.values()), None)
        if isinstance(first, list):
            return str(first[0]) if first else "An error occurred."
        return str(first) if first else "An error occurred."
    if isinstance(data, list) and data:
        return str(data[0])
    return "An error occurred."
