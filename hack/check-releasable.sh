#!/bin/sh
if [ -e ./dist/.unreleasable.txt ]
then
	cat ./dist/.unreleasable.txt 
fi
[ -e ./dist/.releasable.txt ]
