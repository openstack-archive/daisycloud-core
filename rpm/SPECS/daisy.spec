%global release_name kilo
%global service daisy

%{!?upstream_version: %global upstream_version %{version}%{?milestone}}

Name:             daisy
Version:          1.0.0
Release:          %{_release}%{?dist}
Summary:          OpenStack Image Service

Group:            Applications/System
License:          ASL 2.0
URL:              http://daisy.openstack.org
Source0:          http://launchpad.net/%{service}/%{release_name}/%{version}/+download/%{service}-%{upstream_version}.tar.gz

Source1:          daisy-api.service
Source2:          daisy-registry.service
Source4:          daisy.logrotate

Source5:          daisy-api-dist.conf
Source6:          daisy-registry-dist.conf
Source9:          daisy-orchestration.service
Source10:         daisy-orchestration.conf

BuildArch:        noarch
BuildRequires:    python2-devel
BuildRequires:    python-setuptools
BuildRequires:    python-pbr
BuildRequires:    intltool

Requires(pre):    shadow-utils
Requires:         python-daisy = %{version}-%{release}
Requires:         python-daisyclient >= 1:0
Requires:         openstack-utils

Requires(post): systemd
Requires(preun): systemd
Requires(postun): systemd
BuildRequires: systemd

%description
OpenStack Image Service (code-named daisy) provides discovery, registration,
and delivery services for virtual disk images. The Image Service API server
provides a standard REST interface for querying information about virtual disk
images stored in a variety of back-end stores, including OpenStack Object
Storage. Clients can register new virtual disk images with the Image Service,
query for information on publicly available disk images, and use the Image
Service's client library for streaming virtual disk images.

This package contains the API and registry servers.
CI Build Id = %{_description}
SVN Revision = %{_svn_revision}

%package -n       python-daisy
Summary:          daisy Python libraries
Group:            Applications/System

Requires:         MySQL-python
Requires:         pysendfile
Requires:         python-eventlet
Requires:         python-httplib2
Requires:         python-iso8601
Requires:         python-jsonschema
Requires:         python-migrate >= 0.9.5
Requires:         python-paste-deploy
Requires:         python-routes
Requires:         python-sqlalchemy >= 0.8.7
Requires:         python-webob
Requires:         python-crypto
Requires:         pyxattr
Requires:         python-cinderclient
Requires:         python-glance-store >= 0.3.0
Requires:         python-keystoneclient >= 1:1.1.0
Requires:         python-keystonemiddleware
Requires:         python-swiftclient >= 2.2.0
Requires:         python-oslo-config >= 1:1.9.3
Requires:         python-oslo-concurrency >= 1.8.0
Requires:         python-oslo-context >= 0.2.0
Requires:         python-oslo-utils >= 1.4.0
Requires:         python-oslo-log >= 1.0.0
Requires:         python-oslo-policy >= 0.3.1
Requires:         python-oslo-serialization >= 1.4.0
Requires:         python-oslo-messaging >= 1.8.0
Requires:         python-oslo-vmware >= 0.11.1
Requires:         python-oslo-i18n >= 1.5.0
Requires:         python-oslo-db >= 1.7.0
Requires:         python-osprofiler
Requires:         python-retrying
Requires:         python-six >= 1.9.0
Requires:         python-posix_ipc
Requires:         python-stevedore
Requires:         python-anyjson
Requires:         python-netaddr
Requires:         python-wsme >= 0.6
Requires:         pyOpenSSL
Requires:         python-pbr
Requires:         python-semantic-version
Requires:         python-elasticsearch
Requires:         python-taskflow
Requires:         python-repoze-lru

#test deps: python-mox python-nose python-requests
#test and optional store:
#ceph - daisy.store.rdb
#python-boto - daisy.store.s3
Requires:         python-boto

%description -n   python-daisy
OpenStack Image Service (code-named daisy) provides discovery, registration,
and delivery services for virtual disk images.

This package contains the daisy Python library.
CI Build Id = %{_description}
SVN Revision = %{_svn_revision}

