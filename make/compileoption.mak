###################################################################################
###
###     this file is used to config compile options and the pclint check options for
###     all CPU supported.
###     
###
###     Author:  Jixuepeng, CSP
###     History:
###     1. jixuepeng,2011/07/21  创建 
###################################################################################
include $(_TECS_MAK_PATH)/basecompileoption.mak
include $(_TECS_MAK_PATH)/compilepara.mak

ifeq (TRUE,$(INCLUDE_UT))
	COMMON_DEVICE_DEFINE += -DINCLUDE_UT
endif

ifeq (TRUE,$(INCLUDE_IT))
	COMMON_DEVICE_DEFINE += -DINCLUDE_IT
endif

#####TECS PCLint开始#####
#-iX:/x86_64-pc-linux-gnu/include 
#-iX:/lib/gcc/x86_64-pc-linux-gnu/4.1.2/include
#定义Pclint的对应选项

_PCLINT_PATH = $(_TECS_TOOLS_PATH)/PCLint8
LINT = $(_PCLINT_PATH)/LINT-NT.EXE
LINTOPTION = -zero -os($(subst .lob,.txt,$@)) -i$(_PCLINT_PATH)/std.lnt
LINT_OUT_PUT_ERR = $(_PCLINT_PATH)/OutPutErr.bat $(_PCLINT_PATH)/GetFileLen.exe $(LINT_OUT_PUT_FILE) \
                    $< $(subst /,\,$(subst .lob,.txt,$@))
LINT_OUT_PUT_ERR_NEED_SRC = $(_PCLINT_PATH)/OutPutErr.bat $(_PCLINT_PATH)/GetFileLen.exe $(LINT_OUT_PUT_FILE)
LINT_OUT_PUT_ALL_ERR = $(_PCLINT_PATH)/FileStr.exe


#定义Pclint工具链的相关路径
export LINT_TOOLCHAIN_PATH=$(LINT_CROSS_COMPILE_BASE)

TECS_LINT_COMMON_FLAG = $(TOPLINT_COMMON_CFLAGS) $(LINTOPTION)

ifeq ($(_CPU_TYPE), _CPU_X86_64)
TECS_LINT_COMMON_FLAG += -D__x86_64__
export X86_64_PCLINT_FLAG  = -I$(LINT_TOOLCHAIN_PATH)/x86_64_gcc4.1.2_glibc2.5.0/x86_64-pc-linux-gnu/include \
                             -I$(LINT_TOOLCHAIN_PATH)/x86_64_gcc4.1.2_glibc2.5.0/lib/gcc/x86_64-pc-linux-gnu/4.1.2/include
export TECS_LINT_FLAG = $(TECS_LINT_COMMON_FLAG) $(X86_64_PCLINT_FLAG)
endif

ifeq ($(_CPU_TYPE),_CPU_X86)
export X86_PCLINT_FLAG  = -I$(LINT_TOOLCHAIN_PATH)/x86_gcc4.1.2_glibc2.5.0/i686-pc-linux-gnu/include \
                          -I$(LINT_TOOLCHAIN_PATH)/x86_gcc4.1.2_glibc2.5.0/lib/gcc/i686-pc-linux-gnu/4.1.2/include
export TECS_LINT_FLAG = $(TECS_LINT_COMMON_FLAG) $(X86_PCLINT_FLAG)  
endif


#####TECS PCLint结束#####

