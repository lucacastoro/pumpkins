#!/bin/bash

echo 'Starting Jenkins...'

[ -n "$INTERACTIVE" ] && {

	/usr/local/bin/jenkins.sh &>$HOME/jenkins.log &

	echo -n 'Waiting for jenkins to start'
	while [ ! -f $HOME/secrets/initialAdminPassword ]; do
		echo -n '.'
		sleep 1
	done

	echo 'Jenkins is ready.'
	echo "Password: $(cat /var/jenkins_home/secrets/initialAdminPassword)"

} || {

	export JAVA_OPTS="$JAVA_OPTS -Djenkins.install.runSetupWizard=false"

	root=$(mount | grep -vE 'tmpfs|proc|devpts|shm|mqueue|cgroup|sysfs|overlay|/etc|/var/jenkins_home')
	[ -n "$root" ] && root=$(echo $root | awk '{print $3}') || root=/staging

	groovy=$root/setup.groovy
	plugins=$root/plugins.txt
	
	[ -f $groovy ] && [ $(stat -c %s $groovy) -gt 0 ] && {
		cp $groovy /usr/share/jenkins/ref/init.groovy.d/setup.groovy
	}

	[ -f $plugins ] && [ $(stat -c %s $plugins) -gt 0 ] && {
		/usr/local/bin/install-plugins.sh < $plugins
	}

	/usr/local/bin/jenkins.sh &>$HOME/jenkins.log &

	echo -n 'Waiting for jenkins to start'
	while true; do
		grep 'Jenkins is fully up and running' $HOME/jenkins.log > /dev/null && break
		echo -n '.'
		sleep 1
	done
	echo 'Jenkins is ready.'
}

[ "$#" -eq 0 ] && /bin/bash || $@
