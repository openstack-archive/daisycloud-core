Name:		   pxe_server_install
License:   GPL
Group:     Platform Software Department 3 of ZTE Corporation
Version:	 1.0.8
Release:	 %{_release}
Vendor:		 ZTE Corporation
Summary:	 Path for pxe server install.
Packager:  ZTE-OS
Source:    %{name}-%{_release}.tar.gz
BuildRoot: %{_tmppath}/%{name}-%{_release}-root
Requires: tar coreutils
BuildArchitectures: noarch

%define _binaries_in_noarch_packages_terminate_build   0


%description
the path indicated for pxe install .

%prep
%setup -q -n %{name}-%{_release}

%install
echo $RPM_BUILD_ROOT
/bin/rm -rf $RPM_BUILD_ROOT
#make install INSTALLROOT="$RPM_BUILD_ROOT" KVER=%{bit_32}
#chmod -R 755 ${RPM_BUILD_ROOT}/etc/pxe_install


mkdir -p $RPM_BUILD_ROOT/usr/bin/
#mkdir -p $RPM_BUILD_ROOT/etc/pxe_install/
mkdir -p $RPM_BUILD_ROOT/etc/pxe_install/usrdata/
mkdir -p $RPM_BUILD_ROOT/etc/pxe_install/json_format/
mkdir -p $RPM_BUILD_ROOT/etc/pxe_install/scripts/custom/after/nova_compute_mem_moni/
mkdir -p $RPM_BUILD_ROOT/etc/pxe_install/scripts/custom/after/moni_port/
mkdir -p $RPM_BUILD_ROOT/etc/pxe_install/scripts/custom/interact/
mkdir -p $RPM_BUILD_ROOT/etc/pxe_install/scripts/custom/before/
mkdir -p $RPM_BUILD_ROOT/etc/pxe_install/ramdisk/
mkdir -p $RPM_BUILD_ROOT/etc/pxe_install/pxe/



#cp -a pxe_install/*             $RPM_BUILD_ROOT/etc/pxe_install/
cp pxe_os_install           $RPM_BUILD_ROOT/usr/bin/pxe_os_install
cp pxe_os_install_progress  $RPM_BUILD_ROOT/usr/bin/pxe_os_install_progress
cp pxe_os_install_clean  $RPM_BUILD_ROOT/usr/bin/pxe_os_install_clean
cp pxe_server_install       $RPM_BUILD_ROOT/usr/bin/pxe_server_install
cp pxe_server_check         $RPM_BUILD_ROOT/usr/bin/pxe_server_check

