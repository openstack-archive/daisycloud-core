#!/bin/bash
chmod +x nova_compute_mem_moni/*
\cp -rf nova_compute_mem_moni/* /usr/bin
sed -i "/nova_compute_mem_moni/d" /etc/rc.d/rc.local && echo "[ -f /usr/bin/nova_compute_mem_moni.py ] && /usr/bin/python /usr/bin/nova_compute_mem_moni.py start" >> /etc/rc.d/rc.local
/usr/bin/python /usr/bin/nova_compute_mem_moni.py start