FROM jenkins/jenkins:latest
USER root
RUN apt-get update && apt-get -y install python3-pip vim
RUN passwd -d root
RUN pip3 install ipython python-jenkins
COPY start.sh /usr/share/jenkins/start.sh
RUN chmod +x /usr/share/jenkins/start.sh
RUN chown -R jenkins:jenkins /usr/share/jenkins
USER jenkins
ENTRYPOINT ["/usr/share/jenkins/start.sh"]
