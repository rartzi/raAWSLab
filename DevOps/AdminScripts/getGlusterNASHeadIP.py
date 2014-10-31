#!/usr/bin/python
#
#  This script expect to get as an argument the -o outputfile
#  it will append the gluster_server_node_ip if found at the end of the yml file.
#
#   This scripts atakes the first instance that indicate it is A Nas Head and has a FS Type of GlusterFS
#
import sys, getopt
import boto

def main(argv):
   inputfile = ''
   outputfile = ''
   try:
      opts, args = getopt.getopt(argv,"hi:o:",["ifile=","ofile="])
   except getopt.GetoptError:
      print 'test.py -i <inputfile> -o <outputfile>'
      sys.exit(2)
   for opt, arg in opts:
      if opt == '-h':
         print 'test.py  -o <outputfile>'
         sys.exit()
      elif opt in ("-o", "--ofile"):
         outputfile = arg
#   print 'Output file is "', outputfile
   ec2 = boto.connect_ec2()
   instances = [i for r in ec2.get_all_instances(filters={"tag:FSType": "GlusterFS" ,"tag:ApplicationRole": "NasHead" }) for i in r.instances]
   instance = instances[0]
   f = open( outputfile , 'a')
   f.write ('  gluster_server_node_ip: '+str(instance.private_ip_address)+'\n')
   f.close()

if __name__ == "__main__":
   main(sys.argv[1:])