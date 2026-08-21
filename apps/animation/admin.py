from django.contrib import admin

from .models import AnimationFrame, AnimationLayer, AnimationProject


class AnimationLayerInline(admin.TabularInline):
    model = AnimationLayer
    extra = 0


class AnimationFrameInline(admin.TabularInline):
    model = AnimationFrame
    extra = 0


@admin.register(AnimationProject)
class AnimationProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "scene", "fps", "updated_at")
    list_filter = ("fps",)
    search_fields = ("title",)
    inlines = [AnimationLayerInline, AnimationFrameInline]


@admin.register(AnimationLayer)
class AnimationLayerAdmin(admin.ModelAdmin):
    list_display = ("name", "animation", "kind", "visible", "order")
    list_filter = ("kind", "visible")


@admin.register(AnimationFrame)
class AnimationFrameAdmin(admin.ModelAdmin):
    list_display = ("animation", "index", "updated_at")
    list_filter = ("animation",)