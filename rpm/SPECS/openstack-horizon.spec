%global release_name kilo
%global service horizon

%{!?upstream_version: %global upstream_version %{version}%{?milestone}}

%global with_compression 1

Name:       python-django-horizon
Version:    1.0.0
Release:    %{_release}
Summary:    Django application for talking to Openstack

Group:      Development/Libraries
# Code in horizon/horizon/utils taken from django which is BSD
License:    ASL 2.0 and BSD
URL:        http://horizon.openstack.org/
Source0:    http://launchpad.net/%{service}/%{release_name}/%{version}/+download/%{service}-%{upstream_version}.tar.gz

Patch0001: 0001-disable-debug-move-web-root.patch
Patch0002: 0002-remove-runtime-dep-to-python-pbr.patch
Patch0003: 0003-Add-a-customization-module-based-on-RHOS.patch
Patch0004: 0004-RCUE-navbar-and-login-screen.patch
Patch0005: 0005-re-add-lesscpy-to-compile-.less.patch
Patch0006: 0006-Migration-of-LESS-to-SCSS-and-various-fixes.patch
Patch0007: 0007-Remove-the-redundant-Settings-button-on-downstream-t.patch
Patch0008: 0008-Add-dropdown-actions-to-detail-page.patch
Patch0009: 0009-Add-dropdown-actions-to-all-details-pages.patch
Patch0010: 0010-Add-support-for-row-actions-to-detail-pages.patch
Patch0011: 0011-Restore-missing-translation-for-the-downstream-theme.patch
Patch0012: 0012-IE-bug-fixes-https-bugzilla.redhat.com-show_bug.cgi-.patch
Patch0013: 0013-Change-branding.patch
Patch0014: 0014-Add-missing-translation-for-the-downstream-theme-zh_.patch
Patch0015: 0015-Adapt-paths-for-theme-subpackage.patch
Patch0016: 0016-Fixing-data-processing-operations-for-alternate-webr.patch
Patch0017: 0017-More-theme-fixes.patch
Patch0018: 0018-fix-region-selector-for-theme.patch

Source2:    openstack-dashboard-httpd-2.4.conf

# systemd snippet to collect static files and compress on httpd restart
Source3:    python-django-horizon-systemd.conf

# demo config for separate logging
Source4:    openstack-dashboard-httpd-logging.conf

# logrotate config
Source5:    python-django-horizon-logrotate.conf

#
# BuildArch needs to be located below patches in the spec file. Don't ask!
#

BuildArch:  noarch

BuildRequires:   python-django
Requires:   python-django


Requires:   pytz
Requires:   python-lockfile
Requires:   python-six >= 1.7.0
Requires:   python-pbr

BuildRequires: python2-devel
BuildRequires: python-setuptools
BuildRequires: python-pbr >= 0.10.8
BuildRequires: python-lockfile
BuildRequires: python-eventlet
BuildRequires: git
BuildRequires: python-six >= 1.9.0
BuildRequires: gettext

# for checks:
%if 0%{?rhel} == 0
BuildRequires:   python-django-nose >= 1.2
BuildRequires:   python-coverage
BuildRequires:   python-mox
BuildRequires:   python-nose-exclude
BuildRequires:   python-nose
BuildRequires:   python-selenium
%endif
BuildRequires:   python-netaddr
BuildRequires:   python-kombu
BuildRequires:   python-anyjson
BuildRequires:   python-iso8601


# additional provides to be consistent with other django packages
Provides: django-horizon = %{version}-%{release}

%description
Horizon is a Django application for providing Openstack UI components.
It allows performing site administrator (viewing account resource usage,
configuring users, accounts, quotas, flavors, etc.) and end user
operations (start/stop/delete instances, create/restore snapshots, view
instance VNC console, etc.)
CI Build Id = %{_description}
SVN Revision = %{_svn_revision}

%package -n daisy-dashboard
Summary:    Daisy web user interface reference implementation
Group:      Applications/System

Requires:   httpd
Requires:   mod_wsgi
Requires:   %{name} = %{version}-%{release}
Requires:   python-django-openstack-auth >= 1.1.7
Requires:   python-django-compressor >= 1.4
Requires:   python-django-appconf
%if %{?with_compression} > 0
Requires:   python-lesscpy
%endif

