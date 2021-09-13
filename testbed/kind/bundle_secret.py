#!/usr/bin/env python3

import sys
import requests
import time
import subprocess
from nextensio_controller import *

url = "https://" + sys.argv[1] + ":8080"

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
        print('Cannot get access token for bundle %s, exiting' % sys.argv[2])
        exit(1)

    secret = get_bundle_key(url, "nextensio", sys.argv[2], token).strip()
    if secret == "":
        print('Cannot get secret for bundle %s' % sys.argv[2])
        exit(1)

    print(secret)
