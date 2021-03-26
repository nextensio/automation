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

* Now lets say we create the controller. So "cd controller"; and "create.py -terraform controller".
You have to answer "yes" at some point, and then this will take 15 to 20 minutes. You have to be
ready for manual intervention if something goes wrong with terraform. Once its all done, the 
directory will have files names terraform.tfstate. Be VERY CAREFUL and DO NOT delete this file,
if you do, then terraform cannot tell you information about the cluster (like kubernetes keys)
or it cant destroy the cluster etc.. Then you will have to do all that very painfully and manually
via the aws UI or CLIs etc..

* Now that the controller cluster is terraformed, we need to configure nextensio software on it by saying
"create.py  -create controller -docker /home/gopa/.docker/config.json" - the docker parameter
will copy our docker credentials to the cluster so that more nextensio software can be downloaded on
the cluster. 

The above step will install all required nextensio software and also create domain name mappings 
for controller.nextensio.net (the UI), server.nextensio.net (controller), and three mongodb names
mongodb-service-0.nextensio.net, mongodb-service-1.nextensio.net, mongodb-service-2.nextensio.net
At this point you can access controller.nextensio.net and start configuring the controller

* Next to terraform the gateways, do the same as for controller. Lets say we are terraforming the
uswest2 gateway, first create a directory uswest2 in /tmp/nextensio-eks and "cd uswest2" and
"create.py -terraform uswest2". Once thats done then configure the gateways with nextensio software,
"create.py  -create uswest2 -docker /home/gopa/.docker/config.json"

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