# Requires:   python-glanceclient
Requires:   python-keystoneclient >= 0.7.0
# Requires:   python-novaclient >= 2.15.0
# Requires:   python-neutronclient
# Requires:   python-cinderclient >= 1.0.6
# Requires:   python-swiftclient
# Requires:   python-heatclient
# Requires:   python-ceilometerclient
# Requires:   python-troveclient >= 1.0.0
# Requires:   python-saharaclient
Requires:   python-netaddr
Requires:   python-oslo-config
Requires:   python-eventlet
Requires:   python-django-pyscss >= 1.0.5
Requires:   python-XStatic
Requires:   python-XStatic-jQuery
Requires:   python-XStatic-Angular >= 1:1.3.7
Requires:   python-XStatic-Angular-Mock
Requires:   python-XStatic-Angular-Bootstrap
Requires:   python-XStatic-D3
Requires:   python-XStatic-Font-Awesome >= 4.1.0.0-4
Requires:   python-XStatic-Hogan
Requires:   python-XStatic-JQuery-Migrate
Requires:   python-XStatic-JQuery-TableSorter
Requires:   python-XStatic-JQuery-quicksearch
Requires:   python-XStatic-JSEncrypt
Requires:   python-XStatic-Jasmine
Requires:   python-XStatic-QUnit
Requires:   python-XStatic-Rickshaw
Requires:   python-XStatic-Spin
Requires:   python-XStatic-jquery-ui
Requires:   python-XStatic-Bootstrap-Datepicker
Requires:   python-XStatic-Bootstrap-SCSS
Requires:   python-XStatic-termjs
Requires:   python-XStatic-smart-table
Requires:   python-XStatic-Angular-lrdragndrop
Requires:   python-XStatic-Magic-Search

Requires:   python-scss >= 1.2.1
Requires:   fontawesome-fonts-web >= 4.1.0

Requires:   python-oslo-concurrency
Requires:   python-oslo-config
Requires:   python-oslo-i18n
Requires:   python-oslo-serialization
Requires:   python-oslo-utils
Requires:   python-babel
Requires:   python-pint

Requires:   openssl
Requires:   logrotate

BuildRequires: python-django-openstack-auth >= 1.2.0
BuildRequires: python-django-compressor >= 1.4
BuildRequires: python-django-appconf
BuildRequires: python-lesscpy
BuildRequires: python-oslo-config >= 1.9.3
BuildRequires: python-django-pyscss >= 1.0.5
BuildRequires: python-XStatic
BuildRequires: python-XStatic-jQuery
BuildRequires: python-XStatic-Angular >= 1:1.3.7
BuildRequires: python-XStatic-Angular-Mock
BuildRequires: python-XStatic-Angular-Bootstrap
BuildRequires: python-XStatic-D3
BuildRequires: python-XStatic-Font-Awesome
BuildRequires: python-XStatic-Hogan
BuildRequires: python-XStatic-JQuery-Migrate
BuildRequires: python-XStatic-JQuery-TableSorter
BuildRequires: python-XStatic-JQuery-quicksearch
BuildRequires: python-XStatic-JSEncrypt
BuildRequires: python-XStatic-Jasmine
BuildRequires: python-XStatic-QUnit
BuildRequires: python-XStatic-Rickshaw
BuildRequires: python-XStatic-Spin
BuildRequires: python-XStatic-jquery-ui
BuildRequires: python-XStatic-Bootstrap-Datepicker
BuildRequires: python-XStatic-Bootstrap-SCSS
BuildRequires: python-XStatic-termjs
BuildRequires: python-XStatic-smart-table
BuildRequires: python-XStatic-Angular-lrdragndrop
BuildRequires: python-XStatic-Magic-Search
# bootstrap-scss requires at least python-scss >= 1.2.1
BuildRequires: python-scss >= 1.2.1
BuildRequires: fontawesome-fonts-web >= 4.1.0
BuildRequires: python-oslo-concurrency
BuildRequires: python-oslo-config
BuildRequires: python-oslo-i18n
BuildRequires: python-oslo-serialization
BuildRequires: python-oslo-utils >= 1.4.0
BuildRequires: python-babel
BuildRequires: python-pint

