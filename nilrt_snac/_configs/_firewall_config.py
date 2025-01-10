import argparse
import subprocess

from nilrt_snac._configs._base_config import _BaseConfig

from nilrt_snac import logger
from nilrt_snac.opkg import opkg_helper

def _cmd(dry_run: bool, *args: str):
    "Syntactic sugar for firewall-cmd -q."
    if not dry_run:
        subprocess.run(["firewall-cmd", "-q"] + list(args), check=True)
    else:
        print("Dry run: would have run firewall-cmd -q " + " ".join(args))

def _offlinecmd(dry_run: bool, *args: str):
    "Syntactic sugar for firewall-offline-cmd -q."
    if not dry_run:
        subprocess.run(["firewall-offline-cmd", "-q"] + list(args), check=True)
    else:
        print("Dry run: would have run firewall-offline-cmd -q " + " ".join(args))

def _check_target(dry_run: bool, policy: str, expected: str = "REJECT") -> bool:
    "Verifies firewall-cmd --policy=POLICY --get-target matches what is expected."

    if not dry_run:
        actual: str = subprocess.getoutput(
            f"firewall-cmd --permanent --policy={policy} --get-target")
        if expected == actual:
            return True
        logger.error(f"ERROR: policy {policy} target: expected {expected}, observed {actual}")
        return False
    else:
        print("Dry run: would have run firewall-cmd --policy=" + policy + " --get-target")
        return True

def _check_service(dry_run: bool, Q: str, service: str, expected: str = "yes") -> bool:
    """Verifies firewall-cmd (--policy=POLICY/--zone=ZONE/etc.) --query-service=SERVICE
    matches what is expected.
    """

    if not dry_run:
        actual: str = subprocess.getoutput(
            f"firewall-cmd --permanent {Q} --query-service={service}")
        if expected == actual:
            return True
        logger.error(f"ERROR: {Q} service {service}: expected {expected}, observed {actual}")
        return False
    else:
        print("Dry run: would have run firewall-cmd " + Q + " --query-service=" + service)
        return True

def _check_service_info(dry_run: bool, service: str, Q: str, expected: str) -> bool:
    """Verifies firewall-cmd --service=SERVICE (--get-ports/--get-description/etc.)
    matches what is expected.
    """

    if not dry_run:
        actual: str = subprocess.getoutput(
            f"firewall-cmd --permanent --service={service} {Q}")
        if expected == actual:
            return True
        logger.error(f"ERROR: service {service} {Q}: expected {expected}, observed {actual}")
        return False
    else:
        print("Dry run: would have run firewall-cmd --service=" + service + " " + Q)
        return True

