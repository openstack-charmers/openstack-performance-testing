#!/bin/bash

set -x

# All in seconds
RAMP_INTERVAL=120
TEST_DURATION=3600
OPERATION=randrw
NUMBER_OF_UNITS=200
BATCH_SIZE=20
BATCHES=$(($NUMBER_OF_UNITS/$BATCH_SIZE-1))
LATENCY_TARGET=10000

for i in `seq 0 $BATCHES`; do
    BATCH_START=$(($i * $BATCH_SIZE))
    BATCH_END=$(($BATCH_START + $BATCH_SIZE -1))
    juju run-action `seq --format="woodpecker/%g" $BATCH_START $BATCH_END` \
        fio operation=$OPERATION runtime=$TEST_DURATION
    sleep $RAMP_INTERVAL
done