BuildRequires: pytz
BuildRequires: systemd

%description -n daisy-dashboard
Daisy Dashboard is a web user interface for Daisy. The package
provides a reference implementation using the Django Horizon project,
mostly consisting of JavaScript and CSS to tie it altogether as a standalone
site.
CI Build Id = %{_description}
SVN Revision = %{_svn_revision}

%package doc
Summary:    Documentation for Django Horizon
Group:      Documentation

Requires:   %{name} = %{version}-%{release}
BuildRequires: python-sphinx >= 1.1.3

# Doc building basically means we have to mirror Requires:
# BuildRequires: python-glanceclient
BuildRequires: python-keystoneclient
# BuildRequires: python-novaclient >= 2.15.0
# BuildRequires: python-neutronclient
# BuildRequires: python-cinderclient
# BuildRequires: python-swiftclient
# BuildRequires: python-heatclient
# BuildRequires: python-ceilometerclient
# BuildRequires: python-troveclient >= 1.0.0
# BuildRequires: python-saharaclient
# BuildRequires: python-oslo-sphinx >= 2.3.0

%description doc
Documentation for the Django Horizon application for talking with Openstack

# %package -n openstack-dashboard-theme
# Summary: OpenStack web user interface reference implementation theme module
# Requires: openstack-dashboard = %{version}

# %description -n openstack-dashboard-theme
# Customization module for OpenStack Dashboard to provide a branded logo.
# CI Build Id = %{_description}
# SVN Revision = %{_svn_revision}

%prep
%setup -q -n horizon-%{upstream_version}

# remove precompiled egg-info
rm -rf horizon.egg-info

# Use git to manage patches.
# http://rwmj.wordpress.com/2011/08/09/nice-rpm-git-patch-management-trick/
git init
git config user.email "python-django-horizon-owner@fedoraproject.org"
git config user.name "python-django-horizon"
git add .
git commit -a -q -m "%{version} baseline"
# git am %{patches}

# remove unnecessary .mo files
# they will be generated later during package build
find . -name "django*.mo" -exec rm -f '{}' \;

# Remove the requirements file so that pbr hooks don't add it
# to distutils requires_dist config
rm -rf {test-,}requirements.txt tools/{pip,test}-requires

# drop config snippet
cp -p %{SOURCE4} .

%if 0%{?with_compression} > 0
# set COMPRESS_OFFLINE=True
sed -i 's:COMPRESS_OFFLINE.=.False:COMPRESS_OFFLINE = True:' openstack_dashboard/settings.py
%else
# set COMPRESS_OFFLINE=False
sed -i 's:COMPRESS_OFFLINE = True:COMPRESS_OFFLINE = False:' openstack_dashboard/settings.py
%endif



%build
# compile message strings
cd horizon && django-admin compilemessages && cd ..
cd openstack_dashboard && django-admin compilemessages && cd ..
%{__python} setup.py build

# compress css, js etc.
cp openstack_dashboard/local/local_settings.py.example openstack_dashboard/local/local_settings.py

mkdir -p /var/log/horizon/

# get it ready for compressing later in puppet-horizon
%{__python} manage.py collectstatic --noinput


# build docs
export PYTHONPATH="$( pwd ):$PYTHONPATH"
sphinx-build -b html doc/source html

# undo hack
cp openstack_dashboard/local/local_settings.py.example openstack_dashboard/local/local_settings.py

# Fix hidden-file-or-dir warnings
rm -fr html/.doctrees html/.buildinfo

%install
%{__python} setup.py install -O1 --skip-build --root %{buildroot}

# drop httpd-conf snippet
install -m 0644 -D -p %{SOURCE2} %{buildroot}%{_sysconfdir}/httpd/conf.d/openstack-dashboard.conf
install -d -m 755 %{buildroot}%{_datadir}/openstack-dashboard
install -d -m 755 %{buildroot}%{_sharedstatedir}/openstack-dashboard
install -d -m 755 %{buildroot}%{_sysconfdir}/openstack-dashboard


# create directory for systemd snippet
mkdir -p %{buildroot}%{_unitdir}/httpd.service.d/
cp %{SOURCE3} %{buildroot}%{_unitdir}/httpd.service.d/openstack-dashboard.conf

