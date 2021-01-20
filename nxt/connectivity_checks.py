import logging
import argparse
from pyats import aetest
from dotenv import load_dotenv
import os
import re
import requests
import time
from nextensio_controller import *
import subprocess
from containers import kube_get_pod
from containers import docker_run

# THE MOTTO: DO DETERMINISTIC TESTING. What it means is simple. Lets say we configure something
# on the controller and we want to wait to ensure all the pods have got that config. One approach
# is just to sleep for a random period of time after configuration, and then run our test cases.
# That is something we SHOULD NOT DO. We should make whatever code changes required in the pods
# to give the scripts some feedback that "ok I got the config", so the scripts are waiting on a
# deterministic event rather than random period of time.
# The above applies to code that WE WRITE and WE CONTROL. There are times when we have to check
# for things in code we dont control. For example when we add a consul entry, it takes time to
# propagate through kubernetes coredns. And we dont have any control or indication of how long it
# takes or when its complete, so in those cases we do "check for dns, sleep 1 second if not ready",
# that is not a great thing to do, if we could control every piece of code in the system we would
# do it more predictably.

logger = logging.getLogger(__name__)
url = None
tenant = None
clusters = []
agents = []
numPods = 0

# In nextensio, all services are words seperated by dashes, all dots and @ symbols
# are converted to dashes


def nameToService(name):
    svc = name.replace(".", "-")
    svc = svc.replace("@", "-")
    return svc

# The consul service names are registered as servicename-domain where domain is the
# kuberentes domain created for that tenant/customer. We create kubernetes domains
# using the tenant id of the customer


def nameToConsul(name, tenant):
    svc = nameToService(name)
    consul = svc + "-" + tenant + '.query.consul'
    return consul

# We use the clustername-podname as the nomenclature. These names are loaded as
# environment shell variables from the /tmp/nextensio-kin/environment file, and
# hence not using dashes in the names (shell vars cant have dashes)


def clusterPod2Device(cluster, pod):
    return cluster + "_" + pod


def minionDevice(cluster, pod):
    return clusterPod2Device(cluster, "pod" + str(pod))


def runCmd(cmd):
    try:
        output = subprocess.check_output(cmd, shell=True)
        return output.decode()
    except:
        pass
        return ""


def podHasService(cluster, podname, xfor, xconnect):
    cmd = "/tmp/nextensio-kind/istioctl x describe pod %s -n %s --context %s" % (
        podname, tenant, cluster)
    out = runCmd(cmd)
    m = re.search(r'.*x-nextensio-for=%s\*' % xfor, out)
    if not m:
        return False
    m = re.search(r'.*x-nextensio-connect=%s\*' % xconnect, out)
    if not m:
        return False
    return True

# Confirm that the istio rules required for this agent are all installed properly


def istioChecks(cluster, podnum, xfor, xconnect):
    cluster = "kind-" + cluster
    pod = "pod" + str(podnum)
    podname = kube_get_pod(cluster, tenant, pod)
    while not podname:
        logger.info("Waiting to get podname for %s from cluster %s" %
                    (pod, cluster))
        time.sleep(1)
        podname = kube_get_pod(cluster, tenant, pod)

    podready = podHasService(cluster, podname, xfor, xconnect)
    while not podready:
        logger.info("Waiting to describe pod %s from cluster %s, xfor %s, xconnect %s" %
                    (podname, cluster, xfor, xconnect))
        time.sleep(1)
        podready = podHasService(cluster, podname, xfor, xconnect)

# Do an nslookup inside consul server pod to ensure that all the services of our
# interest, both local and remote, are reachable. The names will be reachable
# only if the agents / connectors corresponding to those services have connected
# to the cluster and advertised their services via Hello message. So this is the
# best kind of check we have to ensure that the agents and connectors are "ready"


def checkConsulDns(devices, cluster, username):
    device = clusterPod2Device(cluster, "consul")
    service = nameToConsul(username, tenant)
    addr = devices[device].shell.execute('nslookup ' + service)
    while not "Address 1" in addr:
        logger.info('Cluster %s, waiting for consul entry %s' %
                    (cluster, service))
        time.sleep(1)
        addr = devices[device].shell.execute('nslookup ' + service)


