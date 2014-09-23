from starcluster.clustersetup import DefaultClusterSetup
from starcluster.config import StarClusterConfig
from starcluster.logger import log
from starcluster import utils
from boto import ec2
import time

class GlusterfsSetup(DefaultClusterSetup):
	def __init__(self, name, mode, transport, bricks, ebs_size, mount_path, encrypt):
		super(GlusterfsSetup, self).__init__()
		self.name = name
		self.mode = mode
		self.transport = transport
		self.bricks = bricks
		self.ebs_size = ebs_size
		self.mount_path = mount_path
        	self.encrypt = True if encrypt=="True" else False

        	if self.bricks:
			self.bricks = [brick.strip() for brick in bricks.split(' ')]
			
		# set a different lgo directory so that gazzang-secure can encrypt /var/log without stopping
		# the glusterfs volume everytime a brick is being secured
		self.glusterfs_logdir = "/var/glusterfs-log"
	
	def install_glusterfs_packages(self, nodes):
		n = 0
		for node in nodes:
			result = node.ssh.execute("dpkg -l | grep glusterfs-server", ignore_exit_status=True)
			if result is None or len(result) == 0:
				n += 1
				self.pool.simple_job(node.apt_install, "glusterfs-server glusterfs-client", jobid=node.alias)

		if n != 0:
			log.info("Installing glusterfs packages on %s node(s)..." % n)
			self.pool.wait(n)
			
	def mount_glusterfs_volume(self, nodes):
		for node in nodes:
			self.pool.simple_job(self._mount_glusterfs_volume, (node), jobid=node.alias)

		log.info("Mounting glusterfs volume 'master:%s' on %s nodes(s)..." % (self.name,len(nodes)))
		self.pool.wait(len(nodes))
	
	def is_glusterfs_volume_present(self, master, name):
		status = master.ssh.execute("gluster volume info %s | grep Status" % name, ignore_exit_status=True, raise_on_failure=False)
		if status is not None and len(status) >= 1:
			return True
		
		return False

	def add_node_to_volume(self, master, node, name, bricks):
		log.info("Adding %s bricks to %s volume..." % (node.alias, name))
	
		# Attach node to master
		master.ssh.execute("gluster peer probe %s" % node.alias)
	
		# Add bricks to volume
		for brick in bricks:
			master.ssh.execute("gluster volume add-brick %s %s <<< y" % (name, brick))
			
		# Rebalance volume
		self.wait_rebalance(master, self.name)
				
	def remove_node_from_volume(self, master, node, name, bricks):
		log.info("Removing %s bricks from %s volume..." % (node.alias, name))
		
		# Remove bricks from the volume
		for brick in bricks:
			master.ssh.execute("gluster volume remove-brick %s %s <<< y" % (name, brick))
			
		# Detach the node from the master
		master.ssh.execute("gluster peer detach %s" % node.alias)
		
		# Rebalance volume
		self.wait_rebalance(master, self.name)
	
	def get_instance_zone(self, node):
		zone = node.ssh.execute("curl http://169.254.169.254/latest/meta-data/placement/availability-zone 2>/dev/null")
		return node.ec2.get_zone(zone).name
			
	def run(self, nodes, master, user, user_shell, volumes):
		self.ec2 = master.ec2

		log.info("Setting up glusterfs volume: %s" % self.name)
		
		self.install_glusterfs_packages(nodes)
		if self.is_glusterfs_volume_present(master, self.name):
			log.info("Volume %s is already present" % self.name)
			return

		# prepare brick nodes
		bricks_list = []
		for brick in self.bricks:
			if len(brick.split(":")) != 2:
				log.error("Invalid brick format: %s" % brick)
				return

			brick_node, brick_device = brick.split(":")[0], brick.split(":")[1]
			if not brick_node or not brick_device:
				log.error("Invalid brick format: %s" % brick)
				return

			node = self._get_node_object(brick_node, nodes)

			# if brick_device is EBS, then we request a new volume to Amazon
			if brick_device == "EBS":
				zone = self.get_instance_zone(node)
				# set EBS volume type to be the new gp2 SSD type`	
				volumetype = 'gp2'
				volume = self._create_ec2_volume(self.name, self.ebs_size, zone, volumetype , self.encrypt)
				if not volume:
					log.error("Cannot request EBS volume to Amazon")

				mount_path = "/var/glusterfs/bricks/%s/%s" % (self.name, volume.id)

				self._attach_and_format_volume(node, volume)
				self._mount_volume(node, volume, mount_path)
			elif brick_device[0:5] == "/dev/":
				mount_path = "/var/glusterfs/bricks/%s/%s" % (self.name, brick_device[5:])

				self._format_device(node, brick_device)
				self._mount_device(node, brick_device, mount_path)
			elif brick_device[0] == "/":
				mount_path = brick_device
			else:
				log.error("Invalid brick format: %s" % brick)
				return

			bricks_list.append("%s:%s" % (brick_node,mount_path))
			master.ssh.execute("gluster peer probe %s" % brick_node)
			node.ssh.execute("mkdir -p %s/bricks" % self.glusterfs_logdir)

		# create/start glusterfs volume on master
		self.create_volume(master, self.name, self.mode, self.transport, bricks_list)
		self.start_volume(master, self.name)
		
		# share glusterfs volume on all nodes
		self.share_volume(master, nodes, self.name)
		
		# mount the volume on all nodes
		self.mount_glusterfs_volume(nodes)

	def on_add_node(self, new_node, nodes, master, user, user_shell, volumes):
		self.ec2 = master.ec2
		
		self.install_glusterfs_packages(nodes)
		
		# check if this node is part of a glusterfs brick
		bricks_list = []
		for brick in self.bricks:
			if len(brick.split(":")) != 2:
				log.error("Invalid brick format: %s" % brick)
				return

			brick_node, brick_device = brick.split(":")[0], brick.split(":")[1]
			if not brick_node or not brick_device:
				log.error("Invalid brick format: %s" % brick)
				return
				
			# Look for bricks linked to this new node only
			if new_node.alias != brick_node:
				continue
			
			# if brick_device is EBS, then we request a new volume to Amazon
			if brick_device == "EBS":
				zone = self.get_instance_zone(new_node)
				volume = self._create_ec2_volume(self.name, self.ebs_size, zone , self.encrypt )
				if not volume:
					log.error("Cannot request EBS volume to Amazon")

				mount_path = "/var/glusterfs/bricks/%s/%s" % (self.name, volume.id)

				self._attach_and_format_volume(new_node, volume)
				self._mount_volume(new_node, volume, mount_path)
			elif brick_device[0:5] == "/dev/":
				mount_path = "/var/glusterfs/bricks/%s/%s" % (self.name, brick_device[5:])

				self._format_device(new_node, brick_device)
				self._mount_device(new_node, brick_device, mount_path)
			elif brick_device[0] == "/":
				mount_path = brick_device
			else:
				log.error("Invalid brick format: %s" % brick)
				return
				
			bricks_list.append("%s:%s" % (brick_node, mount_path))
			master.ssh.execute("gluster peer probe %s" % brick_node)
			new_node.ssh.execute("mkdir -p %s/bricks" % self.glusterfs_logdir)
		
		if len(bricks_list) > 0:
			self.add_node_to_volume(master, new_node, self.name, bricks_list)

		# share glusterfs volume on new nodes
		self.share_volume(master, nodes, self.name)
					
		# mount the volume on all nodes
		self.mount_glusterfs_volume([new_node])

	def on_remove_node(self, node, nodes, master, user, user_shell, volumes):
		self.ec2 = master.ec2
		
		bricks = master.ssh.execute("gluster volume info %s | awk '/%s:/{print $2}'" % (self.name, node.alias))
		if bricks is not None and len(bricks) > 0:
			# Remove attached bricks from volume
			self.remove_node_from_volume(master, node, self.name, bricks)
			
		self.detach_and_delete_ec2_volumes([node])
		
		# Re-configure glusterfs auth.allow to remove the node
		current_nodes = []
		for i in nodes:
			if i.alias != node.alias:
				current_nodes.append(i)
				
		self.share_volume(master, current_nodes, self.name)
					
	def on_restart(self, nodes, master, user, user_shell, volumes):
		raise NotImplementedError('on_restart method not implemented')

	def on_shutdown(self, nodes, master, user, user_shell, volumes):
		self.ec2 = master.ec2
		self.detach_and_delete_ec2_volumes(nodes)

	def detach_and_delete_ec2_volumes(self, nodes):
		brick_volumes = self.ec2.get_volumes(filters={'tag:Name': self.name})
		for vol in brick_volumes:
			for node in nodes:
				if vol.attach_data.instance_id == node.id:
					log.info("Detaching volume %s from instance %s" % (vol.id,vol.attach_data.instance_id))
					vol.detach(force=True)
					self.ec2.wait_for_volume(vol, status='available')
					log.info("Deleting volume %s" % vol.id)
					vol.delete()
					
	def is_rebalance_completed(self, node, name):
		status = node.ssh.execute("gluster volume rebalance %s status" % name, ignore_exit_status=True)
		if status[0].find("in progress") != -1:
			return False
		else:
			return True

	def wait_rebalance(self, node, name):
		s = utils.get_spinner("Waiting for %s volume to be rebalanced..." % name)
		try:
			node.ssh.execute("gluster volume rebalance %s start" % name, ignore_exit_status=True)
			while not self.is_rebalance_completed(node, name):
				time.sleep(1)
		finally:
			s.stop()

	def create_volume(self, master, volname, mode, transport, bricks):
		brick_uris = ""
		for brick in bricks:
			brick_node = brick.split(":")[0]
			brick_path = brick.split(":")[1]
			brick_uris += " " + brick_node + ":" + brick_path

		log.info("Creating glusterfs volume: %s" % volname);
		status = master.ssh.execute("gluster volume info %s | grep Status" % volname, ignore_exit_status=True, raise_on_failure=False)
		if status is None  or len(status) < 1:
			master.ssh.execute("gluster volume create %s %s transport %s %s" % (volname,mode,transport,brick_uris))
			master.ssh.execute("gluster volume set %s nfs.disable on" % volname)
			master.ssh.execute("gluster volume log filename %s %s/bricks" % (volname,self.glusterfs_logdir))
		else:
			log.info("Volume %s is already created" % volname)

	def start_volume(self, master, volname):
		log.info("Starting glusterfs volume: %s" % volname)
		status = master.ssh.execute("gluster volume info %s | grep Status" % volname)
		if status[0] != "Status: Started":
			master.ssh.execute("gluster volume start %s" % volname)
		else:
			log.info("Volume %s already started" % volname)
			
	def share_volume(self, master, nodes, volname):
		ip_addresses = ""
		for node in nodes:
			if len(ip_addresses) > 0:
				ip_addresses += ","
			ip_addresses += node.private_ip_address
			
		master.ssh.execute("gluster volume set %s auth.allow %s" % (volname,ip_addresses))

	def _get_node_object(self, alias, nodes):
		for node in nodes:
			if node.alias == alias:
				return node

		return None

	def _get_volume_object(self, alias, volumes):
		for volume in self.ec2.get_volumes():
			if volume.id == alias:
				return volume

		return None

	def _format_device(self, node, device):
		log.info("Formatting %s device...", device)
		node.ssh.execute("mkfs.ext4 %s" % device, silent=False)

	def _attach_and_format_volume(self, node, volume):
		if volume.attach_data.instance_id == node.id:
			log.info("Volume %s is already attached" % volume.id)
			return

		if volume.volume_state() != "available":
			log.info("Volume %s is not available" % volume.id)

		mounts = node.get_mount_map()
		for c in "fghijklmnop":
			dev = "/dev/xvd%s"%c
			if dev in mounts:
				continue;
			else:
				device="/dev/sd%s"%c
				break
		
		log.info("Attaching %s on %s" % (volume.id, node.alias))
		volume.attach(node.id, device)
		log.info("Waiting %s until is in state: attached" % volume.id)
		while True:
			volume.update()
			if volume.attachment_state() == 'attached':
				break
			time.sleep(5)

		self._format_device(node, device.replace("sd","xvd"))
	
	def _mount_device(self, node, device, mount_path):
		if not node.ssh.path_exists(mount_path):
			node.ssh.execute("mkdir -p %s" % mount_path)

		if device in node.get_mount_map():
			log.info("Device is already mounted in %s" % node.get_mount_map()[device])
		else:
			log.info("Mounting device %s on %s" % (device, mount_path))
			node.mount_device(device, mount_path)
		
	def _mount_volume(self, node, volume, mount_path):
		if volume.attach_data.device == None:
			log.error("Volume %s has not been attached" % volume.id)
			return

		device = volume.attach_data.device.replace("sd","xvd")
		self._mount_device(node, device, mount_path)

	def _mount_glusterfs_volume(self, node):
		mounts = node.get_mount_map()
		for dev in mounts:
			if mounts[dev][0] == self.mount_path:
				node.ssh.execute("umount %s" % self.mount_path)
				time.sleep(5)

		if not node.ssh.path_exists(self.mount_path):
			node.ssh.execute("mkdir -p %s" % self.mount_path)

		node.ssh.execute("mount -t glusterfs master:%s %s" % (self.name,self.mount_path))
    
	def _create_ec2_volume(self, name, size, zone , volumetype , encrypt):

        	log.info(">>>>>>>>>>>>   Creating new Volume with encrypt option : %s" % encrypt)
		vol = self.ec2.create_volume(size, zone, None , volumetype, encrypt)
		log.info("New volume id: %s" % vol.id)
		self.ec2.wait_for_volume(vol, status='available')
		vol.add_tag("Name", name)
		return vol	
