from rest_framework import serializers
from django.contrib.auth.models import User

from debate.models import Debate, Round, Message, Judgement, MatchQueue, Topic


class UserMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username']


class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = ['id', 'title', 'description']


class MessageSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(read_only=True)

    class Meta:
        model = Message
        fields = ['id', 'user', 'content', 'created_at', 'round_id']


class RoundSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)

    class Meta:
        model = Round
        fields = ['id', 'round_type', 'order', 'started_at', 'ended_at', 'messages']


class DebateListSerializer(serializers.ModelSerializer):
    topic = TopicSerializer(read_only=True)
    user_pro = UserMinimalSerializer(read_only=True)
    user_con = UserMinimalSerializer(read_only=True)
    winner = UserMinimalSerializer(read_only=True)

    class Meta:
        model = Debate
        fields = ['id', 'topic', 'user_pro', 'user_con', 'winner', 'status', 'started_at', 'completed_at']


class DebateDetailSerializer(serializers.ModelSerializer):
    topic = TopicSerializer(read_only=True)
    user_pro = UserMinimalSerializer(read_only=True)
    user_con = UserMinimalSerializer(read_only=True)
    winner = UserMinimalSerializer(read_only=True)
    rounds = RoundSerializer(many=True, read_only=True)

    class Meta:
        model = Debate
        fields = [
            'id', 'topic', 'user_pro', 'user_con', 'winner',
            'status', 'started_at', 'completed_at', 'rounds',
        ]


class JudgementSerializer(serializers.ModelSerializer):
    winner = UserMinimalSerializer(read_only=True)

    class Meta:
        model = Judgement
        fields = [
            'id', 'winner',
            'argument_score_pro', 'rebuttal_score_pro', 'clarity_score_pro', 'persuasion_score_pro',
            'argument_score_con', 'rebuttal_score_con', 'clarity_score_con', 'persuasion_score_con',
            'reasoning', 'strongest_moment', 'coaching_tip_pro', 'coaching_tip_con',
            'created_at',
        ]


class QueueStatusSerializer(serializers.ModelSerializer):
    topic = TopicSerializer(read_only=True)
    debate_id = serializers.SerializerMethodField()

    class Meta:
        model = MatchQueue
        fields = ['id', 'topic', 'status', 'joined_at', 'matched_at', 'debate_id']

    def get_debate_id(self, obj):
        return obj.debate_id


class JoinQueueSerializer(serializers.Serializer):
    topic_id = serializers.IntegerField()


class SubmitMessageSerializer(serializers.Serializer):
    content = serializers.CharField(max_length=400, min_length=1)