def checkConsulDnsAll(devices):
    # TODO: These list of names should be derived by reading the controller itself, or
    # maybe from some testcase data file ?
    usernames = ['test1@nextensio.net', 'test2@nextensio.net', 'default@nextensio.net',
                 'v1.kismis@nextensio.net', 'v2.kismis@nextensio.net', 'default-internet',
                 'v1-kismis-org', 'v2-kismis-org']
    for cluster in clusters:
        for username in usernames:
            checkConsulDns(devices, cluster, username)


def parseVersions(versions):
    m = re.search(r'.*USER=([0-9]+)\.([0-9]+).*', versions)
    if not m:
        return None

    user = int(m[2])
    m = re.search(r'.*BUNDLE=([0-9]+)\.([0-9]+).*', versions)
    if not m:
        return None
    bundle = int(m[2])

    m = re.search(r'.*ROUTE=([0-9]+)\.([0-9]+).*', versions)
    if not m:
        return None
    route = int(m[2])

    m = re.search(r'.*POLICY=([0-9]+)\.([0-9]+).*', versions)
    if not m:
        return None
    policy = int(m[2])

    return (user, bundle, route, policy)


def versionOk(current, previous, increments):
    if not current:
        return False

    if not previous:
        return True

    (cU, cB, cR, cP) = current
    (pU, pB, pR, pP) = previous
    if pU + increments['user'] != cU or pB + increments['bundle'] != cB or pR + increments['route'] != cR or pP + increments['policy'] != cP:
        return False
    return True

# Figure out from OPA in the pod, whether it has received all the expected configurations
# from the controller. This goes back to the motto of "deterministic testing" outlined at
# the beginning of this file


def getOpaVersion(devices, d, previous, increments):
    versions = devices[d].shell.execute(
        "cat /tmp/opa_attr_versions")
    current = parseVersions(versions)
    while not versionOk(current, previous, increments):
        logger.info("Waiting for opa versions from device %s, cur %s, previous %s, incr %s" % (
            d, current, previous, increments))
        time.sleep(1)
        versions = devices[d].shell.execute(
            "cat /tmp/opa_attr_versions")
        current = parseVersions(versions)

    return current


def getAllOpaVersions(devices, current, increments):
    versions = {}
    for c in clusters:
        for p in range(1, numPods+1):
            d = minionDevice(c, p)
            parse = getOpaVersion(devices, d, current.get(d), increments)
            versions[d] = parse
    return versions

# TODO: Its hacky to be restarting an entire device using the shell/console object
# of that device. We do that because the console object is all pyAts allows us to
# override today. Need to find out if pyAts will allow us to override a device object
# itself and if so we can add a device restart in our own custom device object


def resetAgents(devices):
    devices['nxt_agent1'].shell.restart()
    devices['nxt_agent2'].shell.restart()
    devices['nxt_default'].shell.restart()
    devices['nxt_kismis_ONE'].shell.restart()
    devices['nxt_kismis_TWO'].shell.restart()


# Ensure public and private access is successul
def publicAndPvtPass(agent1, agent2):
    if proxyGet('nxt_agent1', 'https://foobar.com',
                "I am Nextensio agent nxt_default") != True:
        raise Exception("agent1 default internet access fail")
    if proxyGet('nxt_agent2', 'https://foobar.com',
                "I am Nextensio agent nxt_default") != True:
        raise Exception("agent2 default internet fail")
    if proxyGet('nxt_agent1', 'https://kismis.org',
                "I am Nextensio agent nxt_kismis_" + agent1) != True:
        raise Exception("agent1 kismis fail")
    if proxyGet('nxt_agent2', 'https://kismis.org',
                "I am Nextensio agent nxt_kismis_" + agent2) != True:
        raise Exception("agent2 kismis fail")

# Ensure public access fails


