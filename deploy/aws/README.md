# Terraform

The terraform files here are copied from https://github.com/WesleyCharlesBlake/terraform-aws-eks    
Another more detailed set of terraform libs for eks is https://github.com/terraform-aws-modules/terraform-aws-eks
We dont need a lot of those things today, but we can refer to / borrow from that as and when needed

## Pre Requisites

* Install terraform

* Install the AWS cli v2 (version2)

* Run "aws configure" so that the CLI can access your aws account

* docker login registry.gitlab.com so that you can access nextensio images

## What is created by terraform

What is created is the below

1. The eks master node(s) which are completely under aws control - we can just specify the kubernetes 
   version that aws supports (1.18 at the moment), and thats pretty much the only control we have

2. A 'node group' of worker nodes. The node group is basically an automated way of spinning up EC2
   instances and adding them as part of the eks cluster. We can specify the minimum and maximum 
   number of nodes in a node group, we can specify when/how to scale up/down the cluster etc.. The
   node group behind the scenes creates an "auto scaling group" in AWS.

3. One or more 'availability zones' (controlled via spec.tf) across which the nodes are spread out,
   this is useful for disaster control, if one zone is totally kaput, we still have some other zone
   to rely on. But this might not be what we want, this needs  some discussion - see the long 
   explanation on loadbalancers and consul etc.. in the section below for how cross zone loadbalancing
   works

4. The Master node(s) are exposed to public internet, outside-to-inside and inside-to-outside. 
   But the worker nodes are not exposed to public internet, inside-to-outside internet of course works,
   but outside-to-inside does not work. The only entities that can access the worker nodes from ouside 
   are the master itself and the workers accessing each other. Note that even the master need not be
   on public internet, we can completely make it a private cluster with a bastion access (we have a 
   bastion already, read below) except that the initial cluster configs/bringups etc.. will all have
   to be via bastion, which is how production systems are. So its a TODO to disable public access 
   for the master(s) once we are all happy and satisfied with this infrastructure and we get to a 
   point where its stable and usable.

5. For reasons explained above, we have a public subnet and private subnet, so the master node(s)
   will be part of both public and private subnets, the workers will be just part of private subnets.
   Now a "public subnet" does not mean a subnet with public IP addresses, its still a subnet with
   private ranges like 10.x etc.. All addresses will get NATed by the aws NAT gateway before it 
   goes out to internet - the terraform scripts also allocate a NAT gateway.

6. A bastion host. We have a bastion host from which we can ssh to any of the worker nodes

## How to create/destroy clusters

Note that terraform is not without its share of problems, sometimes it fails to cleanup a cluster
completely and sometimes it fails to create one - good thing is it will tell us exactly why, and
most of the times its small reasons like theres already an existing vpc with the same name and so
we just go delete it and then the creation succeeds. So be ready for some manual intervention, it
works 99% of the time without manual intervention, but some times it needs some help. Also creating
a cluster on aws / eks takes around 15 to 20 minutes, so be ready for that.

### Terraform configs

In the automation repository, in deploy/aws, there is directories for controller and the gateways
we plan to deploy, eventually it will end up moving to some devops repository, but for now its 
in automation. There is a "common" directory which holds common configs for all clusters, and 
in each cluster directory (like controller, uswest2, useast1 etc..) there is a spec.tf file which
are specifications specific to that cluster, and we can tweak that differently for different clusters.
The script create.py in the deploy/aws directory will search for the common/ files and spec.tf by
figuring out the location of the create.py script itself and then searching in that location for 
common/ and <cluster-name>/spec.tf

### Creating cluster

* This is what I do. I create a directory like /tmp/nextensio-eks. And if I want three clusters, I
create three directories inside that like "controller", "useast1" and "uswest1" (latter two are gateways)

* Since we are still not "official", we use self signed certificates for our tls connections, and 
we need a rootCA certificate which we can use for the controllers and gateways, lets first generate 
that in /tmp/nextensio-eks/ by saying automation/deploy/aws/create.py -genca .

* Now lets say we create the controller. So "cd controller"; and "create.py -terraform controller".
You have to answer "yes" at some point, and then this will take 15 to 20 minutes. You have to be
ready for manual intervention if something goes wrong with terraform. Once its all done, the 
directory will have files names terraform.tfstate. Be VERY CAREFUL and DO NOT delete this file,
if you do, then terraform cannot tell you information about the cluster (like kubernetes keys)
or it cant destroy the cluster etc.. Then you will have to do all that very painfully and manually
via the aws UI or CLIs etc..

