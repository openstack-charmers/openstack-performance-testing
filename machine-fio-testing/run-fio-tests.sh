#!/bin/bash

set -ex

RUNTIME=360

DEVICES="hdd sdd optane"
OPERATIONS="randread randwrite"
BLOCK_SIZE=4k
NUM_JOBS=8

for device in $DEVICES; do
    for operation in $OPERATIONS; do
        echo fio --bs=$BLOCK_SIZE --numjobs=$NUM_JOBS --rw=$operation --section "job $device" \
            --runtime=$RUNTIME --output-format=json --output=$device-$operation-$BLOCK_SIZE.json \
            fio.conf
    done
done

OPERATIONS="read write"
BLOCK_SIZE=128k
NUM_JOBS=1

for device in $DEVICES; do
    for operation in $OPERATIONS; do
        echo fio --bs=$BLOCK_SIZE --numjobs=$NUM_JOBS --rw=$operation --section "job $device" \
            --runtime=$RUNTIME --output-format=json --output=$device-$operation-$BLOCK_SIZE.json \
            fio.conf
    done
done
