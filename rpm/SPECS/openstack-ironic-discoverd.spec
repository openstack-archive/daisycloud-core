%{?!_licensedir:%global license %%doc}

Name:		openstack-ironic-discoverd
Summary:	Hardware introspection service for OpenStack Ironic
Version:	1.0.0
Release:	%{_release}%{?dist}
License:	ASL 2.0
Group:		System Environment/Base
URL:		https://pypi.python.org/pypi/ironic-discoverd

Source0:        https://pypi.python.org/packages/source/i/ironic-discoverd/ironic-discoverd-%{version}.tar.gz
Source1:        openstack-ironic-discoverd.service
Source2:        openstack-ironic-discoverd-dnsmasq.service
Source3:        dnsmasq.conf

BuildArch:	noarch
BuildRequires:	python-setuptools
BuildRequires:	python2-devel
BuildRequires:	systemd
Requires: python-ironic-discoverd = %{version}-%{release}
Requires: dnsmasq
Requires(post): systemd
Requires(preun): systemd
Requires(postun): systemd


%prep
%autosetup -v -p 1 -n ironic-discoverd-%{version}

rm -rf *.egg-info

# Remove the requirements file so that pbr hooks don't add it
# to distutils requires_dist config
rm -rf {test-,}requirements.txt tools/{pip,test}-requires

%build
%{__python2} setup.py build

%install
%{__python2} setup.py install -O1 --skip-build --root=%{buildroot}
mkdir -p %{buildroot}%{_mandir}/man8
install -p -D -m 644 ironic-discoverd.8 %{buildroot}%{_mandir}/man8/

# install systemd scripts
mkdir -p %{buildroot}%{_unitdir}
install -p -D -m 644 %{SOURCE1} %{buildroot}%{_unitdir}
install -p -D -m 644 %{SOURCE2} %{buildroot}%{_unitdir}

# configuration contains passwords, thus 640
install -p -D -m 640 example.conf %{buildroot}/%{_sysconfdir}/ironic-discoverd/discoverd.conf
install -p -D -m 644 %{SOURCE3} %{buildroot}/%{_sysconfdir}/ironic-discoverd/dnsmasq.conf


%package -n python-ironic-discoverd
Summary: Hardware introspection service for OpenStack Ironic - Python modules
Requires: python-eventlet
Requires: python-flask
Requires: python-keystoneclient
Requires: python-keystonemiddleware
Requires: python-requests
Requires: python-setuptools
Requires: python-six
Conflicts: openstack-ironic-discoverd < 1.0.0-1

%description -n python-ironic-discoverd
ironic-discoverd is a service for discovering hardware properties for a node
managed by OpenStack Ironic. Hardware introspection or hardware properties
discovery is a process of getting hardware parameters required for scheduling
from a bare metal node, given it's power management credentials (e.g. IPMI
address, user name and password).

This package contains Python modules and documentation.

%files -n python-ironic-discoverd
%doc README.rst CONTRIBUTING.rst
%license LICENSE
%{python2_sitelib}/ironic_discoverd*


%description
ironic-discoverd is a service for discovering hardware properties for a node
managed by OpenStack Ironic. Hardware introspection or hardware properties
discovery is a process of getting hardware parameters required for scheduling
from a bare metal node, given it's power management credentials (e.g. IPMI
address, user name and password).

This package contains main executable and service files.

%files
%license LICENSE
%config(noreplace) %attr(-,root,root) %{_sysconfdir}/ironic-discoverd
%{_bindir}/ironic-discoverd
%{_unitdir}/openstack-ironic-discoverd.service
%{_unitdir}/openstack-ironic-discoverd-dnsmasq.service
%doc %{_mandir}/man8/ironic-discoverd.8.gz

%post
%systemd_post openstack-ironic-discoverd.service
%systemd_post openstack-ironic-discoverd-dnsmasq.service

%preun
%systemd_preun openstack-ironic-discoverd.service
%systemd_preun openstack-ironic-discoverd-dnsmasq.service

%postun
%systemd_postun_with_restart openstack-ironic-discoverd.service
%systemd_postun_with_restart openstack-ironic-discoverd-dnsmasq.service


%changelog

* Tue Mar 3 2015 Dmitry Tantsur <dtantsur@redhat.com> - 1.0.2-1
- New upstream bugfix release: 1.0.2
- Remove requirements.txt before building
- Dependency on python-keystonemiddleware

* Tue Feb 3 2015 Dmitry Tantsur <dtantsur@redhat.com> - 1.0.0-1
- New upstream release: 1.0.0
- Set default database location to simplify upgrades
- Split into two packages: the service and Python modules

* Thu Dec 4 2014 Dmitry Tantsur <dtantsur@redhat.com> - 0.2.5-1
- Upstream bugfix release 0.2.5
- Install CONTRIBUTING.rst

* Fri Nov 14 2014 Dmitry Tantsur <dtantsur@redhat.com> - 0.2.4-1
- Upstream bugfix release 0.2.4
  Only cosmetic code update, reflects move to StackForge and Launchpad.
- Take description from upstream README.

* Mon Oct 27 2014 Dmitry Tantsur <dtantsur@redhat.com> - 0.2.2-1
- Upstream bugfix release 0.2.2
- Sync all descriptions with upstream variant

* Thu Oct 23 2014 Dmitry Tantsur <dtantsur@redhat.com> - 0.2.1-2
- Require dnsmasq
- Add openstack-ironic-discoverd-dnsmasq.service - sample service for dnsmasq
- Updated description to upstream version

* Thu Oct 16 2014 Dmitry Tantsur <dtantsur@redhat.com> - 0.2.1-1
- Upstream bugfix release

* Wed Oct 8 2014 Dmitry Tantsur <dtantsur@redhat.com> - 0.2.0-1- Initial package build

