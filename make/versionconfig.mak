
##在Windows进行PCLint检测时需求
ifeq (_OS_NT,$(_COMPILE_TYPE))
export _TECS_ROOT_PATH           =    z:
else
export _TECS_ROOT_PATH           =    $(shell pwd)/..
endif

export _TECS_CODE_PATH           = $(_TECS_ROOT_PATH)/code
export _TECS_CLIENT_PATH         = $(_TECS_ROOT_PATH)/client
export _TECS_CONTRIB_PATH        = $(_TECS_ROOT_PATH)/contrib
export _TECS_BACKEND_PATH         = $(_TECS_ROOT_PATH)/backend
export _TECS_TARGET_PATH         = $(_TECS_ROOT_PATH)/target
export _TECS_TMP_PATH            = $(_TECS_ROOT_PATH)/tmp
export _TECS_MAK_PATH            = $(_TECS_ROOT_PATH)/make
export _TECS_TOOLS_PATH          = $(_TECS_ROOT_PATH)/tools
export _TECS_RPM_PATH            = $(_TECS_ROOT_PATH)/rpm


export VER_PREFIX = installdaisy
export VER_SUFFIX = bin
## 编译工具链路径
export CROSS_COMPILE_BASE        = /opt
export LINT_CROSS_COMPILE_BASE   = X:

export _TECS_VERNO        =    02.01.10
##集成测试版本号
ifeq ($(BUILD_NUMBER),) 
export VER_I              = 0
else
export VER_I              = $(BUILD_NUMBER)
endif
##系统测试版本号
export VER_B              = 1
##对外发布版本号
export VER_P              = 1
##RELEASE版本号,此变量一般需要在编译的时候指定
export _VER_REL           = $(VER_P).$(VER_B).$(VER_I)

##Openstack系统测试版本号
export VER_OPENSTACK_B              = 0
##Openstack对外发布版本号
export VER_OPENSTACK_P              = 1
export VER_OPENSTACK_I              = 0

##Openstack RELEASE版本号,此变量一般需要在编译的时候指定
export _VER_OPENSTACK_REL           = $(VER_OPENSTACK_P).$(VER_OPENSTACK_B).$(VER_OPENSTACK_I)

export _VER_DAISYCLIENT_REL        = $(_VER_OPENSTACK_REL)
export _VER_IRONICDISCOVERD_REL        = $(_VER_OPENSTACK_REL)
