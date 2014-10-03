# Original: https://github.com/JohnCEarls/starcluster-plugins/blob/master/tagger.py
#
# Starcluster plugin that adds tags to ec2 instances on startup
#
# Install this file to $HOME/.starcluster/plugins/tagger.py and add similar to config
#
#  [plugin tagger]
#  setup_class=tagger.TaggerPlugin
#  tags = key:value, started-by:John C. Earls, project: testing,  mydate:[[date]], myalias:  [[alias]], localuser:[[localuser]], 
#  Has a few variables that can be used as values.
#
# [[date]] - datetime in UTC
# [[alias]] - node name 
# [[localuser]] - users name on computer that is starting the cluster
#
from starcluster.clustersetup import ClusterSetup
from starcluster.logger import log
import starcluster.logger
import json
from datetime import datetime
import getpass
import re

class TaggerPlugin(ClusterSetup):
    def __init__(self, tags):
        self.tags = self.parse_tags(tags)

    def parse_tags(self, tags):
        tag_dict = {}
        for pair in tags.split(','):
            try:
                key, value = pair.split(':')
                tag_dict[key.strip()] = value.strip()
            except Exception as e:
                log.exception(("Tagger error on given tags [%s] "
                        "for pair <%s>") % (tags, pair))
        log.info("Tagger: %s" % json.dumps(tag_dict))
        return tag_dict
        
    def get_value(self, value, node):
        """
        Handle special values
        [[date]]
        [[alias]] - node name
        [[localuser]] - user name of person that started cluster, 
            according to machine cluster started from
        """
        auto_pattern = r'\[\[(.+)\]\]'
        auto_v = re.match(auto_pattern, value)
        if auto_v:
            special_value = auto_v.group(1).strip()
            if special_value == 'date':
                return datetime.utcnow().strftime('%c UTC')
            if special_value == 'alias':
                return node.alias
#            if special_value == 'master':
#                return master.alias
            if special_value == 'localuser':
                return getpass.getuser()
            log.error(("Tagging: <%s> appears to be a patterned tag, but " 
                    "no special_value found. Tagging as <%s>.") % 
                    (value, special_value) )
            return special_value
        else:
            return value

    def add_tags(self, node):
        for key, value in self.tags.iteritems():
            log.debug("key: <%s>, value: <%s>" % 
                    (key,self.get_value(value, node)))
            node.add_tag(key,self.get_value(value,node))
        log.info('Tagged %s' % node.alias)
                        
    def run(self, nodes, master, user, user_shell, volumes):
        log.info("Tagging all nodes...")
        #Loop goes through master as well.
        for node in nodes:
            self.add_tags(node)

    def on_add_node(self, new_node, nodes, master, user, user_shell, volumes):
        self.add_tags(new_node)        