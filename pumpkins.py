import sys
import getpass
import jenkins
import re

# https://python-jenkins.readthedocs.io/en/latest/examples.html

class Parameter(object):
		
	__slots__ = ('name', 'kind', 'description', 'defaultValue')

	reType = re.compile('^(\w+)ParameterDefinition$')

	def __init__(self, param):
		self.name = themparamap['name']
		self.kind = Parameter.reType.match(param['type']).group(1).lower()
		self.description = param['description']
		self.defaultValue = param['defaultParameterValue']['value']
			if 'defaultParameterValue' in param:
			else None
	
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

	__slots__ = ('_info', '_builds')

	def __init__(self, info):
		self._info = info
		self._builds = None

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
		if not self._builds:
			self._builds = [Build(b) for b in self._info['builds']]
		return self._builds

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
		return [Parameter(p) for p in self._info['property'][0]['parameterDefinitions']]
		
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

class Job(object):

	__slots__ = ('_job', '_server', '_info')

	def __init__(self, job, server):
		self._job = job
		self._server = server
		self._info = None

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

	def copy(self, newname):
		self._server.copy_job(self.name, newname)
		return Job(self._server.get_job(newname))

	def build(self, **kwargs):
		args = {}
		for k, v in kwargs.iteritems():
			args[k] = v
		self._server.build_job(self.name, args)

	def reconfig(self):
		self._server.reconfig_job(self.name)

	def enable(self):
		self._server.enable_job(self.name)

	def disable(self):
		self._server.disable_job(self.name)

	def delete(self):
		self._server.delete_job(self.name)

	def __getattr__(self, name):
		if not self._info:
			self._info = Info(self._server.get_job_info(self.name))
		if hasattr(self._info, name):
			return getattr(self._info, name)
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

	__slots__ = ('_server', '_jobs')

	def __init__(self, url, username=None, password=None):
		
		self._jobs = None
		
		if not username:
			sys.stdout.write('Username: ')
			sys.stdout.flush()
			username = sys.stdin.readline()[:-1]

		if not password:
			password = getpass.getpass()

		self._server = jenkins.Jenkins(url, username, password)

	def _invalidate(self):
		self._jobs = None

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

	@property
	def jobs(self):
		if not self._jobs:
			self._jobs = [Job(j, self._server) for j in self._server.get_jobs()]
		return self._jobs

	@property
	def me(self):
		return User(self._server.get_whoami())


if __name__ == '__main__':

	server = Pumpkins('http://localhost:8080')

	if not server:
		exit(1)

	print(server.me)

