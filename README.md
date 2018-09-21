# 🎃 Pumpkins
Yet another Python API for Jenkins.  
Buy one now, you get a Docker image FOR FREE!

Build the image with (from the repo root directory):

`docker build -f Dockerfile -t pumpkins .`

Launch the container with:

`docker run -h pumpkins --rm -it -p 8080:8080 -v $PWD:/staging pumpkins # $PWD:/staging or whatever`

- Wait for Jenkins to startup and then access the instance at localhost:8080
- Copy&Paste the password reported on the terminal into the Web page.
- Proceed to configure Jenkins as needed.
- Run `python /staging/pumpkins.py` to verify that everything is working properly.

On the bash shell you have ipython and python-jenkins ready to be used,
(as well as VIM, you're welcome) so doing...
```
jenkins@pumpkins:~$ ipython
In[1]: import pumpkins
In[2]: host = pumpkins.Pumpkins('http://localhost:8080')
In[3]: print(host.me)
```
...should do the work

The Docker image is used only for developing/purpose testing, as such it makes little sense to embed
the Python library itself into the container, more useful is mounting the repository root folder
into the container file system so to be able to edit the .py file on the fly.

Once logged into the container issuing `export PYTHONPATH=$PYTHONPATH:/staging` will save you from
having to type `import sys; sys.append(...)` every time you spawn a `python`/`ipython` shell.

The Docker image is built on top of the jenkins image (https://hub.docker.com/\_/jenkins/) and as such
it exposes the 50000 and 8080 TCP ports, only the 8080 is needed to access the web interface so
I would not bother exposing the 50000 as well.