def publicFail():
    if proxyGet('nxt_agent1', 'https://foobar.com',
                "I am Nextensio agent nxt_default") == True:
        raise Exception("agent1 default internet access works!")
    if proxyGet('nxt_agent2', 'https://foobar.com',
                "I am Nextensio agent nxt_default") == True:
        raise Exception("agent2 default internet works!")


def config_routes(tag1, tag2):
    ok = create_route(url, tenant, 'test1@nextensio.net', 'kismis.org', tag1)
    while not ok:
        logger.info('Route creation failed, retrying ...')
        time.sleep(1)
        ok = create_route(url, tenant, 'test1@nextensio.net',
                          'kismis.org', tag1)
    ok = create_route(url, tenant, 'test2@nextensio.net', 'kismis.org', tag2)
    while not ok:
        logger.info('Route creation failed, retrying ...')
        time.sleep(1)
        ok = create_route(url, tenant, 'test2@nextensio.net',
                          'kismis.org', tag2)


def config_user_attr(level1, level2):
    ok = create_user_attr(url, 'test1@nextensio.net', tenant, 'employee',
                          'IC', level1, ['ABU,BBU'], ['engineering', 'sales'])
    while not ok:
        logger.info('UserAttr test1 config failed, retrying ...')
        time.sleep(1)
        ok = create_user_attr(url, 'test1@nextensio.net', tenant, 'employee',
                              'IC', level1, ['ABU,BBU'], ['engineering', 'sales'])

    ok = create_user_attr(url, 'test2@nextensio.net', tenant, 'employee',
                          'IC', level2, ['ABU,BBU'], ['engineering', 'sales'])
    while not ok:
        logger.info('UserAttr test2 config failed, retrying ...')
        time.sleep(1)
        ok = create_user_attr(url, 'test2@nextensio.net', tenant, 'employee',
                              'IC', level2, ['ABU,BBU'], ['engineering', 'sales'])


def config_user(user, service, gateway, pod):
    ok = create_user(url, user, tenant, 'Test User %s' % user, user,
                     [service], gateway, pod)
    while not ok:
        logger.info('User %s updation failed, retrying ...' % user)
        time.sleep(1)
        ok = create_user(url, user, tenant, 'Test User %s' % user, user,
                         [service], gateway, pod)


def config_bundle(bundle, service, gateway, pod):
    ok = create_bundle(url, bundle, tenant, 'Bundle %s' % bundle,
                       [service], gateway, pod)
    while not ok:
        logger.info('Bundle %s updation failed, retrying ...' % bundle)
        time.sleep(1)
        ok = create_bundle(url, bundle, tenant, 'Bundle %s' % bundle,
                           [service], gateway, pod)


def config_default_bundle_attr(depts, teams):
    ok = create_bundle_attr(url, 'default@nextensio.net', tenant,
                            depts, teams, 10, 10, "allowed")
    while not ok:
        logger.info('BundleAttr bundle default config failed, retrying ...')
        time.sleep(1)
        ok = create_bundle_attr(url, 'default@nextensio.net',
                                tenant, depts, teams, 10, 10, "allowed")


def resetPods(devices, cluster, pods):
    for pod in pods:
        device = minionDevice(cluster, pod)
        devices[device].shell.restart()

# Get a URL via a proxy


def proxyGet(agent, url, expected):
    env = {"https_proxy": "http://" + os.getenv(agent) + ":8081"}
    try:
        text = docker_run("curl", "curl --silent --connect-timeout 5 --max-time 5 -k %s" % url, environment=env)
    except Exception as e:
        pass
        print("Exception %s" % e)
        return False
    if expected not in text:
        return False
    return True

# Basic access sanity checks public and private URL access, in some cases
# the accesses are expected to succeed and in some cases its expected to fail
# TODO: The route versions are not in place yet, they are always zero.
# When we add proper route version support in minion/opa, come back here
# and and add the right route version increments whenever we change routes


