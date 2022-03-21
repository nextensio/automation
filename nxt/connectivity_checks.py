import logging
import argparse
from pyats import aetest
from dotenv import load_dotenv
import os
import sys
import re
import requests
import time
import subprocess
from containers import kube_get_pod
from containers import docker_run
import swagger_client

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

GW1 = "gatewaytesta.nextensio.net"
GW2 = "gatewaytestc.nextensio.net"
GW1CLUSTER = "gatewaytesta"
GW2CLUSTER = "gatewaytestc"
TENANT = "nextensio"
USER1 = "test1@nextensio.net"
USER2 = "test2@nextensio.net"
CNCTR1 = "v1kismis"
CNCTR2 = "v2kismis"
CNCTR3 = "default"
CNCTR1POD = "nextensio-v1kismis"
CNCTR2POD = "nextensio-v2kismis"
CNCTR3POD = "nextensio-default"

url = None
tenant = TENANT
clusters = []
agents = []
token = ""
api_instance = None

# In nextensio, all services are words seperated by dashes, all dots and @ symbols
# are converted to dashes


def nameToService(name):
    svc = name.replace(".", "-")
    svc = svc.replace("@", "-")
    return svc

# We use the clustername-podname as the nomenclature. These names are loaded as
# environment shell variables from the /tmp/nextensio-kin/environment file, and
# hence not using dashes in the names (shell vars cant have dashes)

def clusterPod2Device(cluster, pod):
    return cluster + "_" + pod

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

# The dig lookup ensures that the service is reachable, and we also check
# the TXT records from the dig result to ensure that the service is in the
# proper pod that we expect
def checkConsulDnsEntry(devices, cluster, svc, pod):
    device = clusterPod2Device(cluster, "consul")
    service = svc

    while True:
        value = devices[device].shell.execute('dig ' + service + '.nxt-' + TENANT + '.query.consul SRV').strip()
        lines = value.splitlines()
        cur = "None"
        for l in lines:
            m = re.search(r'\"NextensioPod:(.+)\"', l)
            if m != None and m[1] == pod:
                print("Found svc %s pod value %s in cluster %s" % (svc, m[0], cluster))
                return
            if m != None:
                cur = m[1]
        logger.info('Cluster %s, waiting for consul TXT record %s in pod %s, current %s' %
                    (cluster, service, pod, cur))
        time.sleep(1)

def checkConsulDns(specs, devices):
    services = []
    cls = []
    for spec in specs:
        if spec['agent'] != True:
            if spec['service'] != '':
                services.append({'name': spec['service'], 'cluster': spec['cluster'], 'pod': spec['pod']})
            if spec['cluster'] not in cls:
                cls.append(spec['cluster'])

    for cluster in cls:
        for service in services:
            if cluster == service['cluster']:
                checkConsulDnsEntry(devices, cluster, service['name'], service['pod'])

def checkOnboarding(specs):
    for spec in specs:
        if spec['agent'] == True:
            podnm = "nextensio-apod" + str(spec['pod'])
        else:
            podnm = spec['pod']
        gw = spec['cluster'] + ".nextensio.net"
        checkUserOnboarding(spec['name'], gw, podnm)

def checkUserOnboarding(uid, gw, podnm):
    onblog = api_instance.get_user_onboard_log("superadmin", tenant, uid)
    while onblog.result != "ok":
        print('Onboarding log entry fetch failed, retrying ...')
        time.sleep(1)
        onblog = api_instance.get_user_onboard_log("superadmin", tenant, uid)
    while onblog.gw != gw:
        print('Waiting for %s to get onboarded, gw %s / %s' % (uid, gw, onblog.gw))
        time.sleep(1)
        onblog = api_instance.get_user_onboard_log("superadmin", tenant, uid)
    while onblog.connectid != podnm:
        print('Waiting for %s to get onboarded pod %s / %s' % (uid, podnm, onblog.connectid))
        time.sleep(1)
        onblog = api_instance.get_user_onboard_log("superadmin", tenant, uid)
    print("%s onboarded for cluster %s pod %s" % (uid, gw, podnm))

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


def getAllOpaVersions(devices, specs, current, increments):
    versions = {}
    for spec in specs:
        d = spec['device']
        parse = getOpaVersion(devices, d, current, increments)
        versions['ref'] = parse
    return versions

# TODO: Its hacky to be restarting an entire device using the shell/console object
# of that device. We do that because the console object is all pyAts allows us to
# override today. Need to find out if pyAts will allow us to override a device object
# itself and if so we can add a device restart in our own custom device object


def resetAgents(devices):
    devices['nxt_agent1'].shell.restart()
    devices['nxt_agent2'].shell.restart()
    devices['nxt_default1'].shell.restart()
    devices['nxt_default2'].shell.restart()
    devices['nxt_kismis_ONE'].shell.restart()
    devices['nxt_kismis_TWO'].shell.restart()

def quit_error(text):
    print(text)
    raise Exception("Test failed")

# Ensure public and private access is successul
def publicAndPvtPass(kwargs, agent1, agent2):
    proxy, text, err = proxyGet(kwargs, 'nxt_agent1', 'https://foobar.com',
                                "I am Nextensio agent nxt_default", None) 
    if err == True:
        quit_error(text)
    if proxy != True:
        print("agent1 default internet access fail")
        quit_error(text)

    proxy, text, err = proxyGet(kwargs, 'nxt_agent2', 'https://foobar.com',
                                "I am Nextensio agent nxt_default", None) 
    if err == True:
        quit_error(text)
    if proxy != True:
        print("agent2 default internet fail")
        quit_error(text)

    proxy, text, err = proxyGet(kwargs, 'nxt_agent1', 'https://kismis.org',
                                "I am Nextensio agent nxt_kismis_" + agent1, None) 
    if err == True:
        quit_error(text)
    if proxy != True:
        print("agent1 kismis_%s fail" % agent1)
        quit_error(text)

    proxy, text, err = proxyGet(kwargs, 'nxt_agent2', 'https://kismis.org',
                                "I am Nextensio agent nxt_kismis_" + agent2, None) 
    if err == True:
        quit_error(text)
    if proxy != True:
        print("agent2 kismis_%s fail" % agent2)
        quit_error(text)

