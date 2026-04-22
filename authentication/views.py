from rest_framework.views import APIView

from authentication.services import (
    create_user_by_google_data,
    generate_google_login_url,
    get_jwt_access_token,
    get_user_data_from_google_code,
)
from base.decorators import handle_exception
from base.response import status_200


# Create your views here.
class GoogleLogin(APIView):

    def get(self, request, *args, **kwargs):
        login_url = generate_google_login_url()
        return status_200(message="Login successful", data={"url": login_url})

    def post(self, request, *args, **kwargs):
        code = request.GET.get("code", None)
        user_data = get_user_data_from_google_code(code=code)
        user, is_created = create_user_by_google_data(data=user_data)
        access_token = get_jwt_access_token(user=user)
        return status_200(message="Login successful", data={"is_new_user": is_created, "access_token": access_token})


class GoogleLoginCallback(APIView):

    @handle_exception
    def post(self, request, *args, **kwargs):
        code = request.data.get("code", None)
        user_data = get_user_data_from_google_code(code=code)
        user, is_created = create_user_by_google_data(data=user_data)
        access_token = get_jwt_access_token(user=user)
        return status_200(
            message="Login successful",
            data={
                "is_new_user": is_created, "access_token": access_token
            }
        )