%package doc
Summary:          Documentation for OpenStack Image Service
Group:            Documentation

Requires:         %{name} = %{version}-%{release}

BuildRequires:    systemd-units
BuildRequires:    python-sphinx
BuildRequires:    python-oslo-sphinx
BuildRequires:    graphviz

# Required to build module documents
BuildRequires:    python-boto
BuildRequires:    python-eventlet
BuildRequires:    python-routes
BuildRequires:    python-sqlalchemy
BuildRequires:    python-webob

%description      doc
OpenStack Image Service (code-named daisy) provides discovery, registration,
and delivery services for virtual disk images.

This package contains documentation files for daisy.
CI Build Id = %{_description}
SVN Revision = %{_svn_revision}

%prep
%setup -q -n daisy-%{upstream_version}

# Remove the requirements file so that pbr hooks don't add it
# to distutils requiers_dist config
rm -rf {test-,}requirements.txt tools/{pip,test}-requires

# Programmatically update defaults in example config
api_dist=%{SOURCE5}
registry_dist=%{SOURCE6}

%build
%{__python2} setup.py build

%install
%{__python2} setup.py install -O1 --skip-build --root %{buildroot}

# Delete tests
rm -fr %{buildroot}%{python2_sitelib}/daisy/tests

# Drop old daisy CLI it has been deprecated
# and replaced daisyclient
rm -f %{buildroot}%{_bindir}/daisy

export PYTHONPATH="$( pwd ):$PYTHONPATH"
pushd doc
sphinx-build -b html source build/html
#sphinx-build -b man source build/man

mkdir -p %{buildroot}%{_mandir}/man1
#install -p -D -m 644 build/man/*.1 %{buildroot}%{_mandir}/man1/
popd

# Fix hidden-file-or-dir warnings
rm -fr doc/build/html/.doctrees doc/build/html/.buildinfo
rm -f %{buildroot}%{_sysconfdir}/daisy*.conf
rm -f %{buildroot}%{_sysconfdir}/daisy*.ini
rm -f %{buildroot}%{_sysconfdir}/logging.cnf.sample
rm -f %{buildroot}%{_sysconfdir}/policy.json
rm -f %{buildroot}/usr/share/doc/daisy/README.rst

# Setup directories
install -d -m 755 %{buildroot}%{_datadir}/daisy
install -d -m 755 %{buildroot}%{_sharedstatedir}/daisy/images

# Config file
install -p -D -m 640 etc/daisy-api.conf %{buildroot}%{_sysconfdir}/daisy/daisy-api.conf
install -p -D -m 640 etc/daisy-orchestration.conf %{buildroot}%{_sysconfdir}/daisy/daisy-orchestration.conf
install -p -D -m 644 %{SOURCE5} %{buildroot}%{_datadir}/daisy/daisy-api-dist.conf
install -p -D -m 644 etc/daisy-api-paste.ini %{buildroot}%{_datadir}/daisy/daisy-api-dist-paste.ini
install -p -D -m 644 etc/daisy-api-paste.ini %{buildroot}%{_sysconfdir}/daisy/daisy-api-paste.ini
install -p -D -m 640 etc/daisy-registry.conf %{buildroot}%{_sysconfdir}/daisy/daisy-registry.conf
install -p -D -m 644 %{SOURCE6} %{buildroot}%{_datadir}/daisy/daisy-registry-dist.conf
install -p -D -m 644 etc/daisy-registry-paste.ini %{buildroot}%{_datadir}/daisy/daisy-registry-dist-paste.ini
install -p -D -m 644 etc/daisy-registry-paste.ini %{buildroot}%{_sysconfdir}/daisy/daisy-registry-paste.ini

install -p -D -m 640 etc/policy.json %{buildroot}%{_sysconfdir}/daisy/policy.json

