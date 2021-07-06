#!/usr/bin/env python3

import subprocess
import time
import json
import re
import argparse
import os
import sys
from shutil import copyfile
import socket

tmpdir = os.getcwd()
kubectl = "%s/kubectl" % tmpdir
istioctl = "%s/istioctl" % tmpdir
helm = "%s/linux-amd64/helm" % tmpdir
scriptdir = ""
dockercfg = ""
rootca = ""
route53_zone = None

outputState = {}


def check_call(command):
    return subprocess.check_call(command, stderr=subprocess.STDOUT, shell=True)


def check_output(command):
    return subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True).decode()


def kube_scriptdir_apply(cluster, file):
    fname = scriptdir + "/" + cluster + "/" + file
    kubeconfig = "KUBECONFIG=" + tmpdir + "/kubeconfig " + kubectl
    check_output(kubeconfig + " apply -f " + fname)


def kube_tmpdir_apply(cluster, file):
    fname = tmpdir + "/" + file
    kubeconfig = "KUBECONFIG=" + tmpdir + "/kubeconfig " + kubectl
    check_output(kubeconfig + " apply -f " + fname)


def kube_tmpdir_replace(cluster, file):
    fname = tmpdir + "/" + file
    kubeconfig = "KUBECONFIG=" + tmpdir + "/kubeconfig " + kubectl
    check_output(kubeconfig + " replace -n kube-system -f " + fname)


def kube_get_svc_ip(service, namespace):
    kubeconfig = "KUBECONFIG=" + tmpdir + "/kubeconfig " + kubectl 
    return check_output(kubeconfig + " get service " + service + " -n " + namespace + " -o jsonpath='{.spec.clusterIP}'")


def docker_secret(cfg):
    kubeconfig = "KUBECONFIG=" + tmpdir + "/kubeconfig " + kubectl
    check_output(
        "%s create secret generic regcred --from-file=.dockerconfigjson=%s --type=kubernetes.io/dockerconfigjson" % (kubeconfig, cfg))

def tls_secret(name, key, crt):
    kubeconfig = "KUBECONFIG=" + tmpdir + "/kubeconfig " + kubectl
    try:
        check_output(
            "%s create secret tls %s --key=\"%s\" --cert=\"%s\"" % (kubeconfig, name, key, crt))
    except subprocess.CalledProcessError as e:
        print(e.output)
        if "already exists" in e.output.decode():
            pass

def kubectl_permissive_rbac():
    kubeconfig = "KUBECONFIG=" + tmpdir + "/kubeconfig " + kubectl
    check_output("%s create clusterrolebinding permissive-binding --clusterrole=cluster-admin --user=admin --user=kubelet --group=system:serviceaccounts" % kubeconfig)

# The gw-credential is used in the clustermgr files/yaml/ingress_gw.yaml
def kubectl_create_gw_cred():
    kubeconfig = "KUBECONFIG=" + tmpdir + "/kubeconfig " + kubectl
    check_output(
        "%s create -n istio-system secret tls gw-credential --key=%s/nextensio.key --cert=%s/nextensio.crt" % (kubeconfig, rootca, rootca))

def kubectl_create_namespace(namespace):
    kubeconfig = "KUBECONFIG=" + tmpdir + "/kubeconfig " + kubectl
    check_output("%s create namespace %s" % (kubeconfig, namespace))


def helm_apply(cmd):
    helmconfig = "KUBECONFIG=" + tmpdir + "/kubeconfig " + helm
    check_call(helmconfig + " " + cmd)

