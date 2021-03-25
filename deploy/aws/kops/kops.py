#!/usr/bin/env python3

import json
import subprocess

if __name__ == "__main__":
    json_file = open("./spec.json") 
    data = json.load(json_file)
    cmd = "kops create cluster --master-size %s --node-size %s --zones=%s %s.kops.nextensio.net \
          --network-cidr=%s --state s3://clusters.kops.nextensio.net --topology private --networking calico --target=terraform" % \
          (data["master-size"], data["node-size"], data["zone"], data["cluster"], data["cidr"])
    subprocess.check_call(cmd, stderr=subprocess.STDOUT, shell=True)
