#!/usr/bin/env python3
import argparse
import hashlib
import ipaddress
import math
import sys
import time

parser = argparse.ArgumentParser(description="Generate a IPv6 Unique Local Address.")
parser.add_argument(
    "--eui48", required=True,
    type=lambda x: int(x.replace(":", ""), 16) if ":" in x else int(x, 0),
    help="EUI-48 of a network interface")
parser.add_argument(
    "--time", type=float,
    help="""Fractional seconds since 1970-01-01 00:00:00 UTC, defaults to
    current time""")
parser.add_argument(
    "--subnet", type=lambda x: int(x, 0), default=0,
    help="16-bit Subnet ID")
parser.add_argument(
    "--network", type=lambda x: ipaddress.IPv6Network(x, strict=False),
    help="""Construct a new IPv6 address on the same subnet as the specified
    network (with prefix). The algorithm in RFC 4193 §3.2.2 is skipped.""")

def eui48_to_meui64(eui48: int) -> int:
    "Converts an EUI-48 to a Modified EUI-64 as defined by RFC 3513."
    company_id = eui48 >> 24
    mfg_id = (eui48 & 0xffffff)
    meui64 = ((company_id ^ 0x020000) << 40 | 0xfffe000000 | mfg_id)
    return meui64

def unique_local_ipv6(meui64: int, ts: float = None, subnet: int = 0, /,
                      dgst: str = "sha256") -> ipaddress.IPv6Interface:
    """Generate a Local IPv6 Unicast Address as defined by RFC 4193.

    The address components (defined in §3.1) are as follows. L=1 (local
    assignment) so that the overall prefix is fd00::/8. The Subnet ID may be
    optionally specified using the subnet parameter. The Interface ID is defined
    in RFC 3513 to be equal to meui64, the Modified EUI-64. The Global ID is
    computed using an algorithm defined in §3.2.2 whose inputs include the
    Modified EUI-64 (meui64) and a timestamp ts (fractional seconds since the
    epoch).

    NOTE: §3.2.2 specifies hashing with SHA-1. We use SHA-256 in order to
    minimize the use of SHA-1 in new code. The digest function may be overridden
    with the dgst parameter.
    """

    m = hashlib.new(dgst)

    if ts is None:
        # python floats are doubles. doubles have 52 bits of mantissa.
        # nanoseconds only require 30. This is ok
        ts = time.time_ns() / 1e9

    (ns_frac, seconds_frac) = math.modf(ts)
    seconds = int(seconds_frac)
    nanoseconds = int(round(ns_frac * 1e9))

    # RFC 1305 "NTP timestamps are represented as a 64-bit unsigned fixed-point
    # number, in seconds relative to 0h on 1 January 1900. The integer part is
    # in the first 32 bits and the fraction part in the last 32 bits."

    seconds_ntp = seconds + 2208988800 # (3600*24*(17+365*(1972-1900)))
    m.update(seconds_ntp.to_bytes(4, 'big'))
    ns_fix32 = (nanoseconds * 2**32) // 1000000000
    m.update(ns_fix32.to_bytes(4, 'big'))

    m.update(meui64.to_bytes(8, 'big'))
    d = m.digest()

    global_id = d[-5:]
    addr = b'\xfd' + global_id + subnet.to_bytes(2, 'big') + meui64.to_bytes(8, 'big')
    return ipaddress.IPv6Interface((addr, 64))


args = parser.parse_args()
meui64 = eui48_to_meui64(args.eui48)
if args.network:
    subnet = int(args.network.network_address)
    prefix = args.network.prefixlen
    addr = ipaddress.IPv6Interface((subnet | meui64, prefix))
else:
    addr = unique_local_ipv6(meui64, args.time, args.subnet)
print(addr)