* Now that the controller cluster is terraformed, we need to configure nextensio software on it by saying
"create.py  -create controller -docker /home/gopa/.docker/config.json -rootca ../" - the docker parameter
will copy our docker credentials to the cluster so that more nextensio software can be downloaded on
the cluster. The rootca just points to the directory where we created some certificates before.

The above step will install all required nextensio software and also create domain name mappings 
for controller.nextensio.net (the UI), server.nextensio.net (controller), and three mongodb names
mongodb-service-0.nextensio.net, mongodb-service-1.nextensio.net, mongodb-service-2.nextensio.net
At this point you can access controller.nextensio.net and start configuring the controller

* Next to terraform the gateways, do the same as for controller. Lets say we are terraforming the
uswest2 gateway, first create a directory uswest2 in /tmp/nextensio-eks and "cd uswest2" and
"create.py -terraform uswest2". Once thats done then configure the gateways with nextensio software,
"create.py  -create uswest2 -docker /home/gopa/.docker/config.json -rootca ../"

At this point we have a domain name gateway.uswest2.nextensio.net available, with the istio ingress
gateways and consul and nextensio clustermgr etc.. installed. Now the clustermgr will try looking
for the mongodb domains mongodb-service-0.nextensio.net etc.. to listen for tenant/user/app configs
and program istoi yamls etc.. Do the same for the uswest2 cluster, create a directory uswest2 and
repeat the above.

Again be VERY CAREFUL not to delete the terraform.tfstate file or else you will have a lot of 
manual work ahead for deleting the cluster etc.. After the creation is done, a file like
cluster_useast1_state.json and cluster_uswest2_state.json is created with some information 
about the states of the clusters, be sure not to delete that file either
 
* Finally when all the required gateways are created, we need to form a full-mesh connection of
all the consuls on all the gateways, so go to the directory where you have all the other gateway
directories, in my case /tmp/nextensio-eks/, and say "create.py -consul uswest2 useast1" - 
basically space seperated list of gateways after the -consul parameter

### Deleting cluster
 
* To delete the cluster, in your directory uswest2 say "create.py -delete uswest2" 

* Once the above step is done, say "terraform destroy" and that should destroy the cluster, if it
cant destroy, it will usually say some error like "vpc id xyz still in use", then we have to go to
the aws UI and find that vpc and delete it manually and run "terraform destroy" again

### Accessing worker nodes via bastion

* from aws UI, find your bastion node's public IP - the bastion will be named like uswest2-bastion

* from your cluster directory say uswest2, do "ssh -i bastion ec2-user@<public ip>"

* copy the bastion/bastion.pub files to the bastion host - we use the same keys to ssh to bastion
and to ssh to worker nodes, we need to change that, its a TODO

* find the private IP of your worker node from aws UI. From bastion say "ssh -i bastion ec2-user@<private ip>"

* The worker nodes run amazon linux which is redhat based (I think), if you want to install additional 
packages on it, just say "sudo yum install <package name>"

## Cloud provider Loadbalancers

Like we described before, the clusters all run on private addresses themselves, so the only way
to access services inside clusters is by intentionally exposing the required services using a
"loadbalancer". The loadbalancer itself is an entity that is outside the kubernetes cluster, its
an etity provided by the cloud provider. And the issue with a loadbalancer is that there are 
various quirks for loadbalancers that is specific to each cloud provider which we come to only
by trial and error, and some of which are quite problematic and prevents us from doing things the
way we want. Some example quirks are below

1. AWS Loadbalancers can be spread across availability zones, so if there are three AZs, we will
   get three public IPs for the LB. We annotate the istio yaml profile to use "network loadbalancer" 
   (which is what we want because we want UDP support) aka "nlb". So lets say we get three IPs
   A, B and C in three different zones. Now lets say we have worker nodes only in zones B and C
   but not in A. But the loadbalancer will still dish out dns responses with the ip address A, 
   so user traffic will come to A and will get dropped. The only way to solve this is to enable
   "cross zone loadbalancing enabled" option in AWS. So this means that traffic will hit zone A,
   and then get re-routed from there to B or C.

   This brings an interesting question to us - for redundancy reason, if we create a multi-zone
   cluster, and lets say we add a dns CNAME to point gateway.ric.nextensio.net to the AWS loadbalancer
   domain name. Now istio ingress will be on a node in one of the zones, and services can be in
   other zones. Which means that there can be a lot of cross-zone traffic! That will add to the
   latency, and will also cost more since aws charges more for cross zone traffic

   So that makes me think that we should just deploy single-zone clusters and for redundancy 
   reason we should deploy seperate clusters in each zone rather than one cluster that spans zones

