PURE_OS_TYPE = el7
ifeq (_el6,$(_OS_TYPE))
PURE_OS_TYPE = el6 
endif
RPM_OS_TYPE=linux
BIN_TYPE = $(PURE_OS_TYPE)_$(ARCH)

ARCH=noarch

binforce:
	if [ ! -d $(_TECS_TARGET_PATH)/$(PURE_OS_TYPE)/$(ARCH) ]; then $(MKDIR) $(_TECS_TARGET_PATH)/$(PURE_OS_TYPE)/$(ARCH) ; fi

bin: binclean binforce
	$(MKDIR) $(_TECS_TOOLS_PATH)/setup/bin_temp
	$(RM) $(_TECS_TOOLS_PATH)/setup/bin_temp/*
	$(MKDIR) $(_TECS_TOOLS_PATH)/setup/bin_temp/common   
	$(MKDIR) $(_TECS_TOOLS_PATH)/setup/bin_temp/install
	$(RM) $(_TECS_TOOLS_PATH)/setup/bin_temp/install/*
	$(MKDIR) $(_TECS_TOOLS_PATH)/setup/bin_temp/install/ha
	$(MKDIR) $(_TECS_TOOLS_PATH)/setup/bin_temp/upgrade  
	$(MKDIR) $(_TECS_TOOLS_PATH)/setup/bin_temp/uninstall
	$(RM) $(_TECS_TOOLS_PATH)/setup/bin_temp/common/*
	$(RM) $(_TECS_TOOLS_PATH)/setup/bin_temp/upgrade/*
	$(RM) $(_TECS_TOOLS_PATH)/setup/bin_temp/uninstall/*
	
	$(CP) $(_TECS_RPM_PATH)/RPMS/$(PURE_OS_TYPE)/$(ARCH)/* $(_TECS_TOOLS_PATH)/setup/bin_temp
	$(RM) $(_TECS_TOOLS_PATH)/setup/bin_temp/*devel*.rpm
	
	$(CP) $(_TECS_CONTRIB_PATH)/rpm/* $(_TECS_TOOLS_PATH)/setup/bin_temp

	$(CP) $(_TECS_TOOLS_PATH)/setup/setup.sh $(_TECS_TOOLS_PATH)/setup/bin_temp
	$(CP) $(_TECS_TOOLS_PATH)/setup/common/daisy_common_func.sh $(_TECS_TOOLS_PATH)/setup/bin_temp/common
	$(CP) $(_TECS_TOOLS_PATH)/setup/common/daisy_global_var.sh $(_TECS_TOOLS_PATH)/setup/bin_temp/common
	$(CP) $(_TECS_TOOLS_PATH)/setup/common/daisy_yum.sh $(_TECS_TOOLS_PATH)/setup/bin_temp/common
	$(CP) $(_TECS_TOOLS_PATH)/setup/install/install_func.sh $(_TECS_TOOLS_PATH)/setup/bin_temp/install
	$(CP) $(_TECS_TOOLS_PATH)/setup/install/install_interface.sh $(_TECS_TOOLS_PATH)/setup/bin_temp/install
	$(CP) $(_TECS_TOOLS_PATH)/setup/install/install_global_var.sh $(_TECS_TOOLS_PATH)/setup/bin_temp/install
	$(CP) $(_TECS_TOOLS_PATH)/setup/uninstall/uninstall_interface.sh $(_TECS_TOOLS_PATH)/setup/bin_temp/uninstall
	$(CP) $(_TECS_TOOLS_PATH)/setup/uninstall/uninstall_func.sh $(_TECS_TOOLS_PATH)/setup/bin_temp/uninstall
	$(CP) $(_TECS_TOOLS_PATH)/setup/upgrade/upgrade_interface.sh $(_TECS_TOOLS_PATH)/setup/bin_temp/upgrade
	$(CP) $(_TECS_TOOLS_PATH)/setup/upgrade/upgrade_func.sh $(_TECS_TOOLS_PATH)/setup/bin_temp/upgrade
	$(CP) $(_TECS_TOOLS_PATH)/daisy-utils/daisy.conf $(_TECS_TOOLS_PATH)/setup/bin_temp/
	
	chmod +x $(_TECS_TOOLS_PATH)/setup/bin_temp/setup.sh
	chmod +x $(_TECS_TOOLS_PATH)/setup/bin_temp/common/daisy_common_func.sh
	chmod +x $(_TECS_TOOLS_PATH)/setup/bin_temp/common/daisy_global_var.sh
	chmod +x $(_TECS_TOOLS_PATH)/setup/bin_temp/common/daisy_yum.sh
	chmod +x $(_TECS_TOOLS_PATH)/setup/bin_temp/install/install_func.sh
	chmod +x $(_TECS_TOOLS_PATH)/setup/bin_temp/install/install_interface.sh
	chmod +x $(_TECS_TOOLS_PATH)/setup/bin_temp/install/install_global_var.sh
	chmod +x $(_TECS_TOOLS_PATH)/setup/bin_temp/uninstall/uninstall_interface.sh
	chmod +x $(_TECS_TOOLS_PATH)/setup/bin_temp/uninstall/uninstall_func.sh
	chmod +x $(_TECS_TOOLS_PATH)/setup/bin_temp/upgrade/upgrade_interface.sh
	chmod +x $(_TECS_TOOLS_PATH)/setup/bin_temp/upgrade/upgrade_func.sh
	cd $(_TECS_TOOLS_PATH)/setup; chmod +x ./makeself.sh; ./makeself.sh ./bin_temp $(_TECS_TARGET_PATH)/$(PURE_OS_TYPE)/$(ARCH)/$(VER_PREFIX)_$(BIN_TYPE).$(VER_SUFFIX) daisy ./setup.sh
	$(RM) $(_TECS_TOOLS_PATH)/setup/bin_temp

binclean:
	if [ -e $(_TECS_TARGET_PATH)/$(PURE_OS_TYPE)/$(ARCH)/$(VER_PREFIX)_$(BIN_TYPE).$(VER_SUFFIX) ]; then $(RM) $(_TECS_TARGET_PATH)/$(PURE_OS_TYPE)/$(ARCH)/$(VER_PREFIX)_$(BIN_TYPE).$(VER_SUFFIX); fi
	if [ -e $(_TECS_TOOLS_PATH)/setup/bin_temp ]; then $(RM) $(_TECS_TOOLS_PATH)/setup/bin_temp; fi
