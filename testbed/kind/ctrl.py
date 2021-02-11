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

    ok = create_gateway(url, "gateway.testa.nextensio.net")
    while not ok:
        print('Gateway creation failed, retrying ...')
        time.sleep(1)
        ok = create_gateway(url, "gateway.testa.nextensio.net")

    ok = create_gateway(url, "gateway.testc.nextensio.net")
    while not ok:
        print('Gateway creation failed, retrying ...')
        time.sleep(1)
        ok = create_gateway(url, "gateway.testc.nextensio.net")

    ok = create_tenant(url, "Test", ["gateway.testa.nextensio.net","gateway.testc.nextensio.net"], 
                       ["kismis.org"], "registry.gitlab.com/nextensio/cluster/minion:latest", 5)
    while not ok:
        print('Tenant creation failed, retrying ...')
        time.sleep(1)
        ok = create_tenant(url, "Test", ["gateway.testa.nextensio.net","gateway.testc.nextensio.net"], 
                           ["kismis.org"], "registry.gitlab.com/nextensio/cluster/minion:latest", 5)

    ok, tenants = get_tenants(url)
    while not ok:
        print('Tenant fetch failed, retrying ...')
        time.sleep(1)
        ok, tenants = get_tenants(url)

    # The test setup is assumed to be created with just one tenant, if we need more we just need
    # to search for the right tenant name or something inside the returned list of tenants
    tenant = tenants[0]['_id']

    ok = create_user(url, 'test1@nextensio.net', tenant, 'Test User1', 'test1@nextensio.net', ['test1-nextensio-net'], 'gateway.testa.nextensio.net', 1)
    while not ok:
        print('User creation failed, retrying ...')
        time.sleep(1)
        ok = create_user(url, 'test1@nextensio.net', tenant, 'Test User1', 'test1@nextensio.net', ['test1-nextensio-net'], 'gateway.testa.nextensio.net', 1)

    ok = create_user_attr(url, 'test1@nextensio.net', tenant, 'employee', 'IC', 50, ['ABU,BBU'], ['engineering','sales'])
    while not ok:
        print('UserAttr creation failed, retrying ...')
        time.sleep(1)
        ok = create_user_attr(url, 'test1@nextensio.net', tenant, 'employee', 'IC', 50, ['ABU,BBU'], ['engineering','sales'])
    
    ok = create_user(url, 'test2@nextensio.net', tenant, 'Test User2', 'test2@nextensio.net', ['test2-nextensio-net'], 'gateway.testa.nextensio.net', 2)
    while not ok:
        print('User creation failed, retrying ...')
        time.sleep(1)
        ok = create_user(url, 'test2@nextensio.net', tenant, 'Test User2', 'test2@nextensio.net', ['test2-nextensio-net'], 'gateway.testa.nextensio.net', 2)
    
    ok = create_user_attr(url, 'test2@nextensio.net', tenant, 'employee', 'IC', 50, ['ABU,BBU'], ['engineering','sales'])
    while not ok:
        print('UserAttr creation failed, retrying ...')
        time.sleep(1)
        ok = create_user_attr(url, 'test2@nextensio.net', tenant, 'employee', 'IC', 50, ['ABU,BBU'], ['engineering','sales'])

    ok = create_bundle(url, 'default@nextensio.net', tenant, 'Default Internet Route', ['default-internet'], 'gateway.testc.nextensio.net', 3)
    while not ok:
        print('Bundle creation failed, retrying ...')
        time.sleep(1)
        ok = create_bundle(url, 'default@nextensio.net', tenant, 'Default Internet Route', ['default-internet'], 'gateway.testc.nextensio.net', 3)

    ok = create_bundle_attr(url, 'default@nextensio.net', tenant, ['ABU,BBU'], ['engineering','sales'], 1, 1, "allowed")
    while not ok:
        print('BundleAttr creation failed, retrying ...')
        time.sleep(1)
        ok = create_bundle_attr(url, 'default@nextensio.net', tenant, ['ABU,BBU'], ['engineering','sales'], 1, 1, "allowed")

    ok = create_bundle(url, 'v1.kismis@nextensio.net', tenant, 'Kismis Version ONE', ['v1.kismis.org'], 'gateway.testc.nextensio.net', 4)
    while not ok:
        print('Bundle creation failed, retrying ...')
        time.sleep(1)
        ok = create_bundle(url, 'v1.kismis@nextensio.net', tenant, 'Kismis Version ONE', ['v1.kismis.org'], 'gateway.testc.nextensio.net', 4)

    ok = create_bundle_attr(url, 'v1.kismis@nextensio.net', tenant, ['ABU,BBU'], ['engineering','sales'], 1, 1, "allowed")
    while not ok:
        print('BundleAttr creation failed, retrying ...')
        time.sleep(1)
        ok = create_bundle_attr(url, 'v1.kismis@nextensio.net', tenant, ['ABU,BBU'], ['engineering','sales'], 1, 1, "allowed")

    ok = create_bundle(url, 'v2.kismis@nextensio.net', tenant, 'Kismis Version ONE', ['v2.kismis.org'], 'gateway.testc.nextensio.net', 5)
    while not ok:
        print('Bundle creation failed, retrying ...')
        time.sleep(1)
        ok = create_bundle(url, 'v2.kismis@nextensio.net', tenant, 'Kismis Version ONE', ['v2.kismis.org'], 'gateway.testc.nextensio.net', 5)
        
    ok = create_bundle_attr(url, 'v2.kismis@nextensio.net', tenant, ['ABU,BBU'], ['engineering','sales'], 1, 1, "allowed")
    while not ok:
        print('BundleAttr creation failed, retrying ...')
        time.sleep(1)
        ok = create_bundle_attr(url, 'v2.kismis@nextensio.net', tenant, ['ABU,BBU'], ['engineering','sales'], 1, 1, "allowed")

    ok = create_route(url, tenant, 'test1@nextensio.net', 'kismis.org', 'v1')
    while not ok:
        print('Route creation failed, retrying ...')
        time.sleep(1)
        ok = create_route(url, tenant, 'test1@nextensio.net', 'kismis.org', 'v1')
        
    ok = create_route(url, tenant, 'test2@nextensio.net', 'kismis.org', 'v2')
    while not ok:
        print('Route creation failed, retrying ...')
        time.sleep(1)
        ok = create_route(url, tenant, 'test2@nextensio.net', 'kismis.org', 'v2')

    with open('policy.AccessPolicy','r') as file:
        rego = file.read()
    ok = create_policy(url, tenant, 'AccessPolicy', rego)
    while not ok:
        print('Policy creation failed, retrying ...')
        time.sleep(1)
        ok = create_policy(url, tenant, 'AccessPolicy', rego)

    ok = create_cert(url, cert)
    while not ok:
        print('CERT creation failed, retrying ...')
        time.sleep(1)
        ok = create_cert(url, cert)
