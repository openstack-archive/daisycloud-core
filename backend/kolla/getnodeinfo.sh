#!/bin/bash

dhcp_ip="192.0.1.152"
listen_port="5050"
DISCOVERD_URL="http://$dhcp_ip:$listen_port/v1/continue"

function update() {
    jq "$1" data.json > temp.json || echo "Error: update $1 to json failed"
    mv temp.json data.json
}

function get_system_info(){
    PRODUCT=$(dmidecode -s system-product-name)
    FAMILY=$(dmidecode -t system|grep "Family"|cut -d ":" -f2)
    VERSION=$(dmidecode -s system-version)
    SERIAL=$(dmidecode -s system-serial-number)
    MANUFACTURER=$(dmidecode -s system-manufacturer)
    UUID=$(dmidecode -s system-uuid)
    FQDN=$(hostname -f)
    echo '{"system":{}}' > data.json
    update ".system[\"product\"] = \"$PRODUCT\""
    update ".system[\"family\"] = \"$FAMILY\""
    update ".system[\"fqdn\"] = \"$FQDN\""
    update ".system[\"version\"] = \"$VERSION\""
    update ".system[\"serial\"] = \"$SERIAL\""
    update ".system[\"manufacturer\"] = \"$MANUFACTURER\""
    update ".system[\"uuid\"] = \"$UUID\""
}

function get_cpu_info(){
    REAL=$(cat /proc/cpuinfo |grep "physical id"|sort |uniq|wc -l)
    TOTAL=$(cat /proc/cpuinfo |grep "processor"|wc -l)
    update ".cpu[\"real\"] = $REAL"
    update ".cpu[\"total\"] = $TOTAL"

    for i in $(seq $TOTAL)
    do
        if [ ! -z "$i" ]; then
        SPEC_MODEL=$(cat /proc/cpuinfo | grep name | cut -f2 -d:|sed -n $i"p")
        SPEC_FRE=$(cat /proc/cpuinfo | grep MHz | cut -f2 -d:|sed -n $i"p")
        update ".cpu[\"spec_$i\"] = {model:\"$SPEC_MODEL\", frequency:$SPEC_FRE}"
        fi
    done

    for node in $(lscpu | grep "node[0-9]" | awk -F ":" '{print $1}' | awk '{print $2}')
    do
        numanodes=$(lscpu | grep $node | awk -F ":" '{print $2}' | awk 'gsub(/^ *| *$/,"")')
        update ".cpu[\"numa_$node\"] = \"$numanodes\""
    done
}

function get_memory_info(){
    PHY_NUM=$(dmidecode -t memory|grep "Physical Memory Array"|wc -l)
    TOTAL_MEM=$(cat /proc/meminfo |grep MemTotal |cut -d ":" -f2)
    update ".memory[\"total\"] = \"$TOTAL_MEM\""
    for num in $(seq $PHY_NUM)
    do
        SLOTS=$(dmidecode -t memory |grep "Number Of Devices" |cut -d ":" -f2|sed -n $num"p")
        MAX_CAP=$(dmidecode -t memory |grep "Maximum Capacity" |cut -d ":" -f2|sed -n $num"p")
        update ".memory[\"phy_memory_$num\"] = {slots:\"$SLOTS\", maximum_capacity:\"$MAX_CAP\"}"

        for i in $(seq $SLOTS)
        do
            if [ ! -z "$i" ]; then
                DEVICE_FRE=$(dmidecode -t memory |grep "Speed" |cut -d ":" -f2|sed -n $i"p")
                DEVICE_TYPE=$(dmidecode -t memory |grep 'Type:' |grep -v "Error Correction Type"|cut -d ":" -f2|sed -n $i"p")
                DEVICE_SIZE=$(dmidecode -t memory |grep Size |cut -d ":" -f2|sed -n $i"p")
                update ".memory[\"phy_memory_$num\"][\"devices_$i\"] = {frequency:\"$DEVICE_FRE\", type:\"$DEVICE_TYPE\", size:\"$DEVICE_SIZE\"}"
            fi
        done
    done
}