cp pxe_install/usrdata/readme.txt                                                              $RPM_BUILD_ROOT/etc/pxe_install/usrdata/readme.txt
cp pxe_install/json_format/server.json                                                         $RPM_BUILD_ROOT/etc/pxe_install/json_format/server.json
cp pxe_install/json_format/os.json                                                             $RPM_BUILD_ROOT/etc/pxe_install/json_format/os.json
cp pxe_install/scripts/nic_net_cfg.sh                                                          $RPM_BUILD_ROOT/etc/pxe_install/scripts/nic_net_cfg.sh
cp pxe_install/scripts/create_pxesvr.sh                                                        $RPM_BUILD_ROOT/etc/pxe_install/scripts/create_pxesvr.sh
cp pxe_install/scripts/custom/interact.sh                                                      $RPM_BUILD_ROOT/etc/pxe_install/scripts/custom/interact.sh
cp pxe_install/scripts/custom/after.sh                                                         $RPM_BUILD_ROOT/etc/pxe_install/scripts/custom/after.sh
cp pxe_install/scripts/custom/before.sh                                                        $RPM_BUILD_ROOT/etc/pxe_install/scripts/custom/before.sh
#cp pxe_install/scripts/custom/after/nova_compute_mem_moni/nova_compute_mem_moni.py             $RPM_BUILD_ROOT/etc/pxe_install/scripts/custom/after/nova_compute_mem_moni/nova_compute_mem_moni.py
#cp pxe_install/scripts/custom/after/nova_compute_mem_moni/nova_compute_mem_moni_daemonize.py   $RPM_BUILD_ROOT/etc/pxe_install/scripts/custom/after/nova_compute_mem_moni/nova_compute_mem_moni_daemonize.py
cp pxe_install/scripts/custom/after/address_update.sh                                          $RPM_BUILD_ROOT/etc/pxe_install/scripts/custom/after/address_update.sh
cp pxe_install/scripts/custom/after/create_bond.sh                                             $RPM_BUILD_ROOT/etc/pxe_install/scripts/custom/after/create_bond.sh
cp pxe_install/scripts/custom/after/moni_port/nic_vf_status.c                                  $RPM_BUILD_ROOT/etc/pxe_install/scripts/custom/after/moni_port/nic_vf_status.c
cp pxe_install/scripts/custom/after/moni_port/nic_update                                       $RPM_BUILD_ROOT/etc/pxe_install/scripts/custom/after/moni_port/nic_update
cp pxe_install/scripts/custom/after/moni_port/moni_port_status.sh                              $RPM_BUILD_ROOT/etc/pxe_install/scripts/custom/after/moni_port/moni_port_status.sh
cp pxe_install/scripts/custom/after/moni_port/moni_port_status                                 $RPM_BUILD_ROOT/etc/pxe_install/scripts/custom/after/moni_port/moni_port_status
cp pxe_install/scripts/custom/after/install_moni_port.sh                                       $RPM_BUILD_ROOT/etc/pxe_install/scripts/custom/after/install_moni_port.sh
cp pxe_install/scripts/custom/after/install_nova_compute_mem_moni.sh                           $RPM_BUILD_ROOT/etc/pxe_install/scripts/custom/after/install_nova_compute_mem_moni.sh
cp pxe_install/scripts/custom/readme.txt                                                       $RPM_BUILD_ROOT/etc/pxe_install/scripts/custom/readme.txt
cp pxe_install/scripts/custom/interact/neutron_interact.sh                                     $RPM_BUILD_ROOT/etc/pxe_install/scripts/custom/interact/neutron_interact.sh
cp pxe_install/scripts/custom/before/create_manager_port_bond.sh                               $RPM_BUILD_ROOT/etc/pxe_install/scripts/custom/before/create_manager_port_bond.sh
cp pxe_install/scripts/custom/custom.conf                                                      $RPM_BUILD_ROOT/etc/pxe_install/scripts/custom/custom.conf
cp pxe_install/scripts/interface.sh                                                            $RPM_BUILD_ROOT/etc/pxe_install/scripts/interface.sh
cp pxe_install/scripts/setup_func.sh                                                           $RPM_BUILD_ROOT/etc/pxe_install/scripts/setup_func.sh
cp pxe_install/scripts/query_progress.sh                                                       $RPM_BUILD_ROOT/etc/pxe_install/scripts/query_progress.sh
cp pxe_install/scripts/common.sh                                                               $RPM_BUILD_ROOT/etc/pxe_install/scripts/common.sh
cp pxe_install/ramdisk/initrd.img                                                              $RPM_BUILD_ROOT/etc/pxe_install/ramdisk/initrd.img
cp pxe_install/ramdisk/vmlinuz                                                                 $RPM_BUILD_ROOT/etc/pxe_install/ramdisk/vmlinuz
cp pxe_install/pxe/ipxe-roms-qemu-20130517-5.gitc4bce43.el7.noarch.rpm                         $RPM_BUILD_ROOT/etc/pxe_install/pxe/ipxe-roms-qemu-20130517-5.gitc4bce43.el7.noarch.rpm
cp pxe_install/pxe/dhcpd.conf                                                                  $RPM_BUILD_ROOT/etc/pxe_install/pxe/dhcpd.conf
cp pxe_install/pxe/dhcp-common-4.2.5-27.el7.x86_64.rpm                                         $RPM_BUILD_ROOT/etc/pxe_install/pxe/dhcp-common-4.2.5-27.el7.x86_64.rpm
cp pxe_install/pxe/xinetd-2.3.15-12.el7.x86_64.rpm                                             $RPM_BUILD_ROOT/etc/pxe_install/pxe/xinetd-2.3.15-12.el7.x86_64.rpm
cp pxe_install/pxe/tftp-5.2-11.el7.x86_64.rpm                                                  $RPM_BUILD_ROOT/etc/pxe_install/pxe/tftp-5.2-11.el7.x86_64.rpm
cp pxe_install/pxe/dhcp-4.2.5-27.el7.x86_64.rpm                                                $RPM_BUILD_ROOT/etc/pxe_install/pxe/dhcp-4.2.5-27.el7.x86_64.rpm
cp pxe_install/pxe/default                                                                     $RPM_BUILD_ROOT/etc/pxe_install/pxe/default
cp pxe_install/pxe/dhcp-libs-4.2.5-27.el7.x86_64.rpm                                           $RPM_BUILD_ROOT/etc/pxe_install/pxe/dhcp-libs-4.2.5-27.el7.x86_64.rpm
cp pxe_install/pxe/tftp-server-5.2-11.el7.x86_64.rpm                                           $RPM_BUILD_ROOT/etc/pxe_install/pxe/tftp-server-5.2-11.el7.x86_64.rpm
cp pxe_install/pxe/ntpdate-4.2.6p5-18.el7.x86_64.rpm                                           $RPM_BUILD_ROOT/etc/pxe_install/pxe/ntpdate-4.2.6p5-18.el7.x86_64.rpm
cp pxe_install/pxe/pxe_kickstart.cfg                                                           $RPM_BUILD_ROOT/etc/pxe_install/pxe/pxe_kickstart.cfg
cp pxe_install/pxe/linuxinstall.mount                                                          $RPM_BUILD_ROOT/etc/pxe_install/pxe/linuxinstall.mount
cp pxe_install/pxe/tftp                                                                        $RPM_BUILD_ROOT/etc/pxe_install/pxe/tftp
cp pxe_install/pxe/syslinux-4.05-8.el7.x86_64.rpm                                              $RPM_BUILD_ROOT/etc/pxe_install/pxe/syslinux-4.05-8.el7.x86_64.rpm
cp pxe_install/pxe/jq-1.3-2.el7.x86_64.rpm                                                     $RPM_BUILD_ROOT/etc/pxe_install/pxe/jq-1.3-2.el7.x86_64.rpm