# Ensure public access fails


def publicFail(kwargs):
    # Exit code 35 means the curl command timed out, which is what we really
    # expect here
    proxy, text, err = proxyGet(kwargs, 'nxt_agent1', 'https://foobar.com',
                                "I am Nextensio agent nxt_default", 35) 
    if err == True:
        quit_error(text)
    if proxy == True:
        quit_error("agent1 default internet access works!")

    # Exit code 28 means the curl command timed out, which is what we really
    # expect here
    proxy, text, err = proxyGet(kwargs, 'nxt_agent2', 'https://foobar.com',
                                "I am Nextensio agent nxt_default", 35) 
    if err == True:
        quit_error(text)
    if proxy == True:
        quit_error("agent2 default internet works!")

def config_policy():
    with open('policy.AccessPolicy','r') as file:
        rego = file.read()
        ok = create_policy('AccessPolicy', rego)
        while not ok:
            logger.info('Access Policy creation failed, retrying ...')
            time.sleep(1)
            ok = create_policy('AccessPolicy', rego)
        
    with open('policy.RoutePolicy','r') as file:
        rego = file.read()
        ok = create_policy('RoutePolicy', rego)
        while not ok:
            logger.info('Route Policy creation failed, retrying ...')
            time.sleep(1)
            ok = create_policy('RoutePolicy', rego)

        
def config_routes(tag1, tag2):
    routejson = { "host": "kismis.org", 
                      "routeattrs": [
		      {"tag": tag1, "team": ["engineering","sales"], "dept": ["ABU","BBU"],
                       "category":["employee","nonemployee"], "type":["IC"], "IClvl": 1, "mlvl": 1 },
		      {"tag": tag2, "team": ["engineering","sales"], "dept": ["ABU","BBU"],
                       "category":["employee"], "type":["manager"], "IClvl": 1, "mlvl": 1 }
		      ]
                }
    ok = create_host_attr(routejson)
    while not ok:
        logger.info('Route creation failed, retrying ...')
        time.sleep(1)
        ok = create_host_attr(routejson)


def config_user_attr(level1, level2):
    user1attrjson = {"uid":USER1, "category":"employee", "type":"IC", "level":level1,
                     "dept":["ABU","BBU"], "team":["engineering","sales"],
                     "location": "California", "ostype": "Linux", "osver": 20.04 }
    user2attrjson = {"uid":USER2, "category":"employee", "type":"manager", "level":level2,
                     "dept":["ABU","BBU"], "team":["engineering","sales"],
                     "location": "California", "ostype": "Linux", "osver": 20.04 }
    ok = create_user_attr(user1attrjson, USER1)
    while not ok:
        logger.info('UserAttr test1 config failed, retrying ...')
        time.sleep(1)
        ok = create_user_attr(user1attrjson, USER1)

    ok = create_user_attr(user2attrjson, USER2)
    while not ok:
        logger.info('UserAttr test2 config failed, retrying ...')
        time.sleep(1)
        ok = create_user_attr(user2attrjson, USER2)


def config_user(user, service, gateway, pod):
    ok = create_user(user, user, pod, gateway)
    while not ok:
        logger.info('User %s updation failed, retrying ...' % user)
        time.sleep(1)
        ok = create_user(user, user, pod, gateway)


def config_bundle(bundle, service, gateway, pod):
    ok = create_bundle(bundle, bundle, [service], pod, gateway, 2)
    while not ok:
        logger.info('Bundle %s updation failed, retrying ...' % bundle)
        time.sleep(1)
        ok = create_bundle(bundle, bundle, [service], pod, gateway, 2)

def config_default_bundle_attr(depts, teams):
    bundleattrjson = {"bid":CNCTR3, "dept":depts,
                       "team":teams, "IC":10, "manager":10, "nonemployee":"allow"}
    ok = create_bundle_attr(bundleattrjson)
    while not ok:
        logger.info('BundleAttr bundle default config failed, retrying ...')
        time.sleep(1)
        ok = create_bundle_attr(bundleattrjson)


# If testing in webproxy mode, the curl command will open a connection to port 8181
# of the agent and send the url as a CONNECT string. If not in webproxy mode, the
# curl request will generate l3 packets which will get routed to the agent, agent will
# reassemble them as tcp, read the tcp payload and parse it as http and get the url
def webProxyTestMode(kwargs):
    if not 'WebProxy' in kwargs:
        return False
    return True

# Get a URL via a proxy
def proxyGet(kwargs, agent, url, expected, expected_exit):
    try:
        if webProxyTestMode(kwargs):
            env = {"https_proxy": "http://" + os.getenv(agent) + ":8181"}
            text, err = docker_run("curl", "curl --silent --connect-timeout 5 --max-time 5 -k %s" % url, expected_exit, environment=env)
            if err == True:
                return False, text, err
        else:
            docker_run("curl", "route add default gw %s" % os.getenv(agent), None)
            text, err = docker_run("curl", "curl --silent --connect-timeout 5 --max-time 5 -k %s" % url, expected_exit)
            docker_run("curl", "route del default gw %s" % os.getenv(agent), None)
            if err == True:
                return False, text, err
    except Exception as e:
        pass
        return False, "Exception %s" % e, True
    if expected not in text:
        return False, text, False
    return True, "", False

# Basic access sanity checks public and private URL access, in some cases
# the accesses are expected to succeed and in some cases its expected to fail
# TODO: The route versions are not in place yet, they are always zero.
# When we add proper route version support in minion/opa, come back here
# and and add the right route version increments whenever we change routes


