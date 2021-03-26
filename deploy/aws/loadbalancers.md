# Note on Cloud provider Loadbalancers

The clusters are all created and run on private addresses themselves, so the only way
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
