"""Setup or teardown a wireguard tunnel connection between a windows host and a NILRT+SNAC client's wglv0 interface.
"""
import argparse
from enum import IntEnum
import logging
import platform
import sys
import ctypes
from ipaddress import IPv4Interface, IPv4Network

from fabric import Connection

from . import logger
from .wireguard import WireguardClient


LOG_FMT = '%(asctime)s:%(levelname)s:%(name)s:%(filename)s(%(lineno)s): %(message)s'
TUNNEL_NAME = "nilrt-snac-test"
TEST_NETWORK = IPv4Network("172.16.128.0/30")


class EX(IntEnum):
    """Process return codes for the main() method."""
    OK = 0
    ERROR = 1
    BADENV = 128


def check_administrator(force: bool = False) -> bool:
    """Check that the script is being executed as "Administrator"."""
    if force:
        return True

    try:
        if ctypes.windll.shell32.IsUserAnAdmin():
            return True
        else:
            logger.error("Script must be run with 'Administrator' privileges.")
            return False
    except:
        return False


def check_host_os(force: bool = False) -> bool:
    """Check that this script is being run on a Windows OS."""

    if platform.system().lower() == "windows":
        return True
    elif force:
        logger.warning("Invalid execution environment (not Windows). Proceeding due to 'force' argument.")
        return True
    else:
        logger.error("Invalid execution environment (not Windows).")
        return False


# MAIN #
########

def _cmd_setup(
        args,
        wg_local: WireguardClient,
        wg_remote: WireguardClient,
    ) -> int:

    # tear down any leftover tunnels
    if _cmd_teardown(args, wg_local, wg_remote) != EX.OK:
        logger.error(f"Teardown task errored. Bailing out.")
        return EX.ERROR
    
    # pick IPv4 addresses from the test network
    local_wg_ip = IPv4Interface(f"{TEST_NETWORK[1]}/{TEST_NETWORK.prefixlen}")
    remote_wg_ip = IPv4Interface(f"{TEST_NETWORK[2]}/{TEST_NETWORK.prefixlen}")

    # collect remote wireguard tunnel info
    remote_pubkey = wg_remote.get_public_key(args.remote_tunnel)
    remote_port = wg_remote.get_listen_port(args.remote_tunnel)
    remote_host = wg_remote.get_client_hostname()
    wg_remote.add_address(args.remote_tunnel, remote_wg_ip)

    # setup local tunnel
    wg_local.create_tunnel(TUNNEL_NAME, local_wg_ip, listen_port=51820)
    local_pubkey = wg_local.get_public_key(TUNNEL_NAME)
    local_port = wg_local.get_listen_port(TUNNEL_NAME)
    local_host = wg_local.get_client_hostname()
    
    # connect tunnels
    wg_local.add_peer(
        TUNNEL_NAME,
        peer_pubkey=remote_pubkey,
        allowed_ips=[remote_wg_ip.network],
        endpoint=f"{remote_host}:{remote_port}"
    )
    wg_remote.add_peer(
        args.remote_tunnel,
        peer_pubkey=local_pubkey,
        allowed_ips=[local_wg_ip.network],
        endpoint=f"{local_host}:{local_port}"
    )

    print("Setup DONE.")
    logger.info(f"Remote IPv4 tunnel address: {str(remote_wg_ip)}")
    return EX.OK


def _cmd_teardown(
        args,
        wg_local: WireguardClient,
        wg_remote: WireguardClient,
    ) -> int:
    wg_local.remove_tunnel(TUNNEL_NAME)
    wg_remote.remove_all_peers(args.remote_tunnel)

    return EX.OK


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(title="Commands", dest="_cmd")
    common_actions = [  # actions common to all subcommands
        argparse._StoreTrueAction(["-f", "--force"], "force", help="Ignore safety checks."),
        argparse._StoreTrueAction(["-d", "--debug"], "debug", help="Show DEBUG level output."),
        argparse._StoreAction([], "remote_host", required=True),
        argparse._StoreAction([], "remote_tunnel", nargs="?", default="wglv0"),
    ]

    sp_setup = subparsers.add_parser("setup")
    [sp_setup._add_action(a) for a in common_actions]
    
    sp_teardown = subparsers.add_parser("teardown")
    [sp_teardown._add_action(a) for a in common_actions]

    args = parser.parse_args(argv)

    if args._cmd is None:
        parser.print_help()
        parser.exit(2)

    if args.debug:
        logging.basicConfig(level=logging.DEBUG, format=LOG_FMT)
    else:
        logging.basicConfig(level=logging.INFO, format=LOG_FMT)
        
    logger.debug(args)

    if not check_administrator(args.force):
        return EX.BADENV
    if not check_host_os(args.force):
        return EX.BADENV
    
    wg_local = WireguardClient()
    remote_connection = Connection(
        host=args.remote_host,
        connect_kwargs={"password": ""},
        )
    wg_remote = WireguardClient(connection=remote_connection)
    
    if args._cmd == "setup":
        return _cmd_setup(args, wg_local, wg_remote)
    elif args._cmd == "teardown":
        return _cmd_teardown(args, wg_local, wg_remote)
    else:
        raise NotImplementedError()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

