[toc]

Daisy(Openstack project name: daisycloud-core)


Daisy provides automated deployment and management of OpenStack and other distributed systems.

## Website
http://www.daisycloud.org

## Code Layout

code/daisy: The core logic code.
code/daisyclient: The command line interface code. TODO: To be splited out as another project.
code/horizon: The web interface code. TODO: To be splited out as another project.

## Build Daisy artifact

```
# yum install -y epel-release
# yum install -y centos-release-openstack-mitaka
# cd tools
# ./daisy-compile-rpm.sh 
# cd ../make 
# make allrpm
```

Then the artifacts will be at target/el7/noarch/, with name such as installdaisy_el7_noarch.bin.

## Install Daisy

```
# cd target/el7/noarch/
# ./installdaisy_el7_noarch.bin
Verifying archive integrity... All good.
Uncompressing daisy.....................................................................................................................................................................................

====================================
    ZTE DAISY Installation Wizard
====================================
1. install
2. upgrade
3. clean
4. help
5. exit

Please select an operation: 1
```

## Test Daisy

TODO


## Prefered version of python modules



Althrough we are working on catching up with the latest upstream components, currently we still tested building & running Daisy not with the latest upstream python modules but the specific versions list below:

atk-2.8.0-4.el7.x86_64.rpm  
docutils-0.11-1.noarch.rpm  
fontawesome-fonts-web-4.1.0-2.el7.noarch.rpm  
gd-2.0.35-26.el7.x86_64.rpm  
gdk-pixbuf2-2.28.2-4.el7.x86_64.rpm  
gettext-common-devel-0.18.2.1-4.el7.noarch.rpm  
gettext-devel-0.18.2.1-4.el7.x86_64.rpm  
git-1.8.3.1-4.el7.x86_64.rpm  
graphite2-1.2.2-5.el7.x86_64.rpm  
graphviz-2.30.1-19.el7.x86_64.rpm  
gtk2-2.24.22-5.el7.x86_64.rpm  
harfbuzz-0.9.20-3.el7.x86_64.rpm  
hicolor-icon-theme-0.12-7.el7.noarch.rpm  
intltool-0.50.2-5.el7.noarch.rpm  
intltool-0.50.2-6.el7.noarch.rpm  
librsvg2-2.39.0-1.el7.x86_64.rpm  
libthai-0.1.14-9.el7.x86_64.rpm  
libtool-ltdl-2.4.2-20.el7.x86_64.rpm  
libXaw-1.0.11-6.1.el7.x86_64.rpm  
libXcomposite-0.4.4-4.1.el7.x86_64.rpm  
libXcursor-1.1.14-2.1.el7.x86_64.rpm  
libXft-2.3.1-5.1.el7.x86_64.rpm  
libXi-1.7.2-2.1.el7.x86_64.rpm  
libXmu-1.1.1-5.1.el7.x86_64.rpm  
libXpm-3.5.10-5.1.el7.x86_64.rpm  
libXrandr-1.4.1-2.1.el7.x86_64.rpm  
pango-1.34.1-5.el7.x86_64.rpm  
perl-XML-Parser-2.41-10.el7.x86_64.rpm  
Pygments-2.0.2-1.noarch.rpm  
python-anyjson-0.3.3-3.el7.noarch.rpm  
python-boto-2.29.1-1.noarch.rpm  
python-d2to1-0.2.10-3.el7.noarch.rpm  
python-django-appconf-0.6-1.el7.noarch.rpm  
python-django-compressor-1.4-3.el7.noarch.rpm  
python-django-openstack-auth-1.2.0-4.el7.noarch.rpm  
python-django-pyscss-1.0.5-2.el7.noarch.rpm  
python-eventlet-0.17.4-1.el7.noarch.rpm  
python-greenlet-0.4.2-3.el7.x86_64.rpm  
python-iso8601-0.1.10-1.el7.noarch.rpm  
python-jinja2-2.7.2-2.el7.noarch.rpm  
python-keystoneclient-1.3.0-1.el7.noarch.rpm  
python-kombu-2.5.16-1.el7.noarch.rpm  
python-lesscpy-0.9j-4.el7.noarch.rpm  
python-lockfile-0.9.1-4.el7.noarch.rpm  
python-migrate-0.8.2-1.el7.noarch.rpm  
python-oslo-concurrency-1.8.0-1.el7.noarch.rpm  
python-oslo-config-1.9.3-1.el7.noarch.rpm  
python-oslo-i18n-1.5.0-3.el7.noarch.rpm  
python-oslo-serialization-1.4.0-1.el7.noarch.rpm  
python-oslo-sphinx-2.5.0-2.el7.noarch.rpm  
python-oslo-utils-1.4.0-1.el7.noarch.rpm  
python-pbr-0.10.8-1.el7.noarch.rpm  
python-pint-0.6-2.el7.noarch.rpm  
python-pip-1.5.6-5.el7.noarch.rpm  
python-pygments-1.4-9.el7.noarch.rpm  
python-routes-2.0-1.noarch.rpm  
python-scss-1.2.1-1.el7.x86_64.rpm  
python-six-1.9.0-1.el7.noarch.rpm  
python-sphinx-1.2.2-1.noarch.rpm  
python-sqlalchemy-0.9.7-3.el7.x86_64.rpm  
python-webob-1.2.3-8.el7.noarch.rpm  
python-XStatic-1.0.1-1.el7.noarch.rpm  
python-XStatic-Angular-1.3.7.0-4.el7.noarch.rpm  
python-XStatic-Angular-Bootstrap-0.11.0.2-1.el7.noarch.rpm  
python-XStatic-Angular-lrdragndrop-1.0.2.2-1.el7.noarch.rpm  
python-XStatic-Angular-Mock-1.2.1.1-2.el7.noarch.rpm  
python-XStatic-Bootstrap-Datepicker-1.3.1.0-1.el7.noarch.rpm  
python-XStatic-Bootstrap-SCSS-3.2.0.0-1.el7.noarch.rpm  
python-XStatic-D3-3.1.6.2-2.el7.noarch.rpm  
python-XStatic-Font-Awesome-4.1.0.0-4.el7.noarch.rpm  
python-XStatic-Hogan-2.0.0.2-2.el7.noarch.rpm  
python-XStatic-Jasmine-1.3.1.1-2.el7.noarch.rpm  
python-XStatic-jQuery-1.10.2.1-1.el7.noarch.rpm  
python-XStatic-JQuery-Migrate-1.2.1.1-2.el7.noarch.rpm  
python-XStatic-JQuery-quicksearch-2.0.3.1-2.el7.noarch.rpm  
python-XStatic-JQuery-TableSorter-2.14.5.1-2.el7.noarch.rpm  
python-XStatic-jquery-ui-1.10.4.1-1.el7.noarch.rpm  
python-XStatic-JSEncrypt-2.0.0.2-2.el7.noarch.rpm  
python-XStatic-Magic-Search-0.2.0.1-1.el7.noarch.rpm  
python-XStatic-QUnit-1.14.0.2-2.el7.noarch.rpm  
python-XStatic-Rickshaw-1.5.0.0-4.el7.noarch.rpm  
python-XStatic-smart-table-1.4.5.3-1.el7.noarch.rpm  
python-XStatic-Spin-1.2.5.2-2.el7.noarch.rpm   
python-XStatic-termjs-0.0.4.2-1.el7.noarch.rpm
