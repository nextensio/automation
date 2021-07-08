#!/usr/bin/env bash

# The routines in this file sets up a kind (kubernetes in docker) based
# topology with a controller, gatewaytesta gateway cluster and gatewaytestc gateway cluster
# The script does the necessary things to ensure that the clusters are
# connected to each other and the controller is programmed with a sample
# user(agent) and app(connector), the Agent connecting to gatewaytesta and connector
# connecting to gatewaytestc cluster

tmpdir=/tmp/nextensio-kind
kubectl=$tmpdir/kubectl
kind=$tmpdir/kind
istioctl=$tmpdir/istioctl
metric_dir=../../../metrics/monitoring

image_mongo="gopakumarce/mongodb-replica-set:20200330-stable-1"
image_kind_node="kindest/node:v1.21.1@sha256:69860bda5563ac81e3c0057d654b5253219618a22ec3a346306239bba8cfa1a6"
image_metallb_controller="docker.io/metallb/controller:v0.9.3"
image_metallb_speaker="docker.io/metallb/speaker:v0.9.3"
image_kindnetd="docker.io/kindest/kindnetd:v20210326-1e038dc5"
image_localpath="docker.io/rancher/local-path-provisioner:v0.0.14"
image_istio_pilot="docker.io/istio/pilot:1.10.2"
image_istio_proxy="docker.io/istio/proxyv2:1.10.2"
image_jaeger="docker.io/jaegertracing/all-in-one:1.22"
image_consul="gopakumarce/consul:1.9.6"
image_prometheus="docker.io/prom/prometheus:v2.24.0"
image_debian_base="k8s.gcr.io/build-image/debian-base:v2.1.0"
image_coredns="k8s.gcr.io/coredns/coredns:v1.8.0"
image_etcd="k8s.gcr.io/etcd:3.4.13-0"
image_apiserver="k8s.gcr.io/kube-apiserver:v1.21.1"
image_controller_manager="k8s.gcr.io/kube-controller-manager:v1.21.1"
image_kube_proxy="k8s.gcr.io/kube-proxy:v1.21.1"
image_kube_scheduler="k8s.gcr.io/kube-scheduler:v1.21.1"
image_pause="k8s.gcr.io/pause:3.5"
image_kiali="quay.io/kiali/kiali:v1.34"
image_alertmgr="docker.io/prom/alertmanager:v0.15.3"
image_node_exporter="docker.io/prom/node-exporter:v0.16.0"
image_kube_metrics="quay.io/mxinden/kube-state-metrics:v1.4.0-gzip.3"
image_thanos="quay.io/thanos/thanos:v0.12.2"
image_grafana="docker.io/grafana/grafana:7.4.3"
 
function download_common_images {
    docker image inspect ${image_kind_node} > /dev/null || docker pull ${image_kind_node}
    docker image inspect ${image_metallb_controller} > /dev/null || docker pull ${image_metallb_controller}
    docker image inspect ${image_metallb_speaker} > /dev/null || docker pull ${image_metallb_speaker}
    docker image inspect ${image_kindnetd} > /dev/null || docker pull ${image_kindnetd}
    docker image inspect ${image_localpath} > /dev/null || docker pull ${image_localpath}
    docker image inspect ${image_debian_base} > /dev/null || docker pull ${image_debian_base}
    docker image inspect ${image_coredns} > /dev/null || docker pull ${image_coredns}
    docker image inspect ${image_etcd} > /dev/null || docker pull ${image_etcd}
    docker image inspect ${image_apiserver} > /dev/null || docker pull ${image_apiserver}
    docker image inspect ${image_controller_manager} > /dev/null || docker pull ${image_controller_manager}
    docker image inspect ${image_kube_proxy} > /dev/null || docker pull ${image_kube_proxy}
    docker image inspect ${image_kube_scheduler} > /dev/null || docker pull ${image_kube_scheduler}
    docker image inspect ${image_pause} > /dev/null || docker pull ${image_pause}
    docker image inspect ${image_node_exporter} > /dev/null || docker pull ${image_node_exporter}
    docker image inspect ${image_kube_metrics} > /dev/null || docker pull ${image_kube_metrics}
}

