#!/bin/bash
#
# Oct 2 2014 - RA Added Encryption of bricks 
# Oct 9 2014 - RA added a parameter $1 to determine encrypy / plain option
#              ./cfn-setup-gluster  encrypt .. 
# Oct 29 2014 - RA adding Tags : Generating a name to the Instane , Generate a ApplicationRole=FileSystemHead , FSType=GlusterFS
#

# DEBUG uncomment next line
set -x
if [ $# -eq 0 ]; then
        echo "No arguments supplied , expected encryp/plain as first argument. default will be encryptd"
        encrypt="encrypt"
else
        echo " will assign the input value: $1"
        encrypt=$1
fi

# Load enviroment variables
. /etc/profile

# Source cfn data
. /etc/cfn/bash.env

# Update to latest version on aws-ec2-apitools
yum -y install aws-apitools-ec2

# Get my instance-id
MY_INSTANCE_ID=$(curl --silent http://169.254.169.254/latest/meta-data/instance-id)
My_INSTANCE_LOCAL_IP=$(curl --silent http://169.254.169.254/latest/meta-data/local-ipv4)
MY_CFN_STACK_NAME=${cfn_stack_name}
# Create Instance Type
ec2-create-tags $MY_INSTANCE_ID  --tag Name="$MY_CFN_STACK_NAME-GlusterFSHead-$My_INSTANCE_LOCAL_IP"
ec2-create-tags $MY_INSTANCE_ID  --tag "ApplicationRole=NasHead"
ec2-create-tags $MY_INSTANCE_ID  --tag "FSType=GlusterFS"
ec2-create-tags $MY_INSTANCE_ID  --tag "MountVolume=glusterfs"

# Format drives (anything that is not sda is made part of a striped LVM volume and used a the brick for the instance)
DEVS=$(ls /dev/sd? | grep -v sda)
NUM_DEVS=0
for d in $DEVS; do
  dd if=/dev/zero of=${d} bs=32k count=1
  parted -s ${d} mklabel msdos
  parted -s ${d} 
  parted -s -a optimal ${d} mkpart primary 1MB 100%
  parted -s ${d} set 1 raid on
  let NUM_DEVS++
done
# sleep 10 seconds to let partitions settle (bug?)
sleep 10

# Setup /etc/mdadm.conf
cat > "/etc/mdadm.conf" <<'EOF'
DEVICE partitions
HOMEHOST localhost.localdomain
AUTO +1.x +imsm -all
EOF

PARTITIONS=$(ls /dev/sd?1 | grep -v sda)
mdadm --create /dev/md/brick --raid-devices=$NUM_DEVS --level=0 --name=brick $PARTITIONS
# 
# Create Export point
mkdir -p /export/$MY_INSTANCE_ID
# 
# Support Encryption
# Update to the latest version of cryptsetup package.
#
if [ "$encrypt" = "encrypt" ]; then
	echo " Taking the Encryption path"
	yum -y install cryptsetup
	# Creating the cryptFS
	#
	mkdir -p /root/keystore
	mount /dev/ram1 /root/keystore
	dd if=/dev/urandom of=/root/keystore/keyfile bs=1024 count=4
	chmod 0400 /root/keystore/keyfile
	cryptsetup -q luksFormat /dev/md/brick /root/keystore/keyfile
	cryptsetup -d /root/keystore/keyfile luksOpen /dev/md/brick securebrick
fi
mdadm --detail --scan >> /etc/mdadm.conf
if [ "$encrypt" = "encrypt" ]; then
	echo " Creating Encrypted file system"
	mkfs.xfs -i size=512 /dev/mapper/securebrick
	echo "/dev/mapper/securebrick /export/$MY_INSTANCE_ID xfs noatime,nodiratime 0 0" >> /etc/fstab
else
	echo " Creating None Encrypted file system"
	mkfs.xfs -i size=512 /dev/md/brick
	echo "/dev/md/brick /export/$MY_INSTANCE_ID xfs noatime,nodiratime 0 0" >> /etc/fstab
fi


mount -v /export/$MY_INSTANCE_ID

# Rebuild initrd to support MD devices
mkinitrd --force -v /boot/initramfs-`uname -r`.img `uname -r`

# Fetch Gluster repo and install server software
wget -P /etc/yum.repos.d http://download.gluster.org/pub/gluster/glusterfs/LATEST/EPEL.repo/glusterfs-epel.repo
sed -i 's/$releasever/6Server/g' /etc/yum.repos.d/glusterfs-epel.repo
# Install glusterfs server 
yum -y install glusterfs-server.x86_64
modprobe fuse
# Remove RDMA support (less error messages)
sed -i 's/,rdma//' /etc/glusterfs/glusterd.vol
# Start the service
service glusterd start

# Loop to detect "running" instances
function ec2_describe_stack ()
{
 ec2-describe-instances --region ${cfn_region} --show-empty-fields --filter tag:aws:cloudformation:stack-name=${cfn_stack_name} --filter tag:aws:cloudformation:logical-id=GlusterFleet
}
RUNNING_INSTANCES=$(ec2_describe_stack | grep running | wc -l)
iter=0
while [ $cfn_instances -gt $RUNNING_INSTANCES ]; do
  if [ $iter -gt 10 ]; then
    echo "ERROR: Failed to detected all expected instances."
    exit 1
  fi
  sleep 30
  RUNNING_INSTANCES=$(ec2_describe_stack | grep running | wc -l)
  let iter++
done

INSTANCES=$(ec2_describe_stack | grep running | awk '{print $2}')

# Loop to detect all instances are healthy
function ec2_describe_stack_status ()
{
  ec2-describe-instance-status --region ${cfn_region} --filter instance-status.reachability=passed $*
}

HEALTHY=$(ec2_describe_stack_status ${INSTANCES} | grep INSTANCESTATUS | wc -l)
iter=0
while [ $cfn_instances -gt $HEALTHY ]; do
  if [ $iter -gt 10 ]; then
    echo "ERROR: Failed to detected(healthy) all expected instances."
    exit 1
  fi
  sleep 30
  HEALTHY=$(ec2_describe_stack_status ${INSTANCES} | grep INSTANCESTATUS | wc -l)
  let iter++
done

# Annoying but required sleep to make sure everything is running
sleep 60

# Work out who will be sudo master for the trusted storage pool
MASTER=0
SORTED_INSTANCE_ID=$(ec2_describe_stack | grep running | awk '{print $2}' | sort | tail -1)
if [ "$MY_INSTANCE_ID" == "$SORTED_INSTANCE_ID" ]; then
  MASTER=1
fi

# Check if in VPC
MAC=$(curl --silent http://169.254.169.254/latest/meta-data/mac)
VPC_CHECK=$(curl --silent http://169.254.169.254/latest/meta-data/network/interfaces/macs/$MAC/vpc-id)
VPC_TEST=$?
if [ $VPC_TEST -eq 0 ]; then
  # Host is in VPC
  HOST_IPS=$(ec2_describe_stack | grep running | awk '{print $18}')
  for IP in $HOST_IPS; do
    HOST=$(echo $IP|awk -F '.' 'BEGIN{OFS="-";} {print "ip",$1,$2,$3,$4}')
    echo "$IP  $HOST" >> /etc/hosts
  done
  if [ $MASTER -eq 1 ]; then
    function timestamp_to_seconds ()
    {
      DATETIME=$(echo $1 | cut -d'+' -f1)
      TIMESTAMP=$(date --date="$DATETIME" +%s)

      echo $TIMESTAMP
    }
    # Saftey check to make sure a 2nd master is not created later in the life of the stack
    MY_LAUNCH_TIME=$(timestamp_to_seconds $(ec2_describe_stack | grep running | grep ${MY_INSTANCE_ID} | awk '{print $11}'))
    OTHERS_LAUNCH_TIME=$(timestamp_to_seconds $(ec2_describe_stack | grep running | grep -v ${MY_INSTANCE_ID} | awk '{print $11}' | tail -1))
    DELTA=$((MY_LAUNCH_TIME - OTHERS_LAUNCH_TIME))
    if [ $DELTA -gt 901 ]; then
      echo "This is a new master but the other instances have already been running for over 15 minutes!"
      echo "It is most likely a new launch from auto-scaling and should be manually added."
      exit
    fi

    # This is the sudo master and should probe the other hosts
    OTHER_HOST_IPS=$(ec2_describe_stack | grep running | grep -v ${MY_INSTANCE_ID} | awk '{print $18}')
    for IP in $OTHER_HOST_IPS; do
      gluster peer probe $IP
    done
    BRICKS=$(ec2_describe_stack | grep running | awk 'BEGIN{OFS=":"} {print $18,"/export/"$2}')
    case $cfn_fs_type in
      distributed)
        gluster volume create glusterfs transport tcp $BRICKS force
        ;;
      replicated-*)
        COUNT=$(echo $cfn_fs_type | cut -d'-' -f2)
        gluster volume create glusterfs transport tcp replica $COUNT $BRICKS force
        ;;
      striped)
        gluster volume create glusterfs transport tcp stripe $cfn_instances $BRICKS force
        ;;
      distributed-striped-*)
        COUNT=$(echo $cfn_fs_type | cut -d'-' -f3)
        gluster volume create glusterfs transport tcp stripe $COUNT $BRICKS  force
        ;;
      *)
        echo "Failed to match cfn_fs_type: $cfn_fs_type"
        exit 1
        ;;
    esac
    # Start the volume
    gluster volume start glusterfs
  fi
else
  # Host is non-VPC(or error?)
  echo "ERROR: Only supported in a VPC environment"
  exit 1
fi

exit
