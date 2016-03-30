
##定义库临时文件路径
ifneq ('','$(_LIB_VER)')
ifeq (DYNAMIC,$(_LIB_TYPE))
    export _TEMP_PATH    = $(_TECS_TMP_PATH)/$(subst _,,$(_OS_TYPE))/$(subst _,,$(_VERSION_TYPE))/$(subst _CPU_,,$(_CPU_TYPE))/dynamic
else
    export _TEMP_PATH    = $(_TECS_TMP_PATH)/$(subst _,,$(_OS_TYPE))/$(subst _,,$(_VERSION_TYPE))/$(subst _CPU_,,$(_CPU_TYPE))/static
endif
else
    export _TEMP_PATH    = $(_TECS_TMP_PATH)/$(subst _,,$(_OS_TYPE))/$(subst _,,$(_VERSION_TYPE))/$(subst _CPU_,,$(_CPU_TYPE))
endif

##临时目标及依赖文件路径
export _TEMP_OBJ_PATH  = $(_TEMP_PATH)/obj
export _TEMP_DEP_PATH  = $(_TEMP_PATH)/dep

##定义目标输出文件路径
export _TARGET_LIB_PATH = $(_TECS_TARGET_PATH)/lib/$(subst _,,$(_OS_TYPE))/$(subst _,,$(_VERSION_TYPE))/$(subst _CPU_,,$(_CPU_TYPE))
export _TARGET_BIN_BASE_PATH = $(_TECS_TARGET_PATH)/bin/$(subst _,,$(_OS_TYPE))/$(subst _,,$(_VERSION_TYPE))/$(subst _CPU_,,$(_CPU_TYPE))
export _TARGET_BIN_PATH = $(_TARGET_BIN_BASE_PATH)/$(PROCESS)

ifeq (_DEBUG,$(_VERSION_TYPE)) 
export _VER_TYPE = 1  
else 
ifeq (_RELEASE,$(_VERSION_TYPE))
export _VER_TYPE = 0  
endif     
endif

export LOCAL_BUILD = TRUE

ifeq (_ZXVE,$(_OS_TYPE))
export LOCAL_BUILD = FALSE
export _OS_TYPE    = 
endif

ifeq (,$(_OS_TYPE))
ifeq ($(shell uname -a | grep el5 | wc -l),1)
export _OS_TYPE    = _el5
else
ifeq ($(shell uname -a | grep el6 | wc -l),1)
export _OS_TYPE    = _el6
else
ifeq ($(shell uname -a | grep el7 | wc -l),1)
export _OS_TYPE    = _el7
else
export _OS_TYPE    = _$(shell uname -o |awk -F'/' '{ print $$2 }' |tr a-z A-Z)
endif
endif
endif
endif

#echo OS_TYPE:$(_OS_TYPE)

ifeq (_VXWORKS,$(_OS_TYPE))
OS = VX
else
ifeq (_CGSL,$(_OS_TYPE))
OS = CGSL
else
ifeq (_LINUX,$(_OS_TYPE))
OS = LINUX
else
ifeq (_el5,$(_OS_TYPE))
OS = el5
else
ifeq (_el6,$(_OS_TYPE))
OS = el6
else
ifeq (_el7,$(_OS_TYPE))
OS = el7
else
OS = PC
endif
endif
endif
endif
endif
endif

export VERSION_SUFFIX=_$(OS)_$(subst _CPU_,,$(_CPU_TYPE))_$(_VER_TYPE)_$(_TECS_VERNO)


