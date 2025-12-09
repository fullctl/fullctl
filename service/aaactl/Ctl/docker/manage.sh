SERVICE_HOME=/srv/service

. $SERVICE_HOME/venv/bin/activate
cd $SERVICE_HOME/main

./manage.py $@
