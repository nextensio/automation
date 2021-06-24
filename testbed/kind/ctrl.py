#!/usr/bin/env python3

import sys
import requests
import time
import subprocess
from nextensio_controller import *

url = "https://" + sys.argv[1] + ":8080"
token = ""
rootca = ""
cert = ""
GW1 = "gatewaytesta.nextensio.net"
GW2 = "gatewaytestc.nextensio.net"
TENANT = "nextensio"
USER1 = "test1@nextensio.net"
USER2 = "test2@nextensio.net"
CNCTR1 = "v1.kismis@nextensio.net"
CNCTR2 = "v2.kismis@nextensio.net"
CNCTR3 = "default@nextensio.net"

def runCmd(cmd):
    try:
        output = subprocess.check_output(cmd, shell=True)
        return output.decode()
    except:
        pass
        return ""

if __name__ == '__main__':
    token = runCmd("go run ./pkce.go https://dev-635657.okta.com").strip()
    if token == "":
        print('Cannot get access token, exiting')
        exit(1)

    rootca = sys.argv[2]
    f = open(rootca, 'r')
    cert = f.read()
    f.close()

    while not is_controller_up(url, token):
        print('Controller not up, waiting ...')
        time.sleep(5)

    gw1json = {"name":GW1}
    gw2json = {"name":GW2}
    
    ok = create_gateway(url, gw1json, token)
    while not ok:
        print('Gateway1 creation failed, retrying ...')
        time.sleep(1)
        ok = create_gateway(url, gw1json, token)

    ok = create_gateway(url, gw2json, token)
    while not ok:
        print('Gateway2 creation failed, retrying ...')
        time.sleep(1)
        ok = create_gateway(url, gw2json, token)

    tenantjson = {"_id":TENANT,
                  "image":"registry.gitlab.com/nextensio/cluster/minion:latest",
                  }
    
    ok = create_tenant(url, tenantjson, token)
    while not ok:
        print('Tenant creation failed, retrying ...')
        time.sleep(1)
        ok = create_tenant(url, tenantjson, token)

    ok, tenants = get_tenants(url, token)
    while not ok:
        print('Tenant fetch failed, retrying ...')
        time.sleep(1)
        ok, tenants = get_tenants(url, token)

    # The test setup is assumed to be created with just one tenant, if we need more we just need
    # to search for the right tenant name or something inside the returned list of tenants
    tenant = tenants[0]['_id']
    if tenant != TENANT:
        print('Tenant mismatch after readback from DB - %s != %s' % (tenant, TENANT))
        exit(1)

    tenantclusterjson1 = {"gateway":GW1, "image":"", "apodsets":2, "apodrepl":1}
    tenantclusterjson2 = {"gateway":GW2, "image":"", "apodsets":1, "apodrepl":1}

    ok = create_tenant_cluster(url, tenant, tenantclusterjson1, token)
    while not ok:
        print('Tenant cluster1 creation failed, retrying ...')
        time.sleep(1)
        ok = create_tenant_cluster(url, tenant, tenantclusterjson1, token)

    ok = create_tenant_cluster(url, tenant, tenantclusterjson2, token)
    while not ok:
        print('Tenant cluster2 creation failed, retrying ...')
        time.sleep(1)
        ok = create_tenant_cluster(url, tenant, tenantclusterjson2, token)

    user1json = {"uid":USER1, "name":"User1", "email":USER1,
                 "services":[], "gateway":GW1, "pod":1}
    user2json = {"uid":USER2, "name":"User2", "email":USER2,
                 "services":[], "gateway":GW1, "pod":2}

    user1attrjson = {"uid":USER1, "category":"employee",
                     "type":"IC", "level":50, "dept":["ABU","BBU"], "team":["engineering"],
                     "location": "California", "ostype": "Linux", "osver": 20.04 }
    user2attrjson = {"uid":USER2, "category":"employee",
                     "type":"IC", "level":50, "dept":["ABU","BBU"], "team":["sales"],
                     "location": "Massachusets", "ostype": "Windows", "osver": 10.12 }
    

    userattrsetjson = [
        {"name": "category", "appliesTo": "Users", "type": "String", "isArray": False,
         "rangeCheck": "1-16"},
        {"name": "type", "appliesTo": "Users", "type": "String", "isArray": False,
         "rangeCheck": "1-16"},
        {"name": "level", "appliesTo": "Users", "type": "Number", "numType": "int",
         "isArray": False, "rangeCheck": "1-20"},
        {"name": "dept", "appliesTo": "Users", "type": "String", "isArray": True,
         "rangeCheck": "1-16"},
        {"name": "team", "appliesTo": "Users", "type": "String", "isArray": True,
         "rangeCheck": "1-16"},
        {"name": "location", "appliesTo": "Users", "type": "String", "isArray": False,
         "rangeCheck": "1-16"},
        {"name": "ostype", "appliesTo": "Users", "type": "String", "isArray": False,
         "rangeCheck": "1-16"},
        {"name": "osver", "appliesTo": "Users", "type": "Number", "numType": "float",
         "isArray": False, "rangeCheck": "1.0-40.0"}
        ]


    bundle1json = {"bid":CNCTR3, "name":"Default Internet",
                   "services":["nextensio-default-internet"], "gateway":GW2, "cpodrepl":1}
    bundle2json = {"bid":CNCTR1, "name":"Kismis ONE",
                   "services":["v1.kismis.org"], "gateway":GW2, "cpodrepl":1}
    bundle3json = {"bid":CNCTR2, "name":"Kismis TWO",
                   "services":["v2.kismis.org"], "gateway":GW2, "cpodrepl":1}

    bundle1attrjson = {"bid":CNCTR3, "dept":["ABU","BBU"],
                       "team":["engineering","sales"], "IC":1, "manager":1, "nonemployee":"allow"}
    bundle2attrjson = {"bid":CNCTR1, "dept":["ABU","BBU"],
                       "team":["engineering","sales"], "IC":1, "manager":1, "nonemployee":"allow"}
    bundle3attrjson = {"bid":CNCTR2, "dept":["ABU","BBU"],
                       "team":["engineering","sales"], "IC":1, "manager":1, "nonemployee":"allow"}
    

    bundleattrsetjson = [
        {"name": "dept", "appliesTo": "Bundles", "type": "String", "isArray": True,
         "rangeCheck": "1-16"},
        {"name": "team", "appliesTo": "Bundles", "type": "String", "isArray": True,
         "rangeCheck": "1-16"},
        {"name": "IC", "appliesTo": "Bundles", "type": "Number", "numType": "int",
         "isArray": False, "rangeCheck": "1-20"},
        {"name": "manager", "appliesTo": "Bundles", "type": "Number", "numType": "int",
         "isArray": False, "rangeCheck": "1-20"},
        {"name": "nonemployee", "appliesTo": "Bundles", "type": "String", "isArray": False,
         "rangeCheck": "1-8"}
        ]


    host1attrjson = { "host": "kismis.org",
                      "routeattrs": [
		      {"tag": "v2", "team": ["engineering"], "dept": ["ABU","BBU"],
		       "category": ["employee","nonemployee"], "type": ["IC","manager"],
                       "IClvl": 1, "mlvl": 1
                      },
		      {"tag": "v1", "team": ["sales"], "dept": ["BBU","ABU"],
		       "category": ["employee"], "type": ["manager","IC"],
                       "IClvl": 4, "mlvl": 4
		      } ]
		    }

    host2attrjson = { "host": "nextensio-default-internet",
                      "routeattrs": [{ "tag" : "" }]
            }

    hostattrsetjson = [
        {"name": "dept", "appliesTo": "Hosts", "type": "String", "isArray": True,
         "rangeCheck": "1-16"},
        {"name": "team", "appliesTo": "Hosts", "type": "String", "isArray": True,
         "rangeCheck": "1-16"},
        {"name": "IClvl", "appliesTo": "Hosts", "type": "Number", "numType": "int",
         "isArray": False, "rangeCheck": "1-20"},
        {"name": "mlvl", "appliesTo": "Hosts", "type": "Number", "numType": "int",
         "isArray": False, "rangeCheck": "1-20"},
        {"name": "category", "appliesTo": "Hosts", "type": "String", "isArray": True,
         "rangeCheck": "1-16"},
        {"name": "type", "appliesTo": "Hosts", "type": "String", "isArray": False,
         "rangeCheck": "1-16"}
        ]


    # Prime some user, bundle and host attr sets for the UI attribute editor
    ok = create_attrset(url, tenant, userattrsetjson, token)
    while not ok:
        print('User attrset creation failed, retrying ...')
        time.sleep(1)
        ok = create_attrset(url, tenant, userattrsetjson, token)

    ok = create_attrset(url, tenant, bundleattrsetjson, token)
    while not ok:
        print('Bundle attrset creation failed, retrying ...')
        time.sleep(1)
        ok = create_attrset(url, tenant, bundleattrsetjson, token)

    ok = create_attrset(url, tenant, hostattrsetjson, token)
    while not ok:
        print('Host attrset creation failed, retrying ...')
        time.sleep(1)
        ok = create_attrset(url, tenant, hostattrsetjson, token)

    # User info and user attributes creation
    ok = create_user(url, tenant, user1json, token)
    while not ok:
        print('User1 creation failed, retrying ...')
        time.sleep(1)
        ok = create_user(url, tenant, user1json, token)

    ok = create_user_attr(url, tenant, user1attrjson, token)
    while not ok:
        print('User1Attr creation failed, retrying ...')
        time.sleep(1)
        ok = create_user_attr(url, tenant, user1attrjson, token)
    
    ok = create_user(url, tenant, user2json, token)
    while not ok:
        print('User2 creation failed, retrying ...')
        time.sleep(1)
        ok = create_user(url, tenant, user2json, token)
    
    ok = create_user_attr(url, tenant, user2attrjson, token)
    while not ok:
        print('User2Attr creation failed, retrying ...')
        time.sleep(1)
        ok = create_user_attr(url, tenant, user2attrjson, token)

    # Bundle info and bundle attributes creation
    ok = create_bundle(url, tenant, bundle1json, token)
    while not ok:
        print('Bundle1 creation failed, retrying ...')
        time.sleep(1)
        ok = create_bundle(url, tenant, bundle1json, token)

    ok = create_bundle_attr(url, tenant, bundle1attrjson, token)
    while not ok:
        print('Bundle1Attr creation failed, retrying ...')
        time.sleep(1)
        ok = create_bundle_attr(url, tenant, bundle1attrjson, token)

    ok = create_bundle(url, tenant, bundle2json, token)
    while not ok:
        print('Bundle2 creation failed, retrying ...')
        time.sleep(1)
        ok = create_bundle(url, tenant, bundle2json, token)

    ok = create_bundle_attr(url, tenant, bundle2attrjson, token)
    while not ok:
        print('Bundle2Attr creation failed, retrying ...')
        time.sleep(1)
        ok = create_bundle_attr(url, tenant, bundle2attrjson, token)

    ok = create_bundle(url, tenant, bundle3json, token)
    while not ok:
        print('Bundle3 creation failed, retrying ...')
        time.sleep(1)
        ok = create_bundle(url, tenant, bundle3json, token)
        
    ok = create_bundle_attr(url, tenant, bundle3attrjson, token)
    while not ok:
        print('Bundle3Attr creation failed, retrying ...')
        time.sleep(1)
        ok = create_bundle_attr(url, tenant, bundle3attrjson, token)

    ok = create_host_attr(url, tenant, host1attrjson, token)
    while not ok:
        print('HostAttr1 creation failed, retrying ...')
        time.sleep(1)
        ok = create_host_attr(url, tenant, host1attrjson, token)
    
    ok = create_host_attr(url, tenant, host2attrjson, token)
    while not ok:
        print('HostAttr2 creation failed, retrying ...')
        time.sleep(1)
        ok = create_host_attr(url, tenant, host2attrjson, token)
    
    with open('policy.AccessPolicy','r') as file:
        rego = file.read()
    ok = create_policy(url, tenant, 'AccessPolicy', rego, token)
    while not ok:
        print('Access Policy creation failed, retrying ...')
        time.sleep(1)
        ok = create_policy(url, tenant, 'AccessPolicy', rego, token)

    with open('policy.RoutePolicy','r') as file:
        rego = file.read()
    ok = create_policy(url, tenant, 'RoutePolicy', rego, token)
    while not ok:
        print('Route Policy creation failed, retrying ...')
        time.sleep(1)
        ok = create_policy(url, tenant, 'RoutePolicy', rego, token)

    ok = create_cert(url, cert, token)
    while not ok:
        print('CERT creation failed, retrying ...')
        time.sleep(1)
        ok = create_cert(url, cert, token)
