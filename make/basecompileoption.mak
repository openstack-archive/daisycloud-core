###################################################################################
###
###     this file is used to config the basic compile options for all CPU supported.
###     
###
###     Author:  Jixuepeng, CSP
###     History:
###     1. jixuepeng,2011/07/21  创建 
###################################################################################

# CPU类型检查
ifeq (,$(_CPU_TYPE))
    $(error _CPU_TYPE not defined)
endif

ifeq (,$(findstring $(_CPU_TYPE),$(_CPU_TYPE_ALL)))
     $(error cpu type $(_CPU_TYPE) is error)
endif

# OS类型检查
ifeq (,$(_OS_TYPE))
    $(error _OS_TYPE not defined)
endif

ifeq (,$(findstring $(_OS_TYPE),$(_OS_TYPE_ALL)))
#     $(error cpu type $(_OS_TYPE) is error)
endif

# RELEASE/DEBUG类型检查
ifeq (,$(_VERSION_TYPE))
    $(error _VERSION_TYPE not defined)
endif

ifeq (,$(findstring $(_VERSION_TYPE),$(_VERSION_TYPE_ALL)))
     $(error cpu type $(_VERSION_TYPE) is error)
endif

COMMON_DEVICE_DEFINE = -D_CPU_TYPE=$(_CPU_TYPE)

ifeq ($(_OS_TYPE),_LINUX_PC)
    COMMON_DEVICE_DEFINE += -DOS_LINUX_PC
else
    COMMON_DEVICE_DEFINE += -DOS_LINUX
    ifeq ($(_OS_TYPE),_CGSL)
        COMMON_DEVICE_DEFINE += -DOS_CGSL
    endif
endif

ifeq ($(_UT_TEST),TRUE)
    COMMON_DEVICE_DEFINE += -DUT_TEST
endif
###########################################################################
# RELEASE/DEBUG 版本宏定义
ifneq ($(_VERSION_TYPE),_RELEASE)
    COMMON_DEVICE_DEFINE += -DDEBUG_VERSION
else
    COMMON_DEVICE_DEFINE += -DRELEASE_VERSION
endif

###########################################################################
# COMMON_COMPILE_FLAG: 编译选项，由于都使用交叉工具链，不能再使用系统自带头文件
COMMON_COMPILE_FLAG = -fno-builtin -pipe -Wall

ifeq (DYNAMIC,$(_LIB_TYPE))
COMMON_COMPILE_FLAG += -fPIC
endif

ifeq (_RELEASE,$(_VERSION_TYPE))
    COMMON_COMPILE_FLAG += -O2 -fno-strict-aliasing -fno-schedule-insns2 -fsigned-char -fno-omit-frame-pointer
else
    COMMON_COMPILE_FLAG += -g
endif               

# GLIBC_FOR_TECS: TECS所依赖的c++库
 
export GLIBC_FOR_TECS = -lpthread -lreadline -lrt -lutil -lncurses -lboost_regex

export INSTALL_PATH =/opt/tecs
####tecs dynamic lib search path
export TECS_BASE_PATH=$(INSTALL_PATH)/$(PROCESS)

###########################################################################
######   CROSS_COMPILE_BASE : 编译器所在总目录
######   _CROSS_COMPILE_NAME: 定义编译器名字，在运行GetSharelib.sh时用来获取编译器目录
######   CROSS_COMPILE      : 编译器中可执行程序的目录，用于配置GCC/LD等
######   _MAK_INCLUDE_PATH  : 编译器头文件目录
######   TARGET_LIBS_NAME   : 编译器的静态库目录

######   CROSS_FLAGS        ：TECS进程动态链接后，设置PC机或刀片上寻找动态库的路径


#####   X86_64和P4 的PC机版本也统一使用成研编译器
BASE_GLIBC_VER = cgslv3.2_gcc4.1.2_glibc2.5.0
export CROSS_FLAGS =
ifeq ($(_CPU_TYPE), _CPU_X86_64)
export CROSS_COMPILE       = $(CROSS_COMPILE_BASE)/x86_64_$(BASE_GLIBC_VER)/bin/x86_64-pc-linux-gnu-
       TARGET_LIBS_NAME    = $(CROSS_COMPILE_BASE)/x86_64_$(BASE_GLIBC_VER)/x86_64-pc-linux-gnu
