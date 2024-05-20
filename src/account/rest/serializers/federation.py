from rest_framework import serializers

import account.models.federation as federation_models
from account.rest.serializers import Serializers, register  # noqa F401


@register
class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = federation_models.ServiceFederationSupport
        fields = ["id", "name", "slug"]
        read_only_fields = ["id"]


@register
class ServiceURLSerializer(serializers.ModelSerializer):

    service_name = serializers.SerializerMethodField()

    class Meta:
        model = federation_models.FederatedServiceURL
        fields = ["id", "url", "auth", "service", "service_name", "config"]
        read_only_fields = ["id", "auth", "config"]

    def get_service_name(self, obj):
        return obj.service.name

    def save(self, **kwargs):
        result = super().save(**kwargs)
        self.instance.auth.set_redirect_urls()
        return result


@register
class AddServiceURLSerializer(serializers.Serializer):

    service = serializers.PrimaryKeyRelatedField(
        queryset=federation_models.ServiceFederationSupport.objects.all(),
        required=True,
    )

    url = serializers.URLField(required=True)

    ref_tag = "add_federated_service_url"

    class Meta(ServiceURLSerializer.Meta):
        fields = ["url", "service"]

    def validate(self, data):
        # we only allow one service url per service
        auth = self.context["auth"]

        if federation_models.FederatedServiceURL.objects.filter(
            service=data["service"], auth=auth
        ).exists():
            raise serializers.ValidationError(
                "Service URL for this service already exists."
            )

        return data

    def save(self, **kwargs):
        validated_data = self.validated_data
        auth = validated_data["auth"] = self.context["auth"]
        service_url = federation_models.FederatedServiceURL.objects.create(
            url=validated_data["url"], service=validated_data["service"], auth=auth
        )
        auth.set_redirect_urls()
        return service_url


class ServiceURLInlineSerializer(ServiceURLSerializer):
    class Meta(ServiceURLSerializer.Meta):
        fields = ["id", "url", "service"]
        read_only_fields = ["id", "service", "service_name"]


@register
class AuthFederationSerializer(serializers.ModelSerializer):

    federated_service_urls = ServiceURLInlineSerializer(many=True, read_only=True)

    client_id = serializers.SerializerMethodField()
    client_secret = serializers.SerializerMethodField()

    class Meta:
        model = federation_models.AuthFederation
        fields = ["id", "org", "federated_service_urls", "client_id", "client_secret"]
        read_only_fields = ["id", "org", "federated_service_urls"]

    def get_client_id(self, obj):
        return obj.application.client_id

    def get_client_secret(self, obj):
        # client secret will be set in context if it was
        # just created, and will be unhashed.
        #
        # Otherwise, we'll pull it from the application and return
        # the encrypted version
        return self.context.get("client_secret", obj.application.client_secret)
