import fullctl.django.rest.throttle as throttle
import reversion
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django_grainy.helpers import str_flags
from django_grainy.util import get_permissions
from fullctl.django.auditlog import auditlog
from fullctl.django.decorators import origin_allowed
from fullctl.django.rest.core import BadRequest
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

import account.models as models
import account.models.federation as federation_models
import account.rest.serializers.federation
import applications.rest.serializers as application_serializers
from account.rest.decorators import disable_api_key, set_org
from account.rest.route import route
from account.rest.serializers import Serializers
from account.session import set_selected_org
from applications.models import Service
from common.rest.decorators import grainy_endpoint, user_endpoint


@route
class UserInformation(viewsets.ViewSet):
    serializer_class = Serializers.user
    queryset = Serializers.user.Meta.model.objects.all()

    @user_endpoint()
    def list(self, request):
        serializer = Serializers.user(request.user)
        return Response(serializer.data)

    @user_endpoint()
    def put(self, request):
        if request.user.has_usable_password():
            serializer = Serializers.userpasswordprotected(
                data=request.data,
                many=False,
                context={"user": request.user},
            )
        else:
            serializer = Serializers.user(
                data=request.data,
                many=False,
                context={"user": request.user},
            )

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=["PUT"])
    @user_endpoint()
    @disable_api_key
    def user_settings(self, request):
        serializer = Serializers.user_settings(
            instance=request.user.user_settings,
            data=request.data,
            many=False,
            context={"user": request.user, "request": request},
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=["PUT"])
    @auditlog()
    @user_endpoint()
    @disable_api_key
    def set_password(self, request, auditlog=None):
        serializer = Serializers.pwd(
            data=request.data,
            many=False,
            context={"user": request.user, "request": request},
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        serializer.save()

        auditlog.log("set_password")

        return Response(serializer.data)

    @action(detail=False, methods=["POST"])
    @user_endpoint()
    def resend_confirmation_mail(self, request):
        user_settings, created = models.UserSettings.objects.get_or_create(
            user=request.user
        )

        if user_settings.email_confirmed:
            return Response(
                {"non_field_errors": [_("Email address already confirmed")]}, status=400
            )

        models.EmailConfirmation.start(request.user)

        return Response({})

    @action(detail=False)
    @user_endpoint()
    @disable_api_key
    def keys(self, request):
        user = request.user
        queryset = models.APIKey.objects.filter(user__id=user.id)
        serializer = Serializers.key(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False)
    @user_endpoint()
    @disable_api_key
    def invites(self, request):
        user = request.user
        queryset = models.Invitation.objects.filter(email=user.email)
        serializer = Serializers.invite(queryset, many=True)
        return Response(serializer.data)

    @action(
        detail=False, methods=["POST"], url_path="accept-invite/(?P<invite_id>[^/.]+)"
    )
    @user_endpoint()
    @disable_api_key
    def accept_invite(self, request, invite_id=None):
        user = request.user
        invite = models.Invitation.objects.get(email=user.email, id=invite_id)
        serializer = Serializers.invite(invite)
        data = serializer.data
        invite.complete(user)
        return Response(data)

    @action(
        detail=False, methods=["POST"], url_path="reject-invite/(?P<invite_id>[^/.]+)"
    )
    @user_endpoint()
    @disable_api_key
    def reject_invite(self, request, invite_id=None):
        user = request.user
        invite = models.Invitation.objects.get(email=user.email, id=invite_id)
        serializer = Serializers.invite(invite)
        data = serializer.data
        invite.delete()
        return Response(data)

    @action(detail=False, methods=["POST"], url_path="set-default-org")
    @user_endpoint()
    @disable_api_key
    def set_default_org(self, request):
        if not request.selected_org:
            return Response({"non_field_errors": ["no org selected"]}, status=400)

        request.selected_org.set_as_default(request.user)

        return Response({})

    @action(detail=False, methods=["POST"])
    @auditlog()
    @user_endpoint()
    @disable_api_key
    def create_key(self, request, auditlog=None):
        context = {"user": request.user}
        data = dict(request.data)
        data.update(user=request.user.id)
        serializer = Serializers.key(data=data, many=False, context=context)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        key = serializer.save()
        return Response(Serializers.key(key, many=False).data)

    @action(detail=False, methods=["DELETE"])
    @auditlog()
    @user_endpoint()
    @disable_api_key
    def key(self, request, auditlog=None):
        key = models.APIKey.objects.get(id=request.data.get("id"), user=request.user)
        response = Response(Serializers.key(instance=key, many=False).data)
        key.delete()
        return response

    def get_throttles(self):
        if self.action in ["resend_confirmation_mail"]:
            self.throttle_scope = "resend_email"
        return super().get_throttles()


@route
class Organization(viewsets.ViewSet):
    serializer_class = Serializers.org
    queryset = models.Organization.objects.all()

    @user_endpoint()
    def list(self, request):
        # get array of Organization instance that the user
        # is allowed to access and sort them by name

        organizations = models.Organization.get_for_user(request.user)
        organizations = sorted(organizations, key=lambda x: x.label.lower())

        serializer = Serializers.org(
            organizations,
            many=True,
            context={
                "user": request.user,
                "selected_org": getattr(request, "selected_org", None),
            },
        )
        return Response(serializer.data)

    @set_org
    @grainy_endpoint("org.{org.id}")
    def retrieve(self, request, pk, org):
        org = models.Organization.objects.get(slug=pk)
        serializer = Serializers.org(org, many=False, context={"user": request.user})
        return Response(serializer.data)

    @action(detail=False, methods=["POST"])
    @user_endpoint()
    @disable_api_key
    def select(self, request):
        org_id = request.data.get("id")
        userorg = models.OrganizationUser.objects.get(
            user_id=request.user.id, org_id=org_id
        )
        set_selected_org(request, userorg.org)
        return Response(
            Serializers.org(userorg.org, context={"user": request.user}).data
        )

    @auditlog()
    @user_endpoint()
    def create(self, request, auditlog=None):
        serializer = Serializers.org(
            data=request.data, many=False, context={"user": request.user}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        org = serializer.save()

        auditlog.set("org", org)

        if not hasattr(request, "api_key"):
            set_selected_org(request, org)
        return Response(
            Serializers.org(org, many=False, context={"user": request.user}).data
        )

    @set_org
    @auditlog()
    @grainy_endpoint("org.{org.id}.manage", explicit=False)
    def update(self, request, pk, org, auditlog=None):
        user = request.user

        # personal organizations cannot be edited
        if org.is_personal:
            return Response(
                {"non_field_errors": [_("Personal organizations cannot be changed.")]},
                status=403,
            )

        if user.has_usable_password():
            serializer = Serializers.orgeditpwdprotected(
                instance=org,
                data=request.data,
                many=False,
                context={"user": user, "org": org},
            )
        else:
            serializer = Serializers.orgedit(
                instance=org,
                data=request.data,
                many=False,
                context={"user": user, "org": org},
            )

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        org = serializer.save()

        auditlog.set("org", org)

        return Response(
            Serializers.org(org, many=False, context={"user": request.user}).data
        )

    @action(detail=True, methods=["GET"])
    @set_org
    @grainy_endpoint("user.{org.id}", explicit=False)
    def users(self, request, pk, org):
        serializer = Serializers.org_user(
            org.org_user_set.all(),
            many=True,
            context={
                "user": request.user,
                "services": [svc for svc in Service.objects.all()],
                "perms": request.perms,
            },
        )
        return Response(serializer.data)

    @action(detail=True, methods=["DELETE"])
    @set_org
    @auditlog()
    @grainy_endpoint("user.{org.id}", explicit=False)
    def user(self, request, pk, org, auditlog=None):
        org_user = models.OrganizationUser.objects.get(
            id=request.data.get("id"), org=org
        )
        if org_user.user == request.user:
            return Response(
                {
                    "non_field_errors": [
                        _(
                            "Cannot remove yourself from the organization through this endpoint"
                        )
                    ]
                },
                status=400,
            )

        org.remove_user(org_user.user)

        return Response(Serializers.org_user(instance=org_user, many=False).data)

    @action(detail=True, methods=["DELETE"])
    @set_org
    @auditlog()
    @user_endpoint()
    def leave_org(self, request, pk, org, auditlog=None):
        role = models.Role.objects.get(name="Admin")
        org_admins = models.OrganizationRole.objects.filter(org=org, role=role)
        # check if user is the only admin
        if len(org_admins) == 1 and org_admins.first().user == request.user:
            return Response(
                {
                    "non_field_errors": [
                        _(
                            "Cannot remove yourself as you are the only admin for the org."
                        )
                    ]
                },
                status=400,
            )

        org_user = models.OrganizationUser.objects.get(user=request.user, org=org)

        org.remove_user(request.user)

        return Response(Serializers.org_user(instance=org_user, many=False).data)

    @action(detail=True, methods=["POST"])
    @set_org
    @auditlog()
    @grainy_endpoint("user.{org.id}", explicit=False)
    def add_role(self, request, pk, org, auditlog=None):
        user = models.OrganizationUser.objects.get(
            id=request.data.get("org_user")
        ).user_id
        role = models.Role.objects.get(id=request.data.get("role"))

        if models.OrganizationRole.objects.filter(
            org=org, user=user, role=role
        ).exists():
            return BadRequest({"non_field_errors": [_("User already has this role")]})

        serializer = Serializers.org_user_role(
            data={
                "org": org.id,
                "user": user,
                "role": request.data.get("role"),
            },
            many=False,
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=["POST"])
    @set_org
    @auditlog()
    @grainy_endpoint("user.{org.id}", explicit=False)
    def remove_role(self, request, pk, org, auditlog=None):
        user = models.OrganizationUser.objects.get(
            id=request.data.get("org_user")
        ).user_id
        role = models.Role.objects.get(id=request.data.get("role"))
        user_role = models.OrganizationRole.objects.get(org=org, user=user, role=role)
        serializer = Serializers.org_user_role(user_role)
        response = Response(serializer.data)
        user_role.delete()
        return response

    @action(detail=True, methods=["PUT"])
    @set_org
    @auditlog()
    @grainy_endpoint("user.{org.id}", explicit=False)
    def set_permissions(self, request, pk, org, auditlog=None):
        serializer = Serializers.org_userperm(
            data={
                "org": org.id,
                "org_user": request.data.get("id"),
                "component": request.data.get("component"),
                "permissions": request.data.get("permissions"),
            },
            many=False,
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        serializer.save()

        return Response(serializer.data)

    @action(detail=True, methods=["POST"])
    @set_org
    @auditlog()
    @grainy_endpoint("user.{org.id}", explicit=False)
    def remove_permissions(self, request, pk, org, auditlog=None):
        override = models.UserPermissionOverride.objects.get(
            org=org, id=request.data.get("id")
        )
        user = override.user
        namespace = override.namespace
        override.delete()
        permissions = get_permissions(
            get_user_model().objects.get(id=user.id), namespace
        )

        return Response({"perms": str_flags(permissions)})

    @action(detail=True, methods=["GET"])
    @set_org
    @grainy_endpoint("org_key.{org.id}", explicit=False)
    def keys(self, request, pk, org):
        serializer = Serializers.org_key(
            org.org_key_set.filter(managed=True),
            many=True,
            context={
                "user": request.user,
                "services": [svc for svc in Service.objects.all()],
                "perms": request.perms,
            },
        )
        return Response(serializer.data)

    @action(detail=True, methods=["PUT"])
    @set_org
    @auditlog()
    @grainy_endpoint("org_key.{org.id}", explicit=False)
    def set_key_details(self, request, pk, org, auditlog=None):
        """
        Edit the name and email of an OrganizationAPIKey
        """
        org_key = models.OrganizationAPIKey.objects.get(
            id=request.data.get("id"), org=org
        )
        serializer = Serializers.org_key(
            instance=org_key,
            many=False,
        )

        data = serializer.data
        data.update(request.data)

        context = {"user": request.user, "org": org}
        serializer = Serializers.org_key(
            instance=org_key, data=data, many=False, context=context
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        serializer.save()

        return Response(serializer.data)

    @action(detail=True, methods=["PUT"])
    @set_org
    @auditlog()
    @grainy_endpoint("org_key.{org.id}", explicit=False)
    def set_key_permissions(self, request, pk, org, auditlog=None):
        serializer = Serializers.org_key_permission(
            data={
                "org": org.id,
                "org_key": request.data.get("id"),
                "component": request.data.get("component"),
                "permissions": request.data.get("permissions"),
            },
            many=False,
        )

        org_key = models.OrganizationAPIKey.objects.get(
            org=org, id=request.data.get("id")
        )

        if not org_key.managed:
            return Response({"id": ["not a managed key"]}, status=400)

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        serializer.save()

        return Response(serializer.data)

    @action(detail=True, methods=["DELETE"])
    @set_org
    @auditlog()
    @grainy_endpoint("org_key.{org.id}", explicit=False)
    def key(self, request, pk, org, auditlog=None):
        org_key = models.OrganizationAPIKey.objects.get(
            id=request.data.get("id"), org=org
        )
        response = Response(Serializers.org_key(instance=org_key, many=False).data)
        org_key.delete()

        return response

    @action(detail=True, methods=["POST"])
    @set_org
    @auditlog()
    @grainy_endpoint("org_key.{org.id}", explicit=False)
    def create_key(self, request, pk, org, auditlog=None):
        context = {"user": request.user, "org": org}
        data = dict(request.data)
        data.update(org=org.id)
        serializer = Serializers.org_key(data=data, many=False, context=context)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        org_key = serializer.save()

        # TODO: api key roles

        for mperm in models.ManagedPermission.objects.all():
            if mperm.can_grant_to_org(org):
                models.OrganizationAPIKeyPermission.objects.create(
                    api_key=org_key,
                    namespace=mperm.namespace.format(org_id=org.id),
                    permission=0x01,
                )

        return Response(Serializers.org_key(org_key, many=False).data)

    @action(detail=True, methods=["GET"])
    @set_org
    @grainy_endpoint("org.{org.id}")
    def federated_auth(self, request, pk, org):
        auth = federation_models.AuthFederation.objects.get(org=org)
        serializer = Serializers.auth_federation(auth, many=False)
        return Response(serializer.data)

    @action(detail=True, methods=["POST"])
    @set_org
    @auditlog()
    @grainy_endpoint("org.{org.id}")
    def create_federated_auth(self, request, pk, org, auditlog=None):

        # only one application per organization
        if federation_models.AuthFederation.objects.filter(org=org).exists():
            return Response(
                {
                    "non_field_errors": [
                        _("An OAuth application already exists for this organization.")
                    ]
                },
                status=400,
            )

        auth = federation_models.AuthFederation.create_for_org(org, request.user)
        ctx = {"client_secret": auth.client_secret}
        serializer = Serializers.auth_federation(auth.auth, many=False, context=ctx)
        return Response(serializer.data)

    @action(detail=True, methods=["POST"])
    @set_org
    @auditlog()
    @grainy_endpoint("org.{org.id}")
    def regenerate_federated_auth(self, request, pk, org, auditlog=None):
        auth = federation_models.AuthFederation.objects.get(org=org)
        info = auth.new_client_secret()
        ctx = {"client_secret": info.client_secret}
        serializer = Serializers.auth_federation(auth, many=False, context=ctx)
        return Response(serializer.data)

    @action(detail=True, methods=["GET"])
    @set_org
    @grainy_endpoint("org.{org.id}")
    def federated_service_urls(self, request, pk, org):
        urls = federation_models.FederatedServiceURL.objects.filter(auth__org=org)
        serializer = Serializers.federated_service_url(urls, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["POST"])
    @set_org
    @auditlog()
    @grainy_endpoint("org.{org.id}")
    def add_federated_service_url(self, request, pk, org, auditlog=None):
        auth = federation_models.AuthFederation.objects.get(org=org)
        serializer = Serializers.add_federated_service_url(
            data=request.data, many=False, context={"auth": auth}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        serializer.save()
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["PUT"],
        url_path="update_federated_service_url/(?P<url_pk>[^/.]+)",
    )
    @set_org
    @auditlog()
    @grainy_endpoint("org.{org.id}")
    def update_federated_service_url(self, request, pk, url_pk, org, auditlog=None):
        url = federation_models.FederatedServiceURL.objects.get(
            id=url_pk, auth__org=org
        )
        serializer = Serializers.federated_service_url(
            instance=url, data=request.data, many=False
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=["DELETE"])
    @set_org
    @auditlog()
    @grainy_endpoint("org.{org.id}")
    def remove_federated_service_url(self, request, pk, org, auditlog=None):
        url = federation_models.FederatedServiceURL.objects.get(
            id=request.data.get("id"), auth__org=org
        )
        serializer = Serializers.federated_service_url(url)
        response = Response(serializer.data)
        url.delete()
        return response

    @action(detail=True, methods=["GET"])
    @set_org
    @auditlog()
    @grainy_endpoint("org.{org.id}")
    def federated_services(self, request, pk, org, auditlog=None):
        services = federation_models.ServiceFederationSupport.objects.all()
        serializer = Serializers.federated_service(services, many=True)
        response = Response(serializer.data)

        return response

    @action(detail=True, methods=["GET"])
    @set_org
    @grainy_endpoint("user.{org.id}", explicit=False)
    def invites(self, request, pk, org):
        invitations = models.Invitation.objects.filter(org__slug=pk)
        serializer = Serializers.invite(invitations, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["POST", "DELETE"])
    @set_org
    @auditlog()
    @grainy_endpoint("user.{org.id}", explicit=False)
    def invite(self, request, pk, org, auditlog=None):
        """
        Will either create or resend an invite, or delete an invite based on email
        passed in request.data
        """

        if request.method == "POST":
            return self._create_or_resend_invite(request, org)
        elif request.method == "DELETE":
            return self._delete_invite(request, org)

    @action(detail=True, methods=["GET"])
    @set_org
    @grainy_endpoint("user.{org.id}", explicit=False)
    def services(self, request, pk, org):
        services = {svc.slug: svc for svc in Service.objects.all()}

        # loading for specific org, so we need to check if there
        # is service federation setup and replace the service
        # with the federated service

        for fed_svc_url in federation_models.FederatedServiceURL.objects.filter(
            auth__org=org
        ):
            services[fed_svc_url.service.slug] = Service.from_federated_service_url(
                fed_svc_url
            )

        services = list(services.values())
        serializer = application_serializers.Serializers.service_application(
            services, many=True
        )
        return Response(serializer.data)

    def _create_or_resend_invite(self, request, org):
        """
        Will create an invite if one does not exist, or resend an invite if one does exist.

        Invite will be created for `email` passed in request.data
        """
        context = {"user": request.user, "org": org}
        serializer = Serializers.invite(data=request.data, many=False, context=context)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        invite = serializer.save()
        return Response(Serializers.invite(invite, many=False).data)

    def _delete_invite(self, request, org):
        """
        Deletes an invitation.

        Invite will be deleted for `email` passed in request.data
        """
        email = request.data.get("email")
        invites = models.Invitation.objects.filter(email=email, org=org)
        response_data = Serializers.invite(invites, many=True).data
        invites.delete()
        return Response(response_data)

    def get_throttles(self):
        if self.action in ["invite"]:
            self.throttle_scope = "invite"
        return super().get_throttles()


@route
class PasswordReset(viewsets.ViewSet):
    ref_tag = "password_reset"
    serializer_class = Serializers.start_password_reset
    queryset = models.PasswordReset.objects.all()

    @action(detail=False, methods=["POST"], permission_classes=[AllowAny])
    @reversion.create_revision()
    def start(self, request):
        serializer = Serializers.start_password_reset(data=request.data, many=False)

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        password_reset = serializer.save()
        return Response(
            Serializers.start_password_reset(password_reset, many=False).data
        )

    @action(detail=False, methods=["POST"], permission_classes=[AllowAny])
    @reversion.create_revision()
    def complete(self, request):
        serializer = Serializers.password_reset(data=request.data, many=False)

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        password_reset = serializer.save()
        messages.info(request, _("Password has been updated"))
        return Response(Serializers.password_reset(password_reset, many=False).data)

    def get_throttles(self):
        if self.action in ["start"]:
            self.throttle_scope = "password_reset"
        return super().get_throttles()


@route
class Contact(viewsets.ViewSet):
    ref_tag = "contact"
    serializer_class = Serializers.contact_message
    queryset = models.ContactMessage.objects.all()
    permission_classes = [AllowAny]
    throttle_classes = [throttle.ContactMessage]

    @csrf_exempt
    def create(self, request):
        @origin_allowed(settings.CONTACT_ALLOWED_ORIGINS)
        def _create(request):
            serializer = Serializers.contact_message(
                data=request.data, many=False, context={"user": request.user}
            )

            if not serializer.is_valid():
                return Response(serializer.errors, status=400)

            contact = serializer.save()
            contact.notify()
            return Response(serializer.data)

        return _create(request)
