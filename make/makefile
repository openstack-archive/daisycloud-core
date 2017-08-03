include versionconfig.mak
include command.mak
include cpuconfig.mak
include compilepara.mak

ifeq (TRUE,$(CONCURRENT_COMPILE))
    CPU_NUM = $(shell cat /proc/cpuinfo | grep 'processor' | wc -l)
    LOAD_AVERAGE = $(shell expr $(CPU_NUM) + $(CPU_NUM))
    MAKE += -j -l $(LOAD_AVERAGE)
endif

ifeq (,$(_CPU_TYPE))
export _CPU_TYPE     = _CPU_X86_64
endif

ifeq (,$(_CI_VER_NO))
export _CI_VER_NO     = without_input_no
endif

ifeq (,$(_CI_VER_NUM))
export _CI_VER_NUM     = without_input_num
endif

ifeq (,$(_CI_VER_NAME))
export _CI_VER_NAME     = without_input_name
endif

ifeq (_RELEASE,$(_VERSION_TYPE))
export _VERSION_TYPE = _RELEASE
else
export _VERSION_TYPE = _DEBUG
endif

ifeq (,$(_CI_SVN_REVISION))
export _CI_SVN_REVISION     = without_svn_revision
endif

export RPM_ERR=$(_TECS_TARGET_PATH)/rpmErr_$(OS)_$(subst _CPU_,,$(_CPU_TYPE))$(_VERSION_TYPE).txt
##rpmbuild¹ý³ÌÐÅÏ¢»á±»µ±´í´íÎóÐÅÏ¢Êä³ö£¬Îª·½±ãÒÔºó¼ì²é±àÒë¸æ¾¯ºÍ´íÎó£¬Ä¬ÈÏµ¥¶À³ö´íµ½Ò»¸öÎÄ¼þÖÐ¡£
##Èç¹ûÏëÈÃrpmbuildµÄ´íÎóÍ¬µ±Ç°´íÎóÊä³öµ½Ò»Æð£¬ÔÚ±àÒëÊ±¶¨ÒåRPM_ERR_OUTPUTÎª¿Õ¡£
##ÀýÈç make allrpm _OS_TYPE=_CGSL _CPU_TYPE=_CPU_X86_64 _VERSION_TYPE=_RELEASE RPM_ERR_OUTPUT=
##ÓÉÓÚrpmbuild³ö´í»áÍ£Ö¹±àÒë£¬Òò´ËÕâÀïÖ»±£´æÁË×îºóÒ»´Î´íÎóÐÅÏ¢¡£
export RPM_ERR_OUTPUT= 2>$(RPM_ERR)

include compileoption.mak

.PHONY:help allrpm cleanall

help:
	$(ECHO) ===============================================================================
	$(ECHO) make usage:
	$(ECHO) ===============================================================================
	$(ECHO) make allrpm  ... generate all rpms and install.bin
	$(ECHO) ===============================================================================
	$(ECHO) make rpm  ... generate all rpms
	$(ECHO) ===============================================================================
	$(ECHO) make bin  ... generate install.bin
	$(ECHO) ===============================================================================
	$(ECHO) make daisyrpm  ... generate glance rpms
	$(ECHO) ===============================================================================
	$(ECHO) make daisyclientrpm  ... generate daisyclient rpms
	$(ECHO) ===============================================================================
	$(ECHO) make daisydiscoverdrpm  ... generate daisydiscoverd rpms
	$(ECHO) ===============================================================================
	$(ECHO) make pxe_server_install  ... generate pxe_server_install rpms
	$(ECHO) ===============================================================================
	$(ECHO) make rpmclean  ... clean rpms generated
	$(ECHO) ===============================================================================
	$(ECHO) make binclean  ... clean install.bin generated
	$(ECHO) ===============================================================================
	$(ECHO) make cleanall  ... clean rpms and install.bin generated
	$(ECHO) ===============================================================================

export _RPM=all

rpm:
	$(MAKE) -C $(_TECS_RPM_PATH)/ all

buildpkg:
	$(MAKE) -C $(_TECS_TOOLS_PATH)/setup bin
	@echo TECS package success!

allrpm:rpm
	$(MAKE) -C $(_TECS_TOOLS_PATH)/setup bin
	@echo Daisy package success!

rpmclean:
	$(MAKE) -C $(_TECS_RPM_PATH)/ clean

daisyrpm:
	$(MAKE) -C $(_TECS_RPM_PATH)/ daisy

daisyclientrpm:
	$(MAKE) -C $(_TECS_RPM_PATH)/ daisyclient

daisydiscoverdrpm:
	$(MAKE) -C $(_TECS_RPM_PATH)/ daisy-discoverd

horizonrpm:
	$(MAKE) -C $(_TECS_RPM_PATH)/ horizon

pxe_server_install:
	$(MAKE) -C $(_TECS_RPM_PATH)/ pxe_server_install

bin:
	$(MAKE) -C $(_TECS_TOOLS_PATH)/setup bin

cleanall:rpmclean
	$(RMDIR)  $(_TECS_TMP_PATH)
	$(RMDIR)  $(_TECS_TARGET_PATH)
	@echo "clean all successfully!"

