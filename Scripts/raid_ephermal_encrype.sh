#!/bin/bash
#
# This will detect  ephemeral drives on an EC2 instance , bundle them as alogical volume and
# will set them as encrypted volume. It should be run early on the first boot of the system.
#
# Beware, This script is NOT fully idempotent.
#
RC=0
# Add packages as needed :
echo "Installing xfsprogs"
UPDATEP=$(apt-get -y install xfsprogs)
echo "Installing lvm2"
UPDATEP=$(apt-get -y install lvm2)
echo "Installing cryptsetup"
UPDATEP=$(apt-get -y install cryptsetup-bin)

mkdir -p /scratch
chmod 1777 /scratch

METADATA_URL_BASE="http://169.254.169.254/2012-01-12"
 
# Configure Raid - take into account xvdb or sdb
root_drive=`df -h | grep -v grep | awk 'NR==2{print $1}'`
 
if [ "$root_drive" == "/dev/xvda1" ]; then
echo "Detected 'xvd' drive naming scheme (root: $root_drive)"
DRIVE_SCHEME='xvd'
else
echo "Detected 'sd' drive naming scheme (root: $root_drive)"
DRIVE_SCHEME='sd'
fi
 
# figure out how many ephemerals we have by querying the metadata API, and then:
# - convert the drive name returned from the API to the hosts DRIVE_SCHEME, if necessary
# - verify a matching device is available in /dev/
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
        DEVS="$DEVS $device_path"
        ephemeral_count=$((ephemeral_count + 1 ))
    else
    echo "Ephemeral disk $e, $device_path is not present. skipping"
    fi
done
 
if [ "$ephemeral_count" = 0 ]; then
echo "No ephemeral disk detected. exiting"
exit 0
fi

# ephemeral0 is typically mounted for us already. umount it here
umount /mnt

NUM_DEVS=0
for d in $DEVS; do
  d=${d}
  # overwrite first few blocks in case there is a filesystem
  sudo dd if=/dev/zero of=${d} bs=32k count=1
  parted -s ${d} mklabel msdos
  parted -s ${d}
  parted -s -a optimal ${d} mkpart primary 1MB 100%
  parted -s ${d} set 1 lvm on
  let NUM_DEVS++
  PARTITIONS="${d}1 $PARTITIONS"
done
echo "Partitions : $PARTITIONS"

pvcreate $PARTITIONS
vgcreate vg.01 $PARTITIONS
lvcreate -i $NUM_DEVS -I 64 -l 100%FREE -n lv_ephemeral vg.01
  mkfs -q /dev/ram1 1024
  mkdir -p /root/keystore
  mount /dev/ram1 /root/keystore
  dd if=/dev/urandom of=/root/keystore/keyfile bs=1024 count=4
  chmod 0400 /root/keystore/keyfile
  cryptsetup -q luksFormat /dev/vg.01/lv_ephemeral /root/keystore/keyfile
  cryptsetup -d /root/keystore/keyfile luksOpen /dev/vg.01/lv_ephemeral ephemeral_luks
  mkfs.xfs /dev/mapper/ephemeral_luks
  mount -v -t xfs -o noatime,nodiratime /dev/mapper/ephemeral_luks /scratch
chmod 1777 /scratch
