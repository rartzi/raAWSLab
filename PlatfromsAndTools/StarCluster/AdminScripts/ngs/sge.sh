#!/bin/bash

qconf -Ap /usr/local/root/sge.smp.config
qconf -aattr queue pe_list smp all.q

#TMPFILE=/usr/local/root/execd_params.config
#if [ $MOD_SGE_SCHED_INT ]; then
#	grep -v execd_params $1 > $TMPFILE
#	echo "execd_params	S_DESCRIPTORS=20000 S_MAXPROC=1000" >> $TMPFILE
#	sleep 1
#	mv $TMPFILE $1
#else
#	export EDITOR=$0
#	export MOD_SGE_SCHED_INT=$1
#	qconf -mconf
#fi