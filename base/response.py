from typing import Dict, Optional
from rest_framework import status
from rest_framework.response import Response


def status_200(*, message: str, data: Optional[Dict] = None) -> Response:
    """
    Generate a status 200 response dictionary.
    """
    # Create the base response dictionary
    response = {
        "status": 200,
        "message": message
    }

    # If data is provided, add it to the response
    if data is not None:
        response["data"] = data

    # Return the response dictionary
    return Response(response, status=status.HTTP_200_OK)


def status_400(*, message: str, data: Optional[Dict] = None) -> Response:
    """
    Generate a status 400 response dictionary.
    """
    # Create the base response dictionary
    response = {
        "status": 400,
        "message": message
    }

    # If data is provided, add it to the response
    if data is not None:
        response["data"] = data

    # Return the response dictionary
    return Response(response, status=status.HTTP_400_BAD_REQUEST)


def status_500(*, message: str, data: Optional[Dict] = None) -> Response:
    """
    Generate a status 500 response dictionary.
    """
    # Create the base response dictionary
    response = {
        "status": 500,
        "message": message
    }

    # If data is provided, add it to the response
    if data is not None:
        response["data"] = data

    # Return the response dictionary
    return Response(response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