def download_utils():
    try:
        check_call(
            "curl -fsL https://storage.googleapis.com/kubernetes-release/release/v1.21.2/bin/linux/amd64/kubectl -o %s/kubectl" % tmpdir)
        check_call("chmod +x %s/kubectl" % tmpdir)
        check_call(
            "curl -fsL https://github.com/istio/istio/releases/download/1.10.2/istioctl-1.10.2-linux-amd64.tar.gz -o %s/istioctl.tgz" % tmpdir)
        check_call(
            "tar -xvzf %s/istioctl.tgz -C %s/" % (tmpdir, tmpdir))
        check_call("chmod +x %s/istioctl" % tmpdir)
        check_call("rm %s/istioctl.tgz" % tmpdir)
        check_call(
            "curl -fsL https://get.helm.sh/helm-v3.4.0-linux-amd64.tar.gz -o %s/helm.tgz" % tmpdir)
        check_call(
            "tar -zxvf %s/helm.tgz -C %s/" % (tmpdir, tmpdir))
        check_call("chmod +x %s/linux-amd64/helm" % tmpdir)
        check_call("rm %s/helm.tgz" % tmpdir)
    except subprocess.CalledProcessError as e:
        pass
        return False

    try:
        docker_secret(dockercfg)
    except subprocess.CalledProcessError as e:
        pass
        print(e.output)
        if not "AlreadyExists" in str(e.output):
            return False

    return True


def terraform_config(cluster):
    copyfile(scriptdir + "/" + cluster + "/spec.tf", tmpdir + "/spec.tf")
    f = open(tmpdir + "/spec.tf", "r+")
    spec = f.read()
    # Copy the spec to the tmpdir, modify the source to point back to the original source dir
    spec = re.sub(r'\n\s*source\s*=\s*\".+\"\s*\n',
                  "\n  source = \"%s\"\n" % (scriptdir+"/common"), spec)
    # Generate a key-pair for bastion access
    check_call("rm -rf %s/bastion*" % tmpdir)
    check_call(
        """ssh-keygen -t rsa  -C "support@nextensio.net" -q -N "" -f %s/bastion""" % tmpdir)
    with open("%s/bastion.pub" % tmpdir) as b:
        pubkey = b.read().strip()
    spec = re.sub(r'\n\s*ec2-key-public-key\s*=\s*\".+\"\s*\n',
                  "\n  ec2-key-public-key = \"%s\"\n" % pubkey, spec)

    f.seek(0)
    f.write(spec)
    f.truncate()
    f.close()


def terraform_cluster(cluster):
    terraform_config(cluster)
    try:
        check_call("terraform init %s/" % tmpdir)
        check_call("terraform apply %s/" % tmpdir)
        check_call(
            "terraform output -state=%s/terraform.tfstate kubeconfig > %s/kubeconfig" % (tmpdir, tmpdir))
        check_call("chmod 600 %s/kubeconfig" % tmpdir)
    except subprocess.CalledProcessError as e:
        pass
        print(e.output)
        return False

    return True


def controller_ux_keys():
    tls_secret("ux-cert", "%s/nextensio.key" % rootca, "%s/nextensio.crt" % rootca)

def controller_server_keys():
    tls_secret("server-cert", "%s/nextensio.key" % rootca, "%s/nextensio.crt" % rootca)

def bootstrap_controller():
    # Setup the TLS cert and keys
    controller_ux_keys()
    controller_server_keys()

    try:
        kube_scriptdir_apply('controller', 'controller.yaml')
        return True
    except subprocess.CalledProcessError as e:
        pass
        print(e.output)
        return False

    return True


def aws_cli_route53(fname):
    try:
        out = check_output(
            "aws route53 change-resource-record-sets --hosted-zone-id %s --change-batch file://%s" % (route53_zone, fname))
        j = json.loads(out)
        if j['ChangeInfo']['Status'] != 'PENDING' and j['ChangeInfo']['Status'] != 'INSYNC':
            return False
    except subprocess.CalledProcessError as e:
        pass
        print(e.output)
        return False
    return True


def aws_pgm_route53(action, domain, cname):
    json = """{
       "Comment": "CREATE/DELETE/UPSERT a record ",
       "Changes": [{
       "Action": "%s",
                   "ResourceRecordSet": {
                               "Name": "%s",
                               "Type": "CNAME",
                               "TTL": 300,
                            "ResourceRecords": [{ "Value": "%s"}]
    }}]}""" % (action, domain, cname)
    fname = "%s/route53-%s" % (tmpdir, domain)
    file = open(fname, "w")
    file.write(json)
    file.close()
    return aws_cli_route53(fname)


