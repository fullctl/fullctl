from fullctl.django.rest.decorators import serializer_registry
from fullctl.django.rest.serializers import ModelSerializer
from fullctl.django.rest.serializers.template import TemplateSerializer
from rest_framework import serializers

import django_aclctl.models as models

Serializers, register = serializer_registry()


@register
class AccessControlList(ModelSerializer):

    num_filters = serializers.SerializerMethodField()

    class Meta:
        model = models.AccessControlList
        fields = ["instance", "name", "slug", "id", "num_filters"]

    def get_num_filters(self, obj):
        return obj.filter_rules.count()


@register
class FilterRule(ModelSerializer):

    src_prefix_set_name = serializers.SerializerMethodField()
    dest_prefix_set_name = serializers.SerializerMethodField()

    class Meta:
        model = models.FilterRule
        fields = [
            "priority",
            "src_type",
            "src_port",
            "src_prefix",
            "src_prefix_set",
            "src_prefix_set_name",
            "dest_type",
            "dest_port",
            "dest_prefix",
            "dest_prefix_set",
            "dest_prefix_set_name",
            "access_control_list",
        ]

    def get_src_prefix_set_name(self, obj):

        if not obj.src_prefix_set or not hasattr(obj.src_prefix_set, "object"):
            return None

        return obj.src_prefix_set.object.name

    def get_dest_prefix_set_name(self, obj):

        if not obj.dest_prefix_set or not hasattr(obj.dest_prefix_set, "object"):
            return None

        return obj.dest_prefix_set.object.name

    def validate(self, data):

        if (
            not data["src_prefix"]
            and not data["dest_prefix"]
            and not data["src_port"]
            and not data["dest_port"]
        ):
            raise serializers.ValidationError("need to specify destination or source")
        return data


@register
class FilterRuleTemplate(ModelSerializer):

    ref_tag = "filter_rule_template"

    class Meta(TemplateSerializer.Meta):
        model = models.FilterRuleTemplate
        fields = ["id", "name", "instance", "type", "body"]


@register
class FilterRuleConfig(TemplateSerializer):

    ref_tag = "filter_rule_config"

    class Meta(TemplateSerializer.Meta):
        model = models.FilterRuleTemplate