def basicAccessSanity(kwargs, specs, devices):
    increments = {'user': 0, 'bundle': 0, 'route': 0, 'policy': 0}
    logger.info('STEP1')
    versions = getAllOpaVersions(devices, specs, {}, increments)
    config_policy()
    config_routes('v1', 'v2')
    config_user_attr(50, 50)
    config_default_bundle_attr(['ABU,BBU'], ['engineering', 'sales'])
    increments = {'user': 2, 'bundle': 1, 'route': 1, 'policy': 1}
    versions = getAllOpaVersions(devices, specs, versions['ref'], increments)
    # Test public and private access via default routing setup
    publicAndPvtPass(kwargs, "ONE", "TWO")

    logger.info('STEP2')
    # Switch routes and ensure private route http get has switched
    config_routes('v2', 'v1')
    increments = {'user': 0, 'bundle': 0, 'route': 1, 'policy': 0}
    versions = getAllOpaVersions(devices, specs, versions['ref'], increments)
    publicAndPvtPass(kwargs, "TWO", "ONE")

    logger.info('STEP3')
    # Reduce the level of the user and ensure user cant access public
    config_user_attr(5, 5)
    increments = {'user': 2, 'bundle': 0, 'route': 0, 'policy': 0}
    versions = getAllOpaVersions(devices, specs, versions['ref'], increments)
    publicFail(kwargs)

    logger.info('STEP4')
    # Increase the level of the user and ensure user can again access public
    config_user_attr(50, 50)
    increments = {'user': 2, 'bundle': 0, 'route': 0, 'policy': 0}
    versions = getAllOpaVersions(devices, specs, versions['ref'], increments)
    publicAndPvtPass(kwargs, "TWO", "ONE")

    logger.info('STEP5')
    # Change the teams of the bundle and ensure that user cant access default internet
    config_default_bundle_attr(['abcd,efgh'], ['abcd', 'efgh'])
    increments = {'user': 0, 'bundle': 1, 'route': 0, 'policy': 0}
    versions = getAllOpaVersions(devices, specs, versions['ref'], increments)
    publicFail(kwargs)

    logger.info('STEP6')
    # Restore the bundle attributes and ensure default internet works again
    config_default_bundle_attr(['ABU,BBU'], ['engineering', 'sales'])
    increments = {'user': 0, 'bundle': 1, 'route': 0, 'policy': 0}
    versions = getAllOpaVersions(devices, specs, versions['ref'], increments)
    publicAndPvtPass(kwargs, "TWO", "ONE")

# Access default internet four times, ensuring that the accesses are split across
# two connectors (since by default we have round robin loadbalancing)
def basicLoadbalancing(kwargs, specs, devices):
    # Set routes/policies all back to default
    increments = {'user': 0, 'bundle': 0, 'route': 0, 'policy': 0}
    logger.info('STEP1')
    versions = getAllOpaVersions(devices, specs, {}, increments)
    config_policy()
    config_routes('v1', 'v2')
    config_user_attr(50, 50)
    config_default_bundle_attr(['ABU,BBU'], ['engineering', 'sales'])
    increments = {'user': 2, 'bundle': 1, 'route': 1, 'policy': 1}
    versions = getAllOpaVersions(devices, specs, versions['ref'], increments)

    # TODO: The loadbalancing seems to need some warmup with initial few accesses
    # going un-loadbalanced before it starts loadbalancing - not sure why that is
    # the case, this needs to be debugged and understood, the below just hacks around
    # to do a few warmup loads 
    for i in range(16):
        proxy, text, err = proxyGet(kwargs, 'nxt_agent1', 'https://foobar.com',
                                    "I am Nextensio agent nxt_default", None) 
        if err == True:
            quit_error(text)
        if proxy != True:
            print("agent1 default fail")
            quit_error(text)

    def1 = 0
    def2 = 0
    def1_new = 0
    def2_new = 0
    try:
        out, err = docker_run("nxt_default1", "curl http://127.0.0.1/server-status?auto", None)
        m = re.search(r'Total Accesses: ([0-9]+)', out)
        if not m:
            quit_error("Bad lighthttpd stats %s" % out)
        def1 = int(m[1])
        out, err = docker_run("nxt_default2", "curl http://127.0.0.1/server-status?auto", None)
        m = re.search(r'Total Accesses: ([0-9]+)', out)
        if not m:
            quit_error("Bad lighthttpd stats %s" % out)
        def2 = int(m[1])
    except Exception as e:
        quit_error("Exception %s" % e)

    # This should trigger four accesses to default1 and four to default2
    for i in range(8):
        proxy, text, err = proxyGet(kwargs, 'nxt_agent1', 'https://foobar.com',
                                    "I am Nextensio agent nxt_default", None) 
        if err == True:
            quit_error(text)
        if proxy != True:
            print("agent1 default internet access fail")
            quit_error(text)

    # Access kismis multiple times from agent1 and agent2 and ensure
    # it works. kismis has two replicas but only one connector, so here
    # we are trying to ensure that the kismis access does NOT end up
    # on a replica without a connector 
    for i in range(4):
        proxy, text, err = proxyGet(kwargs, 'nxt_agent1', 'https://kismis.org',
                                    "I am Nextensio agent nxt_kismis_ONE", None) 
        if err == True:
            quit_error(text)
        if proxy != True:
            print("agent1 kismis_ONE fail")
            quit_error(text)

    for i in range(4):
        proxy, text, err = proxyGet(kwargs, 'nxt_agent2', 'https://kismis.org',
                                    "I am Nextensio agent nxt_kismis_TWO", None) 
        if err == True:
            quit_error(text)
        if proxy != True:
            print("agent2 kismis_TWO fail")
            quit_error(text)

    try:
        out, err = docker_run("nxt_default1", "curl http://127.0.0.1/server-status?auto", None)
        m = re.search(r'Total Accesses: ([0-9]+)', out)
        if not m:
            quit_error("Bad lighthttpd stats %s" % out)
        def1_new = int(m[1])
        out, err = docker_run("nxt_default2", "curl http://127.0.0.1/server-status?auto", None)
        m = re.search(r'Total Accesses: ([0-9]+)', out)
        if not m:
            quit_error("Bad lighthttpd stats %s" % out)
        def2_new = int(m[1])
    except Exception as e:
        quit_error("Exception %s" % e)

    # The http access to read the stats (the server-status access) itself adds
    # a count of 1 to the Total Accesses ! And then each access is incrementing the Total Accesses
    # count in a wierd way - the first one will increment by one access, next one by two etc..,
    # I dont know what is lighthttpd logic there. So its hard to put an accurate check here
    # on the counts and lighthttpd counts keep changing with a new release, we need some other
    # mechanism to track the counts. So for now just ensure that both servers got accesses
    # more or less close to each other
    
    delta1 = def1_new - def1
    delta2 = def2_new - def2
    if (delta1 - delta2 > 2) or (delta2 - delta1 > 2): 
        quit_error("Mismatching default counts %d / %d, %d / %d" % (def1, def1_new, def2, def2_new))