ifeq ($(_OS_TYPE), _LINUX_PC)
       CROSS_FLAGS        += -Wl,--dynamic-linker,$(CROSS_COMPILE_BASE)/x86_64_$(BASE_GLIBC_VER)/x86_64-pc-linux-gnu/lib/ld-linux-x86-64.so.2 \
                                 -Wl,-rpath,$(CROSS_COMPILE_BASE)/x86_64_$(BASE_GLIBC_VER)/x86_64-pc-linux-gnu/lib64 \
                                 -Wl,-rpath,$(CROSS_COMPILE_BASE)/x86_64_$(BASE_GLIBC_VER)/x86_64-pc-linux-gnu/lib 
endif
endif
ifeq ($(_CPU_TYPE), _CPU_X86)
export CROSS_COMPILE       = $(CROSS_COMPILE_BASE)/x86_$(BASE_GLIBC_VER)/bin/i486-pc-linux-gnu-
       TARGET_LIBS_NAME    = $(CROSS_COMPILE_BASE)/x86_$(BASE_GLIBC_VER)/i486-pc-linux-gnu
ifeq ($(_OS_TYPE), _LINUX_PC)
       CROSS_FLAGS        += -Wl,--dynamic-linker,$(CROSS_COMPILE_BASE)/x86_$(BASE_GLIBC_VER)/i486-pc-linux-gnu/lib/ld-linux.so.2 \
                                 -Wl,-rpath,$(CROSS_COMPILE_BASE)/x86_$(BASE_GLIBC_VER)/i486-pc-linux-gnu/lib 
endif
endif

ifeq (_el6,$(_OS_TYPE))
OSEX = el6
else
OSEX = el7
endif

export CONTRIB_QPID_PATH = $(_TECS_CONTRIB_PATH)/target/$(ARCH)/$(OSEX)/qpid
export CONTRIB_PGSQL_PATH = $(_TECS_CONTRIB_PATH)/target/$(ARCH)/$(OSEX)/postgresql
export CONTRIB_XMLRPC_PATH = $(_TECS_CONTRIB_PATH)/target/$(ARCH)/$(OSEX)/xmlrpc
export CONTRIB_RESTRPC_PATH = $(_TECS_CONTRIB_PATH)/target/$(ARCH)/$(OSEX)/restrpc-c
export CONTRIB_OPENAIS_PATH = $(_TECS_CONTRIB_PATH)/openais
export CONTRIB_VM_SIMULATE_PAHT = $(_TECS_CONTRIB_PATH)/vm_simulate

CROSS_CONTRIB_LINK_PATH = -Wl,-rpath-link,$(CONTRIB_QPID_PATH)/lib \
                          -Wl,-rpath-link,$(CONTRIB_PGSQL_PATH)/lib \
                          -Wl,-rpath-link,$(CONTRIB_XMLRPC_PATH)/lib \
                          -Wl,-rpath-link,$(CONTRIB_OPENAIS_PATH)/lib 
##增加/usr/local等是为了rpath 能通过chrpath修改，否则可能由于长度比较短而不能替换
CROSS_FLAGS         += -Wl,-rpath,$(TECS_BASE_PATH)/lib \
                       -Wl,-rpath,/usr/local/lib -Wl,-rpath,/usr/local/lib64 -Wl,-rpath,/lib64 -Wl,-rpath,/lib -Wl,-rpath,/XXX/XXX/lib
					   
CROSS_FLAGS         += $(CROSS_CONTRIB_LINK_PATH)

			   
export 	_TECS_CONTRIB_LIB_PATH = -L$(CONTRIB_QPID_PATH)/lib \
                                 -L$(CONTRIB_PGSQL_PATH)/lib \
                                 -L$(CONTRIB_XMLRPC_PATH)/lib \
                                 -L$(CONTRIB_RESTRPC_PATH)/restrpc-c/src/cpp \
                                 -L$(CONTRIB_RESTRPC_PATH)/restrpc-c/src \
                                 -L$(CONTRIB_RESTRPC_PATH)/restrpc-c/lib/libutil \
                                 -L$(CONTRIB_RESTRPC_PATH)/restrpc-c/lib/expat/xmlparse \
                                 -L$(CONTRIB_RESTRPC_PATH)/restrpc-c/lib/expat/xmltok \
                                 -L$(CONTRIB_OPENAIS_PATH)/lib

