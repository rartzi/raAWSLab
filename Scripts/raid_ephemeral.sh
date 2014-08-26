#!/bin/bash
#
# this script will attempt to detect any ephemeral drives on an EC2 node and create a RAID-0 stripe
# mounted at /mnt. It should be run on the first boot of an instance.
#
# This Script is still under development and should be treated as such
#
#
# Known Bugs Aug 24 2014
#
#  Ubuntu MDADM installation does not pass as it is trying to install Postfix ( some kind of email notifications ) which goes into interactive more
#  Ubunto umount command does not have the option of umount -A - to release all target FS on devices we will have to look at :
#
#
METADATA_URL_BASE="http://169.254.169.254/2012-01-12"

# Install MDAM - It is now the standard RAID management tool and should be found in any modern distribution
os_type=`cat /etc/issue | grep -o -w 'Amazon\|Ubuntu'`
if [ "$os_type" == "Amazon" ]; then
        yum -y -d0 install mdadm curl
else
#        Still have issues here with mdadm silent install as it tries to install postfix which opens dialog
        if  [ "$os_type" == "Ubuntu" ]; then
                apt-get -y install mdadm
        fi
fi

# Configure Raid: 
# Step 1:  figure out the device naming scheme. 
root_drive=`df -h | grep -v grep | awk 'NR==2{print $1}'`
if [ "$root_drive" == "/dev/xvda1" ]; then
  echo "Detected 'xvd' drive naming scheme (root: $root_drive)"
  DRIVE_SCHEME='xvd'
else
  echo "Detected 'sd' drive naming scheme (root: $root_drive)"
  DRIVE_SCHEME='sd'
fi

# figure out how many ephemerals we have by querying the metadata API, and then:
#  - convert the drive name returned from the API to the hosts DRIVE_SCHEME, if necessary
#  - verify a matching device is available in /dev/
drives=""
ephemeral_count=0
ephemerals=$(curl --silent $METADATA_URL_BASE/meta-data/block-device-mapping/ | grep ephemeral)
for e in $ephemerals; do
  echo "Probing $e .."
  device_name=$(curl --silent $METADATA_URL_BASE/meta-data/block-device-mapping/$e)
  # might have to convert 'sdb' -> 'xvdb'
  device_name=$(echo $device_name | sed "s/sd/$DRIVE_SCHEME/")
  device_path="/dev/$device_name"

  # test that the device actually exists since you can request more ephemeral drives than are available
  # for an instance type and the meta-data API will happily tell you it exists when it really does not.
  if [ -b $device_path ]; then
    echo "Detected ephemeral disk: $device_path"
    drives="$drives $device_path"
    ephemeral_count=$((ephemeral_count + 1 ))
  else
    echo "Ephemeral disk $e, $device_path is not present. skipping"
  fi
done

if [ "$ephemeral_count" = 0 ]; then
  echo "No ephemeral disk detected. exiting"
  exit 0
fi

# Unmound all ephemeral disks if mounted on this instance
# this does not work for Ubunto as it umount command does not support -A option.
for drive in $drives; do
  umount -A $drive
done

# overwrite first few blocks in case there is a filesystem, otherwise mdadm will prompt for input
for drive in $drives; do
  dd if=/dev/zero of=$drive bs=4096 count=1024
done

partprobe
mdadm --create --verbose /dev/md0 --level=0 -c256 --raid-devices=$ephemeral_count $drives
echo DEVICE $drives | tee /etc/mdadm.conf
mdadm --detail --scan | tee -a /etc/mdadm.conf
blockdev --setra 65536 /dev/md0
mkfs -t ext4 /dev/md0
mount -t ext4 -o noatime /dev/md0 /mnt

# Remove xvdb/sdb from fstab
chmod 777 /etc/fstab
sed -i "/${DRIVE_SCHEME}b/d" /etc/fstab

# Make raid appear on reboot
echo "/dev/md0 /mnt ext4 noatime 0 0" | tee -a /etc/fstab