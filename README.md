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
# cd make 
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

-rwxr--r-- 1 root root  238848 Apr 11 10:06 atk-2.8.0-4.el7.x86_64.rpm
-rwxr--r-- 1 root root     743 Apr 11 10:06 dependsrpm.sh
-rwxr--r-- 1 root root 1523060 Apr 11 10:06 docutils-0.11-1.noarch.rpm
-rwxr--r-- 1 root root  180124 Apr 11 10:06 fontawesome-fonts-web-4.1.0-2.el7.noarch.rpm
-rwxr--r-- 1 root root  149492 Apr 11 10:06 gd-2.0.35-26.el7.x86_64.rpm
-rwxr--r-- 1 root root  545532 Apr 11 10:06 gdk-pixbuf2-2.28.2-4.el7.x86_64.rpm
-rwxr--r-- 1 root root  376776 Apr 11 10:06 gettext-common-devel-0.18.2.1-4.el7.noarch.rpm
-rwxr--r-- 1 root root  322876 Apr 11 10:06 gettext-devel-0.18.2.1-4.el7.x86_64.rpm
-rwxr--r-- 1 root root 4539368 Apr 11 10:06 git-1.8.3.1-4.el7.x86_64.rpm
-rwxr--r-- 1 root root   82900 Apr 11 10:06 graphite2-1.2.2-5.el7.x86_64.rpm
-rwxr--r-- 1 root root 1329628 Apr 11 10:06 graphviz-2.30.1-19.el7.x86_64.rpm
-rwxr--r-- 1 root root 3540032 Apr 11 10:06 gtk2-2.24.22-5.el7.x86_64.rpm
-rwxr--r-- 1 root root  147956 Apr 11 10:06 harfbuzz-0.9.20-3.el7.x86_64.rpm
-rwxr--r-- 1 root root   43464 Apr 11 10:06 hicolor-icon-theme-0.12-7.el7.noarch.rpm
-rwxr--r-- 1 root root   59532 Apr 11 10:06 intltool-0.50.2-5.el7.noarch.rpm
-rwxr--r-- 1 root root   60752 Apr 11 10:06 intltool-0.50.2-6.el7.noarch.rpm
-rwxr--r-- 1 root root  125956 Apr 11 10:06 librsvg2-2.39.0-1.el7.x86_64.rpm
-rwxr--r-- 1 root root  190988 Apr 11 10:06 libthai-0.1.14-9.el7.x86_64.rpm
-rwxr--r-- 1 root root   49852 Apr 11 10:06 libtool-ltdl-2.4.2-20.el7.x86_64.rpm
-rwxr--r-- 1 root root  193268 Apr 11 10:06 libXaw-1.0.11-6.1.el7.x86_64.rpm
-rwxr--r-- 1 root root   22792 Apr 11 10:06 libXcomposite-0.4.4-4.1.el7.x86_64.rpm
-rwxr--r-- 1 root root   30248 Apr 11 10:06 libXcursor-1.1.14-2.1.el7.x86_64.rpm
-rwxr--r-- 1 root root   58664 Apr 11 10:06 libXft-2.3.1-5.1.el7.x86_64.rpm
-rwxr--r-- 1 root root   40132 Apr 11 10:06 libXi-1.7.2-2.1.el7.x86_64.rpm
-rwxr--r-- 1 root root   71404 Apr 11 10:06 libXmu-1.1.1-5.1.el7.x86_64.rpm
-rwxr--r-- 1 root root   53572 Apr 11 10:06 libXpm-3.5.10-5.1.el7.x86_64.rpm
-rwxr--r-- 1 root root   25676 Apr 11 10:06 libXrandr-1.4.1-2.1.el7.x86_64.rpm
-rwxr--r-- 1 root root  289888 Apr 11 10:06 pango-1.34.1-5.el7.x86_64.rpm
-rwxr--r-- 1 root root  228008 Apr 11 10:06 perl-XML-Parser-2.41-10.el7.x86_64.rpm
-rwxr--r-- 1 root root 1213928 Apr 11 10:06 Pygments-2.0.2-1.noarch.rpm
-rwxr--r-- 1 root root   11832 Apr 11 10:06 python-anyjson-0.3.3-3.el7.noarch.rpm
-rwxr--r-- 1 root root 1624784 Apr 11 10:06 python-boto-2.29.1-1.noarch.rpm
-rwxr--r-- 1 root root   37060 Apr 11 10:06 python-d2to1-0.2.10-3.el7.noarch.rpm
-rwxr--r-- 1 root root   83532 Apr 11 10:06 python-django-appconf-0.6-1.el7.noarch.rpm
-rwxr--r-- 1 root root  169968 Apr 11 10:06 python-django-compressor-1.4-3.el7.noarch.rpm
-rwxr--r-- 1 root root  106092 Apr 11 10:06 python-django-openstack-auth-1.2.0-4.el7.noarch.rpm
-rwxr--r-- 1 root root   15188 Apr 11 10:06 python-django-pyscss-1.0.5-2.el7.noarch.rpm
-rwxr--r-- 1 root root  252528 Apr 11 10:06 python-eventlet-0.17.4-1.el7.noarch.rpm
-rwxr--r-- 1 root root   25952 Apr 11 10:06 python-greenlet-0.4.2-3.el7.x86_64.rpm
-rwxr--r-- 1 root root   18256 Apr 11 10:06 python-iso8601-0.1.10-1.el7.noarch.rpm
-rwxr--r-- 1 root root  527832 Apr 11 10:06 python-jinja2-2.7.2-2.el7.noarch.rpm
-rwxr--r-- 1 root root  583884 Apr 11 10:06 python-keystoneclient-1.3.0-1.el7.noarch.rpm
-rwxr--r-- 1 root root  359016 Apr 11 10:06 python-kombu-2.5.16-1.el7.noarch.rpm
-rwxr--r-- 1 root root   84408 Apr 11 10:06 python-lesscpy-0.9j-4.el7.noarch.rpm
-rwxr--r-- 1 root root   27204 Apr 11 10:06 python-lockfile-0.9.1-4.el7.noarch.rpm
-rwxr--r-- 1 root root  219472 Apr 11 10:06 python-migrate-0.8.2-1.el7.noarch.rpm
-rwxr--r-- 1 root root   40944 Apr 11 10:06 python-oslo-concurrency-1.8.0-1.el7.noarch.rpm
-rwxr--r-- 1 root root  127772 Apr 11 10:06 python-oslo-config-1.9.3-1.el7.noarch.rpm
-rwxr--r-- 1 root root   54452 Apr 11 10:06 python-oslo-i18n-1.5.0-3.el7.noarch.rpm
-rwxr--r-- 1 root root   25620 Apr 11 10:06 python-oslo-serialization-1.4.0-1.el7.noarch.rpm
-rwxr--r-- 1 root root   27528 Apr 11 10:06 python-oslo-sphinx-2.5.0-2.el7.noarch.rpm
-rwxr--r-- 1 root root   86872 Apr 11 10:06 python-oslo-utils-1.4.0-1.el7.noarch.rpm
-rwxr--r-- 1 root root  168716 Apr 11 10:06 python-pbr-0.10.8-1.el7.noarch.rpm
-rwxr--r-- 1 root root  263612 Apr 11 10:06 python-pint-0.6-2.el7.noarch.rpm
-rwxr--r-- 1 root root 1390196 Apr 11 10:06 python-pip-1.5.6-5.el7.noarch.rpm
-rwxr--r-- 1 root root  613160 Apr 11 10:06 python-pygments-1.4-9.el7.noarch.rpm
-rwxr--r-- 1 root root   78028 Apr 11 10:06 python-routes-2.0-1.noarch.rpm
-rwxr--r-- 1 root root  204920 Apr 11 10:06 python-scss-1.2.1-1.el7.x86_64.rpm
-rwxr--r-- 1 root root   29124 Apr 11 10:06 python-six-1.9.0-1.el7.noarch.rpm
-rwxr--r-- 1 root root 1104048 Apr 11 10:06 python-sphinx-1.2.2-1.noarch.rpm
-rwxr--r-- 1 root root 3061784 Apr 11 10:06 python-sqlalchemy-0.9.7-3.el7.x86_64.rpm
-rwxr--r-- 1 root root  206720 Apr 11 10:06 python-webob-1.2.3-8.el7.noarch.rpm
-rwxr--r-- 1 root root    7032 Apr 11 10:06 python-XStatic-1.0.1-1.el7.noarch.rpm
-rwxr--r-- 1 root root  376116 Apr 11 10:06 python-XStatic-Angular-1.3.7.0-4.el7.noarch.rpm
-rwxr--r-- 1 root root   37748 Apr 11 10:06 python-XStatic-Angular-Bootstrap-0.11.0.2-1.el7.noarch.rpm
-rwxr--r-- 1 root root    9228 Apr 11 10:06 python-XStatic-Angular-lrdragndrop-1.0.2.2-1.el7.noarch.rpm
-rwxr--r-- 1 root root   22964 Apr 11 10:06 python-XStatic-Angular-Mock-1.2.1.1-2.el7.noarch.rpm
-rwxr--r-- 1 root root   41048 Apr 11 10:06 python-XStatic-Bootstrap-Datepicker-1.3.1.0-1.el7.noarch.rpm
-rwxr--r-- 1 root root  159176 Apr 11 10:06 python-XStatic-Bootstrap-SCSS-3.2.0.0-1.el7.noarch.rpm
-rwxr--r-- 1 root root   68052 Apr 11 10:06 python-XStatic-D3-3.1.6.2-2.el7.noarch.rpm
-rwxr--r-- 1 root root    9036 Apr 11 10:06 python-XStatic-Font-Awesome-4.1.0.0-4.el7.noarch.rpm
-rwxr--r-- 1 root root   11780 Apr 11 10:06 python-XStatic-Hogan-2.0.0.2-2.el7.noarch.rpm
-rwxr--r-- 1 root root   28340 Apr 11 10:06 python-XStatic-Jasmine-1.3.1.1-2.el7.noarch.rpm
-rwxr--r-- 1 root root  113744 Apr 11 10:06 python-XStatic-jQuery-1.10.2.1-1.el7.noarch.rpm
-rwxr--r-- 1 root root   15576 Apr 11 10:06 python-XStatic-JQuery-Migrate-1.2.1.1-2.el7.noarch.rpm
-rwxr--r-- 1 root root   11524 Apr 11 10:06 python-XStatic-JQuery-quicksearch-2.0.3.1-2.el7.noarch.rpm
-rwxr--r-- 1 root root   24120 Apr 11 10:06 python-XStatic-JQuery-TableSorter-2.14.5.1-2.el7.noarch.rpm
-rwxr--r-- 1 root root  334108 Apr 11 10:06 python-XStatic-jquery-ui-1.10.4.1-1.el7.noarch.rpm
-rwxr--r-- 1 root root   37492 Apr 11 10:06 python-XStatic-JSEncrypt-2.0.0.2-2.el7.noarch.rpm
-rwxr--r-- 1 root root   12460 Apr 11 10:06 python-XStatic-Magic-Search-0.2.0.1-1.el7.noarch.rpm
-rwxr--r-- 1 root root   25700 Apr 11 10:06 python-XStatic-QUnit-1.14.0.2-2.el7.noarch.rpm
-rwxr--r-- 1 root root   32012 Apr 11 10:06 python-XStatic-Rickshaw-1.5.0.0-4.el7.noarch.rpm
-rwxr--r-- 1 root root   10936 Apr 11 10:06 python-XStatic-smart-table-1.4.5.3-1.el7.noarch.rpm
-rwxr--r-- 1 root root    9760 Apr 11 10:06 python-XStatic-Spin-1.2.5.2-2.el7.noarch.rpm
-rwxr--r-- 1 root root   38644 Apr 11 10:06 python-XStatic-termjs-0.0.4.2-1.el7.noarch.rpm



