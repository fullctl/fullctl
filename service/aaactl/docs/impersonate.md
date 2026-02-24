# Impersonate other users

Superusers can impersonate other users to see what they are seeing by going to the user management tools at `/admin/auth/user` and clicking
the `Start` link in the `Impersonate` column.

Clicking `Stop` in the same column will stop the impersonation.

If you are currently impersonating a user a notification message will be displaed on all non django-admin pages stating that you are current
ly viewing things through another user.

Django-admin views are excluded from impersonation.

Impersonations are propagated to all the fullctl services using this aaactl instance.

# Limited django-admin exposure with impersonation

This is for the case where you want to give a user the ability to impersonate other users but not have full django-admin access.

1. Create new user group at admin/auth/group/add/
	- add permission `auth` with READ - this allows the user to view the user list
	- add permission `impersonate` with CREATE and DELETE - this allows the user to impersonate other users
2. Edit the user atg admin/auth/user
3. Make sure `staff status` is selected
4. Add the user to the group created in step 1
    - select in the left groups list and click the arrow pointing right to transfer to "Chosen groups"