function load_common_images {
    $kind load docker-image $image_metallb_controller --name $1
    $kind load docker-image $image_metallb_speaker --name $1
    $kind load docker-image $image_kindnetd --name $1
    $kind load docker-image $image_localpath --name $1
    $kind load docker-image $image_debian_base --name $1
    $kind load docker-image $image_coredns --name $1
    $kind load docker-image $image_etcd --name $1
    $kind load docker-image $image_apiserver --name $1
    $kind load docker-image $image_controller_manager --name $1
    $kind load docker-image $image_kube_proxy --name $1
    $kind load docker-image $image_kube_scheduler --name $1
    $kind load docker-image $image_pause --name $1
    $kind load docker-image $image_node_exporter --name $1
    $kind load docker-image $image_kube_metrics --name $1
}
   
function download_controller_infra_images {
    docker image inspect ${image_mongo} > /dev/null || docker pull ${image_mongo}
}

function download_nextensio_controller {
    docker pull registry.gitlab.com/nextensio/ux/ux:latest
    docker pull registry.gitlab.com/nextensio/controller/controller:latest
}

function load_controller_images {
    $kind load docker-image $image_mongo --name controller
    $kind load docker-image registry.gitlab.com/nextensio/ux/ux:latest --name controller
    $kind load docker-image registry.gitlab.com/nextensio/controller/controller:latest --name controller
}

function download_cluster_infra_images {
    docker image inspect ${image_prometheus} > /dev/null || docker pull ${image_prometheus}
    docker image inspect ${image_istio_pilot} > /dev/null || docker pull ${image_istio_pilot}
    docker image inspect ${image_istio_proxy} > /dev/null || docker pull ${image_istio_proxy}
    docker image inspect ${image_jaeger} > /dev/null || docker pull ${image_jaeger}
    docker image inspect ${image_consul} > /dev/null || docker pull ${image_consul}
    docker image inspect ${image_kiali} > /dev/null || docker pull ${image_kiali}
    docker image inspect ${image_alertmgr} > /dev/null || docker pull ${image_alertmgr}
    docker image inspect ${image_grafana} > /dev/null || docker pull ${image_grafana}
    docker image inspect ${image_thanos} > /dev/null || docker pull ${image_thanos}
}

function download_nextensio_cluster {
    docker pull registry.gitlab.com/nextensio/clustermgr/mel:latest
    docker pull registry.gitlab.com/nextensio/cluster/minion:latest
}

function load_cluster_images {
    cluster=$1
    $kind load docker-image $image_prometheus --name $cluster
    $kind load docker-image $image_istio_pilot --name $cluster
    $kind load docker-image $image_istio_proxy --name $cluster
    $kind load docker-image $image_jaeger --name $cluster
    $kind load docker-image $image_consul --name $cluster
    $kind load docker-image $image_kiali --name $cluster
    $kind load docker-image registry.gitlab.com/nextensio/cluster/minion:latest --name $cluster
    $kind load docker-image registry.gitlab.com/nextensio/clustermgr/mel:latest --name $cluster
}

function load_monitoring_images {
    $kind load docker-image $image_prometheus --name monitoring
    $kind load docker-image $image_alertmgr --name monitoring
    $kind load docker-image $image_grafana --name monitoring
    $kind load docker-image $image_thanos --name monitoring
}

function download_nextensio_agents {
    docker pull registry.gitlab.com/nextensio/agent/go-agent:latest
    docker pull registry.gitlab.com/nextensio/agent/rust-agent:latest
}

# Create a controller
function create_controller {
    $kind create cluster --config ./kind-config.yaml --name controller

    # Load required images into cluster
    load_common_images controller
    load_controller_images

    # metallb as a loadbalancer to map services to externally accessible IPs
    $kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.9.3/manifests/namespace.yaml
    $kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.9.3/manifests/metallb.yaml
    $kubectl create secret generic -n metallb-system memberlist --from-literal=secretkey="$(openssl rand -base64 128)"
    # Mongo needs some storage, just use local storage
    $kubectl delete storageclass standard
    $kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/master/deploy/local-path-storage.yaml
}

function bootstrap_controller {
    my_ip=$1

    $kubectl config use-context kind-controller

    # Create tls keys for controller (UI) and server (API)
    EXTFILE="$tmpdir/controller-extfile.conf"
    echo "subjectAltName = IP:$my_ip" > "${EXTFILE}"
    # Create ssl keys/certificates for agents/connectors to establish secure websocket
    openssl req -out $tmpdir/controller.csr -newkey rsa:2048 -nodes -keyout $tmpdir/controller.key \
        -subj "/CN=$my_ip/O=Nextensio Controller and Server"
    openssl x509 -req -days 365 -CA ../../testCert/nextensio.crt -CAkey ../../testCert/nextensio.key -set_serial 0 \
        -in $tmpdir/controller.csr -out $tmpdir/controller.crt -extfile "${EXTFILE}" -passin pass:Nextensio123
    $kubectl create secret tls controller-cert --key="$tmpdir/controller.key" --cert="$tmpdir/controller.crt"

    tmpf=$tmpdir/controller.yaml
    cp controller.yaml $tmpf
    sed -i "s/REPLACE_SELF_NODE_IP/$my_ip/g" $tmpf
    sed -i "s/REPLACE_CONTROLLER_IP/$ctrl_ip/g" $tmpf
    $kubectl apply -f $tmpf
    $kubectl apply -f mongo.yaml
}

