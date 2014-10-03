import time,re,string
from starcluster.clustersetup import DefaultClusterSetup
from starcluster.logger import log
from pprint import pprint
 
#[plugin GlusterfsClientSetup]
#setup_class = gluster.GlusterfsClientSetup    - This class will install GlusterFS client ( fuse on the target nodes)

#[plugin glusterMounts]
#setup_class = gluster.glusterMount
#server = <ip address of one of the data cluster nodes>
#volumes = GlusterVolume1 , GlusterVolume2 ...  -  At this point we expect a single Volume
# Consider to add desired mount points per Gluster Volume At this point we expect a single MountPoint

 
class GlusterfsClientSetup(DefaultClusterSetup):
	def __init__(self):
		super(GlusterfsClientSetup, self).__init__()
		
	
	def install_glusterfs_packages(self, nodes):
		n = 0
		for node in nodes:
			result = node.ssh.execute("dpkg -l | grep glusterfs-client", ignore_exit_status=True)
			if result is None or len(result) == 0:
				node.ssh.execute("apt-get install python-software-properties", ignore_exit_status=True)
				node.ssh.execute("add-apt-repository -y ppa:semiosis/ubuntu-glusterfs-3.5", ignore_exit_status=True)
				node.ssh.execute("apt-get update", ignore_exit_status=True)
				n += 1
				self.pool.simple_job(node.apt_install, "glusterfs-client", jobid=node.alias)

		if n != 0:
			log.info("Installing glusterfs-client package on %s node(s)..." % n)
			self.pool.wait(n)
			
	def run(self, nodes, master, user, user_shell, volumes):
		
		self.ec2 = master.ec2
		log.info("Setting up glusterfs-clients")	
		self.install_glusterfs_packages(nodes)

	def on_add_node(self, new_node, nodes, master, user, user_shell, volumes):
		self.ec2 = master.ec2
		self.install_glusterfs_packages(nodes)                        
 
class glusterMount(DefaultClusterSetup):
     def __init__(self, server,volumes, mountpoint,filesystemtype):
          self.server = server
          self.volumes = volumes
          self.mountpoint = mountpoint
          if self.volumes:
              self.volumes= [volume.strip() for volume in volumes.split(',')]
          if filesystemtype =="glusterfs":
          	self.glusterfsMount = True
          else:
          	self.glusterfsMount = False    
 
     def run(self, nodes, master, user, user_shell, volumes):
          conn=master.ssh
          for node in nodes:
               nconn=node.ssh
               log.info("Running plugin on node %s " % node.alias)
 
               mounts = node.get_mount_map()
               for dev in mounts:
                    if mounts[dev]=="/mnt":
                          nconn.execute("umount /mnt")
                          nconn.execute('mount %s /tmp' % dev.replace("sd","xvd"))
                          nconn.execute('chmod 777 /tmp')
                          time.sleep(5)
 
               for volume in self.volumes:
                    if not nconn.path_exists(self.mountpoint):
                          log.info("Create mount point %s" % self.mountpoint)
                          nconn.execute("mkdir -p %s" % self.mountpoint)
 					if self.glusterfsMount:
                    	log.info("Mount glusterfs volume %s at %s  as glusterfs file system type" % (volume,self.mountpoint))
                    	nconn.execute('mount -t glusterfs %s:%s %s' % (self.server,volume,self.mountpoint))
                    else:
 						log.info("Mount glusterfs volume %s at %s  as NFS file system type" % (volume,self.mountpoint))
                    	nconn.execute('mount -t nfs -o nolock %s:%s %s' % (self.server,volume,self.mountpoint))
     
     def on_add_node(self, node, nodes, master, user, user_shell, volumes):
          conn=master.ssh
          for node in nodes:
               nconn=node.ssh
               mounts = node.get_mount_map()
               for dev in mounts:
                    log.info("Dev: %s mountpoint: %s" % (dev, mounts[dev]))
                    if mounts[dev][0]=="/mnt":
                          log.info("Unmount device mounted at /mnt: %s" % dev.replace("sd","xvd"))
                          nconn.execute("umount /mnt")
                          log.info("remount %s at /tmp" % dev.replace("sd","xvd"))
                          nconn.execute('mount %s /tmp' % dev.replace("sd","xvd"))
                          nconn.execute('chmod 777 /tmp')
 
 
          for volume in self.volumes:
               	if not nconn.path_exists(self.mountpoint):
                     log.info("Create mount point %s" % self.mountpoint)
                     nconn.execute("mkdir -p %s" % self.mountpoint)
 				if self.glusterfsMount:
                    	log.info("Mount glusterfs volume %s at %s  as glusterfs file system type" % (volume,self.mountpoint))
                    	nconn.execute('mount -t glusterfs  %s:%s %s' % (self.server,volume,self.mountpoint))
                else:
 						log.info("Mount glusterfs volume %s at %s  as NFS file system type" % (volume,self.mountpoint))
                    	nconn.execute('mount -t nfs -o nolock %s:%s %s' % (self.server,volume,self.mountpoint))