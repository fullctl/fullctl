AUDITCTL_HOME=/srv/service

. $AUDITCTL_HOME/venv/bin/activate
cd $AUDITCTL_HOME/main

./manage.py $@