# This aetest sections in this class is executed at the very beginning BEFORE
# any of the actual test cases run. So we have all the environment loading and
# initializations etc.. here
class CommonSetup(aetest.CommonSetup):

    def loadEnv(self):
        global url
        global tenant
        global token
        global api_instance

        token = runCmd("go run ./pkce.go https://dev-635657.okta.com").strip()
        if token == "":
            print('Cannot get access token, exiting')
            exit(1)

        # Load the testbed information variables as environment variables
        load_dotenv(dotenv_path='/tmp/nextensio-kind/environment')
        config = swagger_client.Configuration()
        config.verify_ssl = False
        config.host = "https://" + os.getenv('ctrl_ip') + ":8080/api/v1"
        api_instance = swagger_client.DefaultApi(swagger_client.ApiClient(config))
        api_instance.api_client.set_default_header("Authorization", "Bearer " + token)

    def parseTestbed(self, testbed):
        global clusters
        global agents
        for d in testbed.devices:
            device = testbed.devices[d]
            if device.type == 'docker':
                agents.append(d)
            elif device.type == 'kubernetes':
                m = re.search(r'([a-zA-Z]+)_apod([1-9]+)', d)
                if m:
                    if m[1] not in clusters:
                        clusters.append(m[1])
                m = re.search(r'([a-zA-Z]+)_cpod([1-9]+)', d)
                if m:
                    if m[1] not in clusters:
                        clusters.append(m[1])

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
                    namespace="nxt-"+tenant, container='minion')


class CommonCleanup(aetest.CommonCleanup):

    @ aetest.subsection
    def cleanup(self):
        logger.info('Cleanup done')


def placeAndVerifyAgents(devices, specs):
    for spec in specs:
        gateway = spec['cluster'] + '.nextensio.net'
        if spec['agent'] == True:
            config_user(spec['name'], spec['service'], gateway,  spec['pod'])
        else:
            config_bundle(spec['name'], spec['service'], gateway, spec['pod'])

class Connector2Connector(aetest.Testcase):
    '''Agents and connectors back to their very first placement.
    '''
    @ aetest.setup
    def setup(self, testbed):
        specs = [
            {'name': USER1, 'agent': True, 'device': GW1CLUSTER+"_apod1",
             'service': '', 'cluster': GW1CLUSTER, 'pod': 1},
            {'name': USER2, 'agent': True, 'device': GW1CLUSTER+"_apod2",
             'service': '', 'cluster': GW1CLUSTER, 'pod': 2},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-0",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-0",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-0",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-1",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-1",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-1",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD}
        ]
        placeAndVerifyAgents(testbed.devices, specs)
        resetAgents(testbed.devices)
        checkOnboarding(specs)
        checkConsulDns(specs, testbed.devices)

    @ aetest.test
    def basicConn2Conn(self, testbed, **kwargs):
        specs = [
            {'name': USER1, 'agent': True, 'device': GW1CLUSTER+"_apod1",
             'service': '', 'cluster': GW1CLUSTER, 'pod': 1},
            {'name': USER2, 'agent': True, 'device': GW1CLUSTER+"_apod2",
             'service': '', 'cluster': GW1CLUSTER, 'pod': 2},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-0",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-0",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-0",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-1",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-1",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-1",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD}
        ]

        # Just allow everything, we are purely testing connector 2 connector connectivity, thats about it
        increments = {'user': 0, 'bundle': 0, 'route': 0, 'policy': 0}
        versions = getAllOpaVersions(testbed.devices, specs, {}, increments)
        conn2conn_policy()
        increments = {'user': 0, 'bundle': 0, 'route': 0, 'policy': 1}
        versions = getAllOpaVersions(testbed.devices, specs, versions['ref'], increments)
        c2c = os.getenv("nxt_conn2conn")
        subprocess.check_output("docker exec -it  curl sh -c \"echo 127.0.0.1 localhost > /etc/hosts\"", shell=True)
        subprocess.check_output("docker exec -it  curl sh -c \"echo %s kismis.org >> /etc/hosts\"" % c2c, shell=True)
        proxy, text, err = proxyGet(kwargs, 'nxt_conn2conn', 'https://kismis.org',
                                    "I am Nextensio agent nxt_kismis_ONE", None) 
        if err == True:
            quit_error(text)
        if proxy != True:
            print("conn2conn kismis ONE access fail")
            quit_error(text)

        subprocess.check_output("docker exec -it  curl sh -c \"echo 127.0.0.1 locahost > /etc/hosts\"", shell=True)
        subprocess.check_output("docker exec -it  curl sh -c \"echo 1.1.1.1 foobar.com >> /etc/hosts\"", shell=True)
        subprocess.check_output("docker exec -it  curl sh -c \"echo 1.1.1.1 kismis.org >> /etc/hosts\"", shell=True)

        # Restore the original policies
        increments = {'user': 0, 'bundle': 0, 'route': 0, 'policy': 0}
        versions = getAllOpaVersions(testbed.devices, specs, {}, increments)
        config_policy()
        increments = {'user': 0, 'bundle': 0, 'route': 0, 'policy': 1}
        versions = getAllOpaVersions(testbed.devices, specs, versions['ref'], increments)

    @ aetest.cleanup
    def cleanup(self):
        return

