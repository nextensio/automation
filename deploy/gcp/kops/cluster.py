#!/usr/bin/env python3

import subprocess
import json
import os
import sys
import argparse
import time
import yaml

tmpdir = os.getcwd()
SCRIPTDIR = ""
DNSPREFIX = "k8s.local"

def check_call(command):
    return subprocess.check_call(command, stderr=subprocess.STDOUT, shell=True)

def check_output(command):
    return subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True).decode()

def yaml_modify():
    f = open("kops_orig.yaml", "r")
    docs = list(yaml.load_all(f, Loader=yaml.FullLoader))
    f.close()
    for doc in docs:
        for k, v in doc.items():
            if k == 'kind' and v == 'Cluster':
                doc['spec']['networking']['calico']['encapsulationMode'] = 'vxlan'
                break
    f = open("kops_mod.yaml", "w")
    yaml.dump_all(docs, f)
    f.close()

def install_addons():
    check_call("../tools/bin/kubectl apply -f ../tools/istio/samples/addons/grafana.yaml")
    sleep(10)
    check_call("../tools/bin/kubectl apply -f ../tools/istio/samples/addons/jaeger.yaml")
    sleep(10)
    check_call("../tools/bin/kubectl apply -f ../tools/istio/samples/addons/prometheus.yaml")
    sleep(10)
    check_call("../tools/bin/kubectl apply -f ../tools/istio/samples/addons/kiali.yaml")
    sleep(10)

def bootstrap_istio(cluster):
    check_call("../tools/istio/bin/istioctl install --set profile=default -y")
    check_call("../tools/bin/kubectl label namespace default istio-injection=enabled")
    install_addons()

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
    account='account@nextensio-308919.iam.gserviceaccount.com'
    name=data["cluster"] + '.' + DNSPREFIX
    cmd = "../tools/bin/kops create cluster --master-size %s --node-size %s --zones=%s %s \
          --node-count=%s --state %s --networking calico --dry-run -oyaml > kops_orig.yaml" % \
          (data["master-size"], data["node-size"], data["zone"], name, data["node-count"], buck)
    #print(cmd)
    check_call(cmd)
    yaml_modify()
    check_call("../tools/bin/kops replace -f kops_mod.yaml --state %s --name %s --force" % (buck, name))
    check_call("rm kops_orig.yaml")
    check_call("rm kops_mod.yaml")
    check_call("../tools/bin/kops update cluster --name %s --yes --admin --state %s" % (name, buck))
    print("please wait for 10mins ...")
    # sleep for 5 minutes for cluster formation
    time.sleep(8*60)
    # now check it
    check_call("../tools/bin/kops validate cluster --wait 5m --state %s" % (buck))
    bringup_nextensio(cluster)

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
