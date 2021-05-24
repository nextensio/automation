import logging
import argparse
from pyats import aetest
from dotenv import load_dotenv
import os
import sys
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
numApods = 0
numCpods = 0
token = ""

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


def ApodminionDevice(cluster, pod):
    return clusterPod2Device(cluster, "apod" + str(pod))
 
def CpodminionDevice(cluster, pod):
    return clusterPod2Device(cluster, "cpod" + str(pod))


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


def istioChecks(cluster, useragent, podnum, xfor, xconnect):
    cluster = "kind-" + cluster
    if useragent == True:
        pod = "apod" + str(podnum)
    else:
        pod = "cpod" + str(podnum)
    podname = kube_get_pod(cluster, tenant, pod)
    while not podname:
        logger.info("Waiting to get podname for %s from cluster %s" %
                    (pod, cluster))
        time.sleep(1)
        podname = kube_get_pod(cluster, tenant, pod)

    while not podready:
        logger.info("Waiting to describe pod %s from cluster %s, xfor %s, xconnect %s" %
                    (podname, cluster, xfor, xconnect))
        time.sleep(1)
        podready = podHasService(cluster, podname, xfor, xconnect)

# First make sure the agent is connected to the right pod, after that do an
# nslookup inside consul server pod to ensure that all the services of our
# interest, both local and remote, are reachable. The names will be reachable
# only if the agents / connectors corresponding to those services have connected
# to the cluster and advertised their services via Hello message. So this is the
# best kind of check we have to ensure that the agents and connectors are "ready"
def checkConsulKV(devices, cluster, svc, pod, agent):
    podnm = 'apod1'
    device = clusterPod2Device(cluster, "consul")
    service = nameToService(svc)

    value = devices[device].shell.execute('consul kv get -recurse ' + service).strip()
    lines = value.splitlines()
    if len(lines) > 1:
        print(value)
        print("Cluster %s service %s has more than one registration!" % (cluster, service))
        sys.exit(1)

    if agent == True:
        m = re.search(r'.*:(apod[0-9]+)', value)
        podnm = 'apod%s' % pod
    else:
        m = re.search(r'.*:(cpod[0-9]+)', value)
        podnm = 'cpod%s' % pod
    while m == None or m[1] != podnm:
        time.sleep(1)
        cur = "None"
        if m != None:
            cur = m[1]
        logger.info('Cluster %s, waiting for consul kv %s in %s, current %s' %
                    (cluster, service, podnm, cur))
        value = devices[device].shell.execute('consul kv get -recurse ' + service).strip()
        if len(lines) > 1:
            print(value)
            print("Cluster %s service %s has more than one registration!" % (cluster, service))
            sys.exit(1)
        if agent == True:
            m = re.search(r'.*:(apod[0-9]+)', value)
        else:
            m = re.search(r'.*:(cpod[0-9]+)', value)
    
def checkConsulDns(devices, cluster, svc):
    device = clusterPod2Device(cluster, "consul")
    service = nameToConsul(svc, tenant)
    addr = devices[device].shell.execute('nslookup ' + service)
    while not "Address 1" in addr:
        logger.info('Cluster %s, waiting for consul entry %s' %
                    (cluster, service))
        time.sleep(1)
        addr = devices[device].shell.execute('nslookup ' + service)


def checkConsulDnsAndKV(specs, devices):
    services = []
    cls = []
    for spec in specs:
        if spec['agent'] != True:
            services.append({'name': 'nextensio-' + spec['name'], 'gateway': spec['gateway'], 'pod': spec['pod']})
            if spec['service'] != '':
                services.append({'name': spec['service'], 'gateway': spec['gateway'], 'pod': spec['pod']})
            if spec['gateway'] not in cls:
                cls.append(spec['gateway'])

    for cluster in cls:
        for service in services:
            if cluster == service['gateway']:
                checkConsulKV(devices, cluster, service['name'], service['pod'], False)
                checkConsulDns(devices, cluster, service['name'])

