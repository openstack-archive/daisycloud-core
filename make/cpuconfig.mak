export _CPU_TYPE_FAMILY_X86  = _CPU_X86
export _CPU_TYPE_FAMILY_IA64 = _CPU_X86_64

export _CPU_TYPE_ALL   = \
                  $(_CPU_TYPE_FAMILY_X86) \
                  $(_CPU_TYPE_FAMILY_IA64)


export _OS_TYPE_ALL = _CGSL _LINUX _el5 _el6 _ZXVE

export _VERSION_TYPE_ALL = _RELEASE _DEBUG