def basicAccessSanity(devices):
    increments = {'user': 0, 'bundle': 0, 'route': 0, 'policy': 0}
    logger.info('STEP1')
    versions = getAllOpaVersions(devices, {}, increments)
    config_routes('v1', 'v2')
    config_user_attr(50, 50)
    config_default_bundle_attr(['ABU,BBU'], ['engineering', 'sales'])
    increments = {'user': 2, 'bundle': 1, 'route': 0, 'policy': 0}
    versions = getAllOpaVersions(devices, versions, increments)
    # Test public and private access via default routing setup
    publicAndPvtPass("ONE", "TWO")

    logger.info('STEP2')
    # Switch routes and ensure private route http get has switched
    config_routes('v2', 'v1')
    increments = {'user': 0, 'bundle': 0, 'route': 0, 'policy': 0}
    versions = getAllOpaVersions(devices, versions, increments)
    publicAndPvtPass("TWO", "ONE")

    logger.info('STEP3')
    # Reduce the level of the user and ensure user cant access public
    config_user_attr(5, 5)
    increments = {'user': 2, 'bundle': 0, 'route': 0, 'policy': 0}
    versions = getAllOpaVersions(devices, versions, increments)
    publicFail()

    logger.info('STEP4')
    # Increase the level of the user and ensure user can again access public
    config_user_attr(50, 50)
    increments = {'user': 2, 'bundle': 0, 'route': 0, 'policy': 0}
    versions = getAllOpaVersions(devices, versions, increments)
    publicAndPvtPass("TWO", "ONE")

    logger.info('STEP5')
    # Change the teams of the bundle and ensure that user cant access default internet
    config_default_bundle_attr(['abcd,efgh'], ['abcd', 'efgh'])
    increments = {'user': 0, 'bundle': 1, 'route': 0, 'policy': 0}
    versions = getAllOpaVersions(devices, versions, increments)
    publicFail()

    logger.info('STEP6')
    # Restore the bundle attributes and ensure default internet works again
    config_default_bundle_attr(['ABU,BBU'], ['engineering', 'sales'])
    increments = {'user': 0, 'bundle': 1, 'route': 0, 'policy': 0}
    versions = getAllOpaVersions(devices, versions, increments)
    publicAndPvtPass("TWO", "ONE")


# This aetest sections in this class is executed at the very beginning BEFORE
# any of the actual test cases run. So we have all the environment loading and
# initializations etc.. here
class CommonSetup(aetest.CommonSetup):

    def loadEnv(self):
        global url
        global tenant

        # Load the testbed information variables as environment variables
        load_dotenv(dotenv_path='/tmp/nextensio-kind/environment')
        url = "http://" + os.getenv('ctrl_ip') + ":8080/api/v1/"
        ok, tenants = get_tenants(url)
        while not ok:
            logger.info('Tenant fetch %s failed, retrying ...' % url)
            time.sleep(1)
            ok, tenants = get_tenants(url)
        # The test setup is assumed to be created with just one tenant, if we need more we just need
        # to search for the right tenant name or something inside the returned list of tenants
        tenant = tenants[0]['_id']

    def parseTestbed(self, testbed):
        global clusters
        global agents
        global numPods
        for d in testbed.devices:
            device = testbed.devices[d]
            if device.type == 'docker':
                agents.append(d)
            elif device.type == 'kubernetes':
                m = re.search(r'([a-zA-Z]+)_pod([1-9]+)', d)
                if m:
                    if m[1] not in clusters:
                        clusters.append(m[1])
                    if int(m[2]) > numPods:
                        numPods = int(m[2])

    @ aetest.subsection
    def verifyTestbed(self,
                      testbed):
        self.loadEnv()
        self.parseTestbed(testbed)
        for d in testbed.devices:
            testbed.devices[d].connect(alias='shell', via='container')
            if 'consul' in d:
                testbed.devices[d].shell.configure(
                    namespace='consul-system', container='')
            else:
                testbed.devices[d].shell.configure(
                    namespace=tenant, container='minion')


class CommonCleanup(aetest.CommonCleanup):

    @ aetest.subsection
    def cleanup(self):
        logger.info('Cleanup done')


