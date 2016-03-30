###################################################################################
###
###     this file is used to define the basic system command.
###     
###
###     Author:  Jixuepeng, CSP
###     History:
###     1. jixuepeng,2011/07/21  ´´½¨ 
###################################################################################
export RM            = rm -rf
export RMDIR         = rm -rf

ifeq ($(_LINT_CHECK),TRUE)
export MKDIR         = mkdir
else
export MKDIR         = mkdir -p
endif

export MOVE          = @mv -f
export ECHO          = @echo
export CP            = @cp -f
export MAKE          = @make
export LN            = @ln -sf
export TARX          = tar -xzvf
export TARC          = tar -czvf