function get_net_info(){
    physical_networks=`ls -l /sys/class/net/ | grep -v lo |grep "pci"|awk -F 'net/' '{print $2}'`
    if [ -f "/sys/class/net/bonding_masters" ]; then
        bond_network=$(cat /sys/class/net/bonding_masters)
        if [ ! -z "$bond_network" ];then
            physical_networks+=" $bond_network"
        fi
    fi
    for nic in $physical_networks
    do
        vlan_nic=`cat /proc/net/vlan/config | grep $nic |awk -F ' ' {'print $1'}`
        if [ ! -z "$vlan_nic" ];then
            all_vlan_nic+=" $vlan_nic "
        fi
    done
    
    all_nic=$all_vlan_nic$physical_networks
    
    for iface in $all_nic
    do
        NAME=$iface
        MAC=$(ip link show $iface | awk '/ether/ {print $2}')
        IP=$(ip addr show $iface | awk '/inet / { sub(/\/.*/, "", $2); print $2 }'| awk 'NR==1{print}')
        NETMASK=$(ifconfig $iface | grep netmask | awk '{print $4}')
        STATE=$(ip link show $iface | awk '/mtu/ {print $3}')
        PCI=$(ethtool -i $iface|grep "bus-info"|cut -d " " -f2)
        CURRENT_SPEED=$(ethtool $iface |grep Speed |awk -F " " '{print $2}')
        LINE=$(ethtool $iface|grep -n "Supported pause frame use"|awk -F ":" '{print $1}')
        LINE=$[ LINE - 1 ]
        LINE_SPEED=$(ethtool $iface|grep -n "Supported link modes"|awk -F ":" '{print $1}')
        BOND=$(ifconfig $iface | grep MASTER)
        if [ $LINE -eq $LINE_SPEED ]; then
            MAX_SPEED=$(ethtool $iface|grep "Supported link modes"|cut -d ":" -f2)  
        else     
            MAX_SPEED=$(ethtool $iface |sed -n $LINE"p"|awk -F " " '{print $1}')
        fi

        UP="UP"
        if [[ "$STATE" =~ "$UP" ]]; then
            STATE="up"
        else
            STATE="down"
        fi
        if [ -z "$BOND" ]; then
            vlan_nic=`cat /proc/net/vlan/config |awk -F ' ' {'print $1'} |grep -w "${iface}$"`
            if [ -z "$vlan_nic" ];then
                TYPE="ether"
            else
                TYPE="vlan"
            fi
        else
            TYPE="bond"
            SLAVES=$(find /etc/sysconfig/network-scripts/ -name "ifcfg-*" |xargs grep "$iface" | grep "MASTER" |awk -F 'ifcfg-' '{print $2}'|awk -F ':' '{print $1}')
        fi
        if [ ! -z "$MAC" ]; then
            update ".interfaces[\"$iface\"] = {mac: \"$MAC\", ip: \"$IP\", netmask: \"$NETMASK\", name: \"$iface\", max_speed: \"$MAX_SPEED\", state: \"$STATE\", pci: \"$PCI\", current_speed: \"$CURRENT_SPEED\", type: \"$TYPE\", slaves:\"$SLAVES\"}"
        fi
    done
}

function get_disk_info(){
    for disk in $(fdisk -l|grep Disk|grep "/dev" |awk -F ": " '{print $1}'|awk -F "/" '{print $NF}')
    do
        DISK_NAME=$disk
        DISK_SIZE=$(fdisk -l|grep Disk|grep "/dev" |grep -w $disk|cut -d "," -f2)
        DISK_DISK=$(ls -l /dev/disk/by-path/|grep $disk"$"|awk '{print $9}')
        DISK_EXTRA_1=$(ls -l /dev/disk/by-id/|grep $disk"$"|awk '{print $9}'|sed -n 1p)
        DISK_EXTRA_2=$(ls -l /dev/disk/by-id/|grep $disk"$"|awk '{print $9}'|sed -n 2p)
        MODEL=$(hdparm  -I /dev/sda |grep Model | cut -d ":" -f2)
        REMOVABLE=$(hdparm  -I /dev/sda |grep removable|awk '{print $4}')
        update ".disk[\"$disk\"] = {name: \"$DISK_NAME\", size: \"$DISK_SIZE\", disk: \"$DISK_DISK\", model: \"$MODEL\", removable: \"$REMOVABLE\",extra: [\"$DISK_EXTRA_1\", \"$DISK_EXTRA_2\"]}"
    done
}

function get_hostname_info(){
    HOST_NAME=$(hostname)
    update ".hostname = \"$HOST_NAME\"" 
}

function get_devices_numa_info(){
    for device in $(ls /sys/bus/pci/devices)
    do
        numa=$(cat /sys/bus/pci/devices/$device/numa_node)
        update ".devices[\"$device\"] = {\"$device\": \"$numa\"}"
    done
}

function get_pci_info(){
    for key in $(lspci | awk '{print $1}')
    do
        info=$(lspci | grep "$key")
        update ".pci[\"$key\"] = \"$info\""
    done
}

function get_fc_port(){
    for host in $(ls /sys/class/fc_host/)
    do
        path="/sys/class/fc_host/"${host}"/port_name"
        port_name=$(cat $path)
        update ".fc_port[\"$host\"] = \"$port_name\""
    done
}

function main(){
    get_system_info
    get_cpu_info
    get_memory_info
    get_net_info
    get_disk_info
    get_hostname_info
    get_devices_numa_info
    get_pci_info
    get_fc_port
}
main

BMC_ADDRESS=$(ipmitool lan print | grep -e "IP Address [^S]" | awk '{ print $4 }')
if [ -z "$BMC_ADDRESS" ]; then
    BMC_ADDRESS=$(ipmitool lan print 3| grep -e "IP Address [^S]" | awk '{ print $4 }')
fi
update ".ipmi_address = \"$BMC_ADDRESS\""

update ".data_name = \"baremetal_source\""

update ".os_status = \"active\"" 

echo Collected:
cat data.json

RESULT=$(eval curl -i -X POST \
       "-H 'Accept: application/json'" \
       "-H 'Content-Type: application/json'" \
       "-d @data.json" \
       "$DISCOVERD_URL")

if echo $RESULT | grep "HTTP/1.0 4"; then
    echo "Ironic API returned error: $RESULT"
fi

echo "Node is now discovered! Halting..."
sleep 5
