import time,re,string
from starcluster.clustersetup import ClusterSetup
from starcluster.logger import log
from pprint import pprint
 
#[plugin glusterfsServer]
#setup_class = gluster.GlusterServer
#volumes = DataCollections
#transport = tcp
#replicas = 2
#brick_mount_point=/var/glusterfs/bricks
#device_order = /dev/xvdf,/dev/xvdg,/dev/xvdh,/dev/xvdi

#[plugin glusterMounts]
#setup_class = gluster.glusterMount
#server = <ip address of one of the data cluster nodes>
#volumes = GlusterVolume1 , GlusterVolume2 ...
# Consider to add desired mount points per Gluster Volume

 
class GlusterServer(ClusterSetup):
     def __init__(self, volumes,transport,replicas,brick_mount_point):
          self.volumes = volumes
          if self.volumes:
                self.volumes= [volume.strip() for volume in volumes.split(',')]
 
          self.transport = transport
          self.replicas = replicas
          self.brick_mount_point = brick_mount_point
          self.volume_devices = {}
 
     def run(self, nodes, master, user, user_shell, volumes):
          self.master=master
          self.ec2 = self.master.ec2
          self.nodes = nodes
 
          self.probe_peers(master,nodes)
          for volume in self.volumes:
                log.info("Preparing volume %s" % volume)
                brick_volumes = self.get_brick_volumes(volume)
                for brick_volume in brick_volumes:
                    log.info("\tBrick volume: %s" % brick_volume)
                    node = nodes[int(brick_volume.tags.get('brickNode'))]
                    self.attach_brick_volume(node, brick_volume)
                    self.mount_brick_device_volume(node, brick_volume, volume)
 
                self.create_volume(master, nodes, volume, self.replicas, self.transport, brick_volumes)
                self.start_volume(master, volume)
 
     def create_volume(self, master, nodes,  volume, replicas, transport, brick_volumes):
          log.info("create_volume() %s" % volume)
          conn = master.ssh
          status = conn.execute("gluster volume info %s | grep Status" % volume)
          if status is None or len(status)<1:
                log.info("Create gluster volume %s" % volume)
                bricks = self._get_brick_uris(brick_volumes, volume, nodes)
                log.info("Bricks: %s"%bricks)
                conn.execute("gluster volume create %s replica %s transport %s %s" % (volume,replicas,transport,bricks))
          else:
               log.info("Volume %s status is %s" % (volume,status))
 
     def start_volume(self, master, volume):
          log.info("start_volume() %s" % volume)
          conn = master.ssh
          status = conn.execute("gluster volume info %s | grep Status" % volume)
          if status is not None and len(status)>0:
                log.info("Volume status: %s"%status)
                if status[0]=="Started":
                    log.info("Gluster Volume already started: %s", volume)
                    return
 
                conn.execute("gluster volume start %s" % volume)
                log.info("Started Gluster Volume: %s" % volume)
                return
          log.error("Volume %s not found, unable to start" % volume)
 
     def _get_brick_uris(self, brick_volumes, volume, nodes):
          bricks=""
          for brick in brick_volumes:
                nodeIdx = brick.tags.get('brickNode')
                node = nodes[int(nodeIdx)]
                bricks = "%s %s:%s" % (bricks, node.instance.private_ip_address,self.brick_mount_point % (volume, brick.tags.get("Name")))
          return bricks
     def get_brick_volumes(self, volume_name):
          """
          Query volumes to find which bricks are tagged for this cluster and volume
          """
          return self.ec2.get_volumes(filters={'tag:volume': volume_name, 'tag:type':'glusterbrick'})
    def mount_brick_device_volume(self, node, brick_volume, volume):
          device = brick_volume.attach_data.device.replace("sd","xvd")
          mount_point = self.brick_mount_point % (volume, brick_volume.tags.get("Name"))
          if not node.ssh.path_exists(mount_point):
                node.ssh.execute("mkdir -p %s"%mount_point)
 
          log.info("Mount %s %s" % (device,mount_point))
          if device in node.get_mount_map():
                log.warn("Device already mounted in: %s" % node.get_mount_map()[device])
                return
          else:
                dev = brick_volume.attach_data.device.replace("sd","xvd")
                res = node.ssh.execute("file -s %s"%dev)
                if res is None:
                   log.error("file -s returned nothing")
                   return
                if res[0]==("%s: data"%dev):
                   log.info("Brick Volume hasn't beenf formatted: %s" %res[0])
                   node.ssh.execute("mkfs -t ext4 %s" % dev)
                else:
                    log.info("\tDevice:" % res)
 
                res = node.ssh.execute("file -s %s"%dev)
                if res is None:
                   log.error("file -s returned nothing")
                   return
                if res[0]==("%s: data"%dev):
                   log.error("Format failed for %s" %res[0])
                   return
                else:
                   log.info("\tDevice:" % res)
 
                node.mount_device(dev, self.brick_mount_point % (volume, brick_volume.tags.get("Name")))
                mounts = node.get_mount_map()
                for dev in mounts:
                     log.info("Device %s -> %s" % (dev, mounts[dev]))
                #log.info("mounted volume: %s" % node.get_mount_map()[brick_volume.attach_data.device.replace("sd","xvd")])     
                log.info("Mounted Brick Volume %s for %s" % (brick_volume.tags.get("Name"),volume))
                return;
 
          log.error("Unable to mount brick volume.")
 
     def attach_brick_volume(self,node,brick_volume):
          if brick_volume.attach_data.instance_id == node.id:
                log.info("Volume %s already attached to node %s ...skipping" % (brick_volume.id, node.id))
                return
 
          if brick_volume.volume_state()!="available":
                log.info("Volume %s not avialable....please check and try again" % brick_volume.id)
                return
 
 
          mounts = node.get_mount_map()
          idx = 0
          for dev in mounts:
                log.info("dev: %s %s" %(dev, mounts[dev]))
 
          for c in "fghijklmnop":
                dev = "/dev/xvd%s"%c
                log.info("Checking for existing mount: %s" % dev)
                if dev in mounts:
                    continue;
                else:
                    attach_device="/dev/sd%s"%c
                    break
          print("attach_device: %s"%attach_device)
 
          brick_volume.attach(node.id, attach_device)
          while True:
                brick_volume.update()
                if brick_volume.attachment_state() == 'attached':
                    break;
                time.sleep(5)
 
 
     def probe_peers(self,master,nodes):
          for node in nodes:
                if not node.is_master():
                    res = master.ssh.execute('gluster peer status | grep %s' % node.instance.private_ip_address)
                    if res:
                         log.info("Peer already attached: %s" % node.instance.private_ip_address)
                    else:
                         log.info("Probing peers %s" % node.instance.private_ip_address)
                         master.ssh.execute("gluster peer probe %s" % node.instance.private_ip_address)
 
