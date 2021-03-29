#!/usr/bin/env python3

import subprocess
import json
import os

tmpdir = os.getcwd()
scriptdir = "."

def check_call(command):
    return subprocess.check_call(command, stderr=subprocess.STDOUT, shell=True)

def check_output(command):
    return subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True).decode()

project=check_output("../tools/google-cloud-sdk/bin/gcloud config get-value project").strip()
print(project)

buck=check_output("../tools/google-cloud-sdk/bin/gsutil ls").strip()

if buck == "gs://kubernetes-clusters-" + project + "/":
    print("bucket exist")
else:
    print("creating bucket")
    check_call("../tools/google-cloud-sdk/bin/gsutil mb gs://kubernetes-clusters-" + project + "/")

#spec = scriptdir + '/%s/spec.json' % cluster
spec = scriptdir + '/%s/spec.json' % 'gatewayuswest1'
with open(spec) as json_file:
    data = json.load(json_file)
cmd = "../tools/bin/kops create cluster --master-size %s --node-size %s --zones=%s %s.kops.kismis.org \
      --state %s --networking weave" % \
      (data["master-size"], data["node-size"], data["zone"], data["cluster"], buck)
print(cmd)
check_call(cmd)
