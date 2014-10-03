#!/bin/bash
#cp /usr/local/root/etc/* /etc
#cp /usr/local/root/home/root/.bash* /root
chown ngs:ngs /ngs
cp /usr/local/root/home/ngs/.profile /home/ngs
cp /usr/local/root/home/ngs/.bashrc /home/ngs
rm -rf /etc/alternatives/java
ln -s /usr/lib/jvm/java-7-openjdk-amd64/jre/bin/java /etc/alternatives/java
apt-get -y install openjdk-7-jdk