# Kops

We let kops generate terraform files and then we tweak the files to our taste and use 
terraform to finally create the resources.

## Software Pre Requisites

* Install Kops

* Install terraform

* Install the AWS cli v2 (version2)

* Run "aws configure" so that the CLI can access your aws account

* docker login registry.gitlab.com so that you can access nextensio images

## AWS Networking pre-requisites

We will automate this too some day, but for now we need a pre-created transit gateway. We can
have multiple clusters in the same region, and NAT gateways are not cheap - we dont need a NAT
gateway per cluster, we can share a single NAT gateway using an aws "transit gateway". There is
plenty of docs online about AWS transit gateways. Basically this is what we need to have setup
before hand

0. Assume that all clusters in the region are using the 10.0.0.0/16 address space - this will be
   an assumption that will help us add a single summary route as seen below. Otherwise we will
   need to add multiple routes

1. A VPC with two subnets - one "private" and one "public" - this can very well be the "default vpc"
   in the account. For example the VPC subnet can be 172.31.0.0/16 and the private subnet can be
   172.31.0.0/28 and 172.31.0.16/28

2. A NAT gateway associated with the public subnet

3. An Internet gateway

4. A Transit gateway created with "Default association route table" enabled and 
   "Default propagation route table" disabled - I dont think the rest of the settings like DNS 
   etc.. matters. Also the transit gateway just needs its default routing table, we DO NOT 
   have to create any additional route tables.

   The transit gateway needs a tag with key as 'Nextensio-Transit' and value as 'true'

5. Attach the VPC's PRIVATE subnet to the transit gateway

6. Add a default route 0.0.0.0/0 in the transit gateway route table --> via the VPC

7. The private subnet's route table should have two routes - 
   0.0.0.0/0 --> via NAT gateway
   10.0.0.0/8 --> via Transit gateway
 
   Later we will attach VPCs of different clusters to the transit gateway and they will all
   send traffic to this VPC created above. The 10.0.0.0/8 is a summary return route that says
   "to reach any of the clusters, send the traffic to transit gateway". If we dont adhere to
   an addressing scheme like 10.0.0.0/16 for clusters, then we will have to add individual routes
   here each time we create a cluster. Having this summary route allows us to not worry about
   modifying this if we create / delete a new cluster

   NOTE: The private route table is shown as the VPC's 'main' route table, I dont know if 
   private being main or not matters, but just noting it down here. And similarly, the public
   route table is not the 'main' route table

8. The public subnets route table should have two routes
   0.0.0.0/0 --> via INTERNET gateway
   10.0.0.0/8 --> via Transit gateway

   The reasoning behind the 10.0.0.0/8 summary route is the same as in the step before.

## Kops networking pre-requisites

This is well documented on the kops page. What we need is 

1. An s3 bucket where kops stores config state of a cluster - we have a bucket clusters.kops.nextensio.net

   
2. A SEPERATE HOSTED ZONE in route53 for kops - we have create a hosted zone named kops.nextensio.net 
   and added NS records in the parent zone nextensio.net pointing to this hosted zone. There is enough
   documentation on internet on how to do that

## Kops terraform config creation

Each cluster has its own directory with a small spec.json file. The kops terraform configs are created 
by doing a "cd <cluster-directory>; ../kops.py" .. This will generate the terraform configs in 
out/terraform/kubernetes.tf. Note that if we already have generated the configs before, kops will store
that in the s3 bucket mentioned in the "kops prerequisite" section, so make sure to delete that before
attempting to regenerate the config - kops will complain and refuse to generate the configs otherwise 
and that will be a clue to check in s3

By default Kops generates NAT gateway for the cluster, and since we have
our own NAT gateway described before, we do the following to remove the NAT gateway from the terraform
file - again this should be automated too.

a. Remove the resource "aws_nat" section in the kubernetes.tf file
b. Remove the resource "aws_route" "private-xyz" - if you look at that route, it refers to the nat gateway
   above. We remove this route, the create.py scripts will add a route pointing to our shared NAT gateway
   later when we create the cluster
c. Remove the "aws_eip" (elastic ip) section - the elastic IP was created for nat gateway, and we dont
   need it since we have our own NAT gateway

Now save the kubernetes.tf file and thats what we will use to create the cluster

## Creating cluster

0. I would just create a directory like ~/deployments/<cluster>/, cd to that directory and do all the
   steps below from that directory

1. First let terraform create the basic kubernetes cluster with no nextensio stuff in it, to do that 
   say "<git-repo-root>/automation/deploy/aws/kops/create.py  -terraform <cluster>"

   This will take approx 5 minutes and generate a file terraform.tfstate - MAKE SURE TO SAVE THIS FILE -
   if we want to destroy the cluster, we need this file, or else we will have to destroy many things
   by hand and is painful

2. Wait a good 10 minutes after step1. A good test on when to start is to say 
   "KUBECONFIG=./kubeconfig kubectl get pods --all-namespaces" - if that gives an output without 
   timing out, then we are ready to create the nextensio stuff in the cluster

   <git-repo-root>/automation/deploy/aws/kops/create.py  -create <cluster> -docker ~/.docker/config.json

   The -docker parameter is a pointer to a file with docker keys which allows us to download images
   from the nextensio gitlab docker repository. If its in some other location, give that location name
   after -docker - if you dont have one, figure out how to configure docker to download nextensio software
   without passwords from gitlab docker repo

## Deleting cluster

Again go to the ~/deployments/<cluster>/ directory used for creating the cluster

1. First say "<git-repo-root>/automation/deploy/aws/kops/create.py  -delete <cluster>" - this will remove 
   all the nextensio specific stuff we added to amazon (like transit gateway attachments, loadbalancers et..)

2. Then say "terraform destroy" - if we dont do step 1, then terraform will not be able to destroy the 
   cluster because of dependent resources not cleaned up. This will take 5 minutes and the cluster will
   be destroyed. 
