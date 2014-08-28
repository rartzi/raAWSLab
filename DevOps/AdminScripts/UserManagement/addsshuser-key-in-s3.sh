#!/bin/bash
#
#  This script is meant to be run on an EC2instance and add a user and it's ssh public key.
#  for example ec2-user / ubuntu
#  running the script, the use will be able to ssh into the machine with his key.
#
#  Assumptions:
#			RSA key pairs were created ( ssh-keygen -t rsa )
# 			This script and the public Key files were uploaded to the initial instance user
# 			Run the script under sudo 
#
if [ $# -lt 2 ]; then
	echo ""
	echo ""	
	echo " Usage:   sudo $0 UserID "
	echo ""
	echo " example : sudo  $0  Ronen ./Test/TestKey.pub" 
	echo "-------------------------------------------------------"
	echo " This script is meant to be run on an EC2instance and add a user and it's ssh public key."
	echo " running the script, the use will be able to ssh into the machine with his key."
	echo "" 
	echo "Assumptions:"
	echo "RSA key pairs were created ( ssh-keygen -t rsa )"
	echo "user public key is transfered to S3 bucket:  /RDI-DevOps/PublickKeys/userid.pub and made public"
	echo "Run the script under sudo " 
  exit 1
fi
user=$1
path_to_public_key=$2
echo $user
echo $path_to_public_key
adduser $user
mkdir /home/$user/.ssh
chmod 700 /home/$user/.ssh
aws s3 cp s3://RDI-DevOps/PublicKeys/$user.pub
cat $user.pub> /home/$user/.ssh/authorized_keys
chmod 600 /home/$user/.ssh/authorized_keys
chown $user /home/$user/.ssh/authorized_keys
chown $user:ec2-user /home/$user/.ssh
echo "Done: check that you can ssh as $user with your private key" 