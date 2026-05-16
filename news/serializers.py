from rest_framework import serializers

from news.models import TopicNews


class TopicNewsSerializer(serializers.ModelSerializer):
    class Meta:
        model = TopicNews
        fields = ("id", "topic", "content", "pro_content", "con_content")
