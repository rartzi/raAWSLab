#!/bin/sh

# Some improved network settings for higher traffic

# Enable jumbo frames if instance type supports 10gE
enable_jumbo_frames ()
{
  ifconfig eth0 mtu 9000
}

INSTANCE_TYPE=$(curl --silent http://169.254.169.254/latest/meta-data/instance-type)
if [ "$INSTANCE_TYPE" == "cc2.8xlarge" ]; then
  enable_jumbo_frames
elif [ "$INSTANCE_TYPE" == "cg1.4xlarge" ]; then
  enable_jumbo_frames
elif [ "$INSTANCE_TYPE" == "hi1.4xlarge" ]; then
  enable_jumbo_frames
elif [ "$INSTANCE_TYPE" == "hs1.8xlarge" ]; then
  enable_jumbo_frames
fi

# Enable some general improvement to the network stack
/sbin/sysctl -q -w net.core.netdev_max_backlog=250000
/sbin/sysctl -q -w net.core.rmem_max=16777216
/sbin/sysctl -q -w net.core.wmem_max=16777216
/sbin/sysctl -q -w net.core.rmem_default=16777216
/sbin/sysctl -q -w net.core.wmem_default=16777216
/sbin/sysctl -q -w net.core.optmem_max=16777216
/sbin/sysctl -q -w net.ipv4.tcp_mem="16777216 16777216 16777216"
/sbin/sysctl -q -w net.ipv4.tcp_rmem="4096 87380 16777216"
/sbin/sysctl -q -w net.ipv4.tcp_wmem="4096 65536 16777216"

exit