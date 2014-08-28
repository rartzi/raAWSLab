#!/bin/bash
#
#  This script is meant to be run on the local admin machine and will push user public key to an 
#  running ec2 instance.
#  The admin is pushing the addsshuser script and the provided public key.
#  The admin will have to run the addsshuser script on the instance to allow ssh to the current user
#
#  Assumptions:
#			User had generated RSA key pairs ( ssh-keygen -t rsa ) and had provided the public key to the administrator
# 	
#
if [ $# -lt 5 ]; then
	echo ""
	echo ""	
	echo "Usage:   sudo $0 instance_access_ssh_key  ec2_user_name ec2_dns_machine_string    path_to_rdi_scripts"
	echo ""
	echo "instance_access_ssh_key	-	full path to the instance ssh access key "
	echo "ec2_user_name 	-	initial ec2 user name ( for exmple ec2-user / ubunto depends on the machine type "
	echo "ec2_dns_machine_string	-	full EC@2instance DNSname"
	echo "path_to_rdi_scripts	-	full path to RDI AWS Scripts "
	echo  ""
	echo " example : sudo  $0  .aws/Keys/mystarkey.pem   ec2-user  ec2-54-166-214-209.compute-1.amazonaws.com  ./Test/TestKey.pub /rdi/scripts" 
	echo "-------------------------------------------------------"
	echo "" 
  exit 1
fi
instance_access_ssh_key=$1
ec2_initial_user_name=$2
ec2_dns_machine_string=$3user_ssh_public_key=$4
path_to_rdi_scripts=$5
scp -i $instance_access_ssh_key $path_to_rdi_scripts/addsshuser.sh $ec2_initial_user_name@ec2_dns_machine_string:/home/$ec2_initial_user_name/