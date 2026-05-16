from django.contrib import admin
from unfold.admin import ModelAdmin
from news.models import Perspective, TopicNews


# Register your models here.
@admin.register(TopicNews)
class TopicNewsAdmin(ModelAdmin):
    fields = ("topic", "content", "pro_content", "con_content")
    list_filter = ("topic",)
    search_fields = ("topic",)


@admin.register(Perspective)
class PerspectiveAdmin(ModelAdmin):
    list_display = ("question", "status", "debatable", "created_at")
    list_filter = ("status", "debatable")
    search_fields = ("question", "view_1_label", "view_2_label", "drop_reason")
    readonly_fields = ("created_at",)
    actions = ("approve_selected", "reject_selected")

    @admin.action(description="Approve selected perspectives")
    def approve_selected(self, request, queryset):
        queryset.update(status=Perspective.STATUS_APPROVED)

    @admin.action(description="Reject selected perspectives")
    def reject_selected(self, request, queryset):
        queryset.update(status=Perspective.STATUS_REJECTED)