# Create a monitoring cluster 
function create_monitoring {
    echo "Create Monitoring cluster for telemetry"
    $kind create cluster --config ./kind-config.yaml --name monitoring 

    # Load required images into cluster
    load_common_images monitoring
    load_monitoring_images 

    # metallb as a loadbalancer to map services to externally accessible IPs
    $kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.9.3/manifests/namespace.yaml
    $kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.9.3/manifests/metallb.yaml
    $kubectl create secret generic -n metallb-system memberlist --from-literal=secretkey="$(openssl rand -base64 128)"
    $kubectl apply -f $metric_dir/monitoring-namespace.yaml
}

function config_gateway_monitoring {
    cluster_name=$1
    alertmgr_ip=$2
    alertmgr_port=$3


    echo "Setup monitoring components on Nxt $cluster_name cluster"
    echo "use-context kind-$cluster_name"

    $kubectl config use-context kind-$cluster_name
    #config prometheus external label and alert-mgr target
    tmpf=$tmpdir/$cluster_name-prometheus-configmap.yaml
    cp $metric_dir/istio-promethues-confmap.yaml $tmpf
    sed -i "s/REPLACE_CLUSTER_NAME/$cluster_name/g" $tmpf
    sed -i "s/REPLACE_ALERTMGR_TARGET/$alertmgr_ip/g" $tmpf
    sed -i "s/REPLACE_AM_TARGET_PORT/$alertmgr_port/g" $tmpf
    $kubectl apply -f $tmpf
    $kubectl apply -f $metric_dir/istio-prometheus-rules-config.yaml
    $kubectl apply -f $metric_dir/istio-prometheus-deployment.yaml  

    #config gateway for thanos side car
    tmpf=$tmpdir/$cluster_name-thanos-store-gateway-svc.yaml
    cp $metric_dir/istio-thanos-store-gateway-svc.yaml $tmpf
    sed -i "s/REPLACE_CLUSTER_NAME/$cluster_name/g" $tmpf
    $kubectl apply -f $tmpf
    tmpf=$tmpdir/$cluster_name-thanos-store-gateway-service.yaml
    cp $metric_dir/thanos-store-gateway-service.yaml $tmpf
    sed -i "s/REPLACE_NAMESPACE/istio-system/g" $tmpf
    $kubectl apply -f $tmpf

    # Create monitoring namespace and install k8s and node exporter
    # metric components
    $kubectl apply -f $metric_dir/monitoring-namespace.yaml
    $kubectl apply -f $metric_dir/node-exporter-daemonset.yml
    $kubectl apply -f $metric_dir/K8SstateMetrics-deployment.yaml
}

function config_controller_monitoring {
    cluster_name=$1
    alertmgr_ip=$2
    alertmgr_port=$3

    echo "Setup monitoring components on Nxt Controller" 
    $kubectl config use-context kind-controller

    #config prometheus server, node-exported and related components   
    $kubectl apply -f $metric_dir/monitoring-namespace.yaml
    tmpf=$tmpdir/$cluster_name-prometheus-config.yaml
    cp $metric_dir/prometheus-config.yaml $tmpf
    sed -i "s/REPLACE_CLUSTER_NAME/nxt-$cluster_name/g" $tmpf
    sed -i "s/REPLACE_ALERTMGR_TARGET/$alertmgr_ip/g" $tmpf
    sed -i "s/REPLACE_AM_TARGET_PORT/$alertmgr_port/g" $tmpf
    $kubectl apply -f $tmpf
    $kubectl apply -f $metric_dir/prometheusRulesConfigmap.yaml
    $kubectl apply -f $metric_dir/prometheus-deployment.yaml

    tmpf=$tmpdir/$cluster_name-thanos-store-gateway-service.yaml
    cp $metric_dir/thanos-store-gateway-service.yaml $tmpf
    sed -i "s/REPLACE_NAMESPACE/monitoring/g" $tmpf
    $kubectl apply -f $tmpf
    $kubectl apply -f $metric_dir/node-exporter-daemonset.yml
    $kubectl apply -f $metric_dir/K8SstateMetrics-deployment.yaml
}