_TECS_CONTRIB_INC_PATH = -I$(CONTRIB_QPID_PATH)/include \
                         -I$(CONTRIB_PGSQL_PATH)/include \
                         -I$(CONTRIB_XMLRPC_PATH)/include \
                         -I$(CONTRIB_RESTRPC_PATH)/restrpc-c/include \
                         -I$(CONTRIB_OPENAIS_PATH)/include \
                         -I$(CONTRIB_VM_SIMULATE_PAHT)/include
ifeq (TRUE,$(LOCAL_BUILD))
#####  如果定义LOCAL_BUILD=TURE则使用本地工具链编译
export CROSS_COMPILE = 
       TARGET_LIBS_NAME = /usr
export CROSS_FLAGS      = -Wl,-rpath,$(_TARGET_LIB_PATH)
CROSS_CONTRIB_LINK_PATH += -Wl,-rpath,$(CONTRIB_QPID_PATH)/lib \
                           -Wl,-rpath,$(CONTRIB_PGSQL_PATH)/lib \
                           -Wl,-rpath,$(CONTRIB_XMLRPC_PATH)/lib \
                           -Wl,-rpath,$(CONTRIB_RESTRPC_PATH)/restrpc-c/src/cpp \
                           -Wl,-rpath,$(CONTRIB_RESTRPC_PATH)/restrpc-c/src \
                           -Wl,-rpath,$(CONTRIB_RESTRPC_PATH)/restrpc-c/lib/libutil \
                           -Wl,-rpath,$(CONTRIB_RESTRPC_PATH)/restrpc-c/lib/expat/xmlparse \
                           -Wl,-rpath,$(CONTRIB_RESTRPC_PATH)/restrpc-c/lib/expat/xmltok \
                           -Wl,-rpath,$(CONTRIB_OPENAIS_PATH)/lib 
ifeq (NO,$(CONTRIB))
###如果要使用CONTRIB LIB,请把下面三个变量定义注掉
CROSS_CONTRIB_LINK_PATH =
_TECS_CONTRIB_INC_PATH =
export 	_TECS_CONTRIB_LIB_PATH = 
###end如果要使用CONTRIB LIB
else
endif
CROSS_FLAGS         += $(CROSS_CONTRIB_LINK_PATH)
endif


##系统头文件搜索路径，默认不指定
SYS_INC_PATH =
ifeq (TRUE,$(LOCAL_BUILD))
SYS_INC_PATH += -I/usr/include
endif
##定义公共模块源文件路径
_TECS_SKY_PATH     =  $(_TECS_CODE_PATH)/sky
_TECS_COMMON_PATH  =  $(_TECS_CODE_PATH)/common

##定义公共模块头文件搜索路径
PUB_INC_PATH = -I$(_TECS_SKY_PATH)/include \
               -I$(_TECS_COMMON_PATH)/include 
PUB_INC_PATH += $(_TECS_CONTRIB_INC_PATH)

_TECS_INC_PATH  = $(SYS_INC_PATH) $(PUB_INC_PATH) 

###########################################################################
# CPPFLAGS
TOPMAKE_COMMON_CPPFLAGS       = $(COMMON_DEVICE_DEFINE) $(COMMON_COMPILE_FLAG) \
                              $(_TECS_INC_PATH) $(CC_ARCH_SPEC)

# LINT_CPPFLAGS
TOPLINT_COMMON_CPPFLAGS       = $(COMMON_DEVICE_DEFINE) \
                              $(_TECS_INC_PATH) $(CC_ARCH_SPEC)

# CPPFLAGS_AS
TOPMAKE_COMMON_CPPFLAGS_AS    = $(COMMON_DEVICE_DEFINE) $(COMMON_COMPILE_FLAG) \
                              $(_AS_DEBUG) \
                              -P -x assembler-with-cpp \
                              $(_TECS_INC_PATH) $(CC_ARCH_SPEC)

# DEPCPPFLAGS
COMMON_DEPCPPFLAGS            = -MM $(COMMON_DEVICE_DEFINE) \
                              $(_TECS_INC_PATH) 

