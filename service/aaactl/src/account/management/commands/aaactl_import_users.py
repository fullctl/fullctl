import csv

from account.models import (
    ManagedPermission,
    ManagedPermissionRoleAutoGrant,
    Organization,
    OrganizationManagedPermission,
    OrganizationUser,
    Role,
)
from django.conf import settings
from django.contrib.auth import get_user_model
from django_grainy.models import UserPermission

from fullctl.django.management.commands.base import CommandInterface

User = get_user_model()


class Command(CommandInterface):
    help = "Import users from a CSV file"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("csv_file", type=str, help="The CSV file to import.")

    def run(self, *args, **kwargs):
        # settings we want to temporarily override while this command runs

        SIGNUP_NOTIFICATION_EMAIL = settings.SIGNUP_NOTIFICATION_EMAIL
        AUTO_USER_TO_ORG = settings.AUTO_USER_TO_ORG
        ENABLE_EMAIL_CONFIRMATION = settings.ENABLE_EMAIL_CONFIRMATION

        settings.SIGNUP_NOTIFICATION_EMAIL = False
        settings.AUTO_USER_TO_ORG = False
        settings.ENABLE_EMAIL_CONFIRMATION = False

        try:
            self.process_rows(*args, **kwargs)
        finally:
            # restore settings

            settings.SIGNUP_NOTIFICATION_EMAIL = SIGNUP_NOTIFICATION_EMAIL
            settings.AUTO_USER_TO_ORG = AUTO_USER_TO_ORG
            settings.ENABLE_EMAIL_CONFIRMATION = ENABLE_EMAIL_CONFIRMATION

    def process_rows(self, *args, **kwargs):
        self.csv_file = csv_file = kwargs["csv_file"]
        # Check if Admin role exists
        role = Role.objects.filter(name="Admin").first()
        if not role:
            self.stdout.write(
                self.style.ERROR("Admin role does not exist. Please create it first.")
            )
            return
        with open(csv_file) as file:
            reader = csv.DictReader(file)
            # Check if all expected fields are in the CSV file
            expected_fields = ["username", "email", "name", "asn"]
            if not all(field in reader.fieldnames for field in expected_fields):
                raise ValueError(
                    f"CSV file does not contain all the expected fields. {expected_fields}"
                )
            for row in reader:
                self.stdout.write(
                    self.style.HTTP_INFO(f'Processing {row["username"]} ' + ("-" * 30))
                )
                self.process_row(row, role)

    def process_row(self, row, role):
        username, email, name, asn = (
            row["username"],
            row["email"],
            row["name"],
            row["asn"],
        )

        org_name = row.get("org_name", f"AS{asn}")

        # Split name into first and last name
        first_name, last_name = self.split_name(name)
        # Check if user already exists
        user = User.objects.filter(email=email).first()
        if user:
            self.stdout.write(self.style.NOTICE(f"User {email} already exists."))
        else:
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
            )
            if row.get("password", None):
                user.password = row["password"]
                user.save()

            self.stdout.write(self.style.SUCCESS(f"Created user {username}."))

        # Check if ASN exists
        asn_org = self.check_asn_exists(asn)

        if asn_org:
            self.stdout.write(
                self.style.NOTICE(f"ASN {asn} exists in organization `{asn_org.name}`.")
            )
            org = asn_org
        else:
            # Check if organization already exists
            org = Organization.objects.filter(name=org_name).first()
            if not org:
                org = Organization.objects.create(name=org_name)

        # Create organization user
        org_user, org_user_created = OrganizationUser.objects.get_or_create(
            user=user, org=org, is_default=True
        )

        if not org_user_created:
            self.stdout.write(
                self.style.NOTICE(
                    f"User {username} already in Organization `{org.name}`."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Added user {username} to organization {org.name}.")
            )

        # finally grany permission to the org for the ASN
        self.grant_asn_permission(org, asn, role)

    def split_name(self, name):
        """
        Split name into first and last name.
        """
        names = name.split()
        first_name = names[0]
        last_name = names[-1] if len(names) > 1 else ""
        return first_name, last_name

    def check_asn_exists(self, asn):
        """
        Placeholder function for checking if ASN exists.
        """
        asn_permission = UserPermission.objects.filter(
            namespace__istartswith=f"verified.asn.{asn}."
        )

        if not asn_permission.exists():
            return False

        org_user = (
            asn_permission.first()
            .user.org_user_set.filter(org__user__isnull=True)
            .first()
        )

        if not org_user:
            return False

        return org_user.org

    def grant_asn_permission(self, org, asn, admin_role):
        """
        Placeholder function for granting ASN permission to the organization.
        """

        managed_perm, _ = ManagedPermission.objects.get_or_create(
            namespace=f"verified.asn.{asn}.imported",
            description=f"ASN {asn}",
            group="asns",
            managable=True,
            grant_mode="restricted",
        )

        ManagedPermissionRoleAutoGrant.objects.get_or_create(
            managed_permission=managed_perm,
            role=admin_role,
            permissions=15,
        )

        OrganizationManagedPermission.objects.get_or_create(
            org=org,
            managed_permission=managed_perm,
            reason=f"Imported from {self.csv_file}",
        )

        try:
            peerctl_access = ManagedPermission.objects.get(
                namespace="service.peerctl.{org_id}"
            )
            if peerctl_access.grant_mode == "restricted":
                OrganizationManagedPermission.objects.get_or_create(
                    org=org,
                    managed_permission=peerctl_access,
                    reason=f"Imported from {self.csv_file}",
                )
        except ManagedPermission.DoesNotExist:
            self.stdout.write(
                self.style.WARNING("Unable to find peerctl service permission")
            )
