from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from base.decorators import handle_exception
from base.response import status_200, status_400

from debate.constants import DebateStatus
from debate.models import Message, Judgement
from debate.selectors import get_active_topics, get_debates_by_status, get_user_debates, get_debate
from debate.services import submit_message, dispute_judgement
from debate.serializers import (
    TopicSerializer,
    DebateListSerializer,
    DebateDetailSerializer,
    JudgementSerializer,
    SubmitMessageSerializer,
    MessageSerializer,
)


class TopicListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @handle_exception
    def get(self, request):
        topics = get_active_topics()
        return status_200(message="Topics fetched", data={"topics": TopicSerializer(topics, many=True).data})


class DebateListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @handle_exception
    def get(self, request):
        debates = get_user_debates(user=request.user)
        return status_200(message="Debates fetched", data={"debates": DebateListSerializer(debates, many=True).data})

class OngoingDebateListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @handle_exception
    def get(self, request):
        debates = get_debates_by_status(status=DebateStatus.ONGOING)
        return status_200(
            message="Ongoing debates fetched",
            data={
                "debates": DebateListSerializer(debates, many=True).data,
            }
        )


class DebateDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @handle_exception
    def get(self, request, debate_id):
        debate = get_debate(debate_id=debate_id)
        if request.user not in (debate.user_pro, debate.user_con):
            return status_400(message="You are not a participant in this debate")
        return status_200(message="Debate fetched", data=DebateDetailSerializer(debate).data)


class MessageListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @handle_exception
    def get(self, request, debate_id):
        debate = get_debate(debate_id=debate_id)
        if request.user not in (debate.user_pro, debate.user_con):
            return status_400(message="You are not a participant in this debate")
        messages = (
            Message.objects
            .filter(debate=debate)
            .select_related('user', 'round')
            .order_by('created_at')
        )
        return status_200(message="Messages fetched", data={"messages": MessageSerializer(messages, many=True).data})

    @handle_exception
    def post(self, request, debate_id):
        serializer = SubmitMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return status_400(message="Invalid data", data=serializer.errors)

        message, _ = submit_message(
            user=request.user,
            debate_id=debate_id,
            content=serializer.validated_data['content'],
        )
        return status_200(message="Message submitted", data=MessageSerializer(message).data)


class JudgementView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @handle_exception
    def get(self, request, debate_id):
        debate = get_debate(debate_id=debate_id)
        if request.user not in (debate.user_pro, debate.user_con):
            return status_400(message="You are not a participant in this debate")
        try:
            judgement = Judgement.objects.select_related('winner').get(debate=debate)
        except Judgement.DoesNotExist:
            return status_400(message="Judgement not available yet")
        return status_200(message="Judgement fetched", data=JudgementSerializer(judgement).data)


class DisputeView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @handle_exception
    def post(self, request, debate_id):
        judgement = dispute_judgement(user=request.user, debate_id=debate_id)
        return status_200(message="Dispute processed", data=JudgementSerializer(judgement).data)
