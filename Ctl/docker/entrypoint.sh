#!/bin/sh

FASTAPI_PORT=${FASTAPI_PORT:-8002}
cd $SERVICE_HOME

case "$1" in
  "fastapi" )
    cd main
    exec uvicorn regctl.api.main:app --host 0.0.0.0 --port $FASTAPI_PORT --reload
    ;;
  "/bin/sh"|"bash" )
    echo dropping to shell "$1" - "$@"
    exec $@
    ;;
  * )
    exec $@
    ;;
esac
