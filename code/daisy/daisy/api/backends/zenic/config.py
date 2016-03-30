# -*- coding: utf-8 -*-
import os
import re
import commands
import types
import subprocess
from ConfigParser import ConfigParser
from daisy.common import exception



default_zenic_conf_template_path = "/var/lib/daisy/zenic/"
zenic_conf_template_path = default_zenic_conf_template_path

def update_conf(zenic, key, value):
    zenic.set("general", key, value)

def get_conf(zenic_conf_file, **kwargs):
    result = {}
    if not kwargs:
        return  result

    zenic = ConfigParser()
    zenic.optionxform = str
    zenic.read(zenic_conf_file)

    result = {key : zenic.get("general",  kwargs.get(key, None))
              for key in kwargs.keys()
              if zenic.has_option("general", kwargs.get(key, None))}
    return result
    
def get_nodeid(deploy_ip,zbp_ips):
    nodeid = 0
    i = 0
    for ip in zbp_ips:
        if deploy_ip == ip:
            break
        else:
            i=i+1
            
    if i == 0:
        nodeid = 1
    elif i == 1:
        nodeid = 256
    else:
        nodeid = i
            
    return nodeid
    
       
def update_zenic_conf(config_data, cluster_conf_path):
    print "zenic config data is:"
    import pprint
    pprint.pprint(config_data)
    
    daisy_zenic_path = zenic_conf_template_path
    zenic_conf_template_file = os.path.join(daisy_zenic_path, "zenic.conf")
    if not os.path.exists(cluster_conf_path):
        os.makedirs(cluster_conf_path)    

    zenic = ConfigParser()
    zenic.optionxform = str
    zenic.read(zenic_conf_template_file)

    zbpips = ''
    for ip in config_data['zbp_ips']:
        if not zbpips:
            zbpips = ip
        else:
            zbpips = zbpips + ',' + ip        
    update_conf(zenic, 'zbpips', zbpips)
    update_conf(zenic, 'zbp_node_num',  config_data['zbp_node_num'])
    nodelist = '1,256'
    if len(config_data['zbp_ips']) > 2:
        for i in range(2,len(config_data['zbp_ips'])):
            nodelist = nodelist + ',' + 'i'            
    update_conf(zenic, 'zbpnodelist',nodelist)
    
    zampips = ''
    for ip in config_data['zamp_ips']:
        if not zampips:
            zampips = ip
        else:
            zampips = zampips + ',' + ip
    update_conf(zenic, 'zampips', zampips)
    update_conf(zenic, 'zamp_node_num', config_data['zamp_node_num'])
    

    mongodbips = ''
    for ip in config_data['mongodb_ips']:
        if not mongodbips:
            mongodbips = ip
        else:
            mongodbips = mongodbips + ',' + ip        
    update_conf(zenic, 'mongodbips', mongodbips)
    update_conf(zenic, 'mongodb_node_num',  config_data['mongodb_node_num'])

    update_conf(zenic, 'zamp_vip', config_data['zamp_vip'])
    update_conf(zenic, 'mongodb_vip', config_data['mongodb_vip'])

    
    deploy_hosts = config_data['deploy_hosts']
    for deploy_host in deploy_hosts:        
        nodeip = deploy_host['nodeip']
        hostname = deploy_host['hostname']
        MacName = deploy_host['MacName']
        memmode = deploy_host['memmode']
        
        update_conf(zenic,'nodeip',nodeip)       
        update_conf(zenic,'hostname',hostname)
        update_conf(zenic,'MacName',MacName)        
        update_conf(zenic,'memmode',memmode)
            
        nodeid = get_nodeid(nodeip,config_data['zbp_ips'])
        update_conf(zenic,'nodeid',nodeid)

        if nodeip in config_data['zamp_ips']:
            update_conf(zenic,'needzamp','y')
        else:
            update_conf(zenic,'needzamp','n')
            
        zenic_conf = "%s_zenic.conf" % deploy_host['mgtip']
        zenic_conf_cluster_out = os.path.join(cluster_conf_path, zenic_conf)
        zenic_conf_out = os.path.join(daisy_zenic_path, zenic_conf) 
        zenic.write(open(zenic_conf_cluster_out, "w+"))

        with open(zenic_conf_cluster_out,'r') as fr,open(zenic_conf_out,'w') as fw:
            for line in fr.readlines():
                fw.write(line.replace(' ', ''))
    return



def test():
    print("Hello, world!")
