#!/usr/bin/env python3
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

                # Build Influx Line Protocol
                out = "wispy2"
                # out = out + ",lf=" + str(lf) + ",hf=" + str(hf) + " "
                out = out + " "
                out = out + str(freqs[0]) + "=" + str(data[0])
                for i in range(numsamples - 1):
                    out = out + "," + str(freqs[i + 1]) + "=" + str(data[i + 1])
                out = out + " " + str(time.time_ns())
                print(out)

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


# The spectool-client-parser entry point imports this module and calls main().
if __name__ == "__main__":
    sys.exit(main())
