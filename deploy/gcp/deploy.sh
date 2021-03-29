#!/usr/bin/env bash

export KOPS_FEATURE_FLAGS=AlphaAllowGCE
export GOOGLE_APPLICATION_CREDENTIALS=~/.google/key.json

PROJECT=nextensio-308919
CURPATH=`pwd`

export PATH=$PATH:$CURPATH/tools/bin:$CURPATH/tools/google-cloud-sdk/bin

cd tools
./init.sh
cd ..

cd kops
./cluster.py
cd ..
