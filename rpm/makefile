PURE_OS_TYPE = el5
ifeq (_el6,$(_OS_TYPE))
PURE_OS_TYPE = el6
else
ifeq (_el7,$(_OS_TYPE))
PURE_OS_TYPE = el7
endif
endif
RPM_OS_TYPE=linux

export RPMBUILD = rpmbuild -bb  --define '_topdir $(_TECS_RPM_PATH)' \
                                --define '_rpmdir %{_topdir}/RPMS/$(PURE_OS_TYPE)' \
				                --define '_release $(_VER_REL)' --define '_description $(_CI_VER_NAME)_$(_CI_VER_NUM)_$(_CI_VER_NO)'  --define '_svn_revision $(_CI_SVN_REVISION)' --define '_VER_TYPE $(_VER_TYPE)'\

rpmforce:
	@if [ ! -d $(_TECS_RPM_PATH)/RPMS/$(PURE_OS_TYPE) ]; then $(MKDIR) $(_TECS_RPM_PATH)/RPMS/$(PURE_OS_TYPE) ; fi

all:clean rpms

rpms:daisy daisyclient daisy-discoverd horizon pxe_server_install

clean:rpmforce
	$(RM) $(_TECS_RPM_PATH)/SOURCES/*
	$(RM) $(_TECS_RPM_PATH)/BUILD/*
	$(RM) $(_TECS_RPM_PATH)/RPMS/*
	$(RM) $(_TECS_RPM_PATH)/SRPMS/*


daisy:rpmforce
	$(CP) $(_TECS_TOOLS_PATH)/daisy-utils/* $(_TECS_RPM_PATH)/SOURCES
	$(CP) -R $(_TECS_BACKEND_PATH)/* $(_TECS_RPM_PATH)/BUILD
	$(RM) $(_TECS_RPM_PATH)/SOURCES/$@-$(_VER_OPENSTACK_REL)
	$(LN) $(_TECS_CODE_PATH)/daisy/ $(_TECS_RPM_PATH)/SOURCES/$@-$(_VER_OPENSTACK_REL)
	@cd $(_TECS_RPM_PATH)/SOURCES; $(TARC) $(_TECS_RPM_PATH)/SOURCES/$@-$(_VER_OPENSTACK_REL).tar.gz --exclude=*.svn \
	$@-$(_VER_OPENSTACK_REL)/*; cd -
	$(RPMBUILD) --rmsource $(_TECS_RPM_PATH)/SPECS/$@.spec
	$(RM) $(_TECS_RPM_PATH)/SOURCES/$@-$(_VER_OPENSTACK_REL)
	$(RM) $(_TECS_RPM_PATH)/BUILD/*

daisyclient:rpmforce
	$(CP) $(_TECS_TOOLS_PATH)/daisy-utils/* $(_TECS_RPM_PATH)/SOURCES
	$(RM) $(_TECS_RPM_PATH)/SOURCES/python-$@-$(_VER_DAISYCLIENT_REL)
	$(LN) $(_TECS_CODE_PATH)/daisyclient/ $(_TECS_RPM_PATH)/SOURCES/python-$@-$(_VER_DAISYCLIENT_REL)
	@cd $(_TECS_RPM_PATH)/SOURCES; $(TARC) $(_TECS_RPM_PATH)/SOURCES/python-$@-$(_VER_DAISYCLIENT_REL).tar.gz --exclude=*.svn python-$@-$(_VER_DAISYCLIENT_REL)/*; cd -
	$(RPMBUILD) --rmsource $(_TECS_RPM_PATH)/SPECS/python-$@.spec
	$(RM) $(_TECS_RPM_PATH)/SOURCES/python-$@-$(_VER_DAISYCLIENT_REL)
	$(RM) $(_TECS_RPM_PATH)/BUILD/python-$@-$(_VER_DAISYCLIENT_REL)

daisy-discoverd:rpmforce
	$(CP) $(_TECS_TOOLS_PATH)/daisy-utils/* $(_TECS_RPM_PATH)/SOURCES
	$(RM) $(_TECS_RPM_PATH)/SOURCES/$@-$(_VER_IRONICDISCOVERD_REL)
	$(LN) $(_TECS_CODE_PATH)/daisy-discoverd/ $(_TECS_RPM_PATH)/SOURCES/$@-$(_VER_IRONICDISCOVERD_REL)
	@cd $(_TECS_RPM_PATH)/SOURCES; $(TARC) $(_TECS_RPM_PATH)/SOURCES/$@-$(_VER_IRONICDISCOVERD_REL).tar.gz --exclude=*.svn $@-$(_VER_IRONICDISCOVERD_REL)/*; cd -
	$(RPMBUILD) --rmsource $(_TECS_RPM_PATH)/SPECS/$@.spec
	$(RM) $(_TECS_RPM_PATH)/SOURCES/python-$@-$(_VER_IRONICDISCOVERD_REL)
	$(RM) $(_TECS_RPM_PATH)/BUILD/python-$@-$(_VER_IRONICDISCOVERD_REL)

horizon:rpmforce
	$(CP) $(_TECS_TOOLS_PATH)/daisy-utils/* $(_TECS_RPM_PATH)/SOURCES
	$(RM) $(_TECS_RPM_PATH)/SOURCES/$@-$(_VER_OPENSTACK_REL)
	$(LN) $(_TECS_CODE_PATH)/$@ $(_TECS_RPM_PATH)/SOURCES/$@-$(_VER_OPENSTACK_REL)
	@cd $(_TECS_RPM_PATH)/SOURCES; $(TARC) $(_TECS_RPM_PATH)/SOURCES/$@-$(_VER_OPENSTACK_REL).tar.gz --exclude=*.svn \
	$@-$(_VER_OPENSTACK_REL)/*; cd -
	$(RPMBUILD) --rmsource $(_TECS_RPM_PATH)/SPECS/openstack-$@.spec
	$(RM) $(_TECS_RPM_PATH)/SOURCES/$@-$(_VER_OPENSTACK_REL)
	$(RM) $(_TECS_RPM_PATH)/BUILD/$@-$(_VER_OPENSTACK_REL)

pxe_server_install:rpmforce
	$(RM) $(_TECS_RPM_PATH)/SOURCES/$@-$(_VER_REL)
	$(LN) $(_TECS_CODE_PATH)/$@ $(_TECS_RPM_PATH)/SOURCES/$@-$(_VER_REL)
	@cd $(_TECS_RPM_PATH)/SOURCES; $(TARC) $(_TECS_RPM_PATH)/SOURCES/$@-$(_VER_REL).tar.gz --exclude=*.svn \
	$@-$(_VER_REL)/*; cd -
	$(RPMBUILD) --rmsource $(_TECS_RPM_PATH)/SPECS/$@.spec
	$(RM) $(_TECS_RPM_PATH)/SOURCES/$@-$(_VER_REL)
	$(RM) $(_TECS_RPM_PATH)/BUILD/$@-$(_VER_REL)
