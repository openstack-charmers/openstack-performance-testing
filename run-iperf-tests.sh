#!/bin/bash

set -x

# All in seconds
BATCH_TIME=30
TEST_DURATION=120
NUMBER_OF_UNITS=200
SPEAKERS=$(($NUMBER_OF_UNITS/2))
OFFSET=0

for speaker in `seq $((0+$OFFSET)) $((SPEAKERS+OFFSET))`; do
    TARGET=$(($speaker + $SPEAKERS))
    juju run-action magpie/$speaker run-iperf \
	units="magpie/$TARGET" \
	iperf-batch-time=$BATCH_TIME \
	concurrency-progression="2 4" \
	total-run-time=$TEST_DURATION
done