class glusterMount(ClusterSetup):
     def __init__(self, server,volumes, mountpoint):
          self.server = server
          self.volumes = volumes
          self.mountpoint = mountpoint
          if self.volumes:
              self.volumes= [volume.strip() for volume in volumes.split(',')]
 
     def run(self, nodes, master, user, user_shell, volumes):
          conn=master.ssh
          #    for volume in self.volumes:
          #        mountpoint = '/mnt/%s' % volume
 
          #    if not conn.path_exists(mountpoint):
          #          conn.mkdir(mountpoint)
 
          #    master.ssh.execute('mount -t nfs -o nolock %s:%s %s' % (self.server,volume,mountpoint))
 
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
                    mountpoint = '/mnt/%s' % volume
 
                    if not nconn.path_exists(mountpoint):
                          log.info("Create mount point %s" % mountpoint)
                          nconn.execute("mkdir -p %s" % mountpoint)
 
                    log.info("Mount glusterfs volume %s at %s" % (volume,mountpoint))
                    nconn.execute('mount -t nfs -o nolock %s:%s %s' % (self.server,volume,mountpoint))
 
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
               mountpoint = '/mnt/%s' % volume
 
               if not nconn.path_exists(mountpoint):
                     log.info("Create mount point %s" % mountpoint)
                     nconn.execute("mkdir -p %s" % mountpoint)
 
               nconn.execute('mount -t glusterfs %s:%s %s' % (self.server,volume,mountpoint))