function bootstrap_monitoring {
    my_ip=$1
    ctrl_ip=$2
    testa_ip=$3
    testc_ip=$4

    echo "Configure monitoring cluster, use context kind-monitoring" 
    $kubectl config use-context kind-monitoring

    # Install loadbalancer to attract traffic to istio ingress gateway via external IP (docker contaier IP)
    tmpf=$tmpdir/monitoring-metallb.yaml
    cp metallb.yaml $tmpf
    sed -i "s/REPLACE_SELF_NODE_IP/$my_ip/g" $tmpf
    $kubectl apply -f $tmpf

    # Config ctrl/testa/testc for thanos querier dns lookup
    tmpf=$tmpdir/monitoring-coredns.yaml
    cp $metric_dir/monitoring-coredns.yaml $tmpf
    sed -i "s/REPLACE_CONTROLLER_IP/$ctrl_ip/g" $tmpf
    sed -i "s/REPLACE_NODE1_IP/$testa_ip/g" $tmpf
    sed -i "s/REPLACE_NODE2_IP/$testc_ip/g" $tmpf
    $kubectl replace -n kube-system -f $tmpf

    #config prometheus external label and alert-mgr target
    tmpf=$tmpdir/monitoring-prometheus-config.yaml
    cp $metric_dir/prometheus-config.yaml $tmpf
    sed -i "s/REPLACE_CLUSTER_NAME/nxt-monitoring/g" $tmpf
    sed -i "s/REPLACE_ALERTMGR_TARGET/alertmanager/g" $tmpf
    sed -i "s/REPLACE_AM_TARGET_PORT/9093/g" $tmpf
    $kubectl apply -f $tmpf

    $kubectl apply -f $metric_dir/prometheusRulesConfigmap.yaml
    $kubectl apply -f $metric_dir/prometheus-deployment.yaml
    $kubectl apply -f $metric_dir/prometheus-service.yaml

    # deploy thanos querier
    $kubectl apply -f $metric_dir/thanos-querier-deployment.yaml

    # deploy grafana
    $kubectl apply -f $metric_dir/grafana-deployment.yaml
    $kubectl apply -f $metric_dir/grafana-service.yaml

    # lets add node metrics
    # deploy node exporter. explain daemonser
    $kubectl apply -f $metric_dir/node-exporter-daemonset.yml

    # deploy kubernetes state metrics
    $kubectl apply -f $metric_dir/K8SstateMetrics-deployment.yaml

    # start prometheus alert manager
    $kubectl apply -f $metric_dir/alertManager-deployment.yaml
    
    config_controller_monitoring controller $my_ip 30393
    config_gateway_monitoring gatewaytesta $my_ip 30393
    config_gateway_monitoring gatewaytestc $my_ip 30393
}

# Create kind clusters for gatewaytesta and gatewaytestc
function create_cluster {
    cluster=$1

    # Create a docker-in-docker kubernetes cluster with a single node (control-plane) running everything
    $kind create cluster --config ./kind-config.yaml --name $cluster

    # Load required images into cluster
    load_common_images $1
    load_cluster_images $1

    # We should have done a docker login to be able to download images from the gitlab registry
    $kubectl create secret generic regcred --from-file=.dockerconfigjson=$HOME/.docker/config.json --type=kubernetes.io/dockerconfigjson

    # This is NOT the right thing to do in real deployment, either we should limit the 
    # roles (RBAC) of the clustermgr or even better make clustermgr use kube APIs instead
    # of kubectl
    $kubectl create clusterrolebinding permissive-binding \
        --clusterrole=cluster-admin \
        --user=admin \
        --user=kubelet \
        --group=system:serviceaccounts

    # Install istio. This is nothing but the demo.yaml in the istio bundle, with addonComponents
    # prometheus, kiali, grafana, tracing all set to false. 
    $istioctl manifest apply -f ./istio.yaml --skip-confirmation
    $kubectl apply -f ./jaeger.yaml
    $kubectl apply -f ./kiali.yaml
    $kubectl apply -f ./prometheus.yaml
    $kubectl apply -f ./grafana.yaml

    # Install metallb. metallb exposes services inside the cluster via external IP addresses
    $kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.9.3/manifests/namespace.yaml
    $kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.9.3/manifests/metallb.yaml
    $kubectl create secret generic -n metallb-system memberlist --from-literal=secretkey="$(openssl rand -base64 128)"

    EXTFILE="$tmpdir/$cluster-extfile.conf"
    echo "subjectAltName = DNS:$cluster.nextensio.net" > "${EXTFILE}"
    # Create ssl keys/certificates for agents/connectors to establish secure websocket
    openssl req -out $tmpdir/$cluster-gw.csr -newkey rsa:2048 -nodes -keyout $tmpdir/$cluster-gw.key \
        -subj "/CN=$cluster.nextensio.net/O=Nextensio Gateway $cluster"
    openssl x509 -req -days 365 -CA ../../testCert/nextensio.crt -CAkey ../../testCert/nextensio.key -set_serial 0 \
        -in $tmpdir/$cluster-gw.csr -out $tmpdir/$cluster-gw.crt -extfile "${EXTFILE}" -passin pass:Nextensio123
}

