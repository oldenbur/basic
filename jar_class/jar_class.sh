#!/bin/bash

if [[ $1 = "-h" ]]; then
	echo "usage: $0 {class_name} [jar(s)]"
	echo "  where jar(s) is an optional space separated list of jars which "
	echo "    defaults to all jars found in the current directory, recursively"
	echo
	exit
fi

C=$1; shift

JLIST=$@
if [ $# -lt 1 ]; then
	JLIST=$(find . -name '*.jar')
fi

for J in $JLIST; do
	for CN in $(jar tvf $J 2>/dev/null | grep $C | awk '{print $8}'); do
		printf "%64s: %s\n" $J $CN
	done
done

