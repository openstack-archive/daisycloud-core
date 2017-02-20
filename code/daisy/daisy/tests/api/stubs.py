# Copyright 2010 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import subprocess
all_network = \
    [
        {
            "ip": None,
            "updated_at": "2016-10-27T01:45:32.000000",
            "cluster_id": "2ddb81b5-db73-4e20-894b-b0d59a7babfc",
            "gre_id_start": None,
            "deleted_at": None,
            "id": "65551b9d-d669-47af-96e1-8092e8627ba7",
            "vlan_id": None,
            "gateway": "",
            "physnet_name": "physnet_enp8s0",
            "gre_id_end": None,
            "vlan_end": 4094,
            "vni_end": None,
            "type": "custom",
            "description": "None",
            "deleted": False,
            "vlan_start": 1,
            "cidr": "192.168.1.1/24",
            "ml2_type": None,
            "name": "TECSClient",
            "custom_name": "",
            "created_at": "2016-10-26T08:32:47.000000",
            "ip_ranges": [

            ],
            "mt": 1500,
            "capability": "high",
            "alias": None,
            "vni_start": None,
            "segmentation_type": None,
            "network_type": "TECSClient"
        },
        {
            "ip": None,
            "updated_at": "2016-10-27T01:45:32.000000",
            "cluster_id": "2ddb81b5-db73-4e20-894b-b0d59a7babfc",
            "gre_id_start": None,
            "deleted_at": None,
            "id": "e9b0573c-ca67-4f65-9d0b-97ef210fa577",
            "vlan_id": None,
            "gateway": "",
            "physnet_name": "physnet_enp8s0",
            "gre_id_end": None,
            "vlan_end": 4094,
            "vni_end": None,
            "type": "default",
            "description": "1.mangement ip\n"
                           "2.test\n3.test\n4.test\n"
                           "5.test\n6.test\n7.test\n8.test\n\n",
            "deleted": False,
            "vlan_start": 1,
            "cidr": "192.168.1.1/24",
            "ml2_type": None,
            "name": "MANAGEMENT",
            "custom_name": "",
            "created_at": "2016-10-26T08:32:45.000000",
            "ip_ranges": [
                {
                    "start": "192.168.1.227",
                    "end": "192.168.1.250"
                }
            ],
            "mt": 1500,
            "capability": "high",
            "alias": None,
            "vni_start": None,
            "segmentation_type": None,
            "network_type": "MANAGEMENT"
        },
        {
            "ip": None,
            "updated_at": "2016-10-27T01:45:32.000000",
            "cluster_id": "2ddb81b5-db73-4e20-894b-b0d59a7babfc",
            "gre_id_start": None,
            "deleted_at": None,
            "id": "bbc5dae6-f687-4a76-9fcf-b15d4c57a1cf",
            "vlan_id": None,
            "gateway": "",
            "physnet_name": "physnet_enp8s0",
            "gre_id_end": None,
            "vlan_end": 4094,
            "vni_end": None,
            "type": "default",
            "description": "",
            "deleted": False,
            "vlan_start": 1,
            "cidr": "192.168.1.1/24",
            "ml2_type": None,
            "name": "STORAGE",
            "custom_name": "",
            "created_at": "2016-10-26T08:32:45.000000",
            "ip_ranges": [

            ],
            "mt": 1500,
            "capability": "high",
            "alias": None,
            "vni_start": None,
            "segmentation_type": None,
            "network_type": "STORAGE"
        },
        {
            "ip": None,
            "updated_at": "2016-10-26T08:32:45.000000",
            "cluster_id": "2ddb81b5-db73-4e20-894b-b0d59a7babfc",
            "gre_id_start": None,
            "deleted_at": None,
            "id": "b4592115-7a4d-4e63-8e9a-7ff58884a55e",
            "vlan_id": None,
            "gateway": None,
            "physnet_name": None,
            "gre_id_end": None,
            "vlan_end": 4094,
            "vni_end": None,
            "type": "default",
            "description": "For external interactive",
            "deleted": False,
            "vlan_start": 1,
            "cidr": "192.170.1.1/24",
            "ml2_type": None,
            "name": "EXTERNAL",
            "custom_name": None,
            "created_at": "2016-10-26T08:32:45.000000",
            "ip_ranges": [

            ],
            "mt": 1500,
            "capability": "high",
            "alias": None,
            "vni_start": None,
            "segmentation_type": None,
            "network_type": "EXTERNAL"
        },
        {
            "ip": None,
            "updated_at": "2016-10-27T01:45:32.000000",
            "cluster_id": "2ddb81b5-db73-4e20-894b-b0d59a7babfc",
            "gre_id_start": None,
            "deleted_at": None,
            "id": "5a3d1ae8-f738-4bc0-a291-85e2df5b4339",
            "vlan_id": None,
            "gateway": "",
            "physnet_name": "physnet_enp8s0",
            "gre_id_end": None,
            "vlan_end": 4094,
            "vni_end": None,
            "type": "default",
            "description": "",
            "deleted": False,
            "vlan_start": 1,
            "cidr": "192.168.1.1/24",
            "ml2_type": None,
            "name": "OUTBAND",
            "custom_name": "",
            "created_at": "2016-10-26T08:32:45.000000",
            "ip_ranges": [

            ],
            "mt": 1500,
            "capability": "high",
            "alias": None,
            "vni_start": None,
            "segmentation_type": None,
            "network_type": "OUTBAND"
        },
        {
            "ip": None,
            "updated_at": "2016-10-26T08:32:45.000000",
            "cluster_id": "2ddb81b5-db73-4e20-894b-b0d59a7babfc",
            "gre_id_start": None,
            "deleted_at": None,
            "id": "324ddc5a-ed08-404a-b50c-006a69685d8a",
            "vlan_id": None,
            "gateway": None,
            "physnet_name": None,
            "gre_id_end": None,
            "vlan_end": 4094,
            "vni_end": None,
            "type": "default",
            "description": "For deploy the infrastructure",
            "deleted": False,
            "vlan_start": 1,
            "cidr": "99.99.1.1/24",
            "ml2_type": None,
            "name": "DEPLOYMENT",
            "custom_name": None,
            "created_at": "2016-10-26T08:32:45.000000",
            "ip_ranges": [

            ],
            "mt": 1500,
            "capability": "high",
            "alias": None,
            "vni_start": None,
            "segmentation_type": None,
            "network_type": "DEPLOYMENT"
        },
        {
            "ip": None,
            "updated_at": "2016-10-27T01:45:32.000000",
            "cluster_id": "2ddb81b5-db73-4e20-894b-b0d59a7babfc",
            "gre_id_start": None,
            "deleted_at": None,
            "id": "114000a2-2300-43e6-bf73-05c74793dbd2",
            "vlan_id": None,
            "gateway": None,
            "physnet_name": "physnet_enp3s0f0",
            "gre_id_end": None,
            "vlan_end": 4094,
            "vni_end": None,
            "type": "default",
            "description": "1.dataplane ip\n2.test\n3.test\n",
            "deleted": False,
            "vlan_start": 1,
            "cidr": None,
            "ml2_type": "ovs",
            "name": "physnet1",
            "custom_name": "",
            "created_at": "2016-10-26T08:32:45.000000",
            "ip_ranges": [

            ],
            "mt": 1500,
            "capability": "high",
            "alias": None,
            "vni_start": None,
            "segmentation_type": "vlan",
            "network_type": "DATAPLANE"
        },
        {
            "ip": None,
            "updated_at": "2016-10-27T01:45:32.000000",
            "cluster_id": "2ddb81b5-db73-4e20-894b-b0d59a7babfc",
            "gre_id_start": None,
            "deleted_at": None,
            "id": "0665dad4-ab80-42ac-b91a-a8bd50f0efcd",
            "vlan_id": None,
            "gateway": "",
            "physnet_name": "physnet_enp9s0",
            "gre_id_end": None,
            "vlan_end": 4094,
            "vni_end": None,
            "type": "default",
            "description": "1.public ip\n2.test\n3.test\n",
            "deleted": False,
            "vlan_start": 1,
            "cidr": "10.43.203.1/24",
            "ml2_type": None,
            "name": "PUBLICAPI",
            "custom_name": "",
            "created_at": "2016-10-26T08:32:45.000000",
            "ip_ranges": [
                {
                    "start": "10.43.203.227",
                    "end": "10.43.203.228"
                }
            ],
            "mt": 1500,
            "capability": "high",
            "alias": None,
            "vni_start": None,
            "segmentation_type": None,
            "network_type": "PUBLICAPI"
        }
    ]
