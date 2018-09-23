import sys
import datetime
import getpass
import jenkins
import re
import xml.etree.ElementTree as XML
import pdb

# https://python-jenkins.readthedocs.io/en/latest/api.html

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

    __slots__ = ('_build', '_job', '_server')

    def __init__(self, build, job, server):
        self._build = build
        self._job = job
        self._server = server

    @property
    def number(self):
        return self._build['number']

    @property
    def url(self):
        return self._build['url']

    @property
    def kind(self):
        return self._build['_class']
    
    @property
    def output(self):
        return self._server.get_build_console_output(self._job.name, self.number)

    def stop(self):
        self._server.stop_build(self._job.name, self.number)
    
    def delete(self):
        self._server.delete_build(self._job.name, self.number)

class Configuration(object):

    __slots__ = ('_node', '_parent', '_header')

    _header = "<?xml version='1.0' encoding='UTF-8'?>\n"

    def __init__(self, conf, parent):
        self._parent = parent
        if isinstance(conf, unicode):
            self._node = XML.fromstring(conf)
            assert(self._node.tag == 'project')
        else:
            self._node = conf

    def __getattr__(self, name):
        child = [c for c in self._node if c.tag == name ]
        if not child:
            raise AttributeError('Attribute %s not found' % name)
        return Configuration(child[0], self)

    def __setattr__(self, name, value):
        if name in self.__slots__:
            return object.__setattr__(self, name, value)
        child = [c for c in self._node if c.tag == name ]
        if not child:
            raise AttributeError('Attribute %s not found' % name)
        
        child[0].text = str(value)
        self._reconfigure()

    def _reconfigure(self):
        if isinstance(self._parent, Configuration):
            self._parent._reconfigure()
        else:
            self._parent._apply(self)

    def toXML(self):
        return self._header + XML.tostring(self._node)

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
        self._apply(conf)

    def _apply(self, conf):
        self._server.reconfig_job(self.name, conf.toXML())

    def copy(self, newname):
        self._server.copy_job(self.name, newname)
        return Job(self._server.get_job(newname))

    def build(self, **kwargs):
        args = {}
        for k, v in kwargs.iteritems():
            args[k] = v
        # return self._server.build_job(self.name, args)  # TODO: return Build
        num = self._server.build_job(self.name, args)
        return [b for b in self.builds if b.number == num][0]

    def reconfig(self):
        self._server.reconfig_job(self.name)

    def enable(self):
        self._server.enable_job(self.name)

    def disable(self):
        self._server.disable_job(self.name)

    def delete(self):
        self._server.delete_job(self.name)

    # -- info --
    
    @property
    def _info(self):
        return self._server.get_job_info(self.name)
    
    @property
    def description(self):
        return self._info['description']

    @property
    def buildable(self):
        return self._info['buildable']

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
        return [Build(b, self, self._server) for b in self._info['builds']]

    def _get_build(self, name):
        build = self._info[name]
        if not build:
            return None
        builds = [b for b in self.builds if b.number == build['number']]
        return builds[0] if builds else None

    @property
    def firstBuild(self):
        return self._get_build('firstBuild')

    @property
    def lastBuild(self):
        return self._get_build('lastBuild')

    @property
    def parameters(self):
        prop = self._info['property']
        if not prop:
            return []
        assert(len(prop) == 1)
        defs = prop[0]['parameterDefinitions']
        if not defs:
            return []
        return [Parameter(p) for p in defs]
        
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
    
    # --

    # -- configuration --
    # --

    def __getattr__(self, name):
        if hasattr(self.configuration, name):
            return getattr(self.configuration, name)
        raise AttributeError('Attribute %s not found' % name)

    def __setattr__(self, name, value):
        if name in self.__slots__:
            return object.__setattr__(self, name, value)
        if hasattr(self.configuration, name):
            setattr(self.configuration, name, value)

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.__str__()


class Jobs(object):
    
    __slots__ = ('_server', '_jobs')
    
    def __init__(self, server):
        self._server = server
        self._jobs = [Job(j, server) for j in self._server.get_jobs()]
    
    def __contains__(self, job):
        return bool(self._server.job_exists(job))
    
    def __getitem__(self, key):
        return self._jobs[key]
    
    def __iter__(self):
        return self._jobs.__iter__()
    
    def __call__(self, name):
        j = self._server.get_job_info(name)
        return None if not j else Job({
            '_class': j['_class'],
            'color': j['color'],
            'fullname': j['fullName'],
            'name': j['name'],
            'url': j['url'],
        }, self._server)

    def __len__(self):
        return self._server.jobs_count()

    def create(self, name):
        self._server.create_job(name, jenkins.EMPTY_CONFIG_XML)
        return self.__call__(name)


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


class Host(object):

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

    @property
    def jobs(self):
        return Jobs(self._server)
    
    @property
    def me(self):
        return User(self._server.get_whoami())


if __name__ == '__main__':

    host = Host('http://localhost:8080', username='admin', password='admin')

    name = 'jhdgalfuyg'

    assert(host)
    assert(name not in host.jobs)
    job = host.jobs.create(name)
    assert(name in host.jobs)
    job.concurrentBuild = True
    for j in host.jobs:
        print j
    job.delete()
