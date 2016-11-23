[toc]

Daisy(Openstack project name: daisycloud-core)


Daisy provies automated deployment and management of OpenStack and other distributed systems.

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
