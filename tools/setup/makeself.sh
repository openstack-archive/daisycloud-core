#!/bin/sh
#

MS_VERSION=2.1.5
MS_COMMAND="$0"
unset CDPATH

for f in "${1+"$@"}"; do
    MS_COMMAND="$MS_COMMAND \\\\
    \\\"$f\\\""
done

# Procedures

MS_Usage()
{
    echo "Usage: $0 [params] archive_dir file_name label [startup_script] [args]"
    echo "params can be one or more of the following :"
    echo "    --version | -v  : Print out Makeself version number and exit"
    echo "    --help | -h     : Print out this help message"
    echo "    --gzip          : Compress using gzip (default if detected)"
    echo "    --bzip2         : Compress using bzip2 instead of gzip"
    echo "    --compress      : Compress using the UNIX 'compress' command"
    echo "    --nocomp        : Do not compress the data"
    echo "    --notemp        : The archive will create archive_dir in the"
    echo "                      current directory and uncompress in ./archive_dir"
    echo "    --copy          : Upon extraction, the archive will first copy itself to"
    echo "                      a temporary directory"
    echo "    --append        : Append more files to an existing Makeself archive"
    echo "                      The label and startup scripts will then be ignored"
    echo "    --current       : Files will be extracted to the current directory."
    echo "                      Implies --notemp."
    echo "    --nomd5         : Don't calculate an MD5 for archive"
    echo "    --nocrc         : Don't calculate a CRC for archive"
    echo "    --header file   : Specify location of the header script"
    echo "    --follow        : Follow the symlinks in the archive"
    echo "    --nox11         : Disable automatic spawn of a xterm"
    echo "    --nowait        : Do not wait for user input after executing embedded"
    echo "                      program from an xterm"
    echo "    --lsm file      : LSM file describing the package"
    echo
    echo "Do not forget to give a fully qualified startup script name"
    echo "(i.e. with a ./ prefix if inside the archive)."
    exit 1
}

# Default settings
if type gzip 2>&1 > /dev/null; then
    COMPRESS=gzip
else
    COMPRESS=Unix
fi
KEEP=n
CURRENT=n
NOX11=n
APPEND=n
COPY=none
TAR_ARGS=cvf
HEADER=`dirname $0`/makeself-header.sh

# LSM file stuff
LSM_CMD="echo No LSM. >> \"\$archname\""

while true
do
    case "$1" in
    --version | -v)
	echo Makeself version $MS_VERSION
	exit 0
	;;
    --bzip2)
	COMPRESS=bzip2
	shift
	;;
    --gzip)
	COMPRESS=gzip
	shift
	;;
    --compress)
	COMPRESS=Unix
	shift
	;;
    --encrypt)
	COMPRESS=gpg
	shift
	;;
    --nocomp)
	COMPRESS=none
	shift
	;;
    --notemp)
	KEEP=y
	shift
	;;
    --copy)
	COPY=copy
	shift
	;;
    --current)
	CURRENT=y
	KEEP=y
	shift
	;;
    --header)
	HEADER="$2"
	shift 2
	;;
    --follow)
	TAR_ARGS=cvfh
	shift
	;;
    --nox11)
	NOX11=y
	shift
	;;
    --nowait)
	shift
	;;
    --nomd5)
	NOMD5=y
	shift
	;;
    --nocrc)
	NOCRC=y
	shift
	;;
    --append)
	APPEND=y
	shift
	;;
    --lsm)
	LSM_CMD="cat \"$2\" >> \"\$archname\""
	shift 2
	;;
    -h | --help)
	MS_Usage
	;;
    -*)
	echo Unrecognized flag : "$1"
	MS_Usage
	;;
    *)
	break
	;;
    esac
done

if test $# -lt 1; then
	MS_Usage
else
	if test -d "$1"; then
		archdir="$1"
	else
		echo "Directory $1 does not exist."
		exit 1
	fi
fi
archname="$2"

if test "$APPEND" = y; then
    if test $# -lt 2; then
	MS_Usage
    fi

    # Gather the info from the original archive
    OLDENV=`sh "$archname" --dumpconf`
    if test $? -ne 0; then
	echo "Unable to update archive: $archname" >&2
	exit 1
    else
	eval "$OLDENV"
    fi
else
    if test "$KEEP" = n -a $# = 3; then
	echo "ERROR: Making a temporary archive with no embedded command does not make sense!" >&2
	echo
	MS_Usage
    fi
    # We don't really want to create an absolute directory...
    if test "$CURRENT" = y; then
	archdirname="."
    else
	archdirname=`basename "$1"`
    fi

    if test $# -lt 3; then
	MS_Usage
    fi

    LABEL="$3"
    SCRIPT="$4"
    test x$SCRIPT = x || shift 1
    shift 3
    SCRIPTARGS="$*"
fi

if test "$KEEP" = n -a "$CURRENT" = y; then
    echo "ERROR: It is A VERY DANGEROUS IDEA to try to combine --notemp and --current." >&2
    exit 1