all_hosts = [
    {
        "os_version_id": "096e87ad-17c6-44df-a644-c94fdee03580",
        "config_set_id": None,
        "root_disk": "sda",
        "os_status": "init",
        "isolcpus": None,
        "updated_at": "2016-10-29T07:51:43.000000",
        "group_list": "core,base",
        "cluster": "test2",
        "dvsp_cpus": "",
        "deleted_at": None,
        "id": "c8a6f556-fcaa-45ee-9e9f- cce11b6bda07",
        "vcpu_pin_set": "",
        "dvsv_cpus": "",
        "hwm_ip": None,
        "os_version_file": None,
        "system": {
            "product": "R4300 G2",
            "uuid": "37E1AF13-98F5-0000-0010-0000542F8155",
            "family": " Server",
            "fqdn": "localhost",
            "version": "1.0.0",
            "serial": "21004134041",
            "manufacturer": "ZTE"
        },
        "dmi_uuid": "37E1AF13-98F5-0000-0010-0000542F8155",
        "role": [
            "CONTROLLER_HA",
            "CONTROLLER_LB"
        ],
        "memory": {
            "total": " 132002068 kB",
            "phy_memory_1": {
                "maximum_capacity": " 256 GB",
                "devices_5": {
                    "frequency": " 1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                },
                "devices_4": {
                    "frequency": "1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                },
                "devices_7": {
                    "frequency": "1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                },
                "devices_6": {
                    "frequency": "1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                },
                "devices_1": {
                    "frequency": "1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                },
                "devices_3": {
                    "frequency": "1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                },
                "devices_2": {
                    "frequency": "1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                },
                "slots": " 8",
                "devices_8": {
                    "frequency": " 1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                }
            },
            "phy_memory_2": {
                "maximum_capacity": " 256 GB",
                "devices_5": {
                    "frequency": " 1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                },
                "devices_4": {
                    "frequency": "1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                },
                "devices_7": {
                    "frequency": "1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                },
                "devices_6": {
                    "frequency": "1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                },
                "devices_1": {
                    "frequency": "1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                },
                "devices_3": {
                    "frequency": "1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                },
                "devices_2": {
                    "frequency": "1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                },
                "slots": " 8",
                "devices_8": {
                    "frequency": " 1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                }
            }
        },
        "virtio_queue_size": "",
        "dvs_config_desc": "",
        "hwm_id": None,
        "pci_high_cpuset": "",
        "status": "with-role",
        "description": "default",
        "dvsc_cpus": "",
        "deleted": False,
        "discover_mode": "PXE",
        "interfaces": [
            {
                "ip": "",
                "updated_at": "2016-10-29T00:47:47.000000",
                "current_speed": "Unknown!",
                "assigned_networks": [],
                "deleted_at": None,
                "id": "132efaf7-bfec-448a-889c- d9d270727408",
                "gateway": None,
                "vswitch_type": "",
                "state": "up",
                "pci": "0000:03:00.1",
                "slave1": None,
                "slave2": None,
                "type": "ether",
                "deleted": False,
                "netmask": "",
                "max_speed": " 10000baseT/Full ",
                "host_id": "c8a6f556 -fcaa-45ee-9e9f-cce11b6bda07",
                "name": "enp3s0f1",
                "is_deployment": False,
                "created_at": "2016-10-29T00:47:47.000000",
                "mac": "90:e2:ba:8f:df:39",
                "mode": None
            },
            {
                "ip": "",
                "updated_at": "2016-10-29T00:47:47.000000",
                "current_speed": "Unknown!",
                "assigned_networks": [
                    {
                        "ip": "",
                        "type": "DATAPLANE",
                        "name": "physnet1"
                    }
                ],
                "deleted_at": None,
                "id": "8115ed84-0f94-4492-ac4c-d5fc28269e0e",
                "gateway": None,
                "vswitch_type": "ovs",
                "state": "up",
                "pci": "0000:03:00.0",
                "slave1": None,
                "slave2": None,
                "type": "ether",
                "deleted": False,
                "netmask": "",
                "max_speed": " 10000baseT/Full ",
                "host_id": "c8a6f556-fcaa-45ee-9e9f- cce11b6bda07",
                "name": "enp3s0f0",
                "is_deployment": False,
                "created_at": "2016-10-29T00:47:47.000000",
                "mac": "90:e2:ba:8f:df:38",
                "mode": None
            },
            {
                "ip": "99.99.1.54",
                "updated_at": "2016-10-29T00:47:47.000000",
                "current_speed": "100Mb/s",
                "assigned_networks": [
                    {
                        "ip": "192.168.1.235",
                        "type": "MANAGEMENT",
                        "name": "MANAGEMENT"
                    }
                ],
                "deleted_at": None,
                "id": "b17bde98-3f33-4fb9-8daf-f67e99997b93",
                "gateway": None,
                "vswitch_type": "",
                "state": "up",
                "pci": "0000:08:00.0",
                "slave1": None,
                "slave2": None,
                "type": "ether",
                "deleted": False,
                "netmask": "255.255.255.0",
                "max_speed": "1000baseT/Half",
                "host_id": "c8a6f556-fcaa-45ee-9e9f-cce11b6bda07",
                "name": "enp8s0",
                "is_deployment": True,
                "created_at": "2016-10-29T00:47:47.000000",
                "mac": "98:f5:37:e1:af:16",
                "mode": None
            },
            {
                "ip": "",
                "updated_at": "2016-10-29T00:47:47.000000",
                "current_speed": "100Mb/s",
                "assigned_networks": [
                    {
                        "ip": "10.43.203.228",
                        "type": "PUBLICAPI",
                        "name": "PUBLICAPI"
                    }
                ],
                "deleted_at": None,
                "id": "cfc34c28-7947-4c50-b5b5-0b8a20817783",
                "gateway": None,
                "vswitch_type": "",
                "state": "up",
                "pci": "0000:09:00.0",
                "slave1": None,
                "slave2": None,
                "type": "ether",
                "deleted": False,
                "netmask": "",
                "max_speed": "1000baseT/Half",
                "host_id": "c8a6f556-fcaa-45ee-9e9f-cce11b6bda07",
                "name": "enp9s0",
                "is_deployment": False,
                "created_at": "2016-10-29T00:47:47.000000",
                "mac": "98:f5:37:e1:af:17",
                "mode": None
            }
        ],
        "os_progress": 0,
        "ipmi_passwd": "superuser",
        "dvs_config_type": "",
        "resource_type": "baremetal",
        "position": "",
        "version_patch_id": None,
        "tecs_version_id": "",
        "flow_mode": "",
        "ipmi_user": "zteroot",
        "hugepagesize": "1G",
        "name": "host-1-232",
        "dvsblank_cpus": "",
        "created_at": "2016-10-26T09:28:29.000000",
        "disks": {
            "sr0": {
                "name": "sr0",
                "extra": [
                    "ata-Optiarc_DVD_RW_AD-7560S",
                    ""
                ],
                "removable": "removable",
                "model": " Optiarc DVD RW AD-7560S ",
                "disk": "",
                "size": ""
            },
            "sdd": {
                "name": "sdd",
                "extra": [
                    "scsi-3500003963828e760",
                    "wwn-0x500003963828e760"
                ],
                "removable": "",
                "model": "",
                "disk": "pci-0000:01:00.0-sas-0x500003963828e762-lun-0",
                "size": " 300000000000bytes"
            },
            "sde": {
                "name": "sde",
                "extra": [
                    "scsi-3500003963828d3c8",
                    "wwn-0x500003963828d3c8"
                ],
                "removable": "",
                "model": "",
                "disk": "pci-0000:01:00.0-sas-0x500003963828d3ca-lun-0",
                "size": " 300000000000 bytes"
            },
            "sdf": {
                "name": "sdf",
                "extra": [
                    "scsi-3500003963828f778",
                    "wwn-0x500003963828f778"
                ],
                "removable": "",
                "model": "",
                "disk": "pci-0000:01:00.0-sas-0x500003963828f77a-lun-0",
                "size": " 300000000000 bytes"
            },
            "sdg": {
                "name": "sdg",
                "extra": [
                    "scsi-3500003963828e458",
                    "wwn-0x500003963828e458"
                ],
                "removable": "",
                "model": "",
                "disk": "pci-0000:01:00.0-sas-0x500003963828e45a-lun-0",
                "size": " 300000000000bytes"
            },
            "sda": {
                "name": "sda",
                "extra": [
                    "scsi-3500003963828c5ec",
                    "wwn-0x500003963828c5ec"
                ],
                "removable": "",
                "model": "",
                "disk": "pci-0000:01:00.0-sas-0x500003963828c5ee-lun-0",
                "size": " 300000000000 bytes"
            },
            "sdb": {
                "name": "sdb",
                "extra": [
                    "scsi-3500003963829512c",
                    "wwn-0x500003963829512c"
                ],
                "removable": "",
                "model": "",
                "disk": "pci-0000:01:00.0-sas-0x500003963829512e-lun-0",
                "size": " 300000000000 bytes"
            },
            "sdc": {
                "name": "sdc",
                "extra": [
                    "scsi-3500003963828f688",
                    "wwn-0x500003963828f688"
                ],
                "removable": "",
                "model": "",
                "disk": "pci-0000:01:00.0-sas-0x500003963828f68a-lun-0",
                "size": " 300000000000bytes"
            },
            "sdh": {
                "name": "sdh",
                "extra": [
                    "scsi-3500003963828c6f8",
                    "wwn-0x500003963828c6f8"
                ],
                "removable": "",
                "model": "",
                "disk": "pci-0000:01:00.0-sas-0x500003963828c6fa-lun-0",
                "size": " 300000000000 bytes"
            }
        },
        "messages": "",
        "hugepages": 0,
        "os_cpus": "",
        "ipmi_addr": "10.43.203.231",
        "root_pwd": "ossdbg1",
        "dvs_high_cpuset": "",
        "dvs_cpus": None,
        "cpu": {},
        "swap_lv_size": 4096,
        "root_lv_size": 102400
    },
    {
        "os_version_id": None,
        "config_set_id": None,
        "root_disk": None,
        "os_status": "active",
        "isolcpus": None,
        "updated_at": "2016-10-29T07:10:57.000000",
        "group_list": None,
        "cluster": "test2",
        "dvsp_cpus": "",
        "deleted_at": None,
        "id": "dd68c9a0-7c95-424a-bff7-d610d7393dad",
        "vcpu_pin_set": "",
        "dvsv_cpus": "",
        "hwm_ip": None,
        "os_version_file": None,
        "system": {
            "product": "SREMB_B",
            "uuid": "B4B0C76C-4C09-0000-0010-000090B08755",
            "family": " Server",
            "fqdn": "host-10-43-203-227",
            "version": "1.0.0",
            "serial": "210074134038",
            "manufacturer": "ZTE"
        },
        "dmi_uuid": "B4B0C76C-4C09-0000-0010-000090B08755",
        "role": [
            "CONTROLLER_LB",
            "CONTROLLER_HA"
        ],
        "memory": {
            "total": "131894716 kB",
            "phy_memory_1": {
                "maximum_capacity": " 256 GB",
                "devices_5": {
                    "frequency": " 1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                },
                "devices_4": {
                    "frequency": " 1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                },
                "devices_7": {
                    "frequency": " 1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                },
                "devices_6": {
                    "frequency": " 1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                },
                "devices_1": {
                    "frequency": " 1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                },
                "devices_3": {
                    "frequency": " 1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                },
                "devices_2": {
                    "frequency": " 1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                },
                "slots": " 8",
                "devices_8": {
                    "frequency": " 1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                }
            },
            "phy_memory_2": {
                "maximum_capacity": " 256 GB",
                "devices_5": {
                    "frequency": " 1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                },
                "devices_4": {
                    "frequency": "1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                },
                "devices_7": {
                    "frequency": "1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                },
                "devices_6": {
                    "frequency": "1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                },
                "devices_1": {
                    "frequency": "1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                },
                "devices_3": {
                    "frequency": "1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                },
                "devices_2": {
                    "frequency": "1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                },
                "slots": " 8",
                "devices_8": {
                    "frequency": " 1333 MHz",
                    "type": " DDR3",
                    "size": " 8192 MB"
                }
            }
        },
        "virtio_queue_size": "",
        "dvs_config_desc": "",
        "hwm_id": None,
        "pci_high_cpuset": "",
        "status": "with-role",
        "description": "default",
        "dvsc_cpus": "",
        "deleted": False,
        "discover_mode": "SSH",
        "interfaces": [
            {
                "ip": "10.43.203.227",
                "updated_at": "2016-10-29T00:48:11.000000",
                "current_speed": "100Mb/s",
                "assigned_networks": [
                    {
                        "ip": "10.43.203.227",
                        "type": "PUBLICAPI",
                        "name": "PUBLICAPI"
                    }
                ],
                "deleted_at": None,
                "id": "0d8de483-860c-4c2f-98f8-f1a4ae8d9862",
                "gateway": None,
                "vswitch_type": "",
                "state": "up",
                "pci": "0000:09:00.0",
                "slave1": None,
                "slave2": None,
                "type": "ether",
                "deleted": False,
                "netmask": "255.255.254.0",
                "max_speed": "1000baseT/Half",
                "host_id": "dd68c9a0-7c95-424a-bff7-d610d7393dad",
                "name": "enp9s0",
                "is_deployment": False,
                "created_at": "2016-10-29T00:48:11.000000",
                "mac": "98:f5:37:e1:ae:9a",
                "mode": None
            },
            {
                "ip": "192.168.1.227",
                "updated_at": "2016-10-29T00:48:11.000000",
                "current_speed": "100Mb/s",
                "assigned_networks": [
                    {
                        "ip": "192.168.1.227",
                        "type": "MANAGEMENT",
                        "name": "MANAGEMENT"
                    }
                ],
                "deleted_at": None,
                "id": "374f17f4-da11-4f6a-a482-9a7598014d05",
                "gateway": None,
                "vswitch_type": "",
                "state": "up",
                "pci": "0000:08:00.0",
                "slave1": None,
                "slave2": None,
                "type": "ether",
                "deleted": False,
                "netmask": "255.255.255.0",
                "max_speed": "1000baseT/Half",
                "host_id": "dd68c9a0-7c95-424a- bff7-d610d7393dad",
                "name": "enp8s0",
                "is_deployment": False,
                "created_at": "2016-10-29T00:48:11.000000",
                "mac": "98:f5:37:e1:ae:99",
                "mode": None
            },
            {
                "ip": "",
                "updated_at": "2016-10-29T00:48:11.000000",
                "current_speed": "Unknown!",
                "assigned_networks": [
                    {
                        "ip": "",
                        "type": "DATAPLANE",
                        "name": "physnet1"
                    }
                ],
                "deleted_at": None,
                "id": "5127eecc-aa14-4d6d-948a-8cc916a98f84",
                "gateway": None,
                "vswitch_type": "ovs",
                "state": "up",
                "pci": "0000:03:00.0",
                "slave1": None,
                "slave2": None,
                "type": "ether",
                "deleted": False,
                "netmask": "",
                "max_speed": " 10000baseT/Full ",
                "host_id": "dd68c9a0-7c95-424a-bff7-d610d7393dad",
                "name": "enp3s0f0",
                "is_deployment": False,
                "created_at": "2016-10-29T00:48:11.000000",
                "mac": "90:e2:ba:8f:e5:54",
                "mode": None
            },
            {
                "ip": "",
                "updated_at": "2016-10-29T00:48:11.000000",
                "current_speed": "Unknown!",
                "assigned_networks": [],
                "deleted_at": None,
                "id": "ee197e3f-71f3-4b2e-b63c- b80845de6d06",
                "gateway": None,
                "vswitch_type": "",
                "state": "up",
                "pci": "0000:03:00.1",
                "slave1": None,
                "slave2": None,
                "type": "ether",
                "deleted": False,
                "netmask": "",
                "max_speed": " 10000baseT/Full ",
                "host_id": "dd68c9a0-7c95-424a-bff7-d610d7393dad",
                "name": "enp3s0f1",
                "is_deployment": False,
                "created_at": "2016-10-29T00:48:11.000000",
                "mac": "90:e2:ba:8f:e5:55",
                "mode": None
            }
        ],
        "os_progress": 0,
        "ipmi_passwd": "superuser",
        "dvs_config_type": "",
        "resource_type": "baremetal",
        "position": "",
        "version_patch_id": None,
        "tecs_version_id": "",
        "flow_mode": "",
        "ipmi_user": "zteroot",
        "hugepagesize": None,
        "name": "host-10-43-203-227",
        "dvsblank_cpus": "",
        "created_at": "2016-10-27T00:28:05.000000",
        "disks": {
            "vg_data-lv_swap": {
                "name": "vg_data-lv_swap",
                "extra": [
                    "",
                    ""
                ],
                "removable": "",
                "model": "",
                "disk": "",
                "size": " 4294967296 bytes"
            },
            "docker-253-0-4196035-b6b9e884de6206632893d8fe5c056158ea2d2c "
            "99453f600742c5dc7437f5775e":
            {
                "name": "docker-253:0-4196035-b6b9e884de6206632893 "
                        "d8fe5c056158ea2d2c99453f600742c5dc7437f5775e",
                "extra": [
                    "",
                    ""
                ],
                "removable": "",
                "model": "",
                "disk": "",
                "size": " 21474836480 bytes"
            },
            "vg_sys-lv_root": {
                "name": "vg_sys-lv_root",
                "extra": [
                    "",
                    ""
                ],
                "removable": "",
                "model": "",
                "disk": "",
                "size": " 107374182400 bytes"
            },
            "sdd": {
                "name": "sdd",
                "extra": [
                    "scsi-3500003963828c768",
                    "wwn-0x500003963828c768"
                ],
                "removable": "",
                "model": "",
                "disk": "pci-0000:01:00.0-sas-0x500003963828c76a-lun-0\n"
                        "pci-0000:01:00.0 -sas-phy5-lun-0",
                "size": " 300000000000 bytes"
            },
            "sde": {
                "name": "sde",
                "extra": [
                    "scsi-3500003963828e1a4",
                    "wwn-0x500003963828e1a4"
                ],
                "removable": "",
                "model": "",
                "disk": "pci-0000:01:00.0-sas-0x500003963828e1a6-lun-0\n"
                        "pci-0000:01:00.0-sas-phy6-lun-0",
                "size": "300000000000 bytes"
            },
            "sdf": {
                "name": "sdf",
                "extra": [
                    "scsi-3500003963828c6f0",
                    "wwn-0x500003963828c6f0"
                ],
                "removable": "",
                "model": "",
                "disk": "pci-0000:01:00.0-sas-0x500003963828c6f2-lun-0\n"
                        "pci-0000:01:00.0-sas-phy3-lun-0",
                "size": " 300000000000 bytes"
            },
            "vg_data-lv_glance": {
                "name": "vg_data-lv_glance",
                "extra": [
                    "",
                    ""
                ],
                "removable": "",
                "model": "",
                "disk": "",
                "size": " 107374182400 bytes"
            },
            "sda": {
                "name": "sda",
                "extra": [
                    "scsi-3500003963828cba4",
                    "wwn-0x500003963828cba4"
                ],
                "removable": "",
                "model": "",
                "disk": "pci-0000:01:00.0-sas-0x500003963828cba6-lun-0\n"
                        "pci-0000:01:00.0-sas-phy7-lun-0",
                "size": " 300000000000 bytes"
            },
            "sdb": {
                "name": "sdb",
                "extra": [
                    "scsi-3500003963828c63c",
                    "wwn-0x500003963828c63c"
                ],
                "removable": "",
                "model": "",
                "disk": "pci-0000:01:00.0-sas-0x500003963828c63e-lun-0\n"
                        "pci-0000:01:00.0 -sas-phy0-lun-0",
                "size": " 300000000000 bytes"
            },
            "sdc": {
                "name": "sdc",
                "extra": [
                    "scsi-3500003963828c714",
                    "wwn-0x500003963828c714"
                ],
                "removable": "",
                "model": "",
                "disk": "pci-0000:01:00.0-sas-0x500003963828c716-lun-0\n"
                        "pci-0000:01:00.0-sas-phy4-lun-0",
                "size": "300000000000 bytes"
            },
            "docker-253-0-4196035-pool": {
                "name": "docker-253:0-4196035-pool",
                "extra": [
                    "",
                    ""
                ],
                "removable": "",
                "model": "",
                "disk": "",
                "size": " 107374182400 bytes"
            },
            "sdg": {
                "name": "sdg",
                "extra": [
                    "scsi-3500003963828c4c8",
                    "wwn-0x500003963828c4c8"
                ],
                "removable": "",
                "model": "",
                "disk": "pci-0000:01:00.0-sas-0x500003963828c4ca-lun-0\n"
                        "pci-0000:01:00.0 -sas-phy1-lun-0",
                "size": " 300000000000 bytes"
            },
            "sdh": {
                "name": "sdh",
                "extra": [
                    "scsi-3500003963828d3b0",
                    "wwn-0x500003963828d3b0"
                ],
                "removable": "",
                "model": "",
                "disk": "pci-0000:01:00.0-sas-0x500003963828d3b2-lun-0\n"
                        "pci-0000:01:00.0-sas-phy2-lun-0",
                "size": "300000000000 bytes"
            }
        },
        "messages": None,
        "hugepages": 0,
        "os_cpus": "",
        "ipmi_addr": "10.43.203.230",
        "root_pwd": None,
        "dvs_high_cpuset": "",
        "dvs_cpus": None,
        "cpu": {},
        "swap_lv_size": 4096,
        "root_lv_size": 102400
    }]

all_roles = [
    {
        "db_vip": None,
        "docker_vg_size": 0,
        "outband_vip": None,
        "updated_at": "2016-10-27T04:07:41.000000",
        "vip": "192.168.1.231",
        "cluster_id": "2ddb81b5-db73-4e20-894b-b0d59a7babfc",
        "provider_mgnt_vip": None,
        "ntp_server": None,
        "deleted_at": None,
        "id": "9d2d096e-d35e-42cf-92cd-800f07b49828",
        "glance_lv_size": 0,
        "provider_public_vip": None,
        "db_lv_size": 0,
        "progress": 100,
        "type": "default",
        "nova_lv_size": 0,
        "glance_vip": None,
        "config_set_id": "56993301-650c-4290-9b9c-df2fd724ff80",
        "description": "Controller role,backup    type is loadbalance",
        "deleted": False,
        "mongodb_vip": None,
        "tecsclient_vip": None,
        "role_type": "CONTROLLER_LB",
        "deployment_backend": "tecs",
        "name": "CONTROLLER_LB",
        "created_at": "2016-10-26T08:32:45.000000",
        "messages": "TECS    installed successfully",
        "public_vip": None,
        "disk_location": "local",
        "status": "active",
        "config_set_update_progress": 0
    },
    {
        "db_vip": "192.168.1.230",
        "docker_vg_size": 104448,
        "outband_vip": None,
        "updated_at": "2016-10-28T07:01:59.000000",
        "vip": "192.168.1.228",
        "cluster_id": "2ddb81b5-db73-4e20-894b-b0d59a7babfc",
        "provider_mgnt_vip": None,
        "ntp_server": "10.43.114.65",
        "deleted_at": None,
        "id": "5c2242fc-8ce7-45e2-970e-e8f5ae065255",
        "glance_lv_size": 51200,
        "provider_public_vip": None,
        "db_lv_size": 0,
        "progress": 100,
        "type": "default",
        "nova_lv_size": 0,
        "glance_vip": "192.168.1.229",
        "config_set_id": "8f7b2afd-0397-4e33-b550-2e74a53717d6",
        "description": "Controller role,backup    type is HA,active/standby",
        "deleted": False,
        "mongodb_vip": None,
        "tecsclient_vip": None,
        "role_type": "CONTROLLER_HA",
        "deployment_backend": "tecs",
        "name": "CONTROLLER_HA",
        "created_at": "2016-10-26T08:32:45.000000",
        "messages": "TECS installed successfully",
        "public_vip": "10.43.203.228",
        "disk_location": "local",
        "status": "active",
        "config_set_update_progress": 0
    },
    {
        "db_vip": None,
        "docker_vg_size": 0,
        "outband_vip": None,
        "updated_at": "2016-10-27T04:07:41.000000",
        "vip": None,
        "cluster_id": "2ddb81b5-db73-4e20      -894b-b0d59a7babfc",
        "provider_mgnt_vip": None,
        "ntp_server": None,
        "deleted_at": None,
        "id": "429fa45a-3b00-46f2-b034-320bc2c34764",
        "glance_lv_size": 0,
        "provider_public_vip": None,
        "db_lv_size": 0,
        "progress": 100,
        "type": "default",
        "nova_lv_size": 51200,
        "glance_vip": None,
        "config_set_id": "619fc60f-a49d-4098-838c-4a39be83fac5",
        "description": "Compute  role",
        "deleted": False,
        "mongodb_vip": None,
        "tecsclient_vip": None,
        "role_type": "COMPUTER",
        "deployment_backend": "tecs",
        "name": "COMPUTER",
        "created_at": "2016-10-26T08:32:45.000000",
        "messages": "TECS installed   successfully",
        "public_vip": None,
        "disk_location": "local",
        "status": "active",
        "config_set_update_progress": 0
    }]


def stub_get_cluster_metadata(context, cluster_id):
    return {
        "vlan_end": None,
        "updated_at": "2016-10-27T01:45:31.000000",
        "owner": None,
        "networking_parameters": {
            "vni_range": [
                None,
                None
            ],
            "public_vip": "10.43.203.113",
            "net_l23_provider": None,
            "base_mac": "",
            "gre_id_range": [
                None,
                None
            ],
            "vlan_range": [
                None,
                None
            ],
            "segmentation_type": None
        },
        "gre_id_start": None,
        "deleted_at": None,
        "id": "2ddb81b5-db73-4e20-894b-b0d59a7babfc",
        "hwm_ip": "",
        "networks": [
            "65551b9d-d669-47af-96e1-8092e8627ba7",
            "e9b0573c-ca67-4f65-9d0b-97ef210fa577",
            "bbc5dae6-f687-4a76-9fcf-b15d4c57a1cf",
            "b4592115-7a4d-4e63-8e9a-7ff58884a55e",
            "5a3d1ae8-f738-4bc0-a291-85e2df5b4339",
            "324ddc5a-ed08-404a-b50c-006a69685d8a",
            "114000a2-2300-43e6-bf73-05c74793dbd2",
            "0665dad4-ab80-42ac-b91a-a8bd50f0efcd"
        ],
        "base_mac": "",
        "auto_scale": 0,
        "target_systems": "os+tecs",
        "vni_end": None,
        "gre_id_end": None,
        "nodes": [
            "d8568ec2-8659-41bb-a436-a5f3200bd6b0",
            "dd68c9a0-7c95-424a-bff7-d610d7393dad",
            "c8a6f556-fcaa-45ee-9e9f-cce11b6bda07",
            "b7759958-4cbf-4afd-ad48-ec3ca3bfcf4f"
        ],
        "description": "",
        "deleted": False,
        "routers": [

        ],
        "logic_networks": [

        ],
        "net_l23_provider": None,
        "vlan_start": None,
        "tecs_version_id": "3d701745-e56d-44ca-a9d9-2c57d31a4f3d",
        "name": "vertify",
        "created_at": "2016-10-26T08:32:45.000000",
        "public_vip": "10.43.203.113",
        "use_dns": 1,
        "vni_start": None,
        "use_provider_ha": 0,
        "segmentation_type": None
    }


def stub_get_cluster_roles_detail(req, cluster_id):
    return all_roles


def stub_get_network_metadata(context, network_id):
    for network in all_network:
        if network['id'] == network_id:
            return network


def stub_get_networks_detail(context, cluster_id):
    return all_network


def stub_get_hosts_detail(context, **params):
    return [{"id": "c8a6f556-fcaa-45ee-9e9f- cce11b6bda07"},
            {"id": "dd68c9a0-7c95-424a-bff7-d610d7393dad"}]


def stub_get_host_metadata(context, host_id):
    for host in all_hosts:
        if host["id"] == host_id:
            return host


def stub_get_role_metadata(context, role_id):
    for role in all_roles:
        if role["id"] == role_id:
            return role


def stub_subprocesscall(cmd):
    subprocess.call(cmd, shell=True,
                    stdout=open('/dev/null', 'w'),
                    stderr=subprocess.STDOUT)


def stub_land_networks_config(req, cluster_id, update_config):
    pass


def stub_get_role_nodes_info(req, cluster_id):
    role_nodes_info = {'ha': [], 'lb': [], 'computer': []}
    return role_nodes_info


def stub_stop_ha_cluster(req, ssh_hosts_info):
    pass