function bootstrap_cluster {
    cluster=$1
    my_ip=$2
    ctrl_ip=$3

    $kubectl config use-context kind-$cluster

    $kubectl create -n istio-system secret tls gw-credential --key=$tmpdir/$cluster-gw.key --cert=$tmpdir/$cluster-gw.crt

    # Deploy the cluster manager "mel"
    tmpf=$tmpdir/$cluster-mel.yaml
    cp mel.yaml $tmpf
    sed -i "s/REPLACE_CLUSTER/$cluster/g" $tmpf
    sed -i "s/REPLACE_CONTROLLER_IP/$ctrl_ip/g" $tmpf
    sed -i "s/REPLACE_CONSUL_WAN_IP/$my_ip/g" $tmpf
    sed -i "s/REPLACE_CONSUL_STORAGE/standard/g" $tmpf
    $kubectl apply -f $tmpf

    # Install loadbalancer to attract traffic to istio ingress gateway via external IP (docker contaier IP)
    tmpf=$tmpdir/$cluster-metallb.yaml
    cp metallb.yaml $tmpf
    sed -i "s/REPLACE_SELF_NODE_IP/$my_ip/g" $tmpf
    $kubectl apply -f $tmpf

    # Find consul dns server address. Mel would have launched consul pods, so wait
    # for the service to be available
    consul_dns=`$kubectl get svc $cluster-consul-dns -n consul-system -o jsonpath='{.spec.clusterIP}'`
    while [ -z "$consul_dns" ];
    do
      consul_dns=`$kubectl get svc $cluster-consul-dns -n consul-system -o jsonpath='{.spec.clusterIP}'`
      echo "waiting for consul, sleeping 5 seconds"
      sleep 5
    done
    echo "Success from server: service $cluster-consul-dns found"

    # Point dns server to redirect to consul for lookups of x.y.consul names
    tmpf=$tmpdir/$cluster-coredns.yaml
    # $tmpdir/coredns.yaml has been created before this is called
    cp $tmpdir/coredns.yaml $tmpf
    sed -i "s/REPLACE_CONSUL_DNS/$consul_dns/g" $tmpf
    sed -i "s/REPLACE_CONTROLLER_IP/$ctrl_ip/g" $tmpf
    $kubectl replace -n kube-system -f $tmpf
}

# Setup prepared query so that consul forwards the dns lookup to multiple DCs
# TODO: What if consul pod crashes, do we have to reapply these rules or consul saves it ?
function consul_query_config {
    cluster=$1

    $kubectl config use-context kind-$cluster
    ret=`kubectl exec -it $cluster-consul-server-0 -n consul-system -- curl --request GET http://127.0.0.1:8500/v1/query`
    while [[ "$ret" == "[]" ]]; 
    do
    echo "Adding consul query in $cluster"
    $kubectl exec -it $cluster-consul-server-0 -n consul-system -- curl --request POST http://127.0.0.1:8500/v1/query --data-binary @- << EOF
{
  "Name": "",
  "Template": {
    "Type": "name_prefix_match"
  },
  "Service": {
    "Service": "\${name.full}",
    "Failover": {
      "NearestN": 3,
      "Datacenters": ["gatewaytestc", "gatewaytesta"]
    }
  }
}
EOF
    ret=`kubectl exec -it $cluster-consul-server-0 -n consul-system -- curl --request GET http://127.0.0.1:8500/v1/query`
    done
}

