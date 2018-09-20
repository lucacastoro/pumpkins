#!/bin/bash

echo 'Starting Jenkins...'

/usr/local/bin/jenkins.sh &>$HOME/jenkins.log &

while [ ! -f /var/jenkins_home/secrets/initialAdminPassword ]; do
	sleep 1
done

echo 'Jenkins is ready.'
echo -n 'Password: '
cat /var/jenkins_home/secrets/initialAdminPassword
bash
