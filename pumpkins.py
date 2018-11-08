import sys
import datetime
import getpass
import jenkins
import re
import xml.etree.ElementTree as XML

# https://python-jenkins.readthedocs.io/en/latest/api.html


class Parameter(object):

    """Represents a configurable build parameter"""

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

    """When a job is 'executed' is not immediately started, instead it is 'queued' for a short time (usually ~5sec)
    before being assigned to a node for the actual execution.
    This class represents this 'Queue' intermediate state, from where you can access the associated (to be spawn)
    build process, or cancel.
    The 'queue' object itself has a short lifespan (~5min), from the 'server.build_job()' documentation:
     > This method returns a queue item number that you can pass to Jenkins.get_queue_item().
     > Note that this queue number is only valid for about five minutes after the job completes,
     > so you should get/poll the queue information as soon as possible to determine the job's URL.
    """

    SLEEP_SECONDS = 1.0

    __slots__ = ('_number', '_job', '_server', '_ready')

    def __init__(self, number, job, server):
        self._number = number
        self._job = job
        self._server = server
        self._ready = False

    @property
    def _info(self):
        """accesses the underlying queue informations
        :return dict"""
        return self._server.get_queue_item(self._number)

    def wait(self):
        """wait for the related build process to start"""
        if not self._ready:
            while 'executable' not in self._info:
                time.sleep(self.SLEEP_SECONDS)
            self._ready = True

    @property
    def id(self):
        """the queue id
        :return int"""
        return self._info['id']

    @property
    def stuck(self):
        """the queue is stuck
        :return bool"""
        return self._info['stuck']

    @property
    def blocked(self):
        """the queue is blocked
        :return bool"""
        return self._info['blocked']

    @property
    def buildable(self):
        """the queue is buildable
        :return bool"""
        return self._info['buildable']

    @property
    def build(self):
        """the associated build process
        if the build process is not yet started when this method is called,
        the current thread will be paused until is not started
        :return Build"""
        self.wait()
        name = self._info['task']['name']
        number = self._info['executable']['number']
        b = self._server.get_build_info(name, number)
        return Build(b, self._job, self._server)

    def cancel(self):
        """cnacel a scheduled (but not yet started) build process"""
        self._server.cancel_queue(self.id)


class Build(object):

    """Represents job build process.
    A Build can be ongoing (.building = True) or completed, some of the informations related to a Build will be
    available only when the build process is complete, as the build duration, the build result and so on.
    """

    SLEEP_SECONDS = 1.0

    __slots__ = ('_build', '_job', '_server', '_complete')

    def __init__(self, build, job, server):
        """c'tor
        :param build, dict, a dictionary containing the build information, returned by server.get_build_info()
        :param job, Job, the parent Job
        :param server, jenkins.Jenkins, the root server instance
        """
        self._build = build
        self._job = job
        self._server = server
        self._complete = None

    @property
    def number(self):
        """the build number
        :return int"""
        return self._build['number']

    @property
    def url(self):
        """the build url
        :return str"""
        return self._build['url']

    @property
    def kind(self):
        """the build type
        :return str"""
        return self._build['_class']
    
    @property
    def output(self):
        """the build console output
        :return str"""
        return self._server.get_build_console_output(self._job.name, self.number)

    def stop(self):
        """stop a running build process"""
        self._server.stop_build(self._job.name, self.number)
    
    def delete(self):
        """delete a build"""
        self._server.delete_build(self._job.name, self.number)

    @property
    def _info(self):
        """the build info structure
        :return dict"""
        return self._server.get_build_info(self._job.name, self.number)

    @property
    def env(self):
        """the build environment variables map
        :return dict"""
        return self._server.get_build_env_vars(self._job.name, self.number)

    @property
    def testReport(self):
        """the build test reports
        :return dict"""
        return self._server.get_build_test_report(self._job.name, self.number)

    @property
    def building(self):
        """the build is in progress
        :return bool"""
        return self._info['building']

    def wait(self):
        """wait for the build to complete"""
        if not self._complete:
            while self.building:
                time.sleep(self.SLEEP_SECONDS)
            self._complete = True

    @property
    def result(self):
        """the build process result
        This method waits for the build process to complete if necessary
        :return str"""
        self.wait()
        return self._info['result']

    @property
    def succeed(self):
        """the build process was successful
        This method waits for the build process to complete if necessary
        :return bool"""
        return self.result == 'SUCCESS'

    @property
    def failed(self):
        """the build process failed
        This method waits for the build process to complete if necessary
        :return bool"""
        return not self.succeed

    @property
    def url(self):
        """the build url
        :return str"""
        return self._info['url']

    @property
    def description(self):
        """the build description
        :return str"""
        desc = self._info['description']
        return desc if desc else ''

    @property
    def duration(self):
        """the build process time duration
        This method waits for the build process to complete if necessary
        :return timedelta"""
        self.wait()
        return datetime.timedelta(milliseconds=self._info['duration'])

    @property
    def estimatedDuration(self):
        """the build process estimated duration
        :return timedelta"""
        return datetime.timedelta(milliseconds=self._info['estimatedDuration'])

    @property
    def keepLog(self):
        """the logs should be kept
        :return bool"""
        return self._info['keepLog']

    @property
    def time(self):
        """the build start time
        :return datetime"""
        return datetime.datetime.fromtimestamp(self._info['timestamp'] / 1000)

    def __str__(self):
        return self._info['fullDisplayName']

    def __repr__(self):
        return self.__str__()


