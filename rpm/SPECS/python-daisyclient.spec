Name:             python-daisyclient
Epoch:            1
Version:          1.0.0
Release:          %{_release}%{?dist}
Summary:          Python API and CLI for OpenStack daisy

License:          ASL 2.0
URL:              http://github.com/openstack/python-daisyclient
Source0:          https://pypi.python.org/packages/source/p/%{name}/%{name}-%{version}.tar.gz

BuildArch:        noarch
BuildRequires:    python2-devel
BuildRequires:    python-setuptools
BuildRequires:    python-d2to1
BuildRequires:    python-pbr

Requires:         python-httplib2
Requires:         python-keystoneclient
Requires:         python-oslo-utils
Requires:         python-pbr
Requires:         python-prettytable
Requires:         python-requests >= 2.2.0
Requires:         python-setuptools
Requires:         python-warlock
Requires:         pyOpenSSL


%description
This is a client for the OpenStack daisy API. There's a Python API (the
daisyclient module), and a command-line script (daisy). Each implements
100% of the OpenStack daisy API.
CI Build Id = %{_description}
SVN Revision = %{_svn_revision}

%package doc
Summary:          Documentation for OpenStack Nova API Client

BuildRequires:    python-sphinx
BuildRequires:    python-oslo-sphinx

%description      doc
This is a client for the OpenStack daisy API. There's a Python API (the
daisyclient module), and a command-line script (daisy). Each implements
100% of the OpenStack daisy API.

This package contains auto-generated documentation.
CI Build Id = %{_description}
SVN Revision = %{_svn_revision}

%prep
%setup -q

# Remove bundled egg-info
rm -rf python_daisyclient.egg-info
# let RPM handle deps
sed -i '/setup_requires/d; /install_requires/d; /dependency_links/d' setup.py
rm -rf {,test-}requirements.txt


%build
%{__python2} setup.py build


%install
%{__python2} setup.py install -O1 --skip-build --root %{buildroot}

export PYTHONPATH="$( pwd ):$PYTHONPATH"
sphinx-build -b html doc/source html

# generate man page
#sphinx-build -b man doc/source man
#install -p -D -m 644 man/daisy.1 %{buildroot}%{_mandir}/man1/daisy.1


%files
%doc README.rst
%doc LICENSE
%{_bindir}/daisy
%{python2_sitelib}/daisyclient
%{python2_sitelib}/*.egg-info
#%{_mandir}/man1/daisy.1.gz

%files doc
%doc html