chmod -R 755 ${RPM_BUILD_ROOT}/etc/pxe_install
chmod +x $RPM_BUILD_ROOT/usr/bin/pxe_os_install
chmod +x $RPM_BUILD_ROOT/usr/bin/pxe_os_install_progress
chmod +x $RPM_BUILD_ROOT/usr/bin/pxe_os_install_clean
chmod +x $RPM_BUILD_ROOT/usr/bin/pxe_server_install
chmod +x $RPM_BUILD_ROOT/usr/bin/pxe_server_check


%files
%defattr(-,root,root)
/usr/bin/pxe_os_install
/usr/bin/pxe_os_install_progress
/usr/bin/pxe_os_install_clean
/usr/bin/pxe_server_install
/usr/bin/pxe_server_check
#/etc/pxe_install/

%doc /etc/pxe_install/usrdata/readme.txt
/etc/pxe_install/scripts/nic_net_cfg.sh
/etc/pxe_install/json_format/server.json
/etc/pxe_install/json_format/os.json
/etc/pxe_install/scripts/create_pxesvr.sh
/etc/pxe_install/scripts/custom/interact.sh
/etc/pxe_install/scripts/custom/after.sh
/etc/pxe_install/scripts/custom/before.sh
#/etc/pxe_install/scripts/custom/after/nova_compute_mem_moni/nova_compute_mem_moni.py
#/etc/pxe_install/scripts/custom/after/nova_compute_mem_moni/nova_compute_mem_moni_daemonize.py
/etc/pxe_install/scripts/custom/after/address_update.sh
/etc/pxe_install/scripts/custom/after/create_bond.sh
/etc/pxe_install/scripts/custom/after/moni_port/nic_vf_status.c
/etc/pxe_install/scripts/custom/after/moni_port/nic_update
/etc/pxe_install/scripts/custom/after/moni_port/moni_port_status.sh
/etc/pxe_install/scripts/custom/after/moni_port/moni_port_status
/etc/pxe_install/scripts/custom/after/install_moni_port.sh
/etc/pxe_install/scripts/custom/after/install_nova_compute_mem_moni.sh
/etc/pxe_install/scripts/custom/readme.txt
/etc/pxe_install/scripts/custom/interact/neutron_interact.sh
/etc/pxe_install/scripts/custom/before/create_manager_port_bond.sh
/etc/pxe_install/scripts/custom/custom.conf
/etc/pxe_install/scripts/interface.sh
/etc/pxe_install/scripts/setup_func.sh
/etc/pxe_install/scripts/query_progress.sh
/etc/pxe_install/scripts/common.sh
/etc/pxe_install/ramdisk/initrd.img
/etc/pxe_install/ramdisk/vmlinuz
/etc/pxe_install/pxe/ipxe-roms-qemu-20130517-5.gitc4bce43.el7.noarch.rpm
/etc/pxe_install/pxe/dhcpd.conf
/etc/pxe_install/pxe/dhcp-common-4.2.5-27.el7.x86_64.rpm
/etc/pxe_install/pxe/xinetd-2.3.15-12.el7.x86_64.rpm
/etc/pxe_install/pxe/tftp-5.2-11.el7.x86_64.rpm
/etc/pxe_install/pxe/dhcp-4.2.5-27.el7.x86_64.rpm
/etc/pxe_install/pxe/default
/etc/pxe_install/pxe/dhcp-libs-4.2.5-27.el7.x86_64.rpm
/etc/pxe_install/pxe/tftp-server-5.2-11.el7.x86_64.rpm
/etc/pxe_install/pxe/ntpdate-4.2.6p5-18.el7.x86_64.rpm
/etc/pxe_install/pxe/pxe_kickstart.cfg
/etc/pxe_install/pxe/linuxinstall.mount
/etc/pxe_install/pxe/tftp
/etc/pxe_install/pxe/syslinux-4.05-8.el7.x86_64.rpm
/etc/pxe_install/pxe/jq-1.3-2.el7.x86_64.rpm







#%dir %{_prefix}/.channels







%clean
/bin/rm -rf $RPM_BUILD_ROOT

%post

%postun
if [ $1 -eq 0 ];then
/bin/rm -rf /etc/pxe_install
/bin/rm -rf /usr/bin/pxe_os_install
/bin/rm -rf /usr/bin/pxe_os_install_progress
/bin/rm -rf /usr/bin/pxe_server_install
/bin/rm -rf /usr/bin/pxe_os_install_clean
fi
%changelog