def aws_del_loadbalancer(region, name):
    try:
        out = check_output(
            "aws elb delete-load-balancer --region %s --load-balancer-name %s" % (region, name))
        return True
    except subprocess.CalledProcessError as e:
        pass
        print(e.output)
        return False


def aws_get_loadbalancer_tags(region, name):
    try:
        out = check_output(
            "aws elb describe-tags --no-paginate --region %s  --load-balancer-name %s" % (region, name))
        o = json.loads(out)
        return o['TagDescriptions'][0]['Tags']
    except subprocess.CalledProcessError as e:
        pass
        print(e.output)
        return []


def aws_get_loadbalancers(region):
    try:
        out = check_output(
            "aws elb describe-load-balancers --no-paginate --region %s" % region)
        o = json.loads(out)
        return o['LoadBalancerDescriptions']
    except subprocess.CalledProcessError as e:
        pass
        print(e.output)
        return []


def aws_get_cluster_loadbalancers(cluster, region):
    clusterLoads = []
    loads = aws_get_loadbalancers(region)
    for l in loads:
        tags = aws_get_loadbalancer_tags(region, l['LoadBalancerName'])
        match = False
        for t in tags:
            if t['Key'] == 'kubernetes.io/cluster/%s' % cluster:
                match = True
        if match:
            for t in tags:
                if t['Key'] == 'kubernetes.io/service-name':
                    clusterLoads.append(
                        {'service': t['Value'], 'domain': l['DNSName'], 'loadbalancer': l['LoadBalancerName']})
    return clusterLoads


def aws_del_loadbalancerv2(region, name):
    try:
        out = check_output(
            "aws elbv2 delete-load-balancer --region %s --load-balancer-arn %s" % (region, name))
        return True
    except subprocess.CalledProcessError as e:
        pass
        print(e.output)
        return False


def aws_get_loadbalancerv2_tags(region, name):
    try:
        out = check_output(
            "aws elbv2 describe-tags --no-paginate --region %s  --resource-arns %s" % (region, name))
        o = json.loads(out)
        return o['TagDescriptions'][0]['Tags']
    except subprocess.CalledProcessError as e:
        pass
        print(e.output)
        return []


def aws_get_loadbalancersv2(region):
    try:
        out = check_output(
            "aws elbv2 describe-load-balancers --no-paginate --region %s" % region)
        o = json.loads(out)
        return o['LoadBalancers']
    except subprocess.CalledProcessError as e:
        pass
        print(e.output)
        return []


def aws_get_cluster_loadbalancersv2(cluster, region):
    clusterLoads = []
    loads = aws_get_loadbalancersv2(region)
    for l in loads:
        tags = aws_get_loadbalancerv2_tags(region, l['LoadBalancerArn'])
        match = False
        for t in tags:
            if t['Key'] == 'kubernetes.io/cluster/%s' % cluster:
                match = True
        if match:
            for t in tags:
                if t['Key'] == 'kubernetes.io/service-name':
                    clusterLoads.append(
                        {'service': t['Value'], 'domain': l['DNSName'], 'loadbalancer': l['LoadBalancerArn'], 'vpc': l['VpcId']})
    return clusterLoads


def aws_loadbalancerv2_enable_cross_zone(region, loadbalancer):
    cmd = "aws elbv2 modify-load-balancer-attributes --no-paginate --load-balancer-arn %s --attributes Key=load_balancing.cross_zone.enabled,Value=true --region %s" % (
        loadbalancer, region)
    check_output(cmd)


def aws_check_target_attributes(target, cluster, region):
    out = check_output(
        "aws elbv2 describe-tags --resource-arn %s --region %s --no-paginate" % (target, region))
    o = json.loads(out)
    tags = o['TagDescriptions'][0]['Tags']
    for t in tags:
        if t['Key'] == "kubernetes.io/cluster/%s" % cluster:
            return True
    return False