def placeAgent(spec):
    gateway = 'gateway.' + spec['gateway'] + '.nextensio.net'
    if spec['agent'] == True:
        config_user(spec['name'], spec['service'], gateway,  spec['pod'])
    else:
        config_bundle(spec['name'], spec['service'], gateway, spec['pod'])


def verifyIstio(spec):
    for cluster in clusters:
        istioChecks(cluster, spec['pod'],
                    spec['service'], nameToService(spec['name']))


def placeAndVerifyAgents(specs):
    for spec in specs:
        placeAgent(spec)
    for spec in specs:
        verifyIstio(spec)

# The aetest.setup section in this class is executed BEFORE the aetest.test sections,
# so this is like a big-test with a setup, and then a set of test cases and then a teardown,
# and then the next big-test class is run similarly


class Agent2PodsConnector3PodsClusters2(aetest.Testcase):
    '''Agent1 and Agent2 in two seperate pods, default, kismis.v1 and kismisv2 in
    three seperate pods, and agent and connector in two seperate clusters (testa, testc)
    '''
    @ aetest.setup
    def setup(self, testbed):
        specs = [
            {'name': 'test1@nextensio.net', 'agent': True,
                'service': 'test1-nextensio-net', 'gateway': 'testa', 'pod': 1},
            {'name': 'test2@nextensio.net', 'agent': True,
                'service': 'test2-nextensio-net', 'gateway': 'testa', 'pod': 2},
            {'name': 'default@nextensio.net', 'agent': False,
                'service': 'default-internet', 'gateway': 'testc', 'pod': 3},
            {'name': 'v1.kismis@nextensio.net', 'agent': False,
                'service': 'v1.kismis.org', 'gateway': 'testc', 'pod': 4},
            {'name': 'v2.kismis@nextensio.net', 'agent': False,
                'service': 'v2.kismis.org', 'gateway': 'testc', 'pod': 5}
        ]
        placeAndVerifyAgents(specs)
        resetAgents(testbed.devices)
        # reset all pods everywhere
        resetPods(testbed.devices, 'testa', [1, 2, 3, 4, 5])
        resetPods(testbed.devices, 'testc', [1, 2, 3, 4, 5])
        checkConsulDnsAll(testbed.devices)

    @ aetest.test
    def basicConnectivity(self, testbed, **kwargs):
        basicAccessSanity(testbed.devices)

    @ aetest.cleanup
    def cleanup(self):
        return


