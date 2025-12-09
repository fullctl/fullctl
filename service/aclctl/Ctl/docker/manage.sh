ACLCTL_HOME=/srv/service

. $ACLCTL_HOME/venv/bin/activate
cd $ACLCTL_HOME/main

./manage.py $@