2. Loadbalancers and Healthcheck: every loadbalancer will forward traffic to a service only if the 
   service passes a healthcheck. Now how a loadbalancer does a healthcheck is very specific to the
   cloud vendor. This becomes a problem for istio ingress gateway. The ingress gateway defines a 
   list of service ports (see automation/deploy/aws/istio.yaml), but there is only one port in that
   which is meant for health checking. But by default, AWS tries to health check every port, which
   obviously fails, and loadbalancer will not forward traffic to ports that fail health check.
   Very recently, aws has introduced an annotation for this, but looks like its only going to be
   in kubernetes 1.20 - service.beta.kubernetes.io/aws-load-balancer-healthcheck-port
   So till then what istio recommends is to set externalTrafficPolicy: "Local" to force istio to
   switch to a http health check mode where all the ports are health checked by the same http 
   endpoint registered by istio.

   And which also brings in the interesting question on whether we should have external traffic
   policy local or cluster. Read about it, cluster basically means the traffic can land on any
   node in the cluster and will get re-routed to the correct node (the istio ingress gateway 
   for example). But do we really need that ? ALL TRAFFIC comes via ingress gateway, so we would
   rather have the traffic land on the node hosting the istio ingress gateway, so traffic policy
   Local seems to be the right thing to do.

3. AWS loadbalancer "maps" an outside user-visible port (like port 443) to an inside port - the
   outside and inside port maybe the same or different, loadbalancer does not care about that. 
   By default in kubernetes if we add a Service type:LoadBalancer rule to expose say port 443,
   kubernetes will allocate an internal port > 32000 on the node (host/physical machine) and 
   add iptable rules to map the >32000 port to 443. Also it will communicate to the loadbalancer
   (via the loadbalancer controller) information that "if anyone sends traffic to loadbalancer
   on port 443, loadbalancer should send that to the physical machine in port X(>32000)"

   All well and good so far, standard loadbalancer behaviour, no surprises. But, the surprise 
   that AWS has is that it assumes that if an application like consul needs to use port 8302
   using tcp and udp, then 8302 is mapped internally to the host using the same port say 32256.
   This is what AWS calles protocol "TCP_UDP" in the loadbalancer listener config - it says 
   in one rule that both tcp and udp port 8302 maps to tcp/udp port say 32256. It cant be 
   configured any other way. 

   Now why is this an issue ? We configure consul as a "stateful-set" with a "headless service".
   And the way to expose a headless service to outside world is by adding a kubernetes
   service per stateful-set member - https://itnext.io/exposing-statefulsets-in-kubernetes-698730fb92a1
   But the problem is that like I mentioned above, in Kubernetes service, we need to ensure 
   that the "internal port" allocated for 8302 tcp and 8302 udp is the same - and there is 
   no way to do that - https://github.com/kubernetes/kubernetes/issues/20092 .. One may ask - if
   aws disallows a loadbalancer from having the same port for udp and tcp mapped to different
   ports on the host, why not just create two different loadbalancers, one for tcp and one for
   udp. Well then the issue is that consul wants to be contacted on the same ip address for 
   both udp and tcp ports 8302, its ONE SERVER with ONE IP and two ports! Well then one can
   ask why not just allocate an elastic IP and give that same ip to both the loadbalancers. That
   is do-able, but the only catch is that AWS (rightfully so) allows only FIVE EIPs per region,
   and if we have a cluster spanning three zones, then we lose three EIPs right there for ONE
   loadbalancer ! We will very soon be crippled with lack of EIPs and be unable to spin up 
   new clusters etc.., we dont want our cluster design to have such a small limitation

   So basically for consul, we are stuck - what aws loadbalancer wants and what kubernetes wants
   are the exact opposites, so we just cant make it work via "standard" kubernetes service 
   defenitions. The way we kludge around it is by using the "hostPort" defenition in the consul
   Deployment rule which basically just adds an iptable rule mapping a the "hostPort" to the 
   actual consul port - and thankfully the hostPort allows us to use the same port for tcp and
   udp. Eventually we need to think of a better way to get consul working with kubernetes. 
   Today we have just one consul server in the stateful set - if we make it two servers for example,
   the stateful set will fail because two members cannot try to allocate the same hostPort 
   defentitions. So then if we want two servers (will we ever want that ?), then we will have to
   do some hack like two replica sets with one member each etc.. So the whole consul deployment
   strategy in long term needs some thinking

   Note that for consul, since we keep things working using a hostPort as described above, 
   the external traffic policy automatically ends up being "local" - the loadbalancer will try
   to probe all the nodes for consul liveliness and only one of them will respond, so loadbalancer
   will send all consul traffic to the specific node running consul
