#  Original: https://gist.github.com/jtriley/3305302
#  Install this file to $HOME/.starcluster/plugins/tagger.py  or somewhere on your $PYTHONPATH
#
# Once tagger is uploaded into the plugins folder you can add it to the config as:
#
#  [plugin tagger]
#  setup_class = tagger.TaggerPlugin
#  #add as many key=value pairs as you like separated by ','
#  tags = 'mykey=myvalue, mykey2=myvalue2'
#  
#  [cluster default]
#  ...
#  plugins = tagger
#
from starcluster.clustersetup import ClusterSetup
from starcluster.logger import log
 
class TaggerPlugin(ClusterSetup):
    def __init__(self, tags):
        self.tags = [t.strip() for t in tags.split(',')]
        self.tags = dict([t.split('=') for t in self.tags])
 
    def run(self, nodes, master, user, user_shell, volumes):
        log.info("Tagging all nodes...")
        for tag in self.tags:
            val = self.tags.get(tag)
            log.info("Applying tag - %s: %s" % (tag, val))
            for node in nodes:
                node.add_tag(tag, val)