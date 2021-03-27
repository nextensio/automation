#!/usr/bin/env bash

GVER=333.0.0
OS=linux
ARCH=x86_64
GSDK=google-cloud-sdk-${GVER}-${OS}-${ARCH}.tar.gz
GURL=https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/${GSDK}

if [ -f .ginstalled ]; then
    echo "gloud already installed"
else
    echo "gcloud installation started..."
    if [ ! -f ${GSDK} ]; then
        curl -O ${GURL}
    fi
    rm -r -f google-cloud-sdk
    tar zxvf ${GSDK}
    cd google-cloud-sdk
    ./install.sh --quiet
    bin/gcloud auth activate-service-account --key-file ~/.google/key.json
    cd ..
    touch .ginstalled
    echo "gcloud installed"
fi

if [ -f .kinstalled ]; then
    echo "kops already installed"
    echo "kubectl already installed"
else
    mkdir -p bin
    curl -Lo kops https://github.com/kubernetes/kops/releases/download/$(curl -s https://api.github.com/repos/kubernetes/kops/releases/latest | grep tag_name | cut -d '"' -f 4)/kops-linux-amd64
    chmod +x ./kops
    mv ./kops ./bin/
    curl -Lo kubectl https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl
    chmod +x ./kubectl
    mv ./kubectl ./bin/
    touch .kinstalled
    echo "kops installed"
    echo "kubectl installed"
fi

exit 0