class _FirewallConfig(_BaseConfig):
    def __init__(self):
        self._opkg_helper = opkg_helper

    def configure(self, args: argparse.Namespace) -> None:
        print("Configuring firewall...")
        dry_run: bool = args.dry_run

        # nftables installed via deps
        self._opkg_helper.install("firewalld")
        self._opkg_helper.install("firewalld-offline-cmd")
        self._opkg_helper.install("firewalld-log-rotate")
        self._opkg_helper.install("ni-firewalld-servicedefs")

        _offlinecmd(dry_run, "--reset-to-defaults")

        _offlinecmd(dry_run, "--zone=work", "--add-interface=wglv0")
        _offlinecmd(dry_run, "--zone=work", "--remove-forward")
        _offlinecmd(dry_run, "--zone=public", "--remove-forward")

        _offlinecmd(dry_run, "--new-policy=work-in")
        _offlinecmd(dry_run, "--policy=work-in", "--add-ingress-zone=work")
        _offlinecmd(dry_run, "--policy=work-in", "--add-egress-zone=HOST")
        _offlinecmd(dry_run, "--policy=work-in", "--add-protocol=icmp")
        _offlinecmd(dry_run, "--policy=work-in", "--add-protocol=ipv6-icmp")
        _offlinecmd(dry_run, "--policy=work-in",
                    "--add-service=ssh",
                    "--add-service=mdns",
                    )

        _offlinecmd(dry_run, "--new-policy=work-out")
        _offlinecmd(dry_run, "--policy=work-out", "--add-ingress-zone=HOST")
        _offlinecmd(dry_run, "--policy=work-out", "--add-egress-zone=work")
        _offlinecmd(dry_run, "--policy=work-out", "--add-protocol=icmp")
        _offlinecmd(dry_run, "--policy=work-out", "--add-protocol=ipv6-icmp")
        _offlinecmd(dry_run, "--policy=work-out",
                    "--add-service=ssh",
                    "--add-service=http",
                    "--add-service=https",
                    )
        _offlinecmd(dry_run, "--policy=work-out", "--set-target=REJECT")

        _offlinecmd(dry_run, "--new-policy=public-in")
        _offlinecmd(dry_run, "--policy=public-in", "--add-ingress-zone=public")
        _offlinecmd(dry_run, "--policy=public-in", "--add-egress-zone=HOST")
        _offlinecmd(dry_run, "--policy=public-in", "--add-protocol=icmp")
        _offlinecmd(dry_run, "--policy=public-in", "--add-protocol=ipv6-icmp")
        _offlinecmd(dry_run, "--policy=public-in",
                    "--add-service=ssh",
                    "--add-service=wireguard",
                    )

        _offlinecmd(dry_run, "--new-policy=public-out")
        _offlinecmd(dry_run, "--policy=public-out", "--add-ingress-zone=HOST")
        _offlinecmd(dry_run, "--policy=public-out", "--add-egress-zone=public")
        _offlinecmd(dry_run, "--policy=public-out",  "--add-protocol=icmp")
        _offlinecmd(dry_run, "--policy=public-out",  "--add-protocol=ipv6-icmp")
        _offlinecmd(dry_run, "--policy=public-out",
                    "--add-service=dhcp",
                    "--add-service=dhcpv6",
                    "--add-service=http",
                    "--add-service=https",
                    "--add-service=wireguard",
                    "--add-service=dns",
                    "--add-service=ntp",
                    )
        _offlinecmd(dry_run, "--policy=public-out", "--set-target=REJECT")

        _offlinecmd(dry_run, "--policy=work-in",
                    "--add-service=ni-labview-realtime",
                    "--add-service=ni-labview-viserver",
                    "--add-service=ni-logos-xt",
                    "--add-service=ni-mxs",
                    "--add-service=ni-rpc-server",
                    "--add-service=ni-service-locator",
                    )
        _offlinecmd(dry_run, "--policy=work-in",
                    # Temporary port add; see x-niroco-static-port.ini
                    "--add-port=55184/tcp",
                    )
        _offlinecmd(dry_run, "--policy=work-out",
                    "--add-service=amqp",
                    "--add-service=salt-master",
                    )

        _cmd(dry_run, "--reload")

    def verify(self, args: argparse.Namespace) -> bool:
        print("Verifying firewall configuration...")
        valid: bool = True
        dry_run: bool = args.dry_run

        try:
            pid: int = int(subprocess.getoutput("pidof -x /usr/sbin/firewalld"))
        except ValueError:
            logger.error(f"MISSING: running firewalld")
            valid = False

        try:
            _cmd(dry_run, "--check-config")
        except FileNotFoundError:
            logger.error(f"MISSING: firewall-cmd")
            valid = False

        valid = all([
            _check_target(dry_run, "work-in", "CONTINUE"),
            _check_target(dry_run, "work-out"),
            _check_target(dry_run, "public-in", "CONTINUE"),
            _check_target(dry_run, "public-out"),
            _check_service(dry_run, "--policy=work-in", "ni-labview-realtime"),
            _check_service(dry_run, "--policy=public-in", "ni-labview-realtime", "no"),
            _check_service(dry_run, "--zone=public", "ni-labview-realtime", "no"),
            _check_service_info("ni-labview-realtime", "--get-ports", "3079/tcp"),
            ])

        return valid
