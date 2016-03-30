#!/bin/bash

scriptsdir=$(cd $(dirname $0) && pwd)
ISODIR=`mktemp  -d /mnt/TFG_ISOXXXXXX`
mount -o loop $scriptsdir/*CGSL_VPLAT*.iso ${ISODIR}
cp ${ISODIR}/*CGSL_VPLAT*.bin  $scriptsdir
umount ${ISODIR}
[ -e ${ISODIR} ] && rm -rf ${ISODIR}
$scriptsdir/*CGSL_VPLAT*.bin upgrade reboot