fi

case $COMPRESS in
gzip)
    GZIP_CMD="gzip -c9"
    GUNZIP_CMD="gzip -cd"
    ;;
bzip2)
    GZIP_CMD="bzip2 -9"
    GUNZIP_CMD="bzip2 -d"
    ;;
gpg)
    GZIP_CMD="gpg -ac -z9"
    GUNZIP_CMD="gpg -d"
    ;;
Unix)
    GZIP_CMD="compress -cf"
    GUNZIP_CMD="exec 2>&-; uncompress -c || test \\\$? -eq 2 || gzip -cd"
    ;;
none)
    GZIP_CMD="cat"
    GUNZIP_CMD="cat"
    ;;
esac

tmpfile="${TMPDIR:=/tmp}/mkself$$"

if test -f $HEADER; then
	oldarchname="$archname"
	archname="$tmpfile"
	# Generate a fake header to count its lines
	SKIP=0
    . $HEADER
    SKIP=`cat "$tmpfile" |wc -l`
	# Get rid of any spaces
	SKIP=`expr $SKIP`
	rm -f "$tmpfile"
    echo Header is $SKIP lines long >&2

	archname="$oldarchname"
else
    echo "Unable to open header file: $HEADER" >&2
    exit 1
fi

echo

if test "$APPEND" = n; then
    if test -f "$archname"; then
		echo "WARNING: Overwriting existing file: $archname" >&2
    fi
fi

USIZE=`du -ks $archdir | cut -f1`
DATE=`LC_ALL=C date`

if test "." = "$archdirname"; then
	if test "$KEEP" = n; then
		archdirname="makeself-$$-`date +%Y%m%d%H%M%S`"
	fi
fi

test -d "$archdir" || { echo "Error: $archdir does not exist."; rm -f "$tmpfile"; exit 1; }
echo About to compress $USIZE KB of data...
echo Adding files to archive named \"$archname\"...
exec 3<> "$tmpfile"
(cd "$archdir" && ( tar $TAR_ARGS - . | eval "$GZIP_CMD" >&3 ) ) || { echo Aborting: Archive directory not found or temporary file: "$tmpfile" could not be created.; exec 3>&-; rm -f "$tmpfile"; exit 1; }
exec 3>&- # try to close the archive

fsize=`cat "$tmpfile" | wc -c | tr -d " "`

# Compute the checksums

md5sum=00000000000000000000000000000000
crcsum=0000000000

if test "$NOCRC" = y; then
	echo "skipping crc at user request"
else
	crcsum=`cat "$tmpfile" | CMD_ENV=xpg4 cksum | sed -e 's/ /Z/' -e 's/	/Z/' | cut -dZ -f1`
	echo "CRC: $crcsum"
fi

if test "$NOMD5" = y; then
	echo "skipping md5sum at user request"
else
	# Try to locate a MD5 binary
	OLD_PATH=$PATH
	PATH=${GUESS_MD5_PATH:-"$OLD_PATH:/bin:/usr/bin:/sbin:/usr/local/ssl/bin:/usr/local/bin:/opt/openssl/bin"}
	MD5_ARG=""
	MD5_PATH=`exec <&- 2>&-; which md5sum || type md5sum`
	test -x $MD5_PATH || MD5_PATH=`exec <&- 2>&-; which md5 || type md5`
	test -x $MD5_PATH || MD5_PATH=`exec <&- 2>&-; which digest || type digest`
	PATH=$OLD_PATH
	if test `basename $MD5_PATH` = digest; then
		MD5_ARG="-a md5"
	fi
	if test -x "$MD5_PATH"; then
		md5sum=`cat "$tmpfile" | eval "$MD5_PATH $MD5_ARG" | cut -b-32`;
		echo "MD5: $md5sum"
	else
		echo "MD5: none, MD5 command not found"
	fi
fi

if test "$APPEND" = y; then
    mv "$archname" "$archname".bak || exit

    # Prepare entry for new archive
    filesizes="$filesizes $fsize"
    CRCsum="$CRCsum $crcsum"
    MD5sum="$MD5sum $md5sum"
    USIZE=`expr $USIZE + $OLDUSIZE`
    # Generate the header
    . $HEADER
    # Append the original data
    tail -n +$OLDSKIP "$archname".bak >> "$archname"
    # Append the new data
    cat "$tmpfile" >> "$archname"

    chmod +x "$archname"
    rm -f "$archname".bak
    echo Self-extractible archive \"$archname\" successfully updated.
else
    filesizes="$fsize"
    CRCsum="$crcsum"
    MD5sum="$md5sum"

    # Generate the header
    . $HEADER

    # Append the compressed tar data after the stub
    echo
    cat "$tmpfile" >> "$archname"
    chmod +x "$archname"
    echo Self-extractible archive \"$archname\" successfully created.
fi
rm -f "$tmpfile"
