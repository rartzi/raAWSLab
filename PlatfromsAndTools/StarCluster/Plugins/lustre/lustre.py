from starcluster import clustersetup
from starcluster.logger import log

class MountLustre(clustersetup.DefaultClusterSetup):
    def __init__(self, lustre_export, lustre_mountpoint, lustre_security_group):
        self.lustre_export = lustre_export
        self.lustre_mountpoint = lustre_mountpoint
        self.lustre_security_group = lustre_security_group
        log.debug('lustre_export = %s' % lustre_export)
        log.debug('lustre_mountpoint = %s' % lustre_mountpoint)
        log.debug('lustre_security_group = %s' % lustre_security_group)
        super(MountLustre, self).__init__()

    def _has_port(self, group, cluster_group):
        """
        Checks whether the group has the specified port range permission
        """
        for rule in group.rules:
            if rule.ip_protocol != 'tcp':
                continue
            if int(rule.from_port) != 988:
                continue
            if int(rule.to_port) != 988:
                continue
            group_grants = [g for g in rule.grants if g.groupName == cluster_group.name]
            if not group_grants:
                continue
            return True
        return False

    def on_add_node(self, node, nodes, master, user, user_shell, volumes):
        """
        This methods gets executed after a node has been added to the cluster
        """
        log.info('Mounting %s at %s on %s' % (self.lustre_export, self.lustre_mountpoint, node))
        node.ssh.execute('mkdir -p %s' % self.lustre_mountpoint)
        node.ssh.execute('grep %s /proc/mounts 2>/dev/null || mount -t lustre -v %s %s' % 
                        (self.lustre_mountpoint, self.lustre_export, self.lustre_mountpoint))

    def on_remove_node(self, node, nodes, master, user, user_shell, volumes):
        """
        This method gets executed before a node is about to be removed from the
        cluster
        """
        raise NotImplementedError('on_remove_node method not implemented')

    def on_restart(self, nodes, master, user, user_shell, volumes):
        """
        This method gets executed before restart the cluster
        """
        raise NotImplementedError('on_restart method not implemented')

    def run(self, nodes, master, user, user_shell, volumes):
        self.cluster_group = master.cluster_groups[0]
        log.info('Adding %s cluster security group to %s Lustre security group' % (self.cluster_group.name, self.lustre_security_group))
        self.ec2 = master.ec2
        self.group = self.ec2.get_security_group(self.lustre_security_group)

        port_open = self._has_port(self.group, self.cluster_group)
        log.debug('port_open = %s' % port_open)
        if not port_open:
            log.debug('Adding tcp:988 to %s' % self.lustre_security_group)
            self.group.authorize(ip_protocol='tcp', from_port=988, to_port=988, src_group=self.cluster_group)

        log.info('Mounting %s at %s on all nodes...' % (self.lustre_export, self.lustre_mountpoint))
        for node in nodes:
            self.pool.simple_job(node.ssh.execute,
                                 ('mkdir -p %s' % self.lustre_mountpoint),
                                 jobid=node.alias)
            self.pool.simple_job(node.ssh.execute,
                                 ('grep %s /proc/mounts 2>/dev/null || mount -t lustre -v %s %s' % (self.lustre_mountpoint, self.lustre_export, self.lustre_mountpoint)),
                                 jobid=node.alias)
        self.pool.wait(numtasks=len(nodes))

    def on_shutdown(self, nodes, master, user, user_shell, volumes):
        self.cluster_group = master.cluster_groups[0]
        log.info('Removing %s cluster security group from %s Lustre security group' % (self.cluster_group.name, self.lustre_security_group))
        self.ec2 = master.ec2
        self.group = self.ec2.get_security_group(self.lustre_security_group)
        self.group.revoke(ip_protocol='tcp', from_port=988, to_port=988, src_group=self.cluster_group)

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