def aws_get_target_groups(cluster, region, vpc):
    ret = []
    try:
        out = check_output(
            "aws elbv2 describe-target-groups --region %s --no-paginate" % region)
        o = json.loads(out)
        tgts = o['TargetGroups']
        for t in tgts:
            if aws_check_target_attributes(t['TargetGroupArn'], cluster, region) == True and t['VpcId'] == vpc:
                ret.append(t)
        return ret
    except subprocess.CalledProcessError as e:
        pass
        print(e.output)
        return []


def aws_del_target_group(region, name):
    try:
        out = check_output(
            "aws elbv2 delete-target-group --region %s --target-group-arn %s" % (region, name))
        return True
    except subprocess.CalledProcessError as e:
        pass
        print(e.output)
        return False


def aws_get_asg(cluster, region):
    asgs = []
    try:
        out = check_output(
            "aws autoscaling describe-auto-scaling-groups --region %s" % region)
        o = json.loads(out)['AutoScalingGroups']
        for group in o:
            tags = group['Tags']
            for t in tags:
                if t['Key'] == 'eks:cluster-name' and t['Value'] == cluster:
                    asgs.append(group)
    except subprocess.CalledProcessError as e:
        pass
        print(e.output)
        return []

    return asgs


def attach_asg_target(region, asgname, tgt):
    check_output(
        "aws autoscaling attach-load-balancer-target-groups --region %s --auto-scaling-group-name %s --target-group-arns %s" % (region, asgname, tgt))


def create_target_group(cluster, region, name, proto, port, vpc, healthport):
    try:
        out = check_output("""aws elbv2 create-target-group --name %s \
               --protocol %s --port %s --vpc-id %s \
               --health-check-protocol TCP --health-check-port %s --target-type instance \
                --tags Key="kubernetes.io/cluster/%s",Value=owned --region %s""" % (name, proto, port, vpc, healthport, cluster, region))
        o = json.loads(out)
        return o['TargetGroups'][0]
    except Exception as e:
        print("Exception %s" % e)
        pass
        return None


def create_listener(region, loadbalancer, target, protocol, port):
    cmd = "aws elbv2 create-listener --region %s --load-balancer-arn %s --protocol %s --port %s --default-actions Type=forward,TargetGroupArn=%s" % (
        region, loadbalancer, protocol, port, target)
    check_output(cmd)


def add_consul_listeners(region, loadbalancer, consul_svr, consul_serf):
    create_listener(region, loadbalancer, consul_svr, "TCP", 8300)
    create_listener(region, loadbalancer, consul_serf, "TCP_UDP", 8302)


def get_cluster_security_group(cluster, region):
    try:
        out = check_output(
            "aws eks describe-cluster --name %s --region %s" % (cluster, region))
        o = json.loads(out)
        cluster = o['cluster']
        return cluster['resourcesVpcConfig']['clusterSecurityGroupId']
    except:
        pass
        return None


def add_consul_security_rules(region, sgid):
    check_output(
        "aws ec2 authorize-security-group-ingress --region %s --group-id %s --protocol tcp --port 8300 --cidr 0.0.0.0/0" % (region, sgid))
    check_output(
        "aws ec2 authorize-security-group-ingress --region %s --group-id %s --protocol tcp --port 8302 --cidr 0.0.0.0/0" % (region, sgid))
    check_output(
        "aws ec2 authorize-security-group-ingress --region %s --group-id %s --protocol udp --port 8302 --cidr 0.0.0.0/0" % (region, sgid))


def get_cluster_region(cluster):
    spec = tmpdir + '/spec.tf'
    file = open(spec)
    data = file.read()
    file.close()
    m = re.search(r'\n\s*aws-region\s*=\s*\"(.+)\"\s*\n', data)
    if not m:
        return None
    region = m[1]

    return region


def controller_route53():
    region = get_cluster_region('controller')
    if region == None:
        return False
    loads = aws_get_cluster_loadbalancers('controller', region)
    # One service for controller, one for ux
    if len(loads) != 2:
        return False
    for l in loads:
        if l['service'] == 'default/nextensio-ux':
            aws_pgm_route53(
                "UPSERT", "controller.nextensio.net", l['domain'])
        if l['service'] == 'default/nextensio-controller':
            aws_pgm_route53(
                "UPSERT", "server.nextensio.net", l['domain'])

    return True


