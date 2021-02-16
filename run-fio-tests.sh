#!/bin/bash

set -x

OPS_LIST="randwrite randread write read randrw"
BS_LIST="4k 4M"

# All in seconds
RAMP_INTERVAL=90
TEST_DURATION=1800
NUMBER_OF_UNITS=200
BATCH_SIZE=20
BATCHES=$(($NUMBER_OF_UNITS/$BATCH_SIZE-1))

for bs in $BS_LIST; do
    for ops in $OPS_LIST; do
		for i in `seq 0 $BATCHES`; do
		    BATCH_START=$(($i * $BATCH_SIZE))
		    BATCH_END=$(($BATCH_START + $BATCH_SIZE -1))
		    juju run-action `seq --format="woodpecker/%g" $BATCH_START $BATCH_END` \
		        fio operation=$ops runtime=$TEST_DURATION block-size=$bs
		    sleep $RAMP_INTERVAL
		done
		# Wait for last set of tests submitted to complete before
		# moving onto the next test combination
		sleep $TEST_DURATION
	done
done
