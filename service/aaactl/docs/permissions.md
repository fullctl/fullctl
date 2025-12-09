# Django Admin

## Role

You can manage user `Roles` at `/admin/account/role/`

In the end a role will describe a set of permissions, and the names should reflect that.

- level: when a user is in more than one role the permissions of each role will need to be merged, the `level` value will determine the order of merging, with the lowest value merged last.
- auto_set_on_creator: if True this role will automatically be granted to the creator of an organization
- auto_set_on_member: if True this role will automatically be granted to members of an organization

## Manage user's role in an organization

Once the `Role` objects are created, users can be put into that role on a per organization basis through the django-admin organization management interface at `/admin/account/organization/1/change/`.

Scroll down to "User roles within organization" and add new entries to assign users to roles. A user can be in more than one role.

## Manage automatic permission grants based on role

Managed permissions can use roles to auto grant permissions to users based on the roles they are in.

When editing a `ManagedPermission` scroll down to "PERMISSION ASSIGNMENTS FOR ROLES" and add an entry for each role that you want to auto grant permissions for.

### A fullctl_poll_tasks process is mandatory

After saving changes here an `UpdatePermissions` job will be spawned that will sync permissions for all users that are affected.

This means that an aaactl task worker needs to be running to pickup and process the job.

```sh
python manage.py fullctl_poll_tasks --workers 1 
```

# Controlpanel (user-facing)

The user management system allows organization members with permission to the `user.` namespace to add / remove roles for a user.

Furthermore manual overrides for each permission can also be set through the same interface.