class Agent2PodsConnector3PodsClusters1(aetest.Testcase):
    '''Agent1 and Agent2 in two seperate pods, default, kismis.v1 and kismisv2 in
    three seperate pods, and agent and connector in the same cluster (testa)
    '''
    @ aetest.setup
    def setup(self, testbed):
        specs = [
            {'name': 'test1@nextensio.net', 'agent': True,
                'service': 'test1-nextensio-net', 'gateway': 'testa', 'pod': 1},
            {'name': 'test2@nextensio.net', 'agent': True,
                'service': 'test2-nextensio-net', 'gateway': 'testa', 'pod': 2},
            {'name': 'default@nextensio.net', 'agent': False,
                'service': 'default-internet', 'gateway': 'testa', 'pod': 3},
            {'name': 'v1.kismis@nextensio.net', 'agent': False,
                'service': 'v1.kismis.org', 'gateway': 'testa', 'pod': 4},
            {'name': 'v2.kismis@nextensio.net', 'agent': False,
                'service': 'v2.kismis.org', 'gateway': 'testa', 'pod': 5}
        ]
        resetAgents(testbed.devices)
        # reset all pods everywhere
        resetPods(testbed.devices, 'testa', [1, 2, 3, 4, 5])
        resetPods(testbed.devices, 'testc', [1, 2, 3, 4, 5])
        checkConsulDnsAll(testbed.devices)

    @ aetest.test
    def basicConnectivity(self, testbed, **kwargs):
        basicAccessSanity(testbed.devices)

    @ aetest.test
    def dynamicSwitchSameCluster(self, testbed, **kwargs):
        '''Switch from the current connection model to go to different set of pods, and 
        come back, all without doing pod restarts. This is to ensure nothing in the pod 
        like agent<-->socket hashtables etc.. remain stale when agents come and go
        '''
        # Switch to two cluster and a different set of pods
        specs = [
            {'name': 'test1@nextensio.net', 'agent': True,
                'service': 'test1-nextensio-net', 'gateway': 'testa', 'pod': 3},
            {'name': 'test2@nextensio.net', 'agent': True,
                'service': 'test2-nextensio-net', 'gateway': 'testa', 'pod': 1},
            {'name': 'default@nextensio.net', 'agent': False,
                'service': 'default-internet', 'gateway': 'testa', 'pod': 2},
            {'name': 'v1.kismis@nextensio.net', 'agent': False,
                'service': 'v1.kismis.org', 'gateway': 'testa', 'pod': 5},
            {'name': 'v2.kismis@nextensio.net', 'agent': False,
                'service': 'v2.kismis.org', 'gateway': 'testa', 'pod': 4}
        ]
        # Reset agents so they reconnect to new pod assignments, but dont reset pods
        resetAgents(testbed.devices)
        # wait for all consul entries to be populated, which means all connections are fine
        checkConsulDnsAll(testbed.devices)
        basicAccessSanity(testbed.devices)
        # And now go back to the original configuration of this test case
        specs = [
            {'name': 'test1@nextensio.net', 'agent': True,
                'service': 'test1-nextensio-net', 'gateway': 'testa', 'pod': 1},
            {'name': 'test2@nextensio.net', 'agent': True,
                'service': 'test2-nextensio-net', 'gateway': 'testa', 'pod': 2},
            {'name': 'default@nextensio.net', 'agent': False,
                'service': 'default-internet', 'gateway': 'testa', 'pod': 3},
            {'name': 'v1.kismis@nextensio.net', 'agent': False,
                'service': 'v1.kismis.org', 'gateway': 'testa', 'pod': 4},
            {'name': 'v2.kismis@nextensio.net', 'agent': False,
                'service': 'v2.kismis.org', 'gateway': 'testa', 'pod': 5}
        ]
        resetAgents(testbed.devices)
        checkConsulDnsAll(testbed.devices)
        basicAccessSanity(testbed.devices)

    @ aetest.test
    def dynamicSwitch2Cluster(self, testbed, **kwargs):
        '''Switch from the current connection model to go to different set of pods 
        and different cluster, and  come back, all without doing pod restarts. 
        This is to ensure nothing in the pod  like agent<-->socket hashtables etc.. 
        remain stale when agents come and go
        '''
        # Switch to two cluster and a different set of pods
        specs = [
            {'name': 'test1@nextensio.net', 'agent': True,
                'service': 'test1-nextensio-net', 'gateway': 'testa', 'pod': 3},
            {'name': 'test2@nextensio.net', 'agent': True,
                'service': 'test2-nextensio-net', 'gateway': 'testc', 'pod': 1},
            {'name': 'default@nextensio.net', 'agent': False,
                'service': 'default-internet', 'gateway': 'testa', 'pod': 2},
            {'name': 'v1.kismis@nextensio.net', 'agent': False,
                'service': 'v1.kismis.org', 'gateway': 'testc', 'pod': 5},
            {'name': 'v2.kismis@nextensio.net', 'agent': False,
                'service': 'v2.kismis.org', 'gateway': 'testa', 'pod': 4}
        ]
        # Reset agents so they reconnect to new pod assignments, but dont reset pods
        resetAgents(testbed.devices)
        # wait for all consul entries to be populated, which means all connections are fine
        checkConsulDnsAll(testbed.devices)
        basicAccessSanity(testbed.devices)
        # And now go back to the original configuration of this test case
        specs = [
            {'name': 'test1@nextensio.net', 'agent': True,
                'service': 'test1-nextensio-net', 'gateway': 'testa', 'pod': 1},
            {'name': 'test2@nextensio.net', 'agent': True,
                'service': 'test2-nextensio-net', 'gateway': 'testa', 'pod': 2},
            {'name': 'default@nextensio.net', 'agent': False,
                'service': 'default-internet', 'gateway': 'testa', 'pod': 3},
            {'name': 'v1.kismis@nextensio.net', 'agent': False,
                'service': 'v1.kismis.org', 'gateway': 'testa', 'pod': 4},
            {'name': 'v2.kismis@nextensio.net', 'agent': False,
                'service': 'v2.kismis.org', 'gateway': 'testa', 'pod': 5}
        ]
        resetAgents(testbed.devices)
        checkConsulDnsAll(testbed.devices)
        basicAccessSanity(testbed.devices)

    @ aetest.cleanup
    def cleanup(self):
        return


