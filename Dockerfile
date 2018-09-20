FROM jenkins
USER root
RUN apt-get update && apt-get -y install python-pip
ENV HOME=/home/jenkins
RUN mkdir -p ${HOME}
COPY start-jenkins.sh ${HOME}/
RUN chmod +x ${HOME}/start-jenkins.sh
RUN chown -R jenkins:jenkins ${HOME}
USER jenkins
RUN pip install ipython python-jenkins
WORKDIR ${HOME}
ENTRYPOINT ${HOME}/start-jenkins.sh
