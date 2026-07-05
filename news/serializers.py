from rest_framework import serializers

from news.models import Perspective, TopicNews


class TopicNewsSerializer(serializers.ModelSerializer):
    class Meta:
        model = TopicNews
        fields = ("id", "topic", "content", "pro_content", "con_content")


class PerspectiveSerializer(serializers.ModelSerializer):
    article = serializers.SerializerMethodField()
    perspective = serializers.SerializerMethodField()

    class Meta:
        model = Perspective
        fields = (
            "id",
            "status",
            "debatable",
            "drop_reason",
            "article",
            "perspective",
            "created_at",
        )

    def get_article(self, obj):
        return {
            "title": obj.event_title,
            "context": obj.event_context,
            "source": obj.event_source,
            "date": obj.event_date,
            "url": obj.source_event_url,
        }

    def get_perspective(self, obj):
        if not obj.debatable:
            return None
        return {
            "question": obj.question,
            "context_2line": obj.context_2line,
            "view_1": {"label": obj.view_1_label, "view": obj.view_1_text},
            "view_2": {"label": obj.view_2_label, "view": obj.view_2_text},
        }
