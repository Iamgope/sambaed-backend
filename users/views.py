from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from base.decorators import handle_exception
from base.response import status_200, status_400

from users.serializers import UserFeedbackSerializer, UserProfileSerializer
from users.selectors import get_user_feedbacks, get_user_profile
from users.services import create_feedback


# Create your views here.
class GetUserProfileView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @handle_exception
    def get(self, request):
        user = request.user
        user_profile = get_user_profile(user_id=user.id)
        return status_200(message="User profile fetched", data={"user": UserProfileSerializer(user_profile).data})


class FeedbackView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @handle_exception
    def get(self, request):
        feedbacks = get_user_feedbacks(user_id=request.user.id)
        return status_200(
            message="Feedbacks fetched",
            data={"feedbacks": UserFeedbackSerializer(feedbacks, many=True).data},
        )

    @handle_exception
    def post(self, request):
        serializer = UserFeedbackSerializer(data=request.data)
        if not serializer.is_valid():
            return status_400(message="Invalid data", data=serializer.errors)
        feedback = create_feedback(
            user=request.user,
            feedback_type=serializer.validated_data["feedback_type"],
            title=serializer.validated_data["title"],
            message=serializer.validated_data["message"],
        )
        return status_200(
            message="Feedback submitted",
            data={"feedback": UserFeedbackSerializer(feedback).data},
        )

