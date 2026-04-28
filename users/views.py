from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from base.decorators import handle_exception
from base.response import status_200

from users.serializers import UserProfileSerializer
from users.selectors import get_user_profile


# Create your views here.
class GetUserProfileView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @handle_exception
    def get(self, request):
        user = request.user
        user_profile = get_user_profile(user_id=user.id)
        return status_200(message="User profile fetched", data={"user": UserProfileSerializer(user_profile).data})

