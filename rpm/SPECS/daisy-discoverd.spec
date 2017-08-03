%{?!_licensedir:%global license %%doc}

Name:		daisy-discoverd
Summary:	Hardware introspection service for Daisy
Version:	1.0.0
Release:	%{_release}%{?dist}
License:	ASL 2.0
Group:		System Environment/Base
URL:		http://www.daisycloud.org

Source0:        https://pypi.python.org/packages/source/i/daisy-discoverd/daisy-discoverd-%{version}.tar.gz
Source1:        daisy-discoverd.service
Source2:        daisy-discoverd-dnsmasq.service
Source3:        dnsmasq.conf

BuildArch:	noarch
BuildRequires:	python-setuptools
BuildRequires:	python2-devel
BuildRequires:	systemd
Requires: python-daisy-discoverd = %{version}-%{release}
Requires: dnsmasq
Requires(post): systemd
Requires(preun): systemd
Requires(postun): systemd


%prep
%autosetup -v -p 1 -n daisy-discoverd-%{version}

rm -rf *.egg-info

# Remove the requirements file so that pbr hooks don't add it
# to distutils requires_dist config
rm -rf {test-,}requirements.txt tools/{pip,test}-requires

%build
%{__python2} setup.py build

%install
%{__python2} setup.py install -O1 --skip-build --root=%{buildroot}
mkdir -p %{buildroot}%{_mandir}/man8
install -p -D -m 644 daisy-discoverd.8 %{buildroot}%{_mandir}/man8/

# install systemd scripts
mkdir -p %{buildroot}%{_unitdir}
install -p -D -m 644 %{SOURCE1} %{buildroot}%{_unitdir}
install -p -D -m 644 %{SOURCE2} %{buildroot}%{_unitdir}

# configuration contains passwords, thus 640
install -p -D -m 640 example.conf %{buildroot}/%{_sysconfdir}/daisy-discoverd/discoverd.conf
install -p -D -m 644 %{SOURCE3} %{buildroot}/%{_sysconfdir}/daisy-discoverd/dnsmasq.conf

install -d -m 755 %{buildroot}%{_localstatedir}/log/daisy-discoverd
install -d -m 755 %{buildroot}%{_localstatedir}/lib/daisy-discoverd
install -d -m 755 %{buildroot}%{_localstatedir}/run/daisy-discoverd

%package -n python-daisy-discoverd
Summary: Hardware introspection service for OpenStack Ironic - Python modules
Requires: python-eventlet
Requires: python-flask
Requires: python-keystoneclient
Requires: python-keystonemiddleware
Requires: python-requests
Requires: python-setuptools
Requires: python-six

%description -n python-daisy-discoverd
daisy-discoverd is a service for discovering hardware properties for a node
managed by Daisy installer. Hardware introspection or hardware properties
discovery is a process of getting hardware parameters required for scheduling
from a bare metal node, given it's power management credentials (e.g. IPMI
address, user name and password).

This package contains Python modules and documentation.

%files -n python-daisy-discoverd
%doc README.rst CONTRIBUTING.rst
%license LICENSE
%{python2_sitelib}/daisy_discoverd*


%description
daisy-discoverd is a service for discovering hardware properties for a node
managed by Daisy installer. Hardware introspection or hardware properties
discovery is a process of getting hardware parameters required for scheduling
from a bare metal node, given it's power management credentials (e.g. IPMI
address, user name and password).

This package contains main executable and service files.

%files
%license LICENSE
%config(noreplace) %attr(-,root,root) %{_sysconfdir}/daisy-discoverd
%{_bindir}/daisy-discoverd
%{_unitdir}/daisy-discoverd.service
%{_unitdir}/daisy-discoverd-dnsmasq.service
%doc %{_mandir}/man8/daisy-discoverd.8.gz

%dir %attr(0755, daisy, daisy) %{_localstatedir}/log/daisy-discoverd
%dir %attr(0755, daisy, daisy) %{_localstatedir}/lib/daisy-discoverd
%dir %attr(0755, daisy, daisy) %{_localstatedir}/run/daisy-discoverd

%post
%systemd_post daisy-discoverd.service
%systemd_post daisy-discoverd-dnsmasq.service

%preun
%systemd_preun daisy-discoverd.service
%systemd_preun daisy-discoverd-dnsmasq.service

%postun
%systemd_postun_with_restart daisy-discoverd.service
%systemd_postun_with_restart daisy-discoverd-dnsmasq.service

