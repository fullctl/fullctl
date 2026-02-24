#!/bin/sh

function migrate_all() {
  echo applying all migrations
  manage migrate
}

function collect_static() {
  echo collecting static files
  manage collectstatic --no-input
}


cd $SERVICE_HOME
case "$@" in
  "uwsgi" )
    echo starting uwsgi
    if [[ -z "$NO_MIGRATE" ]]; then
      migrate_all
    fi
    if [[ -z "$NO_COLLECT_STATIC" ]]; then
      collect_static
    fi
    exec venv/bin/uwsgi --ini etc/django-uwsgi.ini
    ;;
	# good to keep it as a separate arg incase we end up with multi stage migrations tho
  "migrate_all" )
    migrate_all
    ;;
  "run_tests" )
    source venv/bin/activate
    cd main
    export DJANGO_SETTINGS_MODULE=aaactl.settings
    export RELEASE_ENV=run_tests
    unset AUTO_USER_TO_ORG
    unset ENABLE_ACCOUNT_REGISTRATION
    pytest tests/ -vv --cov-report=term-missing --cov-report=xml --cov=account --cov=billing --cov=common --cov=applications
    ;;
  "test_mode" )
    source venv/bin/activate
    cd main
    export DJANGO_SETTINGS_MODULE=aaactl.settings
    echo dropping to shell
    exec "/bin/sh"
    ;;
  "pdb_sync" )
    peeringdb -C etc/peeringdb/ sync
    ;;
  "/bin/sh" )
    echo dropping to shell "$1" - "$@"
    exec $@
    ;;
  * )
    if [[ -z "$NO_MIGRATE" ]]; then
      migrate_all
    fi
    exec manage $@
    ;;
esac
