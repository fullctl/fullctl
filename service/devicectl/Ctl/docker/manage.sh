DEVICECTL_HOME=/srv/service

. $DEVICECTL_HOME/venv/bin/activate
cd $DEVICECTL_HOME/main

./manage.py $@