def checkOnboarding(specs):
    for spec in specs:
        if spec['agent'] == True:
            podnm = "apod" + str(spec['pod'])
        else:
            podnm = "cpod" + str(spec['pod'])
        gw = spec['gateway'] + ".nextensio.net"
        checkUserOnboarding(spec['name'], gw, podnm)

def checkUserOnboarding(uid, gw, podnm):
    ok, onblog = get_onboard_log(url, tenant, uid, token)
    while not ok:
        print('Onboarding log entry fetch failed, retrying ...')
        time.sleep(1)
        ok, onblog = get_onboard_log(url, tenant, uid, token)
    while onblog['gw'] != gw:
        print('Waiting for %s to get onboarded' % uid)
        time.sleep(1)
        ok, onblog = get_onboard_log(url, tenant, uid, token)
    while onblog['podnm'] != podnm:
        print('Waiting for %s to get onboarded' % uid)
        time.sleep(1)
        ok, onblog = get_onboard_log(url, tenant, uid, token)

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
        for p in range(1, numApods+1):
            d = ApodminionDevice(c, p)
            parse = getOpaVersion(devices, d, current.get(d), increments)
            versions[d] = parse
        for p in range(1, numCpods+1):
            d = CpodminionDevice(c, p)
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

def resetUserAgents(devices):
    devices['nxt_agent1'].shell.restart()
    devices['nxt_agent2'].shell.restart()


# Ensure public and private access is successul
def publicAndPvtPass(agent1, agent2):
    if proxyGet('nxt_agent1', 'https://foobar.com',
                "I am Nextensio agent nxt_default") != True:
        print("agent1 default internet access fail")
        sys.exit(1)
    if proxyGet('nxt_agent2', 'https://foobar.com',
                "I am Nextensio agent nxt_default") != True:
        print("agent2 default internet fail")
        sys.exit(1)
    if proxyGet('nxt_agent1', 'https://kismis.org',
                "I am Nextensio agent nxt_kismis_" + agent1) != True:
        print("agent1 kismis fail")
        sys.exit(1)
    if proxyGet('nxt_agent2', 'https://kismis.org',
                "I am Nextensio agent nxt_kismis_" + agent2) != True:
        print("agent2 kismis fail")
        sys.exit(1)

# Ensure public access fails


def publicFail():
    if proxyGet('nxt_agent1', 'https://foobar.com',
                "I am Nextensio agent nxt_default") == True:
        raise Exception("agent1 default internet access works!")
    if proxyGet('nxt_agent2', 'https://foobar.com',
                "I am Nextensio agent nxt_default") == True:
        raise Exception("agent2 default internet works!")

    
def config_policy():
    global token

    with open('policy.AccessPolicy','r') as file:
        rego = file.read()
    ok = create_policy(url, tenant, 'AccessPolicy', rego, token)
    while not ok:
        logger.info('Access Policy creation failed, retrying ...')
        time.sleep(1)
        ok = create_policy(url, tenant, 'AccessPolicy', rego, token)
        
    with open('policy.RoutePolicy','r') as file:
        rego = file.read()
    ok = create_policy(url, tenant, 'RoutePolicy', rego, token)
    while not ok:
        logger.info('Route Policy creation failed, retrying ...')
        time.sleep(1)
        ok = create_policy(url, tenant, 'RoutePolicy', rego, token)

        
def config_routes(tag1, tag2):
    global token

    routejson = { "host": "kismis.org", 
                      "routeattrs": [
		      {"tag": tag1, "team": ["engineering","sales"], "dept": ["ABU","BBU"],
                       "category":["employee","nonemployee"], "type":["IC"] },
		      {"tag": tag2, "team": ["engineering","sales"], "dept": ["ABU","BBU"],
                       "category":["employee"], "type":["manager"] }
		      ]
                }
    ok = create_host_attr(url, tenant, routejson, token)
    while not ok:
        logger.info('Route creation failed, retrying ...')
        time.sleep(1)
        ok = create_host_attr(url, tenant, routejson, token)