def create_all_controller():
    while bootstrap_controller() != True:
        print("Bootstrap controller failed, retrying")
        time.sleep(1)
    print("Controller bootstrapped")

    while controller_route53() != True:
        print("Controller Route53 mappings failed, retrying")
        time.sleep(1)
    print("Controller Route53 mapping done")


def delete_all_controller():
    region = get_cluster_region("controller")
    if region == None:
        return False
    loads = aws_get_cluster_loadbalancers("controller", region)
    for l in loads:
        if aws_del_loadbalancer(region, l['loadbalancer']) == False:
            return False

    return True


def gateway_route53(cluster):
    region = get_cluster_region(cluster)
    if region == None:
        return False
    loads = aws_get_cluster_loadbalancersv2(cluster, region)
    if len(loads) != 1:
        return False
    aws_pgm_route53(
        "UPSERT", "%s.nextensio.net" % cluster, loads[0]['domain'])

    return True


# TODO: Consul has a problem that it needs to advertise its own WAN IP address
# to remote consuls, for the remote consul query lookup. And amazon loadbalancers
# rightfully so, does not want people to use the IP and rather promote just their
# domain name. But consul doesnt accept a domain name, so we are left with no option
# but to pick whatever IP is associated with the loadbalancer domain at the moment.
# If the amazon loadbalancer fails and switches to another IP, then consul is hosed!
# We need to find some solution to that


def create_gateway_mgr(cluster):
    region = get_cluster_region(cluster)
    if region == None:
        return False
    loads = aws_get_cluster_loadbalancersv2(cluster, region)
    if len(loads) != 1:
        return False
    domain = loads[0]['domain']
    try:
        loadIP = socket.gethostbyname(domain)
        outputState['consulIP'] = loadIP
    except:
        print("Unable to find IP for AWS loadbalancer %s, dns propagation takes time, will retry" %
              loads[0]['domain'])
        pass
        return False
    copyfile(scriptdir + "/../mel.yaml", tmpdir + "/mel.yaml")
    f = open(tmpdir + "/mel.yaml", "r+")
    mel = f.read()
    mel = re.sub(r'REPLACE_CLUSTER', cluster, mel)
    mel = re.sub(r'REPLACE_CONSUL_WAN_IP', loadIP, mel)
    mel = re.sub(r'REPLACE_CONSUL_STORAGE', "default", mel)
    f.seek(0)
    f.write(mel)
    f.truncate()
    f.close()

    try:
        kube_tmpdir_apply(cluster, "mel.yaml")
    except:
        pass
        return False

    return True


def create_consul_dns(cluster):
    try:
        consul_dns = kube_get_svc_ip(cluster + "-consul-dns", "consul-system")
    except subprocess.CalledProcessError as e:
        pass
        print(e.output)
        return False

    copyfile(scriptdir + "/../coredns.yaml", tmpdir + "/coredns.yaml")
    f = open(tmpdir + "/coredns.yaml", "r+")
    dns = f.read()
    dns = re.sub(r'REPLACE_CONSUL_DNS', consul_dns, dns)
    f.seek(0)
    f.write(dns)
    f.truncate()
    f.close()

    try:
        kube_tmpdir_replace(cluster, "coredns.yaml")
    except subprocess.CalledProcessError as e:
        pass
        print(e.output)
        return False

    return True


