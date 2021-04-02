#!/usr/bin/env bash

export KOPS_FEATURE_FLAGS=AlphaAllowGCE
export GOOGLE_APPLICATION_CREDENTIALS=~/.google/key.json

PROJECT=nextensio-308919
CURPATH=`pwd`

export PATH=$PATH:$CURPATH/tools/bin:$CURPATH/tools/google-cloud-sdk/bin:$CURPATH/tools/istio/bin

allClusters=( gatewayuswest1 gatewayuscentral1 )

usage()
{
cat << EOF
usage: deploy.sh
    -c | --create     create kubernetes cluster
    -d | --delete     delete kubernetes cluster
    -h | --help
EOF
}

op=""
while [ "$1" != "" ]; do
    case $1 in
       -c | --create )
           shift
           op="-create"
       ;;
       -d | --delete )
           shift
           op="-delete"
       ;;
       -h | --help )
           usage
           exit 0
       ;;
       * )
           usage
           exit 1
    esac
    shift
done

if [ x$op == "x" ]; then
    usage
    exit 1
fi

cd tools
./init.sh $PROJECT
cd ..

cd kops
for t in "${allClusters[@]}"; do
    echo "./cluster.py $op $t"
    ./cluster.py $op $t
done
cd ..

exit 0