class BuildSteps(object):

    """The jobs consist of a number of parameters and a sequence of build steps.
    This class represents a sequence of build steps"""

    def __init__(self, node, conf):
        """c'tor
        :param node, XML.Node, the <builders> node in the job configuration"""
        assert (node.tag == 'builders')
        self._node = node
        self._conf = conf

    def __len__(self):
        """the number of steps for this configuration
        :return int"""
        return len(self._node)

    def add(self, script):
        """add a script to be executed by the job
        :param script, str, the shell script to execute"""
        node = XML.Element('hudson.tasks.Shell')
        comm = XML.Element('command')
        comm.text = script
        node.append(comm)
        self._node.append(node)
        self._conf._apply()

    def __setitem__(self, index, value):
        """sets a specific step
        :param index, int, the index of the step to set
        :param value, str, the script to assign to the step"""
        self._node[index].find('command').text = value
        self._conf._apply()


class Configuration(object):

    """Every job is described by a complex XML configuration document,
    this class tries to ease the manipulation of such XML document.
    You can see the job configuration document at:
        http[s]://[hostname]/job/[jobname]/config.xml
    To change a job parameter you have to reissue the whole configuration to the server,
    this is done through the ._apply() method, that's implicitly called whenever one field of this class is modified.
    """

    __slots__ = ('_node', '_job', '_header')

    _header = "<?xml version='1.0' encoding='UTF-8'?>\n"

    def __init__(self, conf, job):
        """c'tor
        :param conf, str, the configuration document content as XML
        :param job, Job, the parent job instance"""
        self._job = job
        self._node = XML.fromstring(conf)
        assert(self._node.tag == 'project')

    @property
    def actions(self):
        raise NotImplementedError()

    def _set(self, name, value):
        """utility function used to ease propagating changes to the owner job
        :param name, str, the field to change in this configuration
        :param value, object, the new value of that field"""
        self._node.find(name).text = str(value)
        self._apply()

    @property
    def description(self):
        """the job description
        :return str"""
        return self._node.find('description').text

    @description.setter
    def set_description(self, cb):
        """set the job description
        :param cb, str, the description"""
        self._set('description', cb)

    @property
    def canRoam(self):
        """the job can roam
        :return bool"""
        return bool(self._node.find('canRoam').text)

    @canRoam.setter
    def set_canRoam(self, cb):
        """set the roaming of the job
        :param cb, bool, the job roaming"""
        self._set('canRoam', cb)

    @property
    def disabled(self):
        """the job is disabled
        :return bool"""
        return bool(self._find('disabled').text)

    @disabled.setter
    def set_disabled(self, cb):
        """set if the job is disabled
        :param cb, bool, the job is disabled or not"""
        self._set('disabled', cb)

    @property
    def concurrentBuild(self):
        """the job is can be ran concurrently
        :return bool"""
        return bool(self._node.find('concurrentBuild').text)

    @concurrentBuild.setter
    def set_concurrentBuild(self, cb):
        """set if the job is can be ran concurrently
        :param cb, bool, ..."""
        self._set('concurrentBuild', cb)

    @property
    def buildSteps(self):
        """the job build steps
        :return BuildSteps"""
        return BuildSteps(self._node.find('builders'), self)

    def toXML(self):
        """string representing the XML content of this configuration
        :return str"""
        return self._header + XML.tostring(self._node)

    def _apply(self):
        """notify the related Job instance that something has changed in this configuration, the job will take
        care of propagating the change to the server, eventually invoking .toXML()"""
        self._job._apply(self)

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
        self._server.create_job(name, jenkins.EMPTY_CONFIG_XML)
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
