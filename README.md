# pumpkins
Yet another Python API for Jenkins.
Buy one now, you get a Docker container FOR FREE!

launch the container with:

  docker run --rm -it -p 8080:8080 -v $PWD:$PWD pumpkins

- Wait for Jenkins to startup and then access the instance at localhost:8080
- Copy&Paste the password reported on the terminal into the Web page.
- Proceed to configure Jenkins as needed.
- Run `python ./pumpkins.py` to verify that everything is working properly.
- On the bash shell you have ipython and python-jenkins ready to be used.

The Docker image is built on top of jenkins (https://hub.docker.com/_/jenkins/) and as such
it exposes the 50000 and 8080 TCP ports, only the 8080 is needed to access the web interface
so I would not bother accessing the 50000 as well.

