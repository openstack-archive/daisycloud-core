#! /bin/bash 

log_path=compile-logs
mkdir -p $log_path

module=`ls | sed -n '/.rpm$/p'`
for mod in $module
do
    module_name=`basename $mod .rpm`
    already_install=`rpm -qi $module_name | grep "not installed" `
   
    if [ "" == "$already_install" ] ; then
        echo "$module_name  already install..."
    else
        echo "install $module_name..." 
        rpm -ivh --nodeps $mod 1>$log_path/$mod.log 2>$log_path/$mod.err
    fi
done

for module in $module
do
    
    if [ -s $log_path/$mod.err ]; then            
        echo "compile environment installing  has error..." 
        cat $log_path/$mod.err                       
        exit 1        
    fi
done 

echo "compile environment is successfully installed..."
exit 0


