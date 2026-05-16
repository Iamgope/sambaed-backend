from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from base.decorators import handle_exception
from base.response import status_200

from news.selectors import get_latest_perspectives
from news.serializers import PerspectiveSerializer, TopicNewsSerializer
from news.services import fetch_world_events, get_topic_news_data_by_topic_id


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


class EventListView(APIView):
    @handle_exception
    def get(self, request):
        limit = int(request.query_params.get("limit", 50))
        time_filter = request.query_params.get("time", "week")
        events = fetch_world_events(limit=limit, time_filter=time_filter)
        return status_200(
            message="Events fetched",
            data={"events": events, "count": len(events)},
        )


class PerspectiveListView(APIView):
    @handle_exception
    def get(self, request):
        status = request.query_params.get("status")
        perspectives = get_latest_perspectives(status=status)
        return status_200(
            message="Perspectives fetched",
            data={
                "perspectives": PerspectiveSerializer(perspectives, many=True).data,
                "count": perspectives.count(),
            },
        )
