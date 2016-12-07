#!/bin/bash
chmod +x moni_port/*
\cp -rf moni_port/* /usr/bin
sed -i "/moni_port_status/d" /etc/rc.d/rc.local && echo "[ -f /usr/bin/moni_port_status ] && /usr/bin/moni_port_status start" >> /etc/rc.d/rc.local
/usr/bin/moni_port_status start