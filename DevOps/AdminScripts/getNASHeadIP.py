#!/usr/bin/python
# 
#  11/1/2014 Ronen Artzi
# 
#  This script find a NAS head in a certain VPC and create or append to yml file that can be used to later on subsitute values in 
#  Starclusetr/other erb template files. The Scripts retunrns the NAsHead private IP.
#
#   This scripts find the NasHead Ip for an instance that has a certain :
#   If more than one are find , the fist NasHead Instance is being used to retrieve it's private IP.
#
#   ApplicationRole: NasHead , 
#   FSType :  default is GlusterFS  ( -f is the option  )
#   ConfigTypeName: default is   ( -t is the option ) - for the key name in the yml file
#   VPCID  ( -v is the option ) - the VPC where the NAS hed is to be searched at
#
import sys, getopt
import boto

def main(argv):
	vpcid = 'vpc-46e35823'
	outputfile = 'values.yml'
	filesystemtype="GlusterFS"
	configtagname='gluster_server_node_ip'
	try:
		opts, args = getopt.getopt(argv,"h:v:o:t:f",["help","vpcid=","ofile=","tagname=","filesystemtype=" ])
	except getopt.GetoptError:
		print 'test.py -v <vpc_id> -o <outputfile> -f <FileSystemType> -t <configtag>'
		sys.exit(2)
#   if len(sys.argv)<2:
#   		print 'test.py -t <config_tag_name> -v <vpc_id> -o <outputfile>'
#		sys.exit(2)
	for opt, arg in opts:
		if opt == '-h':
#			print 'test.py -t <config_tag_name> -v <vpc_id> -o <outputfile> -t <tagname>'
			sys.exit()
		elif opt in ("-o", "--ofile"):
#			print " -o "+arg
			outputfile = arg
		elif opt in ("-v", "--vpcid"):
#			print " -v "+arg
			vpcid = arg
		elif opt in ("-f", "--fstype"):
#			print " -f "+arg
			filesystemtype = arg
		elif opt in ("-t", "--vonfigtag"):
			print " -t "+arg
			configtagname = arg

	print 'Output file is:"', outputfile , " vpc : " , vpcid , " File system Type: ",filesystemtype , " ConfigTagName: ",configtagname
	ec2 = boto.connect_ec2()
	instances = [i for r in ec2.get_all_instances(filters={"tag:FSType": filesystemtype ,"tag:ApplicationRole": "NasHead" , "vpc_id": vpcid }) for i in r.instances]
	try:
		instance = instances[0]
   		f = open( outputfile , 'a')
   		f.write ('  '+configtagname+': '+str(instance.private_ip_address)+'\n')
   		f.close()
	except:
   		print "No NasHeadFound"
   		sys.exit(99)

if __name__ == "__main__":
   main(sys.argv[1:])
