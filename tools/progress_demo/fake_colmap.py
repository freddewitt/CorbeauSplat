#!/usr/bin/env python3
"""Stand-in for COLMAP, for the progress demo. Prints glog lines, does no work.

The counters below are the formats seen in a real 684-image run:
  feature_extraction.cc:270] Processed file [12/684]
  pairing.cc:562] Processing image [37/684]      sequential pass
  pairing.cc:333] Processing image [5/69]        loop detection pass
  pairing.cc:214] Processing block [2/14, 9/14]  exhaustive
  incremental_mapper.cc] Registering image #42 (num_reg_frames=43)
  undistortion.cc] Undistorting image [12/684]
"""

import random
import sys
import time
from datetime import datetime

N = 40
rng = random.Random(3)


def glog(src: str, msg: str) -> None:
    now = datetime.now()
    print(f"I{now:%Y%m%d %H:%M:%S.%f} 0x16ff87000 {src}] {msg}", flush=True)


def pause(base: float) -> None:
    time.sleep(base * rng.uniform(0.4, 1.8))


def main() -> int:
    sub = sys.argv[1] if len(sys.argv) > 1 else ""
    if sub == "feature_extractor":
        for i in range(1, N + 1):
            pause(0.12)
            glog("feature_extraction.cc:270", f"Processed file [{i}/{N}]")
    elif sub == "sequential_matcher":
        for i in range(1, N + 1):
            pause(0.10)
            glog("pairing.cc:562", f"Processing image [{i}/{N}]")
            glog("feature_matching.cc:218", f"in {rng.uniform(0.1, 0.4):.3f}s")
        loops = N // 10
        for i in range(1, loops + 1):
            pause(0.55)
            glog("pairing.cc:333", f"Processing image [{i}/{loops}]")
    elif sub == "exhaustive_matcher":
        blocks = 4
        for r in range(1, blocks + 1):
            for c in range(1, blocks + 1):
                pause(0.5 if c > r else 0.25 if c == r else 0.02)
                glog("pairing.cc:214", f"Processing block [{r}/{blocks}, {c}/{blocks}]")
    elif sub == "mapper":
        glog("incremental_pipeline.cc:323", "Initializing with image pair #1 and #9")
        for i in range(3, N + 1):
            pause(0.08)
            glog("incremental_pipeline.cc:388", f"Registering image #{i} (num_reg_frames={i})")
            if i % 10 == 0:
                glog("bundle_adjustment.cc:866", "Bundle adjustment report")
                pause(0.3)
    elif sub == "image_undistorter":
        for i in range(1, N + 1):
            pause(0.04)
            glog("undistortion.cc:191", f"Undistorting image [{i}/{N}]")
    else:
        print(f"fake_colmap: unknown command {sub!r}", file=sys.stderr)
        return 1
    glog("timer.cc:90", f"Elapsed time: {rng.uniform(0.1, 0.9):.3f} [minutes]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