# Copy everything to /usr/share
mv %{buildroot}%{python_sitelib}/openstack_dashboard \
   %{buildroot}%{_datadir}/openstack-dashboard
cp manage.py %{buildroot}%{_datadir}/openstack-dashboard
rm -rf %{buildroot}%{python_sitelib}/openstack_dashboard

# remove unnecessary .po files
find %{buildroot} -name django.po -exec rm '{}' \;
find %{buildroot} -name djangojs.po -exec rm '{}' \;

# Move config to /etc, symlink it back to /usr/share
mv %{buildroot}%{_datadir}/openstack-dashboard/openstack_dashboard/local/local_settings.py.example %{buildroot}%{_sysconfdir}/openstack-dashboard/local_settings
ln -s ../../../../../%{_sysconfdir}/openstack-dashboard/local_settings %{buildroot}%{_datadir}/openstack-dashboard/openstack_dashboard/local/local_settings.py

# mv %{buildroot}%{_datadir}/openstack-dashboard/openstack_dashboard/conf/*.json %{buildroot}%{_sysconfdir}/openstack-dashboard

%find_lang django
%find_lang djangojs

grep "\/usr\/share\/openstack-dashboard" django.lang > dashboard.lang
grep "\/site-packages\/horizon" django.lang > horizon.lang

%if 0%{?rhel} > 6 || 0%{?fedora} >= 16
cat djangojs.lang >> horizon.lang
%endif

