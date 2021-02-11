#!/usr/bin/env python3
"""split bulk-delete csv files into chunks of max N accounts

while the bulk-delete docs claim to support requests of more than 500k users,
we have reliable failures to upload ~150k
"""

import os
import sys

def split_csv(filename, per_file=100000, header_lines=2):
    """Split a csv file into chunks, preserving common header"""

    filename = sys.argv[1]
    base, ext = os.path.splitext(filename)

    with open(filename, newline="") as f:
        lines = f.readlines()

    header = lines[:header_lines]
    body = lines[header_lines:]

    n = 1
    print(repr(per_file))
    while body:
        chunk, body = body[:per_file], body[per_file:]
        dest = f"{base}-{per_file}-{n:02}{ext}"
        print(f"Writing {len(chunk)} to {dest}")
        with open(dest, "w") as f:
            f.write("".join(header))
            f.write("".join(chunk))
        n += 1


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", help="csv filename to split")
    parser.add_argument("-n", default=100000, type=int, help="number of entries per file")
    parser.add_argument("--header-lines", default=2, type=int, help="Number of header lines to preserve in split files")
    opts = parser.parse_args()
    split_csv(opts.filename, opts.n, opts.header_lines)
