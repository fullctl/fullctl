from django import template

register = template.Library()


@register.filter
def social_id(user, backend_name):
    data = user.social_auth.filter(provider=backend_name).first()
    if not data:
        return ""
    if backend_name == "peeringdb":
        # peeringdb does not provide email or username as uid
        # but rather the actual user id - display email instead
        return data.extra_data.get("email")

    return data.uid
