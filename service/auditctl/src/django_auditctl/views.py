import jwt
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect, render

from fullctl.django.decorators import load_instance, require_auth

# Create your views here.


def make_env(request, **kwargs):
    r = {"env": settings.RELEASE_ENV, "version": settings.PACKAGE_VERSION}
    r.update(**kwargs)
    return r


@require_auth()
@load_instance()
def view_instance(request, instance, **kwargs):
    env = make_env(request, instance=instance, org=instance.org)

    return render(request, "theme-select.html", env)


@require_auth()
def org_redirect(request):
    return redirect(f"/{request.org.slug}/")


def generate_jwt(user):
    payload = {
        "user_id": user.id,
        "username": user.username,
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    return token


@require_auth()
def event_stream_url(request):
    if "jwt_token" not in request.session:
        token = generate_jwt(request.user)
        request.session["jwt_token"] = token
        request.session.modified = True

    token = request.session.get("jwt_token")
    websocket_url = f"{settings.EVENT_STREAM_URL}?token={token}"
    return JsonResponse({"websocket_url": websocket_url})
