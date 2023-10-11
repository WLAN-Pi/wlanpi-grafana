#!/usr/bin/env python3
import os
import re
import sys
import time


# Created by Bryan Ward

def main():
    counter = 0
    freqs = []
    lf = 0
    hf = 0
    numsamples = 0

    for line in sys.stdin:
        if line is not None:
            if counter >= 4:
                data = list(map(int, line.split(":")[1].split(" ")[1:-1]))
                x = list(range(len(data)))
                y = data

                # Build Influx Line Protocol
                l = "wispy2"
                # l = l + ",lf=" + str(lf) + ",hf=" + str(hf) + " "
                l = l + " "
                l = l + str(freqs[0]) + "=" + str(data[0])
                for i in range(numsamples - 1):
                    l = l + "," + str(freqs[i + 1]) + "=" + str(data[i + 1])
                l = l + " " + str(time.time_ns())
                print(l)

            else:
                counter = counter + 1
                if counter == 4:
                    m = re.match(r"(\d+)MHz\-(\d+)MHz.*, (\d+) samples", line.strip())
                    if m:
                        lf = int(m.groups()[0])
                        hf = int(m.groups()[1])
                        numsamples = int(m.groups()[2])
                        for i in range(numsamples):
                            freqs.append(round(i * (hf - lf) / numsamples + lf, 4))

sys.exit(main())