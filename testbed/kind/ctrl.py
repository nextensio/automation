#!/usr/bin/env python3

import sys
import requests
import time
from nextensio_controller import *

url = "https://" + sys.argv[1] + ":8080/api/v1/"
rootca = sys.argv[2]
f = open(rootca, 'r')
cert = f.read()
f.close()

if __name__ == '__main__':
    while not is_controller_up(url):
        print('Controller not up, waiting ...')
        time.sleep(5)

    gw1json = {"name":"gatewaytesta.nextensio.net"}
    gw2json = {"name":"gatewaytestc.nextensio.net"}
    
    ok = create_gateway(url, gw1json)
    while not ok:
        print('Gateway creation failed, retrying ...')
        time.sleep(1)
        ok = create_gateway(url, gw1json)

    ok = create_gateway(url, gw2json)
    while not ok:
        print('Gateway creation failed, retrying ...')
        time.sleep(1)
        ok = create_gateway(url, gw2json)

    tenantjson = {"name":"Test", "gateways":["gatewaytesta.nextensio.net","gatewaytestc.nextensio.net"],
                  "domains": ["kismis.org"], "image":"registry.gitlab.com/nextensio/cluster/minion:latest",
                  "pods":5, "curid":""}
    
    ok = create_tenant(url, tenantjson)
    while not ok:
        print('Tenant creation failed, retrying ...')
        time.sleep(1)
        ok = create_tenant(url, tenantjson)

    ok, tenants = get_tenants(url)
    while not ok:
        print('Tenant fetch failed, retrying ...')
        time.sleep(1)
        ok, tenants = get_tenants(url)

    # The test setup is assumed to be created with just one tenant, if we need more we just need
    # to search for the right tenant name or something inside the returned list of tenants
    tenant = tenants[0]['_id']

    user1json = {"uid":"test1@nextensio.net", "tenant":tenant, "name":"User1", "email":"test1@nextensio.net",
                 "services":["test1-nextensio-net"], "gateway":"gatewaytesta.nextensio.net", "pod":1}
    user2json = {"uid":"test2@nextensio.net", "tenant":tenant, "name":"User2", "email":"test2@nextensio.net",
                 "services":["test2-nextensio-net"], "gateway":"gatewaytesta.nextensio.net", "pod":2}

    user1attrjson = {"uid":"test1@nextensio.net", "tenant":tenant, "category":"employee",
                     "type":"IC", "level":50, "dept":["ABU","BBU"], "team":["engineering"] }
    user2attrjson = {"uid":"test2@nextensio.net", "tenant":tenant, "category":"employee",
                     "type":"IC", "level":50, "dept":["ABU","BBU"], "team":["sales"] }
    
    bundle1json = {"bid":"default@nextensio.net", "tenant":tenant, "name":"Default Internet",
                   "services":["default-internet"], "gateway":"gatewaytestc.nextensio.net", "pod":3}
    bundle2json = {"bid":"v1.kismis@nextensio.net", "tenant":tenant, "name":"Kismis ONE",
                   "services":["v1.kismis.org"], "gateway":"gatewaytestc.nextensio.net", "pod":4}
    bundle3json = {"bid":"v2.kismis@nextensio.net", "tenant":tenant, "name":"Kismis TWO",
                   "services":["v2.kismis.org"], "gateway":"gatewaytestc.nextensio.net", "pod":5}

    bundle1attrjson = {"bid":"default@nextensio.net", "tenant":tenant, "dept":["ABU","BBU"],
                       "team":["engineering","sales"], "IC":1, "manager":1, "nonemployee":"allow"}
    bundle2attrjson = {"bid":"v1.kismis@nextensio.net", "tenant":tenant, "dept":["ABU","BBU"],
                       "team":["engineering","sales"], "IC":1, "manager":1, "nonemployee":"allow"}
    bundle3attrjson = {"bid":"v2.kismis@nextensio.net", "tenant":tenant, "dept":["ABU","BBU"],
                       "team":["engineering","sales"], "IC":1, "manager":1, "nonemployee":"allow"}
    
    host1attrjson = { "host": "kismis.org", "tenant":tenant,
                      "routeattrs": [
		      {"tag": "v2", "team": ["engineering"], "dept": ["ABU","BBU"],
		       "category": ["employee","nonemployee"], "type": ["IC","manager"], "IClvl": 1, "mlvl": 1
                      },
		      {"tag": "v1", "team": ["sales"], "dept": ["BBU","ABU"],
		        "category": ["employee"], "type": ["manager","IC"], "IClvl": 4, "mlvl": 4
		      } ]
		    }

    ok = create_user(url, user1json)
    while not ok:
        print('User creation failed, retrying ...')
        time.sleep(1)
        ok = create_user(url, user1json)

    ok = create_user_attr(url, user1attrjson)
    while not ok:
        print('UserAttr creation failed, retrying ...')
        time.sleep(1)
        ok = create_user_attr(url, user1attrjson)
    
    ok = create_user(url, user2json)
    while not ok:
        print('User creation failed, retrying ...')
        time.sleep(1)
        ok = create_user(url, user2json)
    
    ok = create_user_attr(url, user2attrjson)
    while not ok:
        print('UserAttr creation failed, retrying ...')
        time.sleep(1)
        ok = create_user_attr(url, user2attrjson)

    ok = create_bundle(url, bundle1json)
    while not ok:
        print('Bundle creation failed, retrying ...')
        time.sleep(1)
        ok = create_bundle(url, bundle1json)

    ok = create_bundle_attr(url, bundle1attrjson)
    while not ok:
        print('BundleAttr creation failed, retrying ...')
        time.sleep(1)
        ok = create_bundle_attr(url, bundle1attrjson)

    ok = create_bundle(url, bundle2json)
    while not ok:
        print('Bundle creation failed, retrying ...')
        time.sleep(1)
        ok = create_bundle(url, bundle2json)

    ok = create_bundle_attr(url, bundle2attrjson)
    while not ok:
        print('BundleAttr creation failed, retrying ...')
        time.sleep(1)
        ok = create_bundle_attr(url, bundle2attrjson)

    ok = create_bundle(url, bundle3json)
    while not ok:
        print('Bundle creation failed, retrying ...')
        time.sleep(1)
        ok = create_bundle(url, bundle3json)
        
    ok = create_bundle_attr(url, bundle3attrjson)
    while not ok:
        print('BundleAttr creation failed, retrying ...')
        time.sleep(1)
        ok = create_bundle_attr(url, bundle3attrjson)

    ok = create_host_attr(url, host1attrjson)
    while not ok:
        print('HostAttr creation failed, retrying ...')
        time.sleep(1)
        ok = create_host_attr(url, host1attrjson)
    
    route1json = {"tenant":tenant, "route":"test1@nextensio.net:kismis.org", "tag":"v1"}
    route2json = {"tenant":tenant, "route":"test2@nextensio.net:kismis.org", "tag":"v2"}
    
    ok = create_route(url, route1json)
    while not ok:
        print('Route creation failed, retrying ...')
        time.sleep(1)
        ok = create_route(url, route1json)
        
    ok = create_route(url, route2json)
    while not ok:
        print('Route creation failed, retrying ...')
        time.sleep(1)
        ok = create_route(url, route2json)

    with open('policy.AccessPolicy','r') as file:
        rego = file.read()
    ok = create_policy(url, tenant, 'AccessPolicy', rego)
    while not ok:
        print('Access Policy creation failed, retrying ...')
        time.sleep(1)
        ok = create_policy(url, tenant, 'AccessPolicy', rego)

    with open('policy.RoutePolicy','r') as file:
        rego = file.read()
    ok = create_policy(url, tenant, 'RoutePolicy', rego)
    while not ok:
        print('Route Policy creation failed, retrying ...')
        time.sleep(1)
        ok = create_policy(url, tenant, 'RoutePolicy', rego)

    ok = create_cert(url, cert)
    while not ok:
        print('CERT creation failed, retrying ...')
        time.sleep(1)
        ok = create_cert(url, cert)