class Agent2PodsConnector3PodsClusters2LoadBalance(aetest.Testcase):
    '''In this class of tests, all agents and connectors are in separate pods.
    Agent1 and Agent2 are kept in cluster gatewaytesta, while default, v1.kismis and v2.kismis
    are kept in cluster gatewaytestc. Then we test loadbalancing across the default connectors
    '''
    @ aetest.setup
    def setup(self, testbed):
        specs = [
            {'name': USER1, 'agent': True, 'device': GW1CLUSTER+"_apod1",
                'service': '', 'cluster': GW1CLUSTER, 'pod': 1},
            {'name': USER2, 'agent': True, 'device': GW1CLUSTER+"_apod2",
                'service': '', 'cluster': GW1CLUSTER, 'pod': 2},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-0",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-0",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-0",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-1",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-1",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-1",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD}
        ]
        placeAndVerifyAgents(testbed.devices, specs)
        resetAgents(testbed.devices)
        checkOnboarding(specs)
        checkConsulDns(specs, testbed.devices)

    @ aetest.test
    def basicConnectivity(self, testbed, **kwargs):
        specs = [
            {'name': USER1, 'agent': True, 'device': GW1CLUSTER+"_apod1",
                'service': '', 'cluster': GW1CLUSTER, 'pod': 1},
            {'name': USER2, 'agent': True, 'device': GW1CLUSTER+"_apod2",
                'service': '', 'cluster': GW1CLUSTER, 'pod': 2},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-0",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-0",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-0",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-1",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-1",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-1",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD}
        ]
        basicLoadbalancing(kwargs, specs, testbed.devices)

    @ aetest.cleanup
    def cleanup(self):
        return

class Agent2PodsConnector3PodsClusters2(aetest.Testcase):
    '''In this class of tests, all agents and connectors are in separate pods.
    Agent1 and Agent2 are kept in cluster gatewaytesta, while default, v1.kismis and v2.kismis
    are kept in cluster gatewaytestc. Then they are randomly switched around to different
    pods within those same clusters.
    '''
    @ aetest.setup
    def setup(self, testbed):
        specs = [
            {'name': USER1, 'agent': True, 'device': GW1CLUSTER+"_apod1",
                'service': '', 'cluster': GW1CLUSTER, 'pod': 1},
            {'name': USER2, 'agent': True, 'device': GW1CLUSTER+"_apod2",
                'service': '', 'cluster': GW1CLUSTER, 'pod': 2},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-0",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-0",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-0",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-1",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-1",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-1",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD}
        ]
        placeAndVerifyAgents(testbed.devices, specs)
        resetAgents(testbed.devices)
        checkOnboarding(specs)
        checkConsulDns(specs, testbed.devices)

    @ aetest.test
    def basicConnectivity(self, testbed, **kwargs):
        specs = [
            {'name': USER1, 'agent': True, 'device': GW1CLUSTER+"_apod1",
                'service': '', 'cluster': GW1CLUSTER, 'pod': 1},
            {'name': USER2, 'agent': True, 'device': GW1CLUSTER+"_apod2",
                'service': '', 'cluster': GW1CLUSTER, 'pod': 2},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-0",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-0",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-0",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-1",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-1",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-1",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD}
        ]
        basicAccessSanity(kwargs, specs, testbed.devices)

    @ aetest.test
    def basicConnectivitySameCluster(self, testbed, **kwargs):
        '''Previous test had all cpods in GW2CLUSTER. Before running through all test cases,
        first just run through one test with all cpods in GW1CLUSTER as well. 
        '''
        specs = [
            {'name': USER1, 'agent': True, 'device': GW1CLUSTER+"_apod1",
                'service': '', 'cluster': GW1CLUSTER, 'pod': 1},
            {'name': USER2, 'agent': True, 'device': GW1CLUSTER+"_apod2",
                'service': '', 'cluster': GW1CLUSTER, 'pod': 2},
            {'name': CNCTR3, 'agent': False, 'device': GW1CLUSTER+"_cpod3-0",
             'service': 'nextensio-default-internet', 'cluster': GW1CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR1, 'agent': False, 'device': GW1CLUSTER+"_cpod1-0",
             'service': 'v1.kismis.org', 'cluster': GW1CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW1CLUSTER+"_cpod2-0",
             'service': 'v2.kismis.org', 'cluster': GW1CLUSTER, 'pod': CNCTR2POD},
            {'name': CNCTR3, 'agent': False, 'device': GW1CLUSTER+"_cpod3-1",
             'service': 'nextensio-default-internet', 'cluster': GW1CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR1, 'agent': False, 'device': GW1CLUSTER+"_cpod1-1",
             'service': 'v1.kismis.org', 'cluster': GW1CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW1CLUSTER+"_cpod2-1",
             'service': 'v2.kismis.org', 'cluster': GW1CLUSTER, 'pod': CNCTR2POD}
        ]
        placeAndVerifyAgents(testbed.devices, specs)
        resetAgents(testbed.devices)
        checkOnboarding(specs)
        checkConsulDns(specs, testbed.devices)
        basicAccessSanity(kwargs, specs, testbed.devices)

    @ aetest.test
    def dynamicSwitchPodsWithinSameClusters(self, testbed, **kwargs):
        '''Switch to a different set of pods in the same clusters, then come back, all
        without doing pod restarts. This is to ensure nothing in the pod like agent<-->socket
        hashtables etc.. remain stale when agents come and go
        '''
        # Switch agents to a different set of pods in same clusters
        specs = [
            {'name': USER1, 'agent': True, 'device': GW1CLUSTER+"_apod2",
             'service': '', 'cluster': GW1CLUSTER, 'pod': 2},
            {'name': USER2, 'agent': True, 'device': GW1CLUSTER+"_apod1",
             'service': '', 'cluster': GW1CLUSTER, 'pod': 1},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-0",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-0",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-0",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-1",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-1",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-1",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD}
        ]
        placeAndVerifyAgents(testbed.devices, specs)
        resetAgents(testbed.devices)
        checkOnboarding(specs)
        checkConsulDns(specs, testbed.devices)
        basicAccessSanity(kwargs, specs, testbed.devices)
        # And now go back to the original configuration of this test case
        specs = [
            {'name': USER1, 'agent': True, 'device': GW1CLUSTER+"_apod1",
             'service': '', 'cluster': GW1CLUSTER, 'pod': 1},
            {'name': USER2, 'agent': True, 'device': GW1CLUSTER+"_apod2",
             'service': '', 'cluster': GW1CLUSTER, 'pod': 2},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-0",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-0",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-0",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-1",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-1",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-1",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD}
        ]
        placeAndVerifyAgents(testbed.devices, specs)
        resetAgents(testbed.devices)
        checkOnboarding(specs)
        checkConsulDns(specs, testbed.devices)
        basicAccessSanity(kwargs, specs, testbed.devices)

    @ aetest.cleanup
    def cleanup(self):
        return


