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

def _check_service(Q: str, service: str, expected: str = "yes") -> bool:
    """Verifies firewall-cmd (--policy=POLICY/--zone=ZONE/etc.) --query-service=SERVICE
    matches what is expected.
    """

    actual: str = subprocess.getoutput(
        f"firewall-cmd --permanent {Q} --query-service={service}")
    if expected == actual:
        return True
    logger.error(f"ERROR: {Q} service {service}: expected {expected}, observed {actual}")
    return False


def _check_service_info(service: str, Q: str, expected: str) -> bool:
    """Verifies firewall-cmd --service=SERVICE (--get-ports/--get-description/etc.)
    matches what is expected.
    """

    actual: str = subprocess.getoutput(
        f"firewall-cmd --permanent --service={service} {Q}")
    if expected == actual:
        return True
    logger.error(f"ERROR: service {service} {Q}: expected {expected}, observed {actual}")
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
        self._opkg_helper.install("ni-firewalld-servicedefs")

        _offlinecmd("--reset-to-defaults")

        _offlinecmd("--zone=work", "--add-interface=wglv0")
        _offlinecmd("--zone=work", "--remove-forward")
        _offlinecmd("--zone=public", "--remove-forward")

        _offlinecmd("--new-policy=work-in")
        _offlinecmd("--policy=work-in", "--add-ingress-zone=work")
        _offlinecmd("--policy=work-in", "--add-egress-zone=HOST")
        _offlinecmd("--policy=work-in", "--add-protocol=icmp")
        _offlinecmd("--policy=work-in", "--add-protocol=ipv6-icmp")
        _offlinecmd("--policy=work-in",
                    "--add-service=ssh",
                    "--add-service=mdns",
                    )

        _offlinecmd("--new-policy=work-out")
        _offlinecmd("--policy=work-out", "--add-ingress-zone=HOST")
        _offlinecmd("--policy=work-out", "--add-egress-zone=work")
        _offlinecmd("--policy=work-out", "--add-protocol=icmp")
        _offlinecmd("--policy=work-out", "--add-protocol=ipv6-icmp")
        _offlinecmd("--policy=work-out",
                    "--add-service=ssh",
                    "--add-service=http",
                    "--add-service=https",
                    "--add-service=syslog",
                    "--add-service=ni-logos-xt",
                    )
        _offlinecmd("--policy=work-out", "--set-target=REJECT")

        _offlinecmd("--new-policy=public-in")
        _offlinecmd("--policy=public-in", "--add-ingress-zone=public")
        _offlinecmd("--policy=public-in", "--add-egress-zone=HOST")
        _offlinecmd("--policy=public-in", "--add-protocol=icmp")
        _offlinecmd("--policy=public-in", "--add-protocol=ipv6-icmp")
        _offlinecmd("--policy=public-in",
                    "--add-service=ssh",
                    "--add-service=wireguard",
                    )

        _offlinecmd("--new-policy=public-out")
        _offlinecmd("--policy=public-out", "--add-ingress-zone=HOST")
        _offlinecmd("--policy=public-out", "--add-egress-zone=public")
        _offlinecmd("--policy=public-out",  "--add-protocol=icmp")
        _offlinecmd("--policy=public-out",  "--add-protocol=ipv6-icmp")
        _offlinecmd("--policy=public-out",
                    "--add-service=dhcp",
                    "--add-service=dhcpv6",
                    "--add-service=http",
                    "--add-service=https",
                    "--add-service=wireguard",
                    "--add-service=dns",
                    "--add-service=ntp",
                    )
        _offlinecmd("--policy=public-out", "--set-target=REJECT")

        _offlinecmd("--policy=work-in",
                    "--add-service=ni-labview-realtime",
                    "--add-service=ni-labview-viserver",
                    "--add-service=ni-logos-xt",
                    "--add-service=ni-mxs",
                    "--add-service=ni-rpc-server",
                    "--add-service=ni-service-locator",
                    )
        _offlinecmd("--policy=work-in",
                    # Temporary port add; see x-niroco-static-port.ini
                    "--add-port=55184/tcp",
                    )
        _offlinecmd("--policy=work-out",
                    "--add-service=amqp",
                    "--add-service=salt-master",
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

        valid = all([
            _check_target("work-in", "CONTINUE"),
            _check_target("work-out"),
            _check_target("public-in", "CONTINUE"),
            _check_target("public-out"),
            _check_service("--policy=work-in", "ni-labview-realtime"),
            _check_service("--policy=public-in", "ni-labview-realtime", "no"),
            _check_service("--zone=public", "ni-labview-realtime", "no"),
            _check_service_info("ni-labview-realtime", "--get-ports", "3079/tcp"),
            ])

        return valid