function consul_join {
    $kubectl config use-context kind-gatewaytesta
    consul=`$kubectl get pods -n consul-system | grep consul-server | grep Running`;
    while [ -z "$consul" ]; do
      echo "Waiting for gatewaytesta consul pod";
      consul=`$kubectl get pods -n consul-system | grep consul-server | grep Running`;
      sleep 5;
    done
    $kubectl config use-context kind-gatewaytestc
    consul=`$kubectl get pods -n consul-system | grep consul-server | grep Running`;
    while [ -z "$consul" ]; do
      echo "Waiting for gatewaytestc consul pod";
      consul=`$kubectl get pods -n consul-system | grep consul-server | grep Running`;
      sleep 5;
    done
    # TODO: Again, if consul crashes, will it remember this join config and automatically
    # rejoin, or we have to monitor and rejoin ourselves ?
    $kubectl exec -it gatewaytestc-consul-server-0 -n consul-system -- consul join -wan $gatewaytesta_ip
}

function create_agent {
    name=$1
    agent=$2
    username=$3
    etchost_ip=$4
    etchost_name=$5

    docker run -d -it --user 0:0 --cap-add=NET_ADMIN --device /dev/net/tun:/dev/net/tun \
        -e NXT_GW_1_IP=$gatewaytesta_ip -e NXT_GW_1_NAME=gatewaytesta.nextensio.net \
        -e NXT_GW_2_IP=$gatewaytestc_ip -e NXT_GW_2_NAME=gatewaytestc.nextensio.net \
        -e NXT_GW_3_IP=$etchost_ip -e NXT_GW_3_NAME=$etchost_name \
        -e NXT_USERNAME=$username -e NXT_PWD=LetMeIn123 \
        -e NXT_AGENT=$agent -e NXT_CONTROLLER=$ctrl_ip:8080 \
        -e NXT_AGENT_NAME=$name \
        --network kind --name $name registry.gitlab.com/nextensio/agent/rust-agent:latest
}

function create_connector {
    name=$1
    agent=$2
    username=$3
    etchost_ip=$4
    etchost_name=$5

    docker run -d -it --user 0:0 --cap-add=NET_ADMIN --device /dev/net/tun:/dev/net/tun \
        -e NXT_GW_1_IP=$gatewaytesta_ip -e NXT_GW_1_NAME=gatewaytesta.nextensio.net \
        -e NXT_GW_2_IP=$gatewaytestc_ip -e NXT_GW_2_NAME=gatewaytestc.nextensio.net \
        -e NXT_GW_3_IP=$etchost_ip -e NXT_GW_3_NAME=$etchost_name \
        -e NXT_USERNAME=$username -e NXT_PWD=LetMeIn123 \
        -e NXT_AGENT=$agent -e NXT_CONTROLLER=$ctrl_ip:8080 \
        -e NXT_AGENT_NAME=$name -e CLIENT_ID=0oaz5lndczD0DSUeh4x6 -e IDP_URI=https://dev-635657.okta.com \
        --network kind --name $name registry.gitlab.com/nextensio/agent/go-agent:latest
}

function create_controller_clusters {
    image=$1
    if [ "$image" != "local" ];
    then
        download_controller_infra_images
        download_nextensio_controller
    fi

    # delete existing clusters
    $kind delete cluster --name controller

    create_controller
    # Find controller ip address
    ctrl_ip=`docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' controller-control-plane`
    bootstrap_controller $ctrl_ip
}

