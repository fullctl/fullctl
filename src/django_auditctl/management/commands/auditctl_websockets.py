import asyncio
import json
from urllib.parse import parse_qs, urlparse

import jwt
import websockets
from channels.db import database_sync_to_async
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from fullctl.django.auth import permissions
from jwt.exceptions import InvalidTokenError

from django_auditctl.models.auditctl import Event
from django_auditctl.rest.serializers.auditctl import Serializers

CONNECTIONS = set()


async def get_qualified_websockets(event):
    """
    Will return a list of websockets from CONNECTIONS based on the event

    Only websockets will be returned that are qualified to receive the event,
    based on the event's object_id and the websocket's filter option
    as well as the authenticated user's permissions.
    """

    object_id = event.object_id
    org = event.org.permission_id

    _websockets = []

    for conn in CONNECTIONS:
        filter = conn.options.get("filter")

        if filter and not object_id.startswith(filter):
            continue

        perms = conn.perms
        has_perms = await database_sync_to_async(perms.check)(f"audit.{org}.view", "r")

        if not has_perms:
            continue

        _websockets.append(conn.websocket)

    return _websockets


class Connection:

    """
    Wraps a websocket with some extra options and the authenticated user with permissions
    loaded.
    """

    def __init__(self, websocket, user, **options):
        self.websocket = websocket
        self.options = options
        self.user = user
        self.perms = permissions(user)


async def handler(websocket, path):
    """
    Handles incoming connections from clients.
    """

    # Extract the token from the WebSocket URL
    query_params = urlparse(path).query
    token = parse_qs(query_params).get("token", [None])[0]

    # Verify the JWT token
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except InvalidTokenError:
        # Close the connection if the token is invalid
        await websocket.close(1008, "authentication failed")
        return

    # Get the user from the payload
    user = await database_sync_to_async(get_user_model().objects.get)(
        id=payload["user_id"]
    )

    conn = Connection(websocket, user)

    # Add the WebSocket to the connections
    CONNECTIONS.add(conn)
    try:
        # Process incoming messages from the client
        async for message in websocket:
            message_data = json.loads(message)
            # Handle the received message
            print(f"Received message from client {conn.user}: {message_data}")

            conn.options["filter"] = message_data.get("filter")

            # You can add custom handling logic for different message types here

    finally:
        print("connection closed")
        CONNECTIONS.remove(conn)


@database_sync_to_async
def get_new_events(last_polled):
    new_events = Event.objects.filter(updated__gt=last_polled).select_related("org")
    return [event for event in new_events]


async def poll_new_events(interval):
    """
    Incrementally polls for new events since the last poll.
    """

    last_polled = timezone.now()
    while True:
        new_events = await get_new_events(last_polled)
        last_polled = timezone.now()

        if new_events:
            for event in new_events:
                message = json.dumps(Serializers.event(instance=event).data)
                _websockets = await get_qualified_websockets(event)
                websockets.broadcast(_websockets, message)

        await asyncio.sleep(interval)


async def main():
    server = await websockets.serve(
        handler, settings.EVENT_STREAM_HOST, settings.EVENT_STREAM_PORT
    )
    poll_task = asyncio.create_task(poll_new_events(1))  # Polls every second
    await asyncio.gather(server.wait_closed(), poll_task)


class Command(BaseCommand):
    help = "Run the WebSocket server that polls for new Event model objects"

    def handle(self, *args, **options):
        asyncio.run(main())
