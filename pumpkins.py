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

    def _apply(self):
        """utility function, propagate the change to the parent entity"""
        self._conf._apply()

    def add(self, script):
        """add a script to be executed by the job
        :param script, str, the shell script to execute"""
        node = XML.Element('hudson.tasks.Shell')
        comm = XML.Element('command')
        comm.text = script
        node.append(comm)
        self._node.append(node)
        self._apply()

    def __getitem__(self, index):
        """retrieve a specific step's script
        :param index, int, the index of the step to set
        :return str, the script assigned to the step"""
        return self._node[index].find('command').text

    def __setitem__(self, index, value):
        """sets a specific step
        :param index, int, the index of the step to set
        :param value, str, the script to assign to the step"""
        self._node[index].find('command').text = value
        self._apply()

    def __delitem__(self, index):
        """remove a build step from the list
        :param index, int, the index of the step to remove"""
        self._node.remove(self._node[index])
        self._apply()

    def __str__(self):
        if 0 == self.__len__():
            return 'no build steps'
        if 1 == self.__len__():
            return self.__getitem__(0)
        return "%d steps" % self.__len__()

    def __repr__(self):
        return self.__str__()


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

    """Da Job"""

    __slots__ = ('_job', '_server')

    def __init__(self, job, server):
        """c'tor
        :param job, dict, a dictionary as returned by jenkins.Jenkins.get_jobs()
        :param server, jenkins.Jenkins, the owner server instance"""
        self._job = job
        self._server = server

    @property
    def kind(self):
        """the kind of job
        :return str"""
        return self._job['_class']

    @property
    def name(self):
        """the name of the job
        :return str"""
        return self._job['name']

    @property
    def url(self):
        """the url of the job
        :return str"""
        return self._job['url']

    @property
    def color(self):
        """the 'color' of the job
        :return str"""
        return self._job['color']

    @property
    def fullname(self):
        """the full name of the job
        :return str"""
        return self._job['fullname']

    @property
    def _configuration(self):
        """the local representation of this job configuration
        :return Configuration"""
        return Configuration(self._server.get_job_config(self.name), self)

    def _apply(self, conf):
        """propagate to the server the given configuration
        :param conf, Configuration, the configuration to apply"""
        self._server.reconfig_job(self.name, conf.toXML())

    def copy(self, newname):
        """create a new job using the current one as a template
        :param newname, str, the name of the new job
        :return Job, the new job instance"""
        self._server.copy_job(self.name, newname)
        return Job(self._server.get_job(newname))

    def schedule(self, **kwargs):
        """schedule a job execution
        :param kwargs, a dictionary that will be used to configure the parameters of the build
        :return Queue, the instance of the enqueued object"""
        args = {}
        for k, v in kwargs.iteritems():
            args[k] = v
        return Queue(self._server.build_job(self.name, args), self, self._server)

    def build(self, **kwargs):
        """schedule a job execution and wait for the build to start
        :param kwargs, a dictionary that will be used to configure the parameters of the build
        :return Build, the build for that job"""
        return self.schedule(**kwargs).build

    def wait(self):
        """wait for the job last build to complete"""
        self.lastBuild.wait()

    def enable(self):
        """enable this job"""
        self._server.enable_job(self.name)

    def disable(self):
        """disable this job"""
        self._server.disable_job(self.name)

    def delete(self):
        """delete this job from the server"""
        self._server.delete_job(self.name)

    # -- info --
    
    @property
    def _info(self):
        """fetch the job informations from the server
        :return dict"""
        return self._server.get_job_info(self.name)
    
    @property
    def description(self):
        """the job description
        :return str"""
        return self._info['description']

    @property
    def buildable(self):
        """is the job buildable
        :return bool"""
        return self._info['buildable']

    @property
    def inQueue(self):
        """is the job in a queue
        :return bool"""
        return self._info['inQueue']

    @property
    def keepDependencies(self):
        """should the job keep its dependencies
        :return bool"""
        return self._info['keepDependencies']

    @property
    def nextBuildNumber(self):
        """the next build number
        :return int"""
        return self._info['lastBuildNumber']

    @property
    def concurentBuild(self):
        """is concurrent build enabled for this job
        :return bool"""
        return self._info['concurrentBuild']

    @property
    def builds(self):
        """the builds for this job
        :return list(Build)"""
        return [Build(b, self, self._server) for b in self._info['builds']]

    def _get_build(self, name):
        """utility function to retrieve a specific build for this job
        :param name, the name of the build
        :return Build|None"""
        build = self._info[name]
        if not build:
            return None
        builds = [b for b in self.builds if b.number == build['number']]
        return builds[0] if builds else None

    @property
    def firstBuild(self):
        """the very first build from this job
        :return Build"""
        return self._get_build('firstBuild')

    @property
    def lastBuild(self):
        """the last build for this job
        :return Build"""
        return self._get_build('lastBuild')

    @property
    def parameters(self):
        """the parameters of this job
        :return list(Parameter)"""
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
        """the last completed build
        :return Build"""
        return self._get_build('lastCompletedBuild')

    @property
    def lastFailedBuild(self):
        """the last failed build
        :return Build"""
        return self._get_build('lastFiledBuild')

    @property
    def lastStableBuild(self):
        """the last stable build
        :return Build"""
        return self._get_build('lastStableBuild')

    @property
    def lastUnstableBuild(self):
        """the last unstable build
        :return Build"""
        return self._get_build('lastUnstableBuild')

    @property
    def lastSuccessfulBuild(self):
        """last successful build
        :return Build"""
        return self._get_build('lastSuccessfulBuild')

    @property
    def lastUnsuccessfulBuild(self):
        """last unsuccessful build
        :return Build"""
        return self._get_build('lastUnsuccessfulBuild')

    # -- configuration --
    # here we forward the job attributes to the underlying Configuration

    def __getattr__(self, name):
        if hasattr(self._configuration, name):
            return getattr(self._configuration, name)
        raise AttributeError('Attribute %s not found' % name)

    def __setattr__(self, name, value):
        if name in self.__slots__:
            return object.__setattr__(self, name, value)
        if hasattr(self._configuration, name):
            setattr(self._configuration, name, value)

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.__str__()