# systemd services
install -p -D -m 644 %{SOURCE1} %{buildroot}%{_unitdir}/daisy-api.service
install -p -D -m 644 %{SOURCE2} %{buildroot}%{_unitdir}/daisy-registry.service
install -p -D -m 644 %{SOURCE9} %{buildroot}%{_unitdir}/daisy-orchestration.service

# Logrotate config
install -p -D -m 644 %{SOURCE4} %{buildroot}%{_sysconfdir}/logrotate.d/daisy

# Install pid directory
install -d -m 755 %{buildroot}%{_localstatedir}/run/daisy

# Install log directory
install -d -m 755 %{buildroot}%{_localstatedir}/log/daisy


mkdir -p %{buildroot}/var/lib/daisy
cp -Rf ../kolla %{buildroot}/var/lib/daisy

%pre
id daisy
if [ $? -ne 0 ];then
	groupadd -r daisy --gid 1610
	useradd -u 1610 -r -g daisy -d %{_sharedstatedir}/daisy -s /bin/bash \
-c "OpenStack daisy Daemons" daisy
else
	usermod -u 1610 daisy
	groupmod -g 1610 daisy
fi
exit 0

%post
# Initial installation
%systemd_post daisy-api.service
%systemd_post daisy-registry.service
%systemd_post daisy-orchestration.service


%preun
%systemd_preun daisy-api.service
%systemd_preun daisy-registry.service
%systemd_preun daisy-orchestration.service

%postun
%systemd_postun_with_restart daisy-api.service
%systemd_postun_with_restart daisy-registry.service
%systemd_postun_with_restart daisy-orchestration.service

if [ $1 -eq 0 ] ; then
    rm -rf /var/lib/daisy
fi

%files
/var/lib/daisy/kolla/trustme.sh
/var/lib/daisy/kolla/prepare.sh
/var/lib/daisy/kolla/getnodeinfo.sh
/etc/daisy/daisy-api-paste.ini
/etc/daisy/daisy-registry-paste.ini
%doc README.rst
%{_bindir}/daisy-api
%{_bindir}/daisy-manage
%{_bindir}/daisy-registry
%{_bindir}/daisy-orchestration

%{_datadir}/daisy/daisy-api-dist.conf
%{_datadir}/daisy/daisy-registry-dist.conf
%{_datadir}/daisy/daisy-api-dist-paste.ini
%{_datadir}/daisy/daisy-registry-dist-paste.ini

%{_unitdir}/daisy-api.service
%{_unitdir}/daisy-registry.service
%{_unitdir}/daisy-orchestration.service


#%{_mandir}/man1/daisy*.1.gz
%dir %{_sysconfdir}/daisy
%config(noreplace) %attr(-, root, daisy) %{_sysconfdir}/daisy/daisy-api-paste.ini
%config(noreplace) %attr(-, root, daisy) %{_sysconfdir}/daisy/daisy-registry-paste.ini
%config(noreplace) %attr(-, root, daisy) %{_sysconfdir}/daisy/daisy-api.conf
%config(noreplace) %attr(-, root, daisy) %{_sysconfdir}/daisy/daisy-registry.conf
%config(noreplace) %attr(-, root, daisy) %{_sysconfdir}/daisy/daisy-orchestration.conf
%config(noreplace) %attr(-, root, daisy) %{_sysconfdir}/daisy/policy.json
%config(noreplace) %attr(-, root, daisy) %{_sysconfdir}/logrotate.d/daisy
%dir %attr(0755, daisy, daisy) %{_sharedstatedir}/daisy
%dir %attr(0750, daisy, daisy) %{_localstatedir}/log/daisy
%dir %attr(0755, daisy, daisy) %{_localstatedir}/run/daisy
%dir %attr(0755, daisy, daisy) /var/lib/daisy/*
%dir %attr(0777, all, all) /var/lib/daisy/kolla/
%attr(0755, daisy, daisy) /var/lib/daisy/kolla/*

%files -n python-daisy
%doc README.rst
%{python2_sitelib}/daisy
%{python2_sitelib}/*.egg-info

%files doc
%doc doc/build/html


