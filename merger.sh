#!/bin/bash
length=$(wc -l $1 | awk '{print $1}')
count=1
while [ "$count" -le "$length" ] ; do
      a=$(head -$count $1 | tail -1)
      b=$(head -$count $2 | tail -1)
      echo "$a,$b"
      count=$(expr $count + 1)
done