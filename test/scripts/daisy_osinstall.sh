#/bin/sh
#
#create cluster
daisy_host="10.43.203.227"
cluster_id=`daisy --os-endpoint http://${daisy_host}:19292 cluster-add $(pwd)''/cluster_params |grep -w id |awk -F'|'  '{print $3}'`
echo $cluster_id
[ -z "$cluster_id" ] && { echo "$cluster_id is null"; exit 1; }

host1_id=`daisy  --os-endpoint http://${daisy_host}:19292  host-list |grep -w '98f537e1ae9a' | awk -F "|" '{print $2}'| grep -o "[^ ]\+\( \+[^ ]\+\)*"`;
echo $host1_id
[ -z "$host1_id" ] && { echo "$host1_id is null"; exit 1; }

interfaces_1="type=ether,name=enp8s0,mac=98:f5:37:e1:ae:99,ip=10.43.203.228,is_deployment=False,netmask=255.255.254.0,assigned_networks=MANAGEMENT,slaves=ebl_ebl \
type=ether,name=enp8s0,mac=98:f5:37:e1:ae:99,ip=10.43.203.228,is_deployment=False,netmask=255.255.254.0,assigned_networks=STORAGE,slaves=ebl_ebl \
type=ether,name=enp9s0,mac=98:f5:37:e1:ae:9a,ip=192.168.1.11,is_deployment=True,netmask=255.255.255.0,assigned_networks=DEPLOYMENT,slaves=ebl_ebl --os-status init"
daisy  --os-endpoint http://${daisy_host}:19292 host-update $host1_id   --dmi-uuid  03000200-0400-0500-0006-000700080009  --ipmi-user zteroot --ipmi-passwd superuser --ipmi-addr 10.43.203.230 --cluster $cluster_id  --interfaces $interfaces_1 --os-version /var/lib/daisy/tecs/CGSL_VPLAT-5.1-231-x86_64.iso

echo "======host-update230================="

host2_id=`daisy  --os-endpoint http://${daisy_host}:19292  host-list |grep -w '98f537e1af17' | awk -F "|" '{print $2}'| grep -o "[^ ]\+\( \+[^ ]\+\)*"`;
echo $host2_id
[ -z "$host2_id" ] && { echo "$host2_id is null"; exit 1; }
interfaces_2="type=ether,name=enp8s0,mac=98:f5:37:e1:af:16,ip=10.43.203.229,is_deployment=False,netmask=255.255.254.0,assigned_networks=MANAGEMENT,slaves=ebl_ebl \
type=ether,name=enp8s0,mac=98:f5:37:e1:af:16,ip=10.43.203.229,is_deployment=False,netmask=255.255.254.0,assigned_networks=STORAGE,slaves=ebl_ebl \
type=ether,name=enp9s0,mac=98:f5:37:e1:af:17,ip=192.168.1.10,is_deployment=True,netmask=255.255.255.0,assigned_networks=DEPLOYMENT,slaves=ebl_ebl  --os-status init"
daisy  --os-endpoint http://${daisy_host}:19292 host-update $host2_id    --dmi-uuid  03000200-0400-0500-0006-000700080009  --ipmi-user zteroot --ipmi-passwd superuser --ipmi-addr 10.43.203.231 --cluster $cluster_id  --interfaces $interfaces_2 --os-version /var/lib/daisy/tecs/CGSL_VPLAT-5.1-231-x86_64.iso

network_id=`daisy  --os-endpoint http://${daisy_host}:19292  network-list  $cluster_id |grep -w MANAGEMENT |grep custom | awk -F "|" '{print $2}'| grep -o "[^ ]\+\( \+[^ ]\+\)*"`;

daisy --os-endpoint http://${daisy_host}:19292 network-update $network_id --gateway 10.43.202.1 

echo "======host-update231================="

host3_id=`daisy  --os-endpoint http://${daisy_host}:19292  host-list |grep -w '98f537e1af0d' | awk -F "|" '{print $2}'| grep -o "[^ ]\+\( \+[^ ]\+\)*"`;
echo $host3_id
[ -z "$host3_id" ] && { echo "$host3_id is null"; exit 1; }

interfaces_1="type=ether,name=enp8s0,mac=98:f5:37:e1:af:0c,ip=10.43.203.113,is_deployment=False,netmask=255.255.254.0,assigned_networks=MANAGEMENT,slaves=ebl_ebl \
type=ether,name=enp8s0,mac=98:f5:37:e1:af:0c,ip=10.43.203.113,is_deployment=False,netmask=255.255.254.0,assigned_networks=STORAGE,slaves=ebl_ebl \
type=ether,name=enp9s0,mac=98:f5:37:e1:af:0d,ip=192.168.1.12,is_deployment=True,netmask=255.255.255.0,assigned_networks=DEPLOYMENT,slaves=ebl_ebl --os-status init"
daisy  --os-endpoint http://${daisy_host}:19292 host-update $host3_id   --dmi-uuid  03000200-0400-0500-0006-000700080009  --ipmi-user zteroot --ipmi-passwd superuser --ipmi-addr 10.43.203.114 --cluster $cluster_id  --interfaces $interfaces_1 --os-version /var/lib/daisy/tecs/CGSL_VPLAT-5.1-231-x86_64.iso

echo "======host-update113================="

role_ha_id=`daisy --os-endpoint http://${daisy_host}:19292  role-list  |grep $cluster_id  |grep "CONTROLLER_HA" | awk -F "|" '{print $2}'| grep -o "[^ ]\+\( \+[^ ]\+\)*"`;
role_lb_id=`daisy --os-endpoint http://${daisy_host}:19292  role-list  |grep $cluster_id  |grep "CONTROLLER_LB" | awk -F "|" '{print $2}'| grep -o "[^ ]\+\( \+[^ ]\+\)*"`;
role_compute_id=`daisy --os-endpoint http://${daisy_host}:19292  role-list  |grep $cluster_id  |grep "Compute" | awk -F "|" '{print $2}'| grep -o "[^ ]\+\( \+[^ ]\+\)*"`;

daisy --os-endpoint http://${daisy_host}:19292 role-update $role_ha_id --nodes $host1_id  --vip 10.43.203.111;
daisy --os-endpoint http://${daisy_host}:19292 role-update $role_ha_id --nodes $host2_id  --vip 10.43.203.111;

daisy --os-endpoint http://${daisy_host}:19292 role-update $role_lb_id --nodes $host1_id  --vip 10.43.203.112;
daisy --os-endpoint http://${daisy_host}:19292 role-update $role_lb_id --nodes $host2_id  --vip 10.43.203.112;

daisy --os-endpoint http://${daisy_host}:19292 role-update $role_compute_id --nodes $host3_id;

exit 0