import sys
import datetime
import getpass
import jenkins
import re
import xml.etree.ElementTree as XML

# https://python-jenkins.readthedocs.io/en/latest/api.html


class Parameter(object):

    __slots__ = ('name', 'kind', 'description', 'defaultValue')

    reType = re.compile('^(\w+)ParameterDefinition$')

    def __init__(self, param):
        self.name = param['name']
        self.kind = Parameter.reType.match(param['type']).group(1).lower()
        self.description = param['description']
        self.defaultValue = param['defaultParameterValue']['value'] if 'defaultParameterValue' in param else None

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.__str__()


class Queue(object):

    SLEEP_SECONDS = 1.0

    __slots__ = ('_number', '_job', '_server', '_ready')

    def __init__(self, number, job, server):
        self._number = number
        self._job = job
        self._server = server
        self._ready = False

    @property
    def _info(self):
        return self._server.get_queue_item(self._number)

    def wait(self):
        if not self._ready:
            while 'executable' not in self._info:
                time.sleep(self.SLEEP_SECONDS)
            self._ready = True

    @property
    def id(self):
        return self._info['id']

    @property
    def stuck(self):
        return self._info['stuck']

    @property
    def blocked(self):
        return self._info['blocked']

    @property
    def buildable(self):
        return self._info['buildable']

    @property
    def build(self):
        self.wait()
        name = self._info['task']['name']
        number = self._info['executable']['number']
        b = self._server.get_build_info(name, number)
        return Build(b, self._job, self._server)


class Build(object):

    SLEEP_SECONDS = 1.0

    __slots__ = ('_build', '_job', '_server', '_complete')

    def __init__(self, build, job, server):
        self._build = build
        self._job = job
        self._server = server
        self._complete = None

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

    @property
    def info(self):
        return self._server.get_build_info(self._job.name, self.number)

    @property
    def env(self):
        return self._server.get_build_env_vars(self._job.name, self.number)

    @property
    def report(self):
        return self._server.get_build_test_report(self._job.name, self.number)

    @property
    def building(self):
        return self.info['building']

    def wait(self):
        if not self._complete:
            while self.building:
                time.sleep(self.SLEEP_SECONDS)
            self._complete = True

    @property
    def result(self):
        self.wait()
        return self.info['result']

    @property
    def succeded(self):
        return self.result == 'SUCCESS'

    @property
    def failed(self):
        return not self.succeded

    @property
    def url(self):
        return self.info['url']

    @property
    def description(self):
        desc =  self.info['description']
        return desc if desc else ''

    @property
    def duration(self):
        self.wait()
        return datetime.timedelta(milliseconds=self.info['duration'])

    @property
    def estimatedDuration(self):
        return datetime.timedelta(milliseconds=self.info['estimatedDuration'])

    @property
    def keepLog(self):
        return self.info['keepLog']

    @property
    def time(self):
        return datetime.datetime.fromtimestamp(self.info['timestamp']/1000)

    def __str__(self):
        return self.info['fullDisplayName']

    def __repr__(self):
        return self.__str__()


class BuildSteps(object):

    def __init__(self, node, conf):
        self._node = node
        self._conf = conf

    def __len__(self):
        return len(self._node)

    def add(self, script):
        node = XML.Element('hudson.tasks.Shell')
        comm = XML.Element('command')
        comm.text = script
        node.append(comm)
        self._node.append(node)
        self._conf._apply()

    def __setitem__(self, key, value):
        self._node[key].find('command').text = value
        self._conf._apply()

    def __iter__(self):
        self.all().__iter__()


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

    @property
    def actions(self):
        return []

    @property
    def description(self):
        return self._node.find('description').text

    @description.setter
    def set_description(self, cb):
        self._node.find('description').text = str(cb)
        self._apply()

    @property
    def canRoam(self):
        return bool(self._node.find('canRoam').text)

    @canRoam.setter
    def set_canRoam(self, cb):
        self._node.find('canRoam').text = str(cb)
        self._apply()

    @property
    def disabled(self):
        return bool(self._find('disabled').text)

    @disabled.setter
    def set_disabled(self, cb):
        self._node.find('disabled').text = str(cb)
        self._apply()

    @property
    def concurrentBuild(self):
        return bool(self._node.find('concurrentBuild').text)

    @concurrentBuild.setter
    def set_concurrentBuild(self, cb):
        self._node.find('concurrentBuild').text = str(cb)
        self._apply()

    @property
    def buildSteps(self):
        return BuildSteps(self._node.find('builders'), self)

    def toXML(self):
        return self._header + XML.tostring(self._node)

    def _apply(self):
        self._parent._apply(self)

    def __str__(self):
        text = self._node.text
        return text if text else ''
    
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

    def _apply(self, conf):
        self._server.reconfig_job(self.name, conf.toXML())

    def copy(self, newname):
        self._server.copy_job(self.name, newname)
        return Job(self._server.get_job(newname))

    def schedule(self, **kwargs):
        args = {}
        for k, v in kwargs.iteritems():
            args[k] = v
        return Queue(self._server.build_job(self.name, args), self, self._server)

    def build(self, **kwargs):
        return self.schedule(**kwargs).build

    def wait(self):
        self.lastBuild.wait()

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

        EmptyConfig = """
        <project>
            <description/>
            <keepDependencies>false</keepDependencies>
            <properties/>
            <scm class="hudson.scm.NullSCM"/>
            <canRoam>true</canRoam>
            <disabled>false</disabled>
            <blockBuildWhenDownstreamBuilding>false</blockBuildWhenDownstreamBuilding>
            <blockBuildWhenUpstreamBuilding>false</blockBuildWhenUpstreamBuilding>
            <triggers/>
            <concurrentBuild>false</concurrentBuild>
            <builders/>
            <publishers/>
            <buildWrappers/>
        </project>
        """

        self._server.create_job(name, EmptyConfig)  # jenkins.EMPTY_CONFIG_XML)
        return self.__call__(name)

    def __str__(self):
        return "%d jobs" % self.__len__()

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
        except ConnectionError:
            return False
        except JenkinsException:
            return False

    def __nonzero__(self):  # 2.x
        return self.__bool__()

    @property
    def jobs(self):
        return Jobs(self._server)
    
    @property
    def me(self):
        return User(self._server.get_whoami())


# Tests

import time
import unittest


class Tester(unittest.TestCase):

    @staticmethod
    def connect():
        hostname = 'http://localhost:8080'
        username = 'admin'
        password = 'admin'
        return Host(hostname, username=username, password=password)

    def test_connection(self):
        host = self.connect()
        self.assertTrue(host)

    def test_job_lifecycle(self):
        host = self.connect()
        self.assertTrue(host)

        name = 'asdasdasd'
        self.assertTrue(name not in host.jobs)

        job = host.jobs.create(name)
        self.assertTrue(name in host.jobs)

        job.configuration.buildSteps.add('true')

        self.assertEqual(len(job.builds), 0)
        queue = job.schedule()
        queue.wait()  # wait for the job to start
        queue.build.wait()  # wait for the job to finish
        self.assertEqual(len(job.builds), 1)
        self.assertTrue(job.lastBuild.succeded)

        job.configuration.buildSteps[0] = 'false'
        self.assertTrue(job.build().failed)
        self.assertEqual(len(job.builds), 2)

        job.delete()
        self.assertTrue(name not in host.jobs)


if __name__ == '__main__':
    unittest.main()