function create_gw_monitoring_clusters {
    image=$1
    if [ "$image" != "local" ];
    then
        download_cluster_infra_images
        download_nextensio_cluster
    fi

    # delete existing clusters
    $kind delete cluster --name gatewaytesta
    $kind delete cluster --name gatewaytestc
    $kind delete cluster --name monitoring

    create_cluster gatewaytesta
    create_cluster gatewaytestc
    # Find out ip addresses of gatewaytesta cluster and gatewaytestc cluster
    gatewaytesta_ip=`docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' gatewaytesta-control-plane`
    gatewaytestc_ip=`docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' gatewaytestc-control-plane`

    # Create dns entries inside kubernetes (coredns) for the gateway hostnames
    tmpf=$tmpdir/coredns.yaml
    cp coredns.yaml $tmpf
    sed -i "s/REPLACE_NODE1_IP/$gatewaytesta_ip/g" $tmpf
    sed -i "s/REPLACE_NODE1_NAME/gatewaytesta.nextensio.net/g" $tmpf
    sed -i "s/REPLACE_NODE2_IP/$gatewaytestc_ip/g" $tmpf
    sed -i "s/REPLACE_NODE2_NAME/gatewaytestc.nextensio.net/g" $tmpf

    # Configure the basic infrastructure elements in the cluster - like the loadbalancer,
    # coredns for DNS entries and the cluster manager itself
    bootstrap_cluster gatewaytesta $gatewaytesta_ip $ctrl_ip
    bootstrap_cluster gatewaytestc $gatewaytestc_ip $ctrl_ip

    # Finally, join the consuls in both clusters after ensuring their pods are Running
    consul_join

    # Configure consul in one cluster to query the remote cluster if local service lookup fails
    # Not sure if this needs to be done on both DCs, doing it anyways
    consul_query_config gatewaytesta
    consul_query_config gatewaytestc

    # Install bind to do dig and get SRV records
    $kubectl config use-context kind-gatewaytesta
    $kubectl exec -it gatewaytesta-consul-server-0 -n consul-system -- apk add bind-tools
    $kubectl config use-context kind-gatewaytestc
    $kubectl exec -it gatewaytestc-consul-server-0 -n consul-system -- apk add bind-tools

    $kubectl config use-context kind-controller
    ctrlpod=`$kubectl get pods -n default | grep nextensio-controller | grep Running`;
    while [ -z "$ctrlpod" ]; do
      ctrlpod=`$kubectl get pods -n default | grep nextensio-controller | grep Running`;
      echo "Waiting for controller pod to be Running";
      sleep 5;
    done
    # configure the controller with some default customer/tenant information
    echo "Configuring the controller, may take a few seconds"
    NEXTENSIO_CERT=../../testCert/nextensio.crt ./ctrl.py $ctrl_ip ../../testCert/nextensio.crt
    echo "Controller config done, going to create agents and connectors"

    # Create monitoring cluster for telemetry
    create_monitoring
    monitoring_ip=`docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' monitoring-control-plane`
  
    # Configure monitoring stuff (prometheus, thanos, grafana). This also install 
    # prometheus and thanos sidecar on all the clusters 
    # TODO: check monitoring cluster readiness
    bootstrap_monitoring $monitoring_ip $ctrl_ip $gatewaytesta_ip $gatewaytestc_ip
}

function create_agent_connector {
    image=$1
    if [ "$image" != "local" ];
    then
        download_nextensio_agents
    fi

    docker kill nxt_agent1; docker rm nxt_agent1
    docker kill nxt_agent2; docker rm nxt_agent2
    docker kill nxt_default1; docker rm nxt_default1
    docker kill nxt_default2; docker rm nxt_default2
    docker kill nxt_kismis_ONE; docker rm nxt_kismis_ONE
    docker kill nxt_kismis_TWO; docker rm nxt_kismis_TWO
    docker container prune -f
    create_agent nxt_agent1 true test1@nextensio.net
    create_agent nxt_agent2 true test2@nextensio.net
    create_connector nxt_default1 false default@nextensio.net 127.0.0.1 foobar.com
    create_connector nxt_default2 false default@nextensio.net 127.0.0.1 foobar.com
    create_connector nxt_kismis_ONE false v1.kismis@nextensio.net 127.0.0.1 kismis.org
    create_connector nxt_kismis_TWO false v2.kismis@nextensio.net 127.0.0.1 kismis.org
    nxt_agent1=`docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' nxt_agent1`
    nxt_agent2=`docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' nxt_agent2`
}

function create_all {
    image=$1
    if [ "$image" != "local" ];
    then
        # Download common infra images we need from docker hub
        download_common_images
    fi
    create_controller_clusters $1
    # People who want to test controller/UX might not want the data clusters, they
    # can set an environment variable to skip data clusters/agents etc..
    if [ "$CONTROLLER_ONLY" != "true" ];
    then
        create_gw_monitoring_clusters $1
        create_agent_connector $1
    fi
}