def configure_gateway_loadbalancers(cluster):
    region = get_cluster_region(cluster)
    if region == None:
        return False

    print("Getting list of gateway loadbalancers")
    loads = aws_get_cluster_loadbalancersv2(cluster, region)
    if len(loads) != 1:
        return False

    print("Enabling cross zone loadbalancing")
    try:
        aws_loadbalancerv2_enable_cross_zone(region, loads[0]['loadbalancer'])
    except subprocess.CalledProcessError as e:
        pass
        print(e.output)
        return False

    print("Creating consul target groups")
    vpc = loads[0]['vpc']
    consul_svr = create_target_group(cluster, region,
                                     "consul-server", "TCP", 8300, vpc, 8300)
    if consul_svr == None:
        return False
    consul_serf = create_target_group(cluster, region,
                                      "consul-serf", "TCP_UDP", 8302, vpc, 8300)
    if consul_serf == None:
        return False

    print("Getting cluster autoscaling group")
    asg = aws_get_asg(cluster, region)
    if len(asg) != 1:
        return False

    print("Adding all target groups to cluster autoscale group")
    tgts = aws_get_target_groups(cluster, region, vpc)
    # Five groups for istio and two for consul
    if len(tgts) != 7:
        return False
    for t in tgts:
        try:
            attach_asg_target(
                region, asg[0]['AutoScalingGroupName'], t['TargetGroupArn'])
        except subprocess.CalledProcessError as e:
            pass
            print(e.output)
            return False

    print("Adding consul ports to loadbalancer listeners")
    add_consul_listeners(
        region, loads[0]['loadbalancer'], consul_svr['TargetGroupArn'], consul_serf['TargetGroupArn'])

    print("Adding consul ports to the cluster security group")
    sg = get_cluster_security_group(cluster, region)
    if sg == None:
        return False
    try:
        add_consul_security_rules(region, sg)
    except subprocess.CalledProcessError as e:
        pass
        print(e.output)
        if not "already exists" in e.output.decode():
            return False

    return True


def bootstrap_gateway(cluster):
    try:
        docker_secret(dockercfg)
    except subprocess.CalledProcessError as e:
        pass
        print(e.output)
        if not "AlreadyExists" in str(e.output):
            return False
    try:
        # TODO: We need to remove this once clustermgr moves to kube APIs away from kubectl
        kubectl_permissive_rbac()
    except subprocess.CalledProcessError as e:
        pass
        print(e.output)
        if not "already exists" in str(e.output):
            return False

    istiocfg = scriptdir + "/../istio.yaml"
    kubeconfig = tmpdir + "/kubeconfig"
    check_call("%s manifest apply --kubeconfig %s -f %s" %
               (istioctl, kubeconfig, istiocfg))

    try:
        kubectl_create_gw_cred()
    except subprocess.CalledProcessError as e:
        pass
        print(e.output)
        if not 'already exists' in e.output.decode():
            return False

    return True


def create_gateway_all(cluster):
    while bootstrap_gateway(cluster) != True:
        print("Bootstrap gateway failed, retrying")
        time.sleep(1)
    print("Gateway bootstrapped")

    while configure_gateway_loadbalancers(cluster) != True:
        print("Configure gateway loadbalancers failed, retrying")
        time.sleep(1)
    print("Gateway loadbalancers configured")

    while create_gateway_mgr(cluster) != True:
        print("Creating gateway manager failed, retrying")
        time.sleep(1)
    print("Gateway manager created")

    while gateway_route53(cluster) != True:
        print("Route53 gateway domain mapping failed, retrying")
        time.sleep(1)
    print("Route53 gateway domain mapping succeeded")

    while create_consul_dns(cluster) != True:
        print("Consul DNS mapping failed, retrying")
        time.sleep(1)
    print("Consul DNS mapping completed")


def get_route53_zone():
    try:
        out = check_output("aws route53 list-hosted-zones")
        o = json.loads(out)
        for z in o['HostedZones']:
            if z["Name"] == "nextensio.net.":
                id = z["Id"]
                return id.strip("/hostedzone/")
        return None
    except subprocess.CalledProcessError as e:
        pass
        print(e.output)
        return None


def consul_join(gws):
    if len(gws) < 2:
        return True
    # Join just needs to be done from one place and then consul
    # automatically discovers everyone else
    gw = gws[0]
    config = "./" + gw + "/kubeconfig"
    for g in gws[1:]:
        gcfg = "./" + g + "/cluster_" + g + "_state.json"
        f = open(gcfg)
        gdata = f.read()
        gjson = json.loads(gdata)

        gwkube = "KUBECONFIG=" "./" + gw + "/kubeconfig ./" + gw + "/kubectl "
        pod = gw + "-consul-server-0"
        try:
            check_output(gwkube + "exec -it " + pod +
                         " -n consul-system -- consul join -wan " + gjson['consulIP'])
        except subprocess.CalledProcessError as e:
            pass
            print(e.output)
            return False

    return True


