# 🎃 Pumpkins
Yet another Python API for Jenkins.  
Buy one now, you get a Docker image FOR FREE!
This library is built on top of `python-jenkins`, and his purpose is just that of offering a simple(r), more "pythonic" interface.

## Building
Build the image with (from the repo root directory):

`docker build -f Dockerfile -t pumpkins .`

## Deployment
Launch the container with:

`docker run -h pumpkins --rm -it -p 8080:8080 -v $PWD:/staging pumpkins # $PWD:/staging or whatever`

- Wait for Jenkins to startup and then access the instance at localhost:8080
- In the container run `python /staging/pumpkins.py` to verify that everything is working properly.

Jenkins will be configured with an 'admin:admin' user, the plugins to install can be specified in a
'plugins.txt' file that can be then mounted into the container aside to the pumpkins library itself.

The starting procedure will try to guess the position of the mounted endpoint inspecting the current
mounted volumes, and fallback to '/staging' eventually, see the `start.sh` script for more details.

If the environment variable '$INTERACTIVE' is set to any non empty value the Jenkins configuration can be
executed manually, the terminal will show a password to Copy&Paste into the Web page and then it will be
possible to configure Jenkins as needed:

`docker run -h pumpkins -e INTERACTIVE=1 --rm -it -p 8080:8080 -v $PWD:/staging pumpkins`

It is possible to pass any command to the container, if none is given a bash shell will be provided.
On the bash shell you have ipython and python-jenkins ready to be used,
(as well as VIM, you're welcome) so doing...
```
jenkins@pumpkins:~$ ipython3
In[1]: import pumpkins
In[2]: host = pumpkins.Host('http://localhost:8080', username='admin', password='admin')
In[3]: print(host.me)
```
...should do the work.

## Testing
The library comes with a builtin simple unit test suite, it is possible to run it issuing a command like:

`docker run --rm -it -v $PWD:/staging pumpkins python3 /staging/pumpkins.py`

(note that is not necessary to expose TCP/UDP ports for the tests to be executed).

## Notes
The Docker image is used only for developing/purpose testing, as such it makes little sense to embed
the Python library itself inside it, more useful is mounting the repository root folder
into the container file system so to be able to edit the .py file on the fly.

Once logged into the container issuing `export PYTHONPATH=$PYTHONPATH:/staging` will save you from
having to type `import sys; sys.append(...)` every time you spawn a `python`/`ipython` shell.

The Docker image is built on top of the jenkins image (https://hub.docker.com/r/jenkins/jenkins) and as such
it exposes the 50000 and 8080 TCP ports, only the 8080 is needed to access the web interface so
I would not bother exposing the 50000 as well.

## References and Thanks
The [Jenkins docker image](https://hub.docker.com/r/jenkins/jenkins)  
The [Jenkins Python library](https://python-jenkins.readthedocs.io)  
Thanks to [Viktor Farcic](https://technologyconversations.com/author/technologyconversations) for his great [blog post](https://technologyconversations.com/2017/06/16/automating-jenkins-docker-setup) on how to deploy Jenkins unsupervised.
---
[![Build Status](https://travis-ci.org/lucacastoro/pumpkins.svg?branch=master)](https://travis-ci.org/lucacastoro/pumpkins)
