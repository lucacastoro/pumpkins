FROM jenkins/jenkins:latest
USER root
RUN apt-get update && apt-get -y install python-pip vim
ENV HOME=/home/jenkins
RUN mkdir -p ${HOME}
COPY start-jenkins.sh ${HOME}/
RUN chmod +x ${HOME}/start-jenkins.sh
RUN chown -R jenkins:jenkins ${HOME}
RUN passwd -d root
USER jenkins
RUN pip install ipython python-jenkins
WORKDIR ${HOME}
ENTRYPOINT ${HOME}/start-jenkins.sh