function save_env {
    echo "###########################################################################"
    echo "######Add the below two lines to /etc/hosts to access controller##########"
    echo "$ctrl_ip controller.nextensio.net"
    echo "$ctrl_ip server.nextensio.net"
    echo "######Then you can access controller UI at https://controller.nextensio.net/ ###"
    echo "##You can set a broswer proxy to $nxt_agent1:8181 to send traffic via nextensio##"
    echo "##OR You can set a broswer proxy to $nxt_agent2:8181 to send traffic via nextensio##"
    echo "##All the above information is saved in $tmpdir/environment for future reference##"
    echo "######You can access Thanos UI at http://$monitoring_ip:9092  ############"
    echo "######You can access Grafana UI at http://$monitoring_ip:3000  ############"
    echo "######Use http://thanos-querier:9092 as Grafana dashboard datasource ############"
    echo "######You can access Alert Mgr UI at http://$monitoring_ip:9093  ############"

    envf=$tmpdir/environment
    echo "gatewaytesta_ip=$gatewaytesta_ip" > $envf
    echo "gatewaytestc_ip=$gatewaytestc_ip" >> $envf
    echo "ctrl_ip=$ctrl_ip" >> $envf
    echo "monitoring_ip=$monitoring_ip" >> $envf
    echo "nxt_agent1=$nxt_agent1" >> $envf
    echo "nxt_agent2=$nxt_agent2" >> $envf
}

function main {
    # Check and prep our working directory - /tmp/nextensio-kind/
    kubefile=https://storage.googleapis.com/kubernetes-release/release/v1.21.2/bin/linux/amd64/kubectl
    mkdir $tmpdir;
    md5=`md5sum /tmp/nextensio-kind/kubectl|awk '{ print $1 }'`
    if [ "$md5" != "35213e0afae6a2015e8a7b2a318708d4" ]
    then
        # Download kubectl
        echo "downloading kubectl..."
        curl -fsL $kubefile -o $tmpdir/kubectl
        chmod +x $tmpdir/kubectl
    fi
    md5=`md5sum /tmp/nextensio-kind/istioctl|awk '{ print $1 }'`
    if [ "$md5" != "eed1be0f1b98a28bd9f0825dd8a6942e" ]
    then
        # Download istioctl
        echo "downloading istioctl..."
        istiofile=https://github.com/istio/istio/releases/download/1.10.2/istioctl-1.10.2-linux-amd64.tar.gz
        curl -fsL $istiofile -o $tmpdir/istioctl.tgz
        tar -xvzf $tmpdir/istioctl.tgz -C $tmpdir/
        chmod +x $tmpdir/istioctl
        rm $tmpdir/istioctl.tgz
    fi
    md5=`md5sum /tmp/nextensio-kind/kind|awk '{ print $1 }'`
    if [ "$md5" != "d20d60208676a13ff058eac2e67855f6" ]
    then
        curl -Lo $tmpdir/kind https://kind.sigs.k8s.io/dl/v0.11.1/kind-linux-amd64
        chmod +x $tmpdir/kind
    fi

    # Create everything!
    create_all $1
    # Display and save environment information
    save_env
}

function usage {
    echo "create.sh usage : this will print this usage message"
    echo "create.sh : this will download images from gitlab and create the entire topology"
    echo "create.sh local-image : this will expect all images to be in local docker and create the entire topology"
    echo "create.sh reset-agent : this will restart the agent docker"
    echo "create.sh reset-conn : this will restart the connector(s) docker(s)"
}

options=$1
case "$options" in
"")
    time main remote
    ;;
*usage)
    usage
    ;;
*local-image)
    time main local
    ;;
*reset-agent)
    source $tmpdir/environment
    docker kill nxt_agent1; docker rm nxt_agent1
    docker kill nxt_agent2; docker rm nxt_agent2
    docker container prune -f
    create_agent nxt_agent1 true test1@nextensio.net
    create_agent nxt_agent2 true test2@nextensio.net
    nxt_agent1=`docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' nxt_agent1`
    nxt_agent2=`docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' nxt_agent2`
    echo "##You can set a broswer proxy to $nxt_agent1:8181 to send traffic via nextensio##"
    echo "##OR You can set a broswer proxy to $nxt_agent2:8181 to send traffic via nextensio##"
    ;;
*reset-conn)
    source $tmpdir/environment
    docker kill nxt_default1; docker rm nxt_default1
    docker kill nxt_default2; docker rm nxt_default2
    docker kill nxt_kismis_ONE; docker rm nxt_kismis_ONE
    docker kill nxt_kismis_TWO; docker rm nxt_kismis_TWO
    docker container prune -f
    create_connector nxt_default1 false default@nextensio.net 127.0.0.1 foobar.com
    create_connector nxt_default2 false default@nextensio.net 127.0.0.1 foobar.com
    create_connector nxt_kismis_ONE false v1.kismis@nextensio.net 127.0.0.1 kismis.org
    create_connector nxt_kismis_TWO false v2.kismis@nextensio.net 127.0.0.1 kismis.org
    ;;
*)
    echo "Unknown option $options"  
    ;;
esac

