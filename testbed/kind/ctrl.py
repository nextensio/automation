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
    token = runCmd("go run ../../pkce.go https://dev-635657.okta.com").strip()
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

    gw1json = {"name":"gatewaytesta.nextensio.net", "cluster": "gatewaytesta"}
    gw2json = {"name":"gatewaytestc.nextensio.net", "cluster": "gatewaytestc"}
    
    ok = create_gateway(url, gw1json, token)
    while not ok:
        print('Gateway creation failed, retrying ...')
        time.sleep(1)
        ok = create_gateway(url, gw1json, token)

    ok = create_gateway(url, gw2json, token)
    while not ok:
        print('Gateway creation failed, retrying ...')
        time.sleep(1)
        ok = create_gateway(url, gw2json, token)

    tenantjson = {"_id":"nextensio",
                  "gateways":["gatewaytesta.nextensio.net","gatewaytestc.nextensio.net"],
                  "domains": ["kismis.org", "nextensio-default-internet"],
                  "image":"registry.gitlab.com/nextensio/cluster/minion:latest",
                  "pods":5,
                  "curid":""}
    
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

    tenantclusterjson1 = {"tenant":tenant, "cluster":"gatewaytesta", "image":"",
                          "pods":5}
    tenantclusterjson2 = {"tenant":tenant, "cluster":"gatewaytestc", "image":"",
                          "pods":5}

    ok = create_tenant_cluster(url, tenant, tenantclusterjson1, token)
    while not ok:
        print('Tenant cluster creation failed, retrying ...')
        time.sleep(1)
        ok = create_tenant_cluster(url, tenant, tenantclusterjson1, token)

    ok = create_tenant_cluster(url, tenant, tenantclusterjson2, token)
    while not ok:
        print('Tenant cluster creation failed, retrying ...')
        time.sleep(1)
        ok = create_tenant_cluster(url, tenant, tenantclusterjson2, token)

    user1json = {"uid":"test1@nextensio.net", "name":"User1", "email":"test1@nextensio.net",
                 "services":[], "gateway":"gatewaytesta.nextensio.net",
                 "cluster": "gatewaytesta", "pod":1}
    user2json = {"uid":"test2@nextensio.net", "name":"User2", "email":"test2@nextensio.net",
                 "services":[], "gateway":"gatewaytesta.nextensio.net",
                 "cluster": "gatewaytesta", "pod":2}

    user1attrjson = {"uid":"test1@nextensio.net", "category":"employee",
                     "type":"IC", "level":50, "dept":["ABU","BBU"], "team":["engineering"] }
    user2attrjson = {"uid":"test2@nextensio.net", "category":"employee",
                     "type":"IC", "level":50, "dept":["ABU","BBU"], "team":["sales"] }
    
    bundle1json = {"bid":"default@nextensio.net", "name":"Default Internet",
                   "services":["nextensio-default-internet"], "gateway":"gatewaytestc.nextensio.net",
                   "cluster": "gatewaytestc", "pod":3}
    bundle2json = {"bid":"v1.kismis@nextensio.net", "name":"Kismis ONE",
                   "services":["v1.kismis.org"], "gateway":"gatewaytestc.nextensio.net",
                   "cluster": "gatewaytestc", "pod":4}
    bundle3json = {"bid":"v2.kismis@nextensio.net", "name":"Kismis TWO",
                   "services":["v2.kismis.org"], "gateway":"gatewaytestc.nextensio.net",
                   "cluster": "gatewaytestc", "pod":5}

    bundle1attrjson = {"bid":"default@nextensio.net", "dept":["ABU","BBU"],
                       "team":["engineering","sales"], "IC":1, "manager":1, "nonemployee":"allow"}
    bundle2attrjson = {"bid":"v1.kismis@nextensio.net", "dept":["ABU","BBU"],
                       "team":["engineering","sales"], "IC":1, "manager":1, "nonemployee":"allow"}
    bundle3attrjson = {"bid":"v2.kismis@nextensio.net", "dept":["ABU","BBU"],
                       "team":["engineering","sales"], "IC":1, "manager":1, "nonemployee":"allow"}
    
    host1attrjson = { "host": "kismis.org",
                      "routeattrs": [
		      {"tag": "v2", "team": ["engineering"], "dept": ["ABU","BBU"],
		       "category": ["employee","nonemployee"], "type": ["IC","manager"], "IClvl": 1, "mlvl": 1
                      },
		      {"tag": "v1", "team": ["sales"], "dept": ["BBU","ABU"],
		        "category": ["employee"], "type": ["manager","IC"], "IClvl": 4, "mlvl": 4
		      } ]
		    }

    ok = create_user(url, tenant, user1json, token)
    while not ok:
        print('User creation failed, retrying ...')
        time.sleep(1)
        ok = create_user(url, tenant, user1json, token)

    ok = create_user_attr(url, tenant, user1attrjson, token)
    while not ok:
        print('UserAttr creation failed, retrying ...')
        time.sleep(1)
        ok = create_user_attr(url, tenant, user1attrjson, token)
    
    ok = create_user(url, tenant, user2json, token)
    while not ok:
        print('User creation failed, retrying ...')
        time.sleep(1)
        ok = create_user(url, tenant, user2json, token)
    
    ok = create_user_attr(url, tenant, user2attrjson, token)
    while not ok:
        print('UserAttr creation failed, retrying ...')
        time.sleep(1)
        ok = create_user_attr(url, tenant, user2attrjson, token)

    ok = create_bundle(url, tenant, bundle1json, token)
    while not ok:
        print('Bundle creation failed, retrying ...')
        time.sleep(1)
        ok = create_bundle(url, tenant, bundle1json, token)

    ok = create_bundle_attr(url, tenant, bundle1attrjson, token)
    while not ok:
        print('BundleAttr creation failed, retrying ...')
        time.sleep(1)
        ok = create_bundle_attr(url, tenant, bundle1attrjson, token)

    ok = create_bundle(url, tenant, bundle2json, token)
    while not ok:
        print('Bundle creation failed, retrying ...')
        time.sleep(1)
        ok = create_bundle(url, tenant, bundle2json, token)

    ok = create_bundle_attr(url, tenant, bundle2attrjson, token)
    while not ok:
        print('BundleAttr creation failed, retrying ...')
        time.sleep(1)
        ok = create_bundle_attr(url, tenant, bundle2attrjson, token)

    ok = create_bundle(url, tenant, bundle3json, token)
    while not ok:
        print('Bundle creation failed, retrying ...')
        time.sleep(1)
        ok = create_bundle(url, tenant, bundle3json, token)
        
    ok = create_bundle_attr(url, tenant, bundle3attrjson, token)
    while not ok:
        print('BundleAttr creation failed, retrying ...')
        time.sleep(1)
        ok = create_bundle_attr(url, tenant, bundle3attrjson, token)

    ok = create_host_attr(url, tenant, host1attrjson, token)
    while not ok:
        print('HostAttr creation failed, retrying ...')
        time.sleep(1)
        ok = create_host_attr(url, tenant, host1attrjson, token)
    
    route1json = {"route":"test1@nextensio.net:kismis.org", "tag":"v1"}
    route2json = {"route":"test2@nextensio.net:kismis.org", "tag":"v2"}
    
    ok = create_route(url, tenant, route1json, token)
    while not ok:
        print('Route creation failed, retrying ...')
        time.sleep(1)
        ok = create_route(url, tenant, route1json, token)
        
    ok = create_route(url, tenant, route2json, token)
    while not ok:
        print('Route creation failed, retrying ...')
        time.sleep(1)
        ok = create_route(url, tenant, route2json, token)

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