def config_user_attr(level1, level2):
    global token

    user1attrjson = {"uid":"test1@nextensio.net", "category":"employee",
                     "type":"IC", "level":level1, "dept":["ABU","BBU"], "team":["engineering","sales"] }
    user2attrjson = {"uid":"test2@nextensio.net", "category":"employee",
                     "type":"manager", "level":level2, "dept":["ABU","BBU"], "team":["engineering","sales"] }
    ok = create_user_attr(url, tenant, user1attrjson, token)
    while not ok:
        logger.info('UserAttr test1 config failed, retrying ...')
        time.sleep(1)
        ok = create_user_attr(url, tenant, user1attrjson, token)

    ok = create_user_attr(url, tenant, user2attrjson, token)
    while not ok:
        logger.info('UserAttr test2 config failed, retrying ...')
        time.sleep(1)
        ok = create_user_attr(url, tenant, user2attrjson, token)


def config_user(user, service, cluster, gateway, pod):
    global token

    usernm = 'Test User %s' % user
    userjson = {"uid":user, "name":usernm, "email":user,
                 "services":[service], "cluster":cluster, "gateway":gateway, "pod":pod}
    ok = create_user(url, tenant, userjson, token)
    while not ok:
        logger.info('User %s updation failed, retrying ...' % user)
        time.sleep(1)
        ok = create_user(url, tenant, userjson, token)


def config_bundle(bundle, service, cluster, gateway, pod):
    global token

    bundlenm = 'Bundle %s' % bundle
    bundlejson = {"bid":bundle, "name":bundlenm,
                   "services":[service], "cluster":cluster, "gateway":gateway, "pod":pod}
    ok = create_bundle(url, tenant, bundlejson, token)
    while not ok:
        logger.info('Bundle %s updation failed, retrying ...' % bundle)
        time.sleep(1)
        ok = create_bundle(url, tenant, bundlejson, token)


def config_default_bundle_attr(depts, teams):
    global token

    bundleattrjson = {"bid":"default@nextensio.net", "dept":depts,
                       "team":teams, "IC":10, "manager":10, "nonemployee":"allow"}
    ok = create_bundle_attr(url, tenant, bundleattrjson, token)
    while not ok:
        logger.info('BundleAttr bundle default config failed, retrying ...')
        time.sleep(1)
        ok = create_bundle_attr(url, tenant, bundleattrjson, token)


# Get a URL via a proxy


def proxyGet(agent, url, expected):
    env = {"https_proxy": "http://" + os.getenv(agent) + ":8181"}
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
    config_policy()
    config_routes('v1', 'v2')
    config_user_attr(50, 50)
    config_default_bundle_attr(['ABU,BBU'], ['engineering', 'sales'])
    increments = {'user': 2, 'bundle': 1, 'route': 1, 'policy': 1}
    versions = getAllOpaVersions(devices, versions, increments)
    # Test public and private access via default routing setup
    publicAndPvtPass("ONE", "TWO")

    logger.info('STEP2')
    # Switch routes and ensure private route http get has switched
    config_routes('v2', 'v1')
    increments = {'user': 0, 'bundle': 0, 'route': 1, 'policy': 0}
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
        global token

        token = runCmd("go run ../pkce.go https://dev-635657.okta.com").strip()
        if token == "":
            print('Cannot get access token, exiting')
            exit(1)

        # Load the testbed information variables as environment variables
        load_dotenv(dotenv_path='/tmp/nextensio-kind/environment')
        url = "https://" + os.getenv('ctrl_ip') + ":8080"
        ok, tenants = get_tenants(url, token)
        while not ok:
            logger.info('Tenant fetch %s failed, retrying ...' % url)
            time.sleep(1)
            ok, tenants = get_tenants(url, token)
        # The test setup is assumed to be created with just one tenant, if we need more we just need
        # to search for the right tenant name or something inside the returned list of tenants
        tenant = tenants[0]['_id']

    def parseTestbed(self, testbed):
        global clusters
        global agents
        global numApods
        global numCpods
        for d in testbed.devices:
            device = testbed.devices[d]
            if device.type == 'docker':
                agents.append(d)
            elif device.type == 'kubernetes':
                m = re.search(r'([a-zA-Z]+)_apod([1-9]+)', d)
                if m:
                    if m[1] not in clusters:
                        clusters.append(m[1])
                    if int(m[2]) > numApods:
                        numApods = int(m[2])
                m = re.search(r'([a-zA-Z]+)_cpod([1-9]+)', d)
                if m:
                    if m[1] not in clusters:
                        clusters.append(m[1])
                    if int(m[2]) > numCpods:
                        numCpods = int(m[2])

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
    gateway = spec['gateway'] + '.nextensio.net'
    if spec['agent'] == True:
        config_user(spec['name'], spec['service'], spec['gateway'], gateway,  spec['pod'])
    else:
        config_bundle(spec['name'], spec['service'], spec['gateway'], gateway, spec['pod'])