class Agent1PodsConnector1PodsClusters1(aetest.Testcase):
    '''Agent1 and Agent2 in the same pod, default, kismis.v1 and kismisv2 in
    the same pod (different from agent pod), and agent and connector in the same cluster (testa)
    '''
    @ aetest.setup
    def setup(self, testbed):
        specs = [
            {'name': 'test1@nextensio.net', 'agent': True,
                'service': 'test1-nextensio-net', 'gateway': 'testa', 'pod': 1},
            {'name': 'test2@nextensio.net', 'agent': True,
                'service': 'test2-nextensio-net', 'gateway': 'testa', 'pod': 1},
            {'name': 'default@nextensio.net', 'agent': False,
                'service': 'default-internet', 'gateway': 'testa', 'pod': 2},
            {'name': 'v1.kismis@nextensio.net', 'agent': False,
                'service': 'v1.kismis.org', 'gateway': 'testa', 'pod': 2},
            {'name': 'v2.kismis@nextensio.net', 'agent': False,
                'service': 'v2.kismis.org', 'gateway': 'testa', 'pod': 2}
        ]
        resetAgents(testbed.devices)
        # reset all pods everywhere
        resetPods(testbed.devices, 'testa', [1, 2, 3, 4, 5])
        resetPods(testbed.devices, 'testc', [1, 2, 3, 4, 5])
        checkConsulDnsAll(testbed.devices)

    @ aetest.test
    def basicConnectivity(self, testbed, **kwargs):
        basicAccessSanity(testbed.devices)


class AgentConnector1PodsClusters1(aetest.Testcase):
    '''Agent1 and Agent2 in the same pod, default, kismis.v1 and kismisv2 in
    the same pod, the same as agent pod, and agent and connector in the same cluster (testa)
    '''
    @ aetest.setup
    def setup(self, testbed):
        specs = [
            {'name': 'test1@nextensio.net', 'agent': True,
                'service': 'test1-nextensio-net', 'gateway': 'testa', 'pod': 1},
            {'name': 'test2@nextensio.net', 'agent': True,
                'service': 'test2-nextensio-net', 'gateway': 'testa', 'pod': 1},
            {'name': 'default@nextensio.net', 'agent': False,
                'service': 'default-internet', 'gateway': 'testa', 'pod': 1},
            {'name': 'v1.kismis@nextensio.net', 'agent': False,
                'service': 'v1.kismis.org', 'gateway': 'testa', 'pod': 1},
            {'name': 'v2.kismis@nextensio.net', 'agent': False,
                'service': 'v2.kismis.org', 'gateway': 'testa', 'pod': 1}
        ]
        resetAgents(testbed.devices)
        # reset all pods everywhere
        resetPods(testbed.devices, 'testa', [1, 2, 3, 4, 5])
        resetPods(testbed.devices, 'testc', [1, 2, 3, 4, 5])
        checkConsulDnsAll(testbed.devices)

    @ aetest.test
    def basicConnectivity(self, testbed, **kwargs):
        basicAccessSanity(testbed.devices)


if __name__ == '__main__':
    import argparse
    from pyats.topology import loader

    parser = argparse.ArgumentParser()
    parser.add_argument('--testbed', dest='testbed',
                        type=loader.load)

    args, unknown = parser.parse_known_args()

    aetest.main(**vars(args))
