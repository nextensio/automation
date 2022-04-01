#!/usr/bin/env bash

# Become a Certificate Authority

# Generate private key
openssl genrsa -des3 -passout pass:"Nextensio123" -out nextensio.key 2048
# Generate root certificate
openssl req -x509 -new -passin pass:"Nextensio123" -config openssl.conf -nodes -key nextensio.key -sha256 -days 825 -out nextensio.crt

# Now in chrome, under Privacy and Security, go to 'security'-->'Manage certificates' and
# selet the 'Authorities' tab and click "Import" and import the nextensio.crt file