# DEPCPPFLAGS_AS
COMMON_DEPCPPFLAGS_AS         = -MM $(COMMON_DEVICE_DEFINE) -x assembler-with-cpp \
                              $(_TECS_INC_PATH) 

# _LD_DEBUG
_LD_DEBUG                   = --warn-common



###############################################################################
# 为 Pentium 配置编译、链接选项
ifeq ($(_CPU_TYPE),_CPU_X86)
    export ARCH=i386
    export ARCH_CPU=i386
    export ARCH_SPEC=i686p4
    export _CPU         = PENTIUM4
    export _ARCH_FAMILY = i386
    AR               = @$(CROSS_COMPILE)ar
    AS               = @$(CROSS_COMPILE)g++
    CC               = @$(CROSS_COMPILE)g++
    CC_ARCH_SPEC     = -DCPU=PENTIUM4
    CPPFLAGS           = $(TOPMAKE_COMMON_CPPFLAGS) \
                       -mtune=pentium -march=i686 -nostdlib -fno-defer-pop -DSYS32
    CPPFLAGS_AS        = $(TOPMAKE_COMMON_CPPFLAGS_AS) \
                       -mtune=pentium -march=i686 -nostdlib -fno-defer-pop 
    DEPCPPFLAGS        = $(COMMON_DEPCPPFLAGS) -DSYS32
    DEPCPPFLAGS_AS     = $(COMMON_DEPCPPFLAGS_AS)
    CPP              = $(CC) -E -P
    COMPILE_LEGEND   = $(CC) -c -fdollars-in-identifiers $(CPPFLAGS)                       
    LD               = @$(CROSS_COMPILE)ld $(_LD_DEBUG)  
    LDFLAGS          = -X -N
    LD_PARTIAL       = $(CC) -r -nostdlib -Wl,-X
    LD_PARTIAL_FLAGS = -X -r
    VX_CPU_FAMILY    = pentium
    NM               = $(CROSS_COMPILE)nm
    SIZE             = $(CROSS_COMPILE)size
    POST_BUILD_RULE  = 
ifneq (,$(findstring -mfpmath=387,$(CPPFLAGS)))
    CPPFLAGS_AS += -D_FPU_TYPE=FPU
endif
ifneq (,$(findstring -mfpmath=sse,$(CPPFLAGS)))
    CPPFLAGS_AS += -D_FPU_TYPE=SSE
endif
endif

ifeq (_CPU_X86_64,$(_CPU_TYPE))
    export ARCH=x86_64
    export ARCH_CPU=x86_64
    AR               = @$(CROSS_COMPILE)ar
    AS               = @$(CROSS_COMPILE)g++
    CC               = @$(CROSS_COMPILE)g++
    CC_ARCH_SPEC     = -DCPU=x86_64
    CPPFLAGS           = $(TOPMAKE_COMMON_CPPFLAGS) \
                        -nostdlib -fno-defer-pop -DSYS64
    CPPFLAGS_AS        = $(TOPMAKE_COMMON_CPPFLAGS_AS) \
                        -nostdlib -fno-defer-pop
    DEPCPPFLAGS        = $(COMMON_DEPCPPFLAGS) -DSYS64
    DEPCPPFLAGS_AS     = $(COMMON_DEPCPPFLAGS_AS)
    CPP              = $(CC) -E -P
    COMPILE_LEGEND   = $(CC) -c -fdollars-in-identifiers $(CPPFLAGS)
    LD		     = @$(CROSS_COMPILE)ld
    LDFLAGS          = -X -N
    LD_PARTIAL       = $(CC) -r -nostdlib -Wl,-X
    LD_PARTIAL_FLAGS = -X -r
    VX_CPU_FAMILY    = x86_64
    NM               = $(CROSS_COMPILE)nm
    SIZE             = @$(CROSS_COMPILE)size
    POST_BUILD_RULE  = 
ifneq (,$(findstring -mfpmath=387,$(CPPFLAGS)))
    CPPFLAGS_AS += -D_FPU_TYPE=FPU
endif
ifneq (,$(findstring -mfpmath=sse,$(CPPFLAGS)))
    CPPFLAGS_AS += -D_FPU_TYPE=SSE
endif
endif


