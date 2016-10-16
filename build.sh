#!/bin/bash
#
echo $1
docker build -t stoka-fb .
docker tag stoka-fb ssabpisa/stoka-fb:$1
docker push ssabpisa/stoka-fb:$1