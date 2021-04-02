#!/usr/bin/env python3

import subprocess
import json
import os
import sys
import argparse
import time

tmpdir = os.getcwd()
SCRIPTDIR = ""
DNSPREFIX = "k8s.local"

def check_call(command):
    return subprocess.check_call(command, stderr=subprocess.STDOUT, shell=True)

def check_output(command):
    return subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True).decode()

def bootstrap_istio(cluster):
    check_call("../tools/istio/bin/istioctl install --set profile=default -y")
    check_call("../tools/bin/kubectl label namespace default istio-injection=enabled")

def bringup_nextensio(cluster):
    print("Bringing up istio...")
    bootstrap_istio(cluster)

def create_cluster(cluster):
    project=check_output("../tools/google-cloud-sdk/bin/gcloud config get-value project").strip()
    print(project)
    buck=check_output("../tools/google-cloud-sdk/bin/gsutil ls").strip()

    if buck == "gs://kubernetes-clusters-" + project + "/":
        print("bucket exist")
    else:
        print("creating bucket")
        check_call("../tools/google-cloud-sdk/bin/gsutil mb gs://kubernetes-clusters-" + project + "/")

    spec = SCRIPTDIR + '/%s/spec.json' % cluster
    with open(spec) as json_file:
        data = json.load(json_file)
    cmd = "../tools/bin/kops create cluster --master-size %s --node-size %s --zones=%s %s.%s \
          --node-count=%s --state %s --networking weave" % \
          (data["master-size"], data["node-size"], data["zone"], data["cluster"], DNSPREFIX, data["node-count"], buck)
    print(cmd)
    check_call(cmd)
    cmd = "../tools/bin/kops update cluster --name %s.%s --yes --admin --state %s" % \
          (data["cluster"], DNSPREFIX, buck)
    print(cmd)
    check_call(cmd)
    # sleep for 5 minutes for cluster formation
    time.sleep(5*60)
    # now check it
    check_call("../tools/bin/kop validate cluster --wait 5m --state gs://kubernetes-clusters-" + project + "/")

def delete_cluster(cluster):
    project=check_output("../tools/google-cloud-sdk/bin/gcloud config get-value project").strip()
    buck=check_output("../tools/google-cloud-sdk/bin/gsutil ls").strip()
    spec = SCRIPTDIR + '/%s/spec.json' % cluster
    with open(spec) as json_file:
        data = json.load(json_file)
    cmd = "kops delete cluster --name=%s.%s --state %s --yes" % (data["cluster"], DNSPREFIX, buck)
    print(cmd)
    check_call(cmd)

def parser_init():
    parser = argparse.ArgumentParser(
        description='Nextensio cluster management')
    parser.add_argument('-create', nargs=1, action='store',
                        help='name of cluster to create')
    parser.add_argument('-delete', nargs=1, action='store',
                        help='name of cluster to delete')
    args = parser.parse_args()
    return args

if __name__ == "__main__":
    SCRIPTDIR = os.path.dirname(sys.argv[0])
    args = parser_init()

    if args.create:
        create_cluster(args.create[0])
        sys.exit(0)

    if args.delete:
        delete_cluster(args.delete[0])
        sys.exit(0)
