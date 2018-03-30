## Build Daisy artifact

```
# cd tools && ./daisy-compile-rpm.sh
(above run only once)
# cd ../make
# make allrpm
```

The artifacts will be at target/el7/noarch/, with name is like installdaisy_el7_noarch.bin.

## Install Daisy


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