#TODO: After we moved around the external-service / egress-gateway rules to be
#in the default namespace, it stopped displaying the ingress gateway virtualSvc
#information! Not sure why, its nice to have this back, need to get it working
#podready = podHasService(cluster, podname, xfor, xconnect)
def verifyIstio(spec):
    return
    for cluster in clusters:
        istioChecks(cluster, spec['agent'], spec['pod'],
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
    three seperate pods, and agent and connector in two seperate clusters (gatewaytesta, gatewaytestc)
    '''
    @ aetest.setup
    def setup(self, testbed):
        specs = [
            {'name': 'test1@nextensio.net', 'agent': True,
                'service': '', 'gateway': 'gatewaytesta', 'pod': 1},
            {'name': 'test2@nextensio.net', 'agent': True,
                'service': '', 'gateway': 'gatewaytesta', 'pod': 2},
            {'name': 'default@nextensio.net', 'agent': False,
                'service': 'nextensio-default-internet', 'gateway': 'gatewaytestc', 'pod': 1},
            {'name': 'v1.kismis@nextensio.net', 'agent': False,
                'service': 'v1.kismis.org', 'gateway': 'gatewaytestc', 'pod': 2},
            {'name': 'v2.kismis@nextensio.net', 'agent': False,
                'service': 'v2.kismis.org', 'gateway': 'gatewaytestc', 'pod': 3}
        ]
        placeAndVerifyAgents(specs)
        resetAgents(testbed.devices)
        checkOnboarding(specs)
        checkConsulDnsAndKV(specs, testbed.devices)

    @ aetest.test
    def basicConnectivity(self, testbed, **kwargs):
        basicAccessSanity(testbed.devices)

    @ aetest.test
    def dynamicSwitchCrossCluster(self, testbed, **kwargs):
        '''Switch from the current connection model to go to different set of pods in 
        different clusters, then come back, all without doing pod restarts. This is to 
        ensure nothing in the pod like agent<-->socket hashtables etc.. remain stale 
        when agents come and go
        '''
        # Switch agents to a different set of pods in different clusters
        specs = [
            {'name': 'test1@nextensio.net', 'agent': True,
                'service': '', 'gateway': 'gatewaytesta', 'pod': 2},
            {'name': 'test2@nextensio.net', 'agent': True,
                'service': '', 'gateway': 'gatewaytestc', 'pod': 1},
            {'name': 'default@nextensio.net', 'agent': False,
                'service': 'nextensio-default-internet', 'gateway': 'gatewaytesta', 'pod': 3},
            {'name': 'v1.kismis@nextensio.net', 'agent': False,
                'service': 'v1.kismis.org', 'gateway': 'gatewaytestc', 'pod': 1},
            {'name': 'v2.kismis@nextensio.net', 'agent': False,
                'service': 'v2.kismis.org', 'gateway': 'gatewaytesta', 'pod': 2}
        ]
        placeAndVerifyAgents(specs)
        resetAgents(testbed.devices)
        checkOnboarding(specs)
        checkConsulDnsAndKV(specs, testbed.devices)
        basicAccessSanity(testbed.devices)
        # And now go back to the original configuration of this test case
        specs = [
            {'name': 'test1@nextensio.net', 'agent': True,
                'service': '', 'gateway': 'gatewaytesta', 'pod': 1},
            {'name': 'test2@nextensio.net', 'agent': True,
                'service': '', 'gateway': 'gatewaytesta', 'pod': 2},
            {'name': 'default@nextensio.net', 'agent': False,
                'service': 'nextensio-default-internet', 'gateway': 'gatewaytestc', 'pod': 1},
            {'name': 'v1.kismis@nextensio.net', 'agent': False,
                'service': 'v1.kismis.org', 'gateway': 'gatewaytestc', 'pod': 2},
            {'name': 'v2.kismis@nextensio.net', 'agent': False,
                'service': 'v2.kismis.org', 'gateway': 'gatewaytestc', 'pod': 3}
        ]
        placeAndVerifyAgents(specs)
        resetAgents(testbed.devices)
        checkOnboarding(specs)
        checkConsulDnsAndKV(specs, testbed.devices)
        basicAccessSanity(testbed.devices)

    @ aetest.cleanup
    def cleanup(self):
        return


class Agent2PodsConnector3PodsClusters1(aetest.Testcase):
    '''Agent1 and Agent2 in two seperate pods, default, kismis.v1 and kismisv2 in
    three seperate pods, and agent and connector in the same cluster (gatewaytesta)
    '''
    @ aetest.setup
    def setup(self, testbed):
        specs = [
            {'name': 'test1@nextensio.net', 'agent': True,
                'service': '', 'gateway': 'gatewaytesta', 'pod': 1},
            {'name': 'test2@nextensio.net', 'agent': True,
                'service': '', 'gateway': 'gatewaytesta', 'pod': 2},
            {'name': 'default@nextensio.net', 'agent': False,
                'service': 'nextensio-default-internet', 'gateway': 'gatewaytesta', 'pod': 1},
            {'name': 'v1.kismis@nextensio.net', 'agent': False,
                'service': 'v1.kismis.org', 'gateway': 'gatewaytesta', 'pod': 2},
            {'name': 'v2.kismis@nextensio.net', 'agent': False,
                'service': 'v2.kismis.org', 'gateway': 'gatewaytesta', 'pod': 3}
        ]
        placeAndVerifyAgents(specs)
        resetAgents(testbed.devices)
        checkOnboarding(specs)
        checkConsulDnsAndKV(specs, testbed.devices)

    @ aetest.test
    def basicConnectivity(self, testbed, **kwargs):
        basicAccessSanity(testbed.devices)

    @ aetest.test
    def dynamicSwitchSameCluster(self, testbed, **kwargs):
        '''Switch from the current connection model to go to different set of pods, and 
        come back, all without doing pod restarts. This is to ensure nothing in the pod 
        like agent<-->socket hashtables etc.. remain stale when agents come and go
        '''
        # Switch agents to a different set of pods
        specs = [
            {'name': 'test1@nextensio.net', 'agent': True,
                'service': '', 'gateway': 'gatewaytesta', 'pod': 2},
            {'name': 'test2@nextensio.net', 'agent': True,
                'service': '', 'gateway': 'gatewaytesta', 'pod': 1},
            {'name': 'default@nextensio.net', 'agent': False,
                'service': 'nextensio-default-internet', 'gateway': 'gatewaytesta', 'pod': 3},
            {'name': 'v1.kismis@nextensio.net', 'agent': False,
                'service': 'v1.kismis.org', 'gateway': 'gatewaytesta', 'pod': 1},
            {'name': 'v2.kismis@nextensio.net', 'agent': False,
                'service': 'v2.kismis.org', 'gateway': 'gatewaytesta', 'pod': 2}
        ]
        placeAndVerifyAgents(specs)
        resetAgents(testbed.devices)
        checkOnboarding(specs)
        checkConsulDnsAndKV(specs, testbed.devices)
        basicAccessSanity(testbed.devices)
        # And now go back to the original configuration of this test case
        specs = [
            {'name': 'test1@nextensio.net', 'agent': True,
                'service': '', 'gateway': 'gatewaytesta', 'pod': 1},
            {'name': 'test2@nextensio.net', 'agent': True,
                'service': '', 'gateway': 'gatewaytesta', 'pod': 2},
            {'name': 'default@nextensio.net', 'agent': False,
                'service': 'nextensio-default-internet', 'gateway': 'gatewaytesta', 'pod': 1},
            {'name': 'v1.kismis@nextensio.net', 'agent': False,
                'service': 'v1.kismis.org', 'gateway': 'gatewaytesta', 'pod': 2},
            {'name': 'v2.kismis@nextensio.net', 'agent': False,
                'service': 'v2.kismis.org', 'gateway': 'gatewaytesta', 'pod': 3}
        ]
        placeAndVerifyAgents(specs)
        resetAgents(testbed.devices)
        checkOnboarding(specs)
        checkConsulDnsAndKV(specs, testbed.devices)
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
                'service': '', 'gateway': 'gatewaytestc', 'pod': 2},
            {'name': 'test2@nextensio.net', 'agent': True,
                'service': '', 'gateway': 'gatewaytestc', 'pod': 1},
            {'name': 'default@nextensio.net', 'agent': False,
                'service': 'nextensio-default-internet', 'gateway': 'gatewaytestc', 'pod': 2},
            {'name': 'v1.kismis@nextensio.net', 'agent': False,
                'service': 'v1.kismis.org', 'gateway': 'gatewaytestc', 'pod': 3},
            {'name': 'v2.kismis@nextensio.net', 'agent': False,
                'service': 'v2.kismis.org', 'gateway': 'gatewaytestc', 'pod': 1}
        ]
        placeAndVerifyAgents(specs)
        resetAgents(testbed.devices)
        checkOnboarding(specs)
        checkConsulDnsAndKV(specs, testbed.devices)
        basicAccessSanity(testbed.devices)
        # And now go back to similar original configuration of this test case but in 2nd cluster
        specs = [
            {'name': 'test1@nextensio.net', 'agent': True,
                'service': '', 'gateway': 'gatewaytestc', 'pod': 1},
            {'name': 'test2@nextensio.net', 'agent': True,
                'service': '', 'gateway': 'gatewaytestc', 'pod': 2},
            {'name': 'default@nextensio.net', 'agent': False,
                'service': 'nextensio-default-internet', 'gateway': 'gatewaytestc', 'pod': 1},
            {'name': 'v1.kismis@nextensio.net', 'agent': False,
                'service': 'v1.kismis.org', 'gateway': 'gatewaytestc', 'pod': 2},
            {'name': 'v2.kismis@nextensio.net', 'agent': False,
                'service': 'v2.kismis.org', 'gateway': 'gatewaytestc', 'pod': 3}
        ]
        placeAndVerifyAgents(specs)
        resetAgents(testbed.devices)
        checkOnboarding(specs)
        checkConsulDnsAndKV(specs, testbed.devices)
        basicAccessSanity(testbed.devices)

    @ aetest.cleanup
    def cleanup(self):
        return


class Agent1PodsConnector1PodsClusters1(aetest.Testcase):
    '''Agent1 and Agent2 in the same pod, default, kismis.v1 and kismisv2 in
    the same pod (different from agent pod), and agent and connector in the same cluster (gatewaytesta)
    '''
    @ aetest.setup
    def setup(self, testbed):
        specs = [
            {'name': 'test1@nextensio.net', 'agent': True,
                'service': '', 'gateway': 'gatewaytesta', 'pod': 1},
            {'name': 'test2@nextensio.net', 'agent': True,
                'service': '', 'gateway': 'gatewaytesta', 'pod': 1},
            {'name': 'default@nextensio.net', 'agent': False,
                'service': 'nextensio-default-internet', 'gateway': 'gatewaytesta', 'pod': 2},
            {'name': 'v1.kismis@nextensio.net', 'agent': False,
                'service': 'v1.kismis.org', 'gateway': 'gatewaytesta', 'pod': 2},
            {'name': 'v2.kismis@nextensio.net', 'agent': False,
                'service': 'v2.kismis.org', 'gateway': 'gatewaytesta', 'pod': 2}
        ]
        placeAndVerifyAgents(specs)
        resetAgents(testbed.devices)
        checkOnboarding(specs)
        checkConsulDnsAndKV(specs, testbed.devices)

    @ aetest.test
    def basicConnectivity(self, testbed, **kwargs):
        basicAccessSanity(testbed.devices)


class AgentConnector1PodsClusters2(aetest.Testcase):
    '''Agent1 and Agent2 in the same pod in one cluster, default, kismis.v1 and kismisv2 in
    the same pod in a different cluster (gatewaytestc)
    '''
    @ aetest.setup
    def setup(self, testbed):
        specs = [
            {'name': 'test1@nextensio.net', 'agent': True,
                'service': '', 'gateway': 'gatewaytesta', 'pod': 2},
            {'name': 'test2@nextensio.net', 'agent': True,
                'service': '', 'gateway': 'gatewaytesta', 'pod': 2},
            {'name': 'default@nextensio.net', 'agent': False,
                'service': 'nextensio-default-internet', 'gateway': 'gatewaytestc', 'pod': 3},
            {'name': 'v1.kismis@nextensio.net', 'agent': False,
                'service': 'v1.kismis.org', 'gateway': 'gatewaytestc', 'pod': 3},
            {'name': 'v2.kismis@nextensio.net', 'agent': False,
                'service': 'v2.kismis.org', 'gateway': 'gatewaytestc', 'pod': 3}
        ]
        placeAndVerifyAgents(specs)
        resetAgents(testbed.devices)
        checkOnboarding(specs)
        checkConsulDnsAndKV(specs, testbed.devices)

    @ aetest.test
    def basicConnectivity(self, testbed, **kwargs):
        basicAccessSanity(testbed.devices)

class AgentConnectorSquareOne(aetest.Testcase):
    '''Agent1 and Agent2 in one cluster, default, kismis.v1 and kismisv2 in
    a different cluster (gatewaytestc)
    '''
    @ aetest.setup
    def setup(self, testbed):
        specs = [
            {'name': 'test1@nextensio.net', 'agent': True,
                'service': '', 'gateway': 'gatewaytesta', 'pod': 1},
            {'name': 'test2@nextensio.net', 'agent': True,
                'service': '', 'gateway': 'gatewaytesta', 'pod': 2},
            {'name': 'default@nextensio.net', 'agent': False,
                'service': 'nextensio-default-internet', 'gateway': 'gatewaytestc', 'pod': 1},
            {'name': 'v1.kismis@nextensio.net', 'agent': False,
                'service': 'v1.kismis.org', 'gateway': 'gatewaytestc', 'pod': 2},
            {'name': 'v2.kismis@nextensio.net', 'agent': False,
                'service': 'v2.kismis.org', 'gateway': 'gatewaytestc', 'pod': 3}
        ]
        placeAndVerifyAgents(specs)
        resetAgents(testbed.devices)
        checkOnboarding(specs)
        checkConsulDnsAndKV(specs, testbed.devices)

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

    token = runCmd("go run ../pkce.go https://dev-635657.okta.com").strip()
    if token == "":
        print('Cannot get access token, exiting')
        exit(1)

    aetest.main(**vars(args))