class Agent2PodsConnector3PodsClustersMixed(aetest.Testcase):
    '''In this class of tests, all agents and connectors are in separate pods.
    Agent1 and Agent2 are initially in cluster gatewaytesta, while default, v1.kismis and
    v2.kismis are initially in cluster gatewaytestc. Then they are randomly switched around
    to different pods in different clusters.
    '''
    @ aetest.setup
    def setup(self, testbed):
        specs = [
            {'name': USER1, 'agent': True, 'device': GW1CLUSTER+"_apod1",
             'service': '', 'cluster': GW1CLUSTER, 'pod': 1},
            {'name': USER2, 'agent': True, 'device': GW1CLUSTER+"_apod2",
             'service': '', 'cluster': GW1CLUSTER, 'pod': 2},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-0",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-0",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-0",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-1",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-1",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-1",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD}
        ]
        placeAndVerifyAgents(testbed.devices, specs)
        resetAgents(testbed.devices)
        checkOnboarding(specs)
        checkConsulDns(specs, testbed.devices)

    @ aetest.test
    def basicConnectivity(self, testbed, **kwargs):
        specs = [
            {'name': USER1, 'agent': True, 'device': GW1CLUSTER+"_apod1",
             'service': '', 'cluster': GW1CLUSTER, 'pod': 1},
            {'name': USER2, 'agent': True, 'device': GW1CLUSTER+"_apod2",
             'service': '', 'cluster': GW1CLUSTER, 'pod': 2},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-0",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-0",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-0",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-1",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-1",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-1",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD}
        ]
        basicAccessSanity(kwargs, specs, testbed.devices)

    @ aetest.test
    def dynamicSwitchApodsCpodsCrossClusterCase1(self, testbed, **kwargs):
        '''Switch to random set of pods in different clusters, and come back, all
        without doing pod restarts. This is to ensure nothing in the pod like
        agent<-->socket hashtables etc.. remain stale when agents come and go
        '''
        # Mix up agents and connectors to a different set of pods across clusters
        specs = [
            {'name': USER1, 'agent': True, 'device': GW1CLUSTER+"_apod2",
             'service': '', 'cluster': GW1CLUSTER, 'pod': 2},
            {'name': USER2, 'agent': True, 'device': GW2CLUSTER+"_apod1",
             'service': '', 'cluster': GW2CLUSTER, 'pod': 1},
            {'name': CNCTR3, 'agent': False, 'device': GW1CLUSTER+"_cpod3-0",
             'service': 'nextensio-default-internet', 'cluster': GW1CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-0",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD},
            {'name': CNCTR2, 'agent': False, 'device': GW1CLUSTER+"_cpod2-0",
             'service': 'v2.kismis.org', 'cluster': GW1CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR3, 'agent': False, 'device': GW1CLUSTER+"_cpod3-1",
             'service': 'nextensio-default-internet', 'cluster': GW1CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-1",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD},
            {'name': CNCTR2, 'agent': False, 'device': GW1CLUSTER+"_cpod2-1",
             'service': 'v2.kismis.org', 'cluster': GW1CLUSTER, 'pod': CNCTR1POD}
        ]
        placeAndVerifyAgents(testbed.devices, specs)
        resetAgents(testbed.devices)
        checkOnboarding(specs)
        checkConsulDns(specs, testbed.devices)
        basicAccessSanity(kwargs, specs, testbed.devices)
        # And now go back to the original configuration of this test case
        specs = [
            {'name': USER1, 'agent': True, 'device': GW1CLUSTER+"_apod1",
             'service': '', 'cluster': GW1CLUSTER, 'pod': 1},
            {'name': USER2, 'agent': True, 'device': GW1CLUSTER+"_apod2",
             'service': '', 'cluster': GW1CLUSTER, 'pod': 2},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-0",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-0",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-0",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-1",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-1",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-1",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD}
        ]
        placeAndVerifyAgents(testbed.devices, specs)
        resetAgents(testbed.devices)
        checkOnboarding(specs)
        checkConsulDns(specs, testbed.devices)
        basicAccessSanity(kwargs, specs, testbed.devices)

    @ aetest.test
    def dynamicSwitchApodsCpodsCrossClusterCase2(self, testbed, **kwargs):
        '''Switch again to different random set of pods across clusters and come back,
        all without doing pod restarts.
        This is to ensure nothing in the pod  like agent<-->socket hashtables etc.
        remain stale when agents come and go
        '''
        # Mix up agents and pods again
        specs = [
            {'name': USER1, 'agent': True, 'device': GW2CLUSTER+"_apod1",
             'service': '', 'cluster': GW2CLUSTER, 'pod': 1},
            {'name': USER2, 'agent': True, 'device': GW1CLUSTER+"_apod1",
             'service': '', 'cluster': GW1CLUSTER, 'pod': 1},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-0",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-0",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD},
            {'name': CNCTR2, 'agent': False, 'device': GW1CLUSTER+"_cpod2-0",
             'service': 'v2.kismis.org', 'cluster': GW1CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-1",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-1",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD},
            {'name': CNCTR2, 'agent': False, 'device': GW1CLUSTER+"_cpod2-1",
             'service': 'v2.kismis.org', 'cluster': GW1CLUSTER, 'pod': CNCTR1POD}
        ]
        placeAndVerifyAgents(testbed.devices, specs)
        resetAgents(testbed.devices)
        checkOnboarding(specs)
        checkConsulDns(specs, testbed.devices)
        basicAccessSanity(kwargs, specs, testbed.devices)

        # And now go back to original configuration of this test case
        specs = [
            {'name': USER1, 'agent': True, 'device': GW1CLUSTER+"_apod1",
             'service': '', 'cluster': GW1CLUSTER, 'pod': 1},
            {'name': USER2, 'agent': True, 'device': GW1CLUSTER+"_apod2",
             'service': '', 'cluster': GW1CLUSTER, 'pod': 2},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-0",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-0",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-0",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-1",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-1",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-1",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD}
        ]
        placeAndVerifyAgents(testbed.devices, specs)
        resetAgents(testbed.devices)
        checkOnboarding(specs)
        checkConsulDns(specs, testbed.devices)
        basicAccessSanity(kwargs, specs, testbed.devices)

    @ aetest.cleanup
    def cleanup(self):
        return


