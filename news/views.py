from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from base.decorators import handle_exception
from base.exception import ServiceException
from base.response import status_200, status_400

from news.selectors import get_topic_news_by_topic_id
from news.serializers import TopicNewsSerializer
from news.services import get_topic_news_data_by_topic_id


class TopicNewsListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @handle_exception
    def get(self, request, topic_id):
        news = get_topic_news_data_by_topic_id(topic_id=topic_id)
        return status_200(
            message="News fetched",
            data={"news": TopicNewsSerializer(news, many=True).data},
        )