class Jobs(object):

    """This is a Jobs container"""

    __slots__ = ('_server', '_jobs')
    
    def __init__(self, server):
        """c'tor
        :param server, jenkins.Jenkins, the owner server instance"""
        self._server = server
        self._jobs = [Job(j, server) for j in self._server.get_jobs()]
    
    def __contains__(self, name):
        return bool(self._server.job_exists(name))
    
    def __getitem__(self, index):
        """access to the jobs by index
        :param index, int, the index
        :return Job"""
        return self._jobs[index]
    
    def __iter__(self):
        return self._jobs.__iter__()
    
    def __call__(self, name):
        """access the job by name
        :param name, str, the job name
       :return Job or None"""
#       j = self._server.get_job_info(name)
#       return None if not j else Job({
#           '_class': j['_class'],
#           'color': j['color'],
#           'fullname': j['fullName'],
#           'name': j['name'],
#           'url': j['url'],
#       }, self._server)
        j = [job for job in self._jobs if job.name == name]
        return j[0] if j else None

    def __len__(self):
#       return self._server.jobs_count()
        return len(self._jobs)

    def create(self, name):
        """create a new job using an empty configuraion as a template
        :param name, str, the name of the new job
        :return Job, the newly created job"""
        self._server.create_job(name, jenkins.EMPTY_CONFIG_XML)
        self._jobs = [Job(j, self._server) for j in self._server.get_jobs()]
        return self.__call__(name)

    def __str__(self):
        return "%d jobs" % self.__len__()

    def __repr__(self):
        return self.__str__()


class User(object):

    """An user"""

    __slots__ = ('_user')

    def __init__(self, user):
        """c'tor
        :param user, dict, as returned by jenkins.Jenkins.get_whoami()"""
        self._user = user

    @property
    def fullName(self):
        """the user full name
        :return str"""
        return self._user['fullName']

    @property
    def name(self):
        """the user name
        :return str"""
        return self.fullName

    @property
    def id(self):
        """the user unique id
        :return int"""
        return self._user['id']

    @property
    def description(self):
        """the user description
        :return str"""
        return self._user['description']

    @property
    def url(self):
        """the url to the user web page
        :return str"""
        return self._user['absoluteUrl']

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.__str__()


class Host(object):

    """The Jenkins server"""

    __slots__ = ('_server')

    def __init__(self, url, username=None, password=None):
        """c'tor, perform the connection to the server
        :param url, str, the url to the server
        :param username, str, the username to use for the authentication
        :param password, str, the password to use for the authentication"""

        if not username:
            sys.stdout.write('Username: ')
            sys.stdout.flush()
            username = sys.stdin.readline()[:-1]

        if not password:
            password = getpass.getpass()

        self._server = jenkins.Jenkins(url, username, password)

    def __bool__(self):  # 3.x
        """check for the server validity (connection established)
        :return bool, True if the server is connected, false otherwise"""
        try:
            self.me
            return True
        except ConnectionError:
            return False
        except JenkinsException:
            return False

    def __nonzero__(self):  # 2.x
        """see __bool__()"""
        return self.__bool__()

    @property
    def jobs(self):
        """the jobs configured on this server
        :return Jobs"""
        return Jobs(self._server)
    
    @property
    def me(self):
        """the current user
        :return User"""
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

        job._configuration.buildSteps.add('true')

        self.assertEqual(len(job.builds), 0)
        a = datetime.datetime.now()
        queue = job.schedule()
        b = datetime.datetime.now()
        queue.wait()  # wait for the job to start
        c = datetime.datetime.now()
        queue.build.wait()  # wait for the job to finish
        d = datetime.datetime.now()

        print('schedule: %s' % (b - a))
        print('queue.wait: %s' % (c - b))
        print('build.wait: %s' % (d - c))

        self.assertEqual(len(job.builds), 1)
        self.assertTrue(job.lastBuild.succeed)

        print(job.lastBuild.duration)

        job._configuration.buildSteps[0] = 'false'
        self.assertTrue(job.build().failed)
        self.assertEqual(len(job.builds), 2)

#       job.delete()
#       self.assertTrue(name not in host.jobs)


if __name__ == '__main__':
    unittest.main()