class Agent1PodsConnector3PodsClustersMixed(aetest.Testcase):
    '''In this class of tests, all agents are kept in the same apod, though they may terminate
    in different replicas of the apod depending on k8s. Connectors are kept in separate pods
    in same or different clusters.
    They are randomly switched around to different pods across clusters.
    '''
    @ aetest.setup
    def setup(self, testbed):
        specs = [
            {'name': USER1, 'agent': True, 'device': GW1CLUSTER+"_apod1",
             'service': '', 'cluster': GW1CLUSTER, 'pod': 1},
            {'name': USER2, 'agent': True, 'device': GW1CLUSTER+"_apod1",
             'service': '', 'cluster': GW1CLUSTER, 'pod': 1},
            {'name': CNCTR3, 'agent': False, 'device': GW1CLUSTER+"_cpod3-0",
             'service': 'nextensio-default-internet', 'cluster': GW1CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-0",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW1CLUSTER+"_cpod2-0",
             'service': 'v2.kismis.org', 'cluster': GW1CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR3, 'agent': False, 'device': GW1CLUSTER+"_cpod3-1",
             'service': 'nextensio-default-internet', 'cluster': GW1CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-1",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW1CLUSTER+"_cpod2-1",
             'service': 'v2.kismis.org', 'cluster': GW1CLUSTER, 'pod': CNCTR3POD}
        ]
        placeAndVerifyAgents(testbed.devices, specs)
        resetAgents(testbed.devices)
        checkOnboarding(specs)
        checkConsulDns(specs, testbed.devices)

    @ aetest.test
    def basicConnectivity(self, testbed, **kwargs):
        specs = [
            {'name': USER1, 'agent': True, 'device': GW1CLUSTER+"_apod1",
             'service': '', 'cluster': GW1CLUSTER, 'pod': 1},
            {'name': USER2, 'agent': True, 'device': GW1CLUSTER+"_apod1",
             'service': '', 'cluster': GW1CLUSTER, 'pod': 1},
            {'name': CNCTR3, 'agent': False, 'device': GW1CLUSTER+"_cpod3-0",
             'service': 'nextensio-default-internet', 'cluster': GW1CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-0",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW1CLUSTER+"_cpod2-0",
             'service': 'v2.kismis.org', 'cluster': GW1CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR3, 'agent': False, 'device': GW1CLUSTER+"_cpod3-1",
             'service': 'nextensio-default-internet', 'cluster': GW1CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-1",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW1CLUSTER+"_cpod2-1",
             'service': 'v2.kismis.org', 'cluster': GW1CLUSTER, 'pod': CNCTR3POD}
        ]
        basicAccessSanity(kwargs, specs, testbed.devices)

    @ aetest.test
    def dynamicSwitchMixedClustersCase1(self, testbed, **kwargs):
        '''Agent1 and Agent2 in the same but different pod in same cluster. default, kismis.v1
        and kismis.v2 mixed up in different pods in different clusters.
        '''
        specs = [
            {'name': USER1, 'agent': True, 'device': GW1CLUSTER+"_apod2",
             'service': '', 'cluster': GW1CLUSTER, 'pod': 2},
            {'name': USER2, 'agent': True, 'device': GW1CLUSTER+"_apod2",
             'service': '', 'cluster': GW1CLUSTER, 'pod': 2},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-0",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD},
            {'name': CNCTR1, 'agent': False, 'device': GW1CLUSTER+"_cpod1-0",
             'service': 'v1.kismis.org', 'cluster': GW1CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-0",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-1",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD},
            {'name': CNCTR1, 'agent': False, 'device': GW1CLUSTER+"_cpod1-1",
             'service': 'v1.kismis.org', 'cluster': GW1CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-1",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD}
        ]
        placeAndVerifyAgents(testbed.devices, specs)
        resetAgents(testbed.devices)
        checkOnboarding(specs)
        checkConsulDns(specs, testbed.devices)
        basicAccessSanity(kwargs, specs, testbed.devices)

    @ aetest.test
    def dynamicSwitchMixedClustersCase2(self, testbed, **kwargs):
        '''Agent1 and Agent2 in the same pod, default, kismis.v1 and kismis.v2 in different
        pods in the same cluster (gatewaytestc)
        '''
        specs = [
            {'name': USER1, 'agent': True, 'device': GW2CLUSTER+"_apod1",
             'service': '', 'cluster': GW2CLUSTER, 'pod': 1},
            {'name': USER1, 'agent': True, 'device': GW2CLUSTER+"_apod1",
             'service': '', 'cluster': GW2CLUSTER, 'pod': 1},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-0",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-0",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-0",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-1",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-1",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-1",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD}
        ]
        placeAndVerifyAgents(testbed.devices, specs)
        resetAgents(testbed.devices)
        checkOnboarding(specs)
        checkConsulDns(specs, testbed.devices)
        basicAccessSanity(kwargs, specs, testbed.devices)