consul_query_json = {
    "Name": "",
    "Template": {
        "Type": "name_prefix_match"
    },
    "Service": {
        "Service": "${name.full}",
        "Failover": {
            "NearestN": 3,
            "Datacenters": []
        }
    }
}


def consul_query(gws):
    if len(gws) < 2:
        return True
    for gw in gws:
        consul_query_json['Service']['Failover']['Datacenters'].append(gw)
    f = open("./consul_query.json", "w")
    json.dump(consul_query_json, f)
    f.close()
    for gw in gws:
        try:
            gwkube = "KUBECONFIG=" "./" + gw + "/kubeconfig ./" + gw + "/kubectl "
            pod = gw + "-consul-server-0"
            check_output(
                gwkube + "cp ./consul_query.json consul-system/" + pod + ":/tmp/query.json")
            check_output(gwkube + "exec -it " + pod +
                         " -n consul-system -- curl -k --request POST --data @/tmp/query.json http://127.0.0.1:8500/v1/query")
        except subprocess.CalledProcessError as e:
            pass
            print(e.output)
            return False

    return True


def consul_all(gws):
    while consul_join(gws) != True:
        print("Consul join failed, retrying")
        time.sleep(1)
    while consul_query(gws) != True:
        print("Consul query failed, retrying")
        time.sleep(1)


def delete_all_gateway(cluster):
    region = get_cluster_region(cluster)
    if region == None:
        return False
    loads = aws_get_cluster_loadbalancersv2(cluster, region)
    for l in loads:
        if aws_del_loadbalancerv2(region, l['loadbalancer']) == False:
            return False
    vpc = loads[0]['vpc']
    targets = aws_get_target_groups(cluster, region, vpc)
    for t in targets:
        if aws_del_target_group(region, t['TargetGroupArn']) == False:
            return False
    return True


def create_cluster(cluster):
    while download_utils() != True:
        print("Download utils failed, retrying")
        time.sleep(1)
    print("Downloaded utilities")

    if cluster == "controller":
        create_all_controller()
    else:
        create_gateway_all(cluster)


def delete_cluster(cluster):
    if cluster == "controller":
        delete_all_controller()
    else:
        delete_all_gateway(cluster)


def parser_init():
    parser = argparse.ArgumentParser(
        description='Nextensio cluster management')
    parser.add_argument('-create', nargs=1, action='store',
                        help='name of cluster to create')
    parser.add_argument('-delete', nargs=1, action='store',
                        help='name of cluster to delete')
    parser.add_argument('-docker', nargs=1, action='store',
                        help='docker config file')
    parser.add_argument('-terraform', nargs=1, action='store',
                        help='name of cluster to terraform')
    parser.add_argument('-consul', nargs='*', action='store',
                        help='name of clusters to join in consul')
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    scriptdir = os.path.dirname(sys.argv[0])
    route53_zone = get_route53_zone()
    if route53_zone == None:
        print("Unable to find route53 zone")
        sys.exit(0)

    args = parser_init()

    if args.terraform:
        terraform_cluster(args.terraform[0])
        sys.exit(0)

    if args.create:
        if not args.docker:
            print("Please provide path to docker config file with -docker <path> option")
            sys.exit(1)
        dockercfg = args.docker[0]
        rootca = scriptdir + "/../../letsencrypt/"
        create_cluster(args.create[0])
        with open('cluster_%s_state.json' % args.create[0], 'w') as f:
            json.dump(outputState, f)
        print("Cluster creation succesful")
        sys.exit(0)

    if args.delete:
        delete_cluster(args.delete[0])
        sys.exit(0)

    if args.consul:
        consul_all(args.consul)
        sys.exit(0)
