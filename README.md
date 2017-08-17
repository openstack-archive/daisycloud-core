[toc]

Daisy(Openstack project name: daisycloud-core)


Daisy provides automated deployment and management of OpenStack and other distributed systems.

## Website
http://www.daisycloud.org

## Code Layout

* code/daisy: core logic code.
* code/daisyclient: command line interface code.
* code/horizon: web interface code.

## Build Daisy artifact

```
# cd tools
# ./daisy-compile-rpm.sh
# cd ../make
# make allrpm
```

The artifacts will be at target/el7/noarch/, with name such as installdaisy_el7_noarch.bin.

## Install Daisy

NOTE:
Daisy's WEBUI rpm includes files which conflicts with OpenStack Horizon, this is Daisy's bug which will be solved in future. For now, please uninstall python-django-horizon and openstack-dashboard before installing Daisy.

```
# cd target/el7/noarch/
# ./installdaisy_el7_noarch.bin
Verifying archive integrity... All good.
Uncompressing daisy...........................................................

=================================
    DAISY Installation Wizard
=================================
1. install
2. upgrade
3. clean
4. help
5. exit

Please select an operation: 1
```

## Uninstall Daisy

```
# cd target/el7/noarch/
# ./installdaisy_el7_noarch.bin
Verifying archive integrity... All good.
Uncompressing daisy...........................................................

=================================
    DAISY Installation Wizard
=================================
1. install
2. upgrade
3. clean
4. help
5. exit

Please select an operation: 3
```

## Test Daisy

TODO
- [ ]: separate daisyclient as another project;
- [ ]: separate horizon as another project;
