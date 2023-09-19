#!/bin/bash

while true; do ./pihealth.sh | ../tografana.sh pihealth; sleep 60; done