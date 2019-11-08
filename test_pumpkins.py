import datetime
import pytest
import pumpkins

hostname = 'http://localhost:8080'
username = 'admin'
password = 'admin'

@pytest.fixture
def host():
    return pumpkins.Host(hostname, username=username, password=password)

def test_connection(host):
    assert host

def test_user(host):
    assert host.me.name == username

def test_job_lifecycle(host):
    assert host

    name = 'asdasdasd'
    if host.job(name):
        host.job(name).delete()
    assert name not in host.jobs()

    job = host.createJob(name)
    assert name in host.jobs()
    assert host.job(name) is not None

    job._configuration.buildSteps.add('true')

    assert len(job.builds) == 0
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

    assert len(job.builds) == 1
    assert job.lastBuild.succeeded

    print(job.lastBuild.duration)

    job._configuration.buildSteps[0] = 'false'
    assert job.start().failed
    assert len(job.builds) == 2

    job.delete()
    assert name not in host.jobs()