# The aetest.setup section in this class is executed BEFORE the aetest.test sections,
# so this is like a big-test with a setup, and then a set of test cases and then a teardown,
# and then the next big-test class is run similarly

# Policies for testing connector to connector
def conn2conn_policy():
    with open('conn2conn.AccessPolicy','r') as file:
        rego = file.read()
        ok = create_policy('AccessPolicy', rego)
        while not ok:
            logger.info('Access Policy creation failed, retrying ...')
            time.sleep(1)
            ok = create_policy('AccessPolicy', rego)
        
    with open('conn2conn.RoutePolicy','r') as file:
        rego = file.read()
        ok = create_policy('RoutePolicy', rego)
        while not ok:
            logger.info('Route Policy creation failed, retrying ...')
            time.sleep(1)
            ok = create_policy('RoutePolicy', rego)

class AgentConnectorSquareOne(aetest.Testcase):
    '''Agents and connectors back to their very first placement.
    '''
    @ aetest.setup
    def setup(self, testbed):
        specs = [
            {'name': USER1, 'agent': True, 'device': GW1CLUSTER+"_apod1",
             'service': '', 'cluster': GW1CLUSTER, 'pod': 1},
            {'name': USER2, 'agent': True, 'device': GW1CLUSTER+"_apod2",
             'service': '', 'cluster': GW1CLUSTER, 'pod': 2},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-0",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-0",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-0",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD},
            {'name': CNCTR3, 'agent': False, 'device': GW2CLUSTER+"_cpod3-1",
             'service': 'nextensio-default-internet', 'cluster': GW2CLUSTER, 'pod': CNCTR3POD},
            {'name': CNCTR1, 'agent': False, 'device': GW2CLUSTER+"_cpod1-1",
             'service': 'v1.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR1POD},
            {'name': CNCTR2, 'agent': False, 'device': GW2CLUSTER+"_cpod2-1",
             'service': 'v2.kismis.org', 'cluster': GW2CLUSTER, 'pod': CNCTR2POD}
        ]
        placeAndVerifyAgents(testbed.devices, specs)
        resetAgents(testbed.devices)
        checkOnboarding(specs)
        checkConsulDns(specs, testbed.devices)

    def squareOneSanity(self, testbed, **kwargs):
        basicAccessSanity(kwargs, specs, testbed.devices)

def create_host_attr(routejson):
    global api_instance

    try:
        resp = api_instance.add_host_attr(routejson, "superadmin", tenant)
        if resp.result != "ok":
            return False
    except Exception as e:
        pass
        return False

    return True

def create_user_attr(userjson, userid):
    global api_instance

    try:
        resp = api_instance.add_user_attr(userjson, "superadmin", tenant, userid)
        if resp.result != "ok":
            return False
    except Exception as e:
        pass
        return False

    return True

def create_user(uid, name, pod, gateway):
    global api_instance

    try:
        add = swagger_client.UserAdd(uid=uid, name=name, pod=pod, gateway=gateway)
        resp = api_instance.add_user(add, "superadmin", tenant)
        if resp.result != "ok":
            return False
    except Exception as e:
        pass
        return False

    return True

def create_bundle(bid, name, services, pod, gateway, cpodrepl):
    global api_instance

    try:
        add = swagger_client.BundleStruct(bid=bid, name=bid, services=services, pod=pod, gateway=gateway, cpodrepl=cpodrepl)  
        resp = api_instance.add_bundle(add, "superadmin", tenant)
        if resp.result != "ok":
            return False
    except Exception as e:
        pass
        return False

    return True

def create_bundle_attr(bjson):
    global api_instance

    try:
        resp = api_instance.add_bundle_attr(bjson, "superadmin", tenant)
        if resp.result != "ok":
            return False
    except Exception as e:
        pass
        return False

    return True

def create_policy(pid, policy):
    global api_instance

    rego = []
    for p in policy:
        rego.append(ord(p))
    add = swagger_client.AddPolicy(pid=pid, rego=rego)
    try:
        resp = api_instance.add_policy_handler(add, "superadmin", tenant)
        if resp.result != "ok":
            return False
    except Exception as e:
        pass
        return False

    return True

if __name__ == '__main__':
    import argparse
    from pyats.topology import loader

    parser = argparse.ArgumentParser()
    parser.add_argument('--testbed', dest='testbed',
                        type=loader.load)

    args, unknown = parser.parse_known_args()

    token = runCmd("go run ./pkce.go https://dev-635657.okta.com").strip()
    if token == "":
        print('Cannot get access token, exiting')
        exit(1)

    # Load the testbed information variables as environment variables
    load_dotenv(dotenv_path='/tmp/nextensio-kind/environment')
    config = swagger_client.Configuration()
    config.verify_ssl = False
    config.host = "https://" + os.getenv('ctrl_ip') + ":8080/api/v1"
    api_instance = swagger_client.DefaultApi(swagger_client.ApiClient(config))
    api_instance.api_client.set_default_header("Authorization", "Bearer " + token)

    aetest.main(**vars(args))
