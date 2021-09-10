from django.contrib.auth import get_user_model
from rest_framework import serializers

import fullctl.django.models as models
from fullctl.django.rest.decorators import serializer_registry
from fullctl.django.rest.serializers import ModelSerializer

Serializers, register = serializer_registry()


@register
class User(ModelSerializer):

    ref_tag = "user"

    class Meta:
        model = get_user_model()
        fields = ["username", "first_name", "last_name", "email"]


@register
class Organization(ModelSerializer):
    class Meta:
        model = models.Organization
        fields = ["name", "slug", "personal", "backend", "remote_id"]


@register
class OrganizationUser(serializers.Serializer):

    ref_tag = "orguser"
    user = serializers.IntegerField()
    orgs = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)

    class Meta:
        fields = ["user", "orgs"]

    def save(self):
        user = get_user_model().objects.get(id=self.validated_data["user"])
        for remote_org_id in self.validated_data["orgs"]:
            try:
                org = models.Organization.objects.get(remote_id=remote_org_id)
            except models.Organization.DoesNotExist:
                continue

            if not user.org_set.filter(org=org).exists():
                models.OrganizationUser.objects.create(org=org, user=user)

        for orguser in user.org_set.all():
            if orguser.org.remote_id not in self.validated_data["orgs"]:
                orguser.delete()


@register
class ExpireSession(serializers.Serializer):

    username = serializers.CharField()

    ref_tag = "expire_session"

    class Meta:
        fields = ["username"]
