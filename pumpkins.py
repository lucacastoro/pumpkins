import sys
import datetime
import getpass
import jenkins
import re
import xml.etree.ElementTree as XML

# https://python-jenkins.readthedocs.io/en/latest/examples.html

class Parameter(object):

    __slots__ = ('name', 'kind', 'description', 'defaultValue')

    reType = re.compile('^(\w+)ParameterDefinition$')

    def __init__(self, param):
        self.name = themparamap['name']
        self.kind = Parameter.reType.match(param['type']).group(1).lower()
        self.description = param['description']
        if 'defaultParameterValue' in param:
            self.defaultValue = param['defaultParameterValue']['value']
        else:
            self.defaultValue = None

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.__str__()

class Build(object):

    __slots__ = ('_build')

    def __init__(self, build):
        self._build = build

    @property
    def number(self):
        return self._build['number']

    @property
    def url(self):
        return self._build['url']

    @property
    def kind(self):
        return self._build['_class']

class Info(object):

    __slots__ = ('_info')

    def __init__(self, info):
        self._info = info

    @property
    def description(self):
        return self._info['description']

    @property
    def buildable(self):
        return self._info['buildable']

    @property
    def color(self):
        return self._info['color']

    @property
    def inQueue(self):
        return self._info['inQueue']

    @property
    def keepDependencies(self):
        return self._info['keepDependencies']

    @property
    def nextBuildNumber(self):
        return self._info['lastBuildNumber']

    @property
    def concurentBuild(self):
        return self._info['concurrentBuild']

    @property
    def builds(self):
        return [Build(b) for b in self._info['builds']]

    def _get_build(self, name):
        number = self._info[name]['number']
        builds = [b for b in self.builds if b.number == number]
        return builds[0] if builds else None

    @property
    def firstBuild(self):
        return self._get_build('firstBuild')

    @property
    def lastBuild(self):
        return self._get_build('lastBuild')

    @property
    def parameters(self):
        return [
            Parameter(p)
            for p in self._info['property'][0]['parameterDefinitions']
        ]
        
    @property
    def lastCompletedBuild(self):
        return self._get_build('lastCompletedBuild')

    @property
    def lastFailedBuild(self):
        return self._get_build('lastFiledBuild')

    @property
    def lastStableBuild(self):
        return self._get_build('lastStableBuild')

    @property
    def lastUnstableBuild(self):
        return self._get_build('lastUnstableBuild')

    @property
    def lastSuccessfulBuild(self):
        return self._get_build('lastSuccessfulBuild')

    @property
    def lastUnsuccessfulBuild(self):
        return self._get_build('lastUnsuccessfulBuild')

class Configuration(object):

    __slots__ = ('_node', '_parent')

    _header = "<?xml version='1.0' encoding='UTF-8'?>\n"

    def __init__(self, conf, parent):
        self._parent = parent
        if isinstance(conf, unicode):
            self._node = XML.fromstring(config)
            assert(self._node.tag == 'project')
        else:
            self._node = conf

    def __getattr__(self, name):
        child = [c for c in self._node if c.tag == name ]
        if not child:
            raise AttributeError('Attribute %s not found' % name)
        return Configuration(child)

    def __setattr__(self, name, value):
        child = [c for c in self._node if c.tag == name ]
        if not child:
            raise AttributeError('Attribute %s not found' % name)
        child = value
        _reconfigure()

    def _reconfigure(self):
        if isinstance(self_parent, Configuration):
            self._parent.reconfigure()
        else:
            self._parent.configuration = self

    def toXML(self):
        return _header + XML.tostring(self._node)

    def __str__(self):
        return self._node.text
    
    def __repr__(self):
        return self.__str__()

class Job(object):

    __slots__ = ('_job', '_server')

    def __init__(self, job, server):
        self._job = job
        self._server = server

    @property
    def kind(self):
        return self._job['_class']

    @property
    def name(self):
        return self._job['name']

    @property
    def url(self):
        return self._job['url']

    @property
    def color(self):
        return self._job['color']

    @property
    def fullname(self):
        return self._job['fullname']

    @property
    def configuration(self):
        return Configuration(self._server.get_job_config(self.name), self)

    @configuration.setter
    def configuration(self, conf):
        self._server.reconfig_job(self.name, conf.toXML())

    def copy(self, newname):
        self._server.copy_job(self.name, newname)
        return Job(self._server.get_job(newname))

    def build(self, **kwargs):
        args = {}
        for k, v in kwargs.iteritems():
            args[k] = v
        return self._server.build_job(self.name, args)

    def reconfig(self):
        self._server.reconfig_job(self.name)

    def enable(self):
        self._server.enable_job(self.name)

    def disable(self):
        self._server.disable_job(self.name)

    def delete(self):
        self._server.delete_job(self.name)

    def __getattr__(self, name):
        info = Info(self._server.get_job_info(self.name))
        if hasattr(info, name):
            return getattr(info, name)
        raise AttributeError('Attribute %s not found' % name)

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.__str__()


class User(object):

    __slots__ = ('_user')

    def __init__(self, user):
        self._user = user

    @property
    def fullName(self):
        return self._user['fullName']

    @property
    def name(self):
        return self.fullName

    @property
    def id(self):
        return self._user['id']

    @property
    def description(self):
        return self._user['description']

    @property
    def url(self):
        return self._user['absoluteUrl']

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.__str__()


class Pumpkins(object):

    __slots__ = ('_server')

    def __init__(self, url, username=None, password=None):

        if not username:
            sys.stdout.write('Username: ')
            sys.stdout.flush()
            username = sys.stdin.readline()[:-1]

        if not password:
            password = getpass.getpass()

        self._server = jenkins.Jenkins(url, username, password)


    def __bool__(self):  # 3.x
        try:
            self.me
            return True
        except:
            return False

    def __nonzero__(self):  # 2.x
        return self.__bool__()

    def job(self, name):
        j = [j for j in self.jobs if j.name == name]
        return j[0] if j else None

    def createJob(self, name):
        self._server.create_job(name, jenkins.EMPTY_CONFIG_XML)
        return self.job(name)

    @property
    def jobs(self):
        return [Job(j, self._server) for j in self._server.get_jobs()]
    
    @property
    def allJobs(self):
        return [Job(j, self._server) for j in self._server.get_all_jobs()]

    @property
    def me(self):
        return User(self._server.get_whoami())


if __name__ == '__main__':

    server = Pumpkins('http://localhost:8080')

    if not server:
        print('Server initialization failed')
        exit(1)

    def greetings(user):
        hour = datetime.datetime.now().hour
        return 'good %s %s' % ('morning' if hour < 13 else 'evening', user)

    print('Connection to server established, %s' % (greetings(server.me)))

