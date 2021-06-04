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

    gw1json = {"name":"gatewaytesta.nextensio.net"}
    gw2json = {"name":"gatewaytestc.nextensio.net"}
    
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

    tenantjson = {"_id":"nextensio",
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

    tenantclusterjson1 = {"tenant":tenant, "gateway":"gatewaytesta.nextensio.net", "image":"",
                          "apods":2, "cpods":2}
    tenantclusterjson2 = {"tenant":tenant, "gateway":"gatewaytestc.nextensio.net", "image":"",
                          "apods":1, "cpods":3}

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

    user1json = {"uid":"test1@nextensio.net", "name":"User1", "email":"test1@nextensio.net",
                 "services":[], "gateway":"gatewaytesta.nextensio.net",
                 "pod":1}
    user2json = {"uid":"test2@nextensio.net", "name":"User2", "email":"test2@nextensio.net",
                 "services":[], "gateway":"gatewaytesta.nextensio.net",
                 "pod":2}

    user1attrjson = {"uid":"test1@nextensio.net", "category":"employee",
                     "type":"IC", "level":50, "dept":["ABU","BBU"], "team":["engineering"],
                     "location": "California", "ostype": "Linux", "osver": 20.04 }
    user2attrjson = {"uid":"test2@nextensio.net", "category":"employee",
                     "type":"IC", "level":50, "dept":["ABU","BBU"], "team":["sales"],
                     "location": "Massachusets", "ostype": "Windows", "osver": 10.12 }
    

    userattrsetjson = [
        {"name": "category", "appliesTo": "Users", "type": "String"},
        {"name": "type", "appliesTo": "Users", "type": "String"},
        {"name": "level", "appliesTo": "Users", "type": "Number"},
        {"name": "dept", "appliesTo": "Users", "type": "String"},
        {"name": "team", "appliesTo": "Users", "type": "String"},
        {"name": "location", "appliesTo": "Users", "type": "String"},
        {"name": "ostype", "appliesTo": "Users", "type": "String"},
        {"name": "osver", "appliesTo": "Users", "type": "Number"}
        ]


    bundle1json = {"bid":"default@nextensio.net", "name":"Default Internet",
                   "services":["nextensio-default-internet"], "gateway":"gatewaytestc.nextensio.net",
                   "pod":1}
    bundle2json = {"bid":"v1.kismis@nextensio.net", "name":"Kismis ONE",
                   "services":["v1.kismis.org"], "gateway":"gatewaytestc.nextensio.net",
                   "pod":2}
    bundle3json = {"bid":"v2.kismis@nextensio.net", "name":"Kismis TWO",
                   "services":["v2.kismis.org"], "gateway":"gatewaytestc.nextensio.net",
                   "pod":3}

    bundle1attrjson = {"bid":"default@nextensio.net", "dept":["ABU","BBU"],
                       "team":["engineering","sales"], "IC":1, "manager":1, "nonemployee":"allow"}
    bundle2attrjson = {"bid":"v1.kismis@nextensio.net", "dept":["ABU","BBU"],
                       "team":["engineering","sales"], "IC":1, "manager":1, "nonemployee":"allow"}
    bundle3attrjson = {"bid":"v2.kismis@nextensio.net", "dept":["ABU","BBU"],
                       "team":["engineering","sales"], "IC":1, "manager":1, "nonemployee":"allow"}
    

    bundleattrsetjson = [
        {"name": "dept", "appliesTo": "Bundles", "type": "String"},
        {"name": "team", "appliesTo": "Bundles", "type": "String"},
        {"name": "IC", "appliesTo": "Bundles", "type": "Number"},
        {"name": "manager", "appliesTo": "Bundles", "type": "Number"},
        {"name": "nonemployee", "appliesTo": "Bundles", "type": "String"}
        ]


    host1attrjson = { "host": "kismis.org",
                      "routeattrs": [
		      {"tag": "v2", "team": ["engineering"], "dept": ["ABU","BBU"],
		       "category": ["employee","nonemployee"], "type": ["IC","manager"], "IClvl": 1, "mlvl": 1
                      },
		      {"tag": "v1", "team": ["sales"], "dept": ["BBU","ABU"],
		        "category": ["employee"], "type": ["manager","IC"], "IClvl": 4, "mlvl": 4
		      } ]
		    }

    host2attrjson = { "host": "nextensio-default-internet",
                      "routeattrs": [{ "tag" : "" }]
            }

    hostattrsetjson = [
        {"name": "dept", "appliesTo": "Hosts", "type": "String"},
        {"name": "team", "appliesTo": "Hosts", "type": "String"},
        {"name": "IClvl", "appliesTo": "Hosts", "type": "Number"},
        {"name": "mlvl", "appliesTo": "Hosts", "type": "Number"},
        {"name": "category", "appliesTo": "Hosts", "type": "String"},
        {"name": "type", "appliesTo": "Hosts", "type": "String"}
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
