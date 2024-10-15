import argparse
import subprocess

from nilrt_snac._configs._base_config import _BaseConfig

from nilrt_snac import logger
from nilrt_snac.opkg import opkg_helper

def _cmd(*args: str):
    "Syntactic sugar for firewall-cmd -q."
    subprocess.run(["firewall-cmd", "-q"] + list(args), check=True)

def _offlinecmd(*args: str):
    "Syntactic sugar for firewall-offline-cmd -q."
    subprocess.run(["firewall-offline-cmd", "-q"] + list(args), check=True)

def _check_target(policy: str, expected: str = "REJECT") -> bool:
    "Verifies firewall-cmd --policy=POLICY --get-target matches what is expected."

    actual: str = subprocess.getoutput(
        f"firewall-cmd --permanent --policy={policy} --get-target")
    if expected == actual:
        return True
    logger.error(f"ERROR: policy {policy} target: expected {expected}, observed {actual}")
    return False


class _FirewallConfig(_BaseConfig):
    def __init__(self):
        self._opkg_helper = opkg_helper

    def configure(self, args: argparse.Namespace) -> None:
        print("Configuring firewall...")
        dry_run: bool = args.dry_run
        if dry_run:
            return

        # nftables installed via deps
        self._opkg_helper.install("firewalld")
        self._opkg_helper.install("firewalld-offline-cmd")
        self._opkg_helper.install("firewalld-log-rotate")

        _offlinecmd("--reset-to-defaults")

        _offlinecmd("--zone=work", "--add-interface=wglv0")
        _offlinecmd("--zone=work", "--remove-forward")
        _offlinecmd("--zone=public", "--remove-forward")

        _offlinecmd("--new-policy=work-in")
        _offlinecmd("--policy=work-in", "--add-ingress-zone=work")
        _offlinecmd("--policy=work-in", "--add-egress-zone=HOST")
        _offlinecmd("--policy=work-in", "--add-protocol=icmp")
        _offlinecmd("--policy=work-in",
                    "--add-service=ssh",
                    "--add-service=mdns",
                    )

        _offlinecmd("--new-policy=work-out")
        _offlinecmd("--policy=work-out", "--add-ingress-zone=HOST")
        _offlinecmd("--policy=work-out", "--add-egress-zone=work")
        _offlinecmd("--policy=work-out", "--add-protocol=icmp")
        _offlinecmd("--policy=work-out",
                    "--add-service=ssh",
                    "--add-service=http",
                    "--add-service=https",
                    )
        _offlinecmd("--policy=work-out", "--set-target=REJECT")
        # Note that quotes around the rule are required when literally typing
        # this on the command line, but are forbidden here. This is because
        # firewall-cmd croaks on them:
        #
        # Warning: INVALID_RULE: internal error in _lexer(): rule family="ipv6"
        # icmp-type name="neighbour-advertisement" accept
        #
        # The quotes are removed by the shell, while Subprocess passes these
        # arguments through verbatim.
        _offlinecmd("--policy=work-out",
                    "--add-rich-rule=rule family=ipv6 icmp-type name=neighbour-advertisement accept",
                    "--add-rich-rule=rule family=ipv6 icmp-type name=neighbour-solicitation accept",
                    "--add-rich-rule=rule family=ipv6 icmp-type name=echo-request accept",
                    "--add-rich-rule=rule family=ipv6 icmp-type name=echo-reply accept",
                    )

        _offlinecmd("--new-policy=public-in")
        _offlinecmd("--policy=public-in", "--add-ingress-zone=public")
        _offlinecmd("--policy=public-in", "--add-egress-zone=HOST")
        _offlinecmd("--policy=public-in", "--add-protocol=icmp")
        _offlinecmd("--policy=public-in",
                    "--add-service=ssh",
                    "--add-service=wireguard",
                    )

        _offlinecmd("--new-policy=public-out")
        _offlinecmd("--policy=public-out", "--add-ingress-zone=HOST")
        _offlinecmd("--policy=public-out", "--add-egress-zone=public")
        _offlinecmd("--policy=public-out",  "--add-protocol=icmp")
        _offlinecmd("--policy=public-out",
                    "--add-service=dhcp",
                    "--add-service=dhcpv6",
                    "--add-service=http",
                    "--add-service=https",
                    "--add-service=wireguard",
                    "--add-service=dns",
                    )
        _offlinecmd("--policy=public-out", "--set-target=REJECT")
        _offlinecmd("--policy=public-out",
                    "--add-rich-rule=rule family=ipv6 icmp-type name=neighbour-advertisement accept",
                    "--add-rich-rule=rule family=ipv6 icmp-type name=neighbour-solicitation accept",
                    "--add-rich-rule=rule family=ipv6 icmp-type name=echo-request accept",
                    "--add-rich-rule=rule family=ipv6 icmp-type name=echo-reply accept",
                    )

        _offlinecmd("--policy=allow-host-ipv6",
                    "--add-rich-rule=rule family=ipv6 icmp-type name=echo-request accept",
                    "--add-rich-rule=rule family=ipv6 icmp-type name=echo-reply accept",
                    )

        _cmd("--reload")

    def verify(self, args: argparse.Namespace) -> bool:
        print("Verifying firewall configuration...")
        valid: bool = True

        try:
            pid: int = int(subprocess.getoutput("pidof -x /usr/sbin/firewalld"))
        except ValueError:
            logger.error(f"MISSING: running firewalld")
            valid = False

        try:
            _cmd("--check-config")
        except FileNotFoundError:
            logger.error(f"MISSING: firewall-cmd")
            valid = False

        valid = _check_target("work-in", "CONTINUE") and valid
        valid = _check_target("work-out") and valid
        valid = _check_target("public-in", "CONTINUE") and valid
        valid = _check_target("public-out") and valid
        return valid
