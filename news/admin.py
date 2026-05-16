from django.contrib import admin
from unfold.admin import ModelAdmin
from news.models import TopicNews


# Register your models here.
@admin.register(TopicNews)
class TopicNewsAdmin(ModelAdmin):
    fields = ("topic", "content", "pro_content", "con_content")
    list_filter = ("topic",)
    search_fields = ("topic",)
