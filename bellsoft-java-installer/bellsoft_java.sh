#!/bin/bash

# https://bell-sw.com/pages/downloads/

#VERSION=21.0.6+10
#FOLDER=jdk-25.0.1

VERSION=25.0.1+13
FOLDER=jdk-25.0.1

cd /tmp
wget https://download.bell-sw.com/java/$VERSION/bellsoft-jdk$VERSION-linux-amd64.tar.gz
tar xvfz bellsoft-$VERSION-linux-amd64.tar.gz
cd $FOLDER

mkdir -p /server/Java/$FOLDER
mv * /server/Java/$FOLDER
rm -rf /tmp/$FOLDER*