# copy static files to %{_datadir}/openstack-dashboard/static
mkdir -p %{buildroot}%{_datadir}/openstack-dashboard/static
cp -a openstack_dashboard/static/* %{buildroot}%{_datadir}/openstack-dashboard/static
cp -a horizon/static/* %{buildroot}%{_datadir}/openstack-dashboard/static 
cp -a static/* %{buildroot}%{_datadir}/openstack-dashboard/static

# create /var/run/openstack-dashboard/ and own it
mkdir -p %{buildroot}%{_sharedstatedir}/openstack-dashboard

# create /var/log/horizon and own it
mkdir -p %{buildroot}%{_var}/log/horizon

# place logrotate config:
mkdir -p %{buildroot}%{_sysconfdir}/logrotate.d
cp -a %{SOURCE5} %{buildroot}%{_sysconfdir}/logrotate.d/openstack-dashboard


%check
# don't run tests on rhel
%if 0%{?rhel} == 0
# since rawhide has django-1.7 now, tests fail
#./run_tests.sh -N -P
%endif

%post -n daisy-dashboard
# ugly hack to set a unique SECRET_KEY
sed -i "/^from horizon.utils import secret_key$/d" /etc/openstack-dashboard/local_settings
sed -i "/^SECRET_KEY.*$/{N;s/^.*$/SECRET_KEY='`openssl rand -hex 10`'/}" /etc/openstack-dashboard/local_settings
systemctl daemon-reload >/dev/null 2>&1 || :

%postun
# update systemd unit files
%{systemd_postun}

%files -f horizon.lang
%doc README.rst openstack-dashboard-httpd-logging.conf
%license LICENSE
%dir %{python_sitelib}/horizon
%{python_sitelib}/horizon/*.py*
%{python_sitelib}/horizon/browsers
%{python_sitelib}/horizon/conf
%{python_sitelib}/horizon/contrib
%{python_sitelib}/horizon/forms
%{python_sitelib}/horizon/management
%{python_sitelib}/horizon/static
%{python_sitelib}/horizon/tables
%{python_sitelib}/horizon/tabs
%{python_sitelib}/horizon/templates
%{python_sitelib}/horizon/templatetags
%{python_sitelib}/horizon/test
%{python_sitelib}/horizon/utils
%{python_sitelib}/horizon/workflows
%{python_sitelib}/*.egg-info

%files -n daisy-dashboard -f dashboard.lang
%dir %{_datadir}/openstack-dashboard/
%{_datadir}/openstack-dashboard/*.py*
%{_datadir}/openstack-dashboard/static
%{_datadir}/openstack-dashboard/openstack_dashboard/*.py*
%{_datadir}/openstack-dashboard/openstack_dashboard/api
%dir %{_datadir}/openstack-dashboard/openstack_dashboard/dashboards/
%{_datadir}/openstack-dashboard/openstack_dashboard/dashboards/environment
%{_datadir}/openstack-dashboard/openstack_dashboard/dashboards/__init__.py*
%{_datadir}/openstack-dashboard/openstack_dashboard/django_pyscss_fix
%{_datadir}/openstack-dashboard/openstack_dashboard/enabled
# %exclude %{_datadir}/openstack-dashboard/openstack_dashboard/enabled/_99_customization.*
%{_datadir}/openstack-dashboard/openstack_dashboard/local
%{_datadir}/openstack-dashboard/openstack_dashboard/management
%{_datadir}/openstack-dashboard/openstack_dashboard/openstack
%{_datadir}/openstack-dashboard/openstack_dashboard/static
%{_datadir}/openstack-dashboard/openstack_dashboard/templates
%{_datadir}/openstack-dashboard/openstack_dashboard/templatetags
%{_datadir}/openstack-dashboard/openstack_dashboard/test
# %{_datadir}/openstack-dashboard/openstack_dashboard/usage
%{_datadir}/openstack-dashboard/openstack_dashboard/utils
%{_datadir}/openstack-dashboard/openstack_dashboard/wsgi
%dir %{_datadir}/openstack-dashboard/openstack_dashboard
%dir %{_datadir}/openstack-dashboard/openstack_dashboard/locale
%dir %{_datadir}/openstack-dashboard/openstack_dashboard/locale/??
%dir %{_datadir}/openstack-dashboard/openstack_dashboard/locale/??_??
%dir %{_datadir}/openstack-dashboard/openstack_dashboard/locale/??/LC_MESSAGES
%dir %{_datadir}/openstack-dashboard/openstack_dashboard/locale/??_??/LC_MESSAGES

%dir %attr(0750, root, apache) %{_sysconfdir}/openstack-dashboard
%dir %attr(0750, apache, apache) %{_sharedstatedir}/openstack-dashboard
%dir %attr(0750, apache, apache) %{_var}/log/horizon
%config(noreplace) %{_sysconfdir}/httpd/conf.d/openstack-dashboard.conf
%config(noreplace) %attr(0640, root, apache) %{_sysconfdir}/openstack-dashboard/local_settings
# %config(noreplace) %attr(0640, root, apache) %{_sysconfdir}/openstack-dashboard/ceilometer_policy.json
# %config(noreplace) %attr(0640, root, apache) %{_sysconfdir}/openstack-dashboard/cinder_policy.json
# %config(noreplace) %attr(0640, root, apache) %{_sysconfdir}/openstack-dashboard/keystone_policy.json
# %config(noreplace) %attr(0640, root, apache) %{_sysconfdir}/openstack-dashboard/nova_policy.json
# %config(noreplace) %attr(0640, root, apache) %{_sysconfdir}/openstack-dashboard/glance_policy.json
# %config(noreplace) %attr(0640, root, apache) %{_sysconfdir}/openstack-dashboard/neutron_policy.json
# %config(noreplace) %attr(0640, root, apache) %{_sysconfdir}/openstack-dashboard/heat_policy.json
%{_sysconfdir}/logrotate.d/openstack-dashboard
%attr(755,root,root) %dir %{_unitdir}/httpd.service.d
%config(noreplace) %{_unitdir}/httpd.service.d/openstack-dashboard.conf

%files doc
%doc html

# %files -n openstack-dashboard-theme
# %{_datadir}/openstack-dashboard/openstack_dashboard/dashboards/theme
# %{_datadir}/openstack-dashboard/openstack_dashboard/enabled/_99_customization.*

%changelog
* Fri May 08 2015 Matthias Runge <mrunge@redhat.com> - 2015.1.0-5
- fix region selector in -theme
- honor moved webroot a little better (rhbz#1218627)
- make sure, systemd service is reloaded (rhbz#1219006)

* Wed May 06 2015 Matthias Runge <mrunge@redhat.com> - 2015.1.0-3
- theme fixes

* Fri May 01 2015  2015.1.0-2
- Fixing data processing operations for alternate webroots (sahara)
  https://bugs.launchpad.net/horizon/+bug/1450535

* Thu Apr 30 2015 Alan Pevec <alan.pevec@redhat.com> 2015.1.0-1
- OpenStack Kilo release
