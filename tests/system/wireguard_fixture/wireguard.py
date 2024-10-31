"""This module abstracts administration of wireguard configurations across Windows and NILRT, and transparently handles remote administration through SSH.
"""
from collections import namedtuple
from datetime import datetime, timedelta
from ipaddress import IPv4Address, IPv4Network
from pathlib import PurePath, PurePosixPath, PureWindowsPath
from socket import gethostname
from tempfile import gettempdir
from time import sleep
import os
import platform
import subprocess as sp

import fabric

from . import logger


class WireguardQuickConfig():

    Peer = namedtuple("Peer", ["public_key", "allowed_ips"])

    addresses: list[IPv4Address] = []
    peers = list[Peer]
    private_key: str
    listen_port: int = None

    def __init__(
        self,
        addresses: list[IPv4Address] = [],
        listen_port: int = None,
        private_key: str = None,
    ):
        self.addresses = addresses
        self.peers = []
        self.private_key = private_key
        self.listen_port = listen_port

    def add_peer(self, public_key: str, *allowed_ips):
        self.peers.append(WireguardQuickConfig.Peer(public_key, allowed_ips))

    def __str__(self):
        lines = ["[Interface]"]
        for address in self.addresses:
            lines.append(f"Address = {str(address)}")
        lines.append(f"PrivateKey = {self.private_key}")
        if self.listen_port:
            lines.append(f"ListenPort = {self.listen_port}")
        # peers
        for peer in self.peers:
            lines.append("\n[Peer]")
            lines.append(f"PublicKey = {peer.public_key}")
            lines.append(f"AllowedIPs = {", ".join(str(peer.allowed_ips))}")
        return "\n".join(lines)



class WireguardClient():

    config_directory: PurePath
    connection: fabric.Connection = None
    platform: str
    
    def __init__(
        self,
        connection: fabric.Connection = None,
    ):
        self.connection = connection
        if self.connection:
            self.connection.open()

        self.platform = self.guess_platform()
        logger.debug(f"Guessed platform: {self.platform}")

    def add_address(
        self,
        tunnel_name: str,
        address: IPv4Address,
    ):
        if self.platform == "linux":
            self._run(f"ip address del {str(address)} dev {tunnel_name}")
            proc = self._run(f"ip address add {str(address)} dev {tunnel_name}")
            proc.check_returncode()
        else:
            raise NotImplementedError()

    def add_peer(
        self,
        tunnel_name: str,
        peer_pubkey: str,
        allowed_ips: list[IPv4Network] = [],
        endpoint: str = None,
        persistent_keepalive_s: int = None,
        preshared_key: os.PathLike = None,
        ):
            set_args = [peer_pubkey]
            if len(allowed_ips) > 0:
                set_args += ["allowed-ips", ",".join([str(ip) for ip in allowed_ips])]
            if persistent_keepalive_s:
                set_args += ["persistent-keepalive", str(persistent_keepalive_s)]
            if endpoint:
                set_args += ["endpoint", endpoint]
            if preshared_key:
                set_args += ["preshared-key", str(preshared_key)]
            proc = self._run(f"wg set {tunnel_name} peer " + " ".join(set_args))
            proc.check_returncode()

    def create_tunnel(
        self,
        tunnel_name: str,
        ip_address: str,
        private_key: str = None,
        timeout_s: int = 5,
        listen_port: int = None,
    ):
        """Add a new wireguard tunnel to the machine's interfaces.
        
        This method asynchronously waits for the interface to come online before returning.
        
        Raises: `TimeoutError` when the interface fails to come oneline before `timeout_s` is reached.
        """
        if private_key is None:
            private_key = self.genkey()

        wg_quick_conf = WireguardQuickConfig(
            addresses = [ip_address],
            private_key = private_key,
            listen_port = listen_port,
        )

        if self.platform == "windows":
            conf_file = PureWindowsPath(gettempdir()) / (tunnel_name + ".conf")
            with open(conf_file, 'w+t') as fp_conf:
                logger.debug(f"Writing conf file: {conf_file}")
                fp_conf.write(str(wg_quick_conf))
            proc = self._run(
                f"wireguard.exe /installtunnelservice \"{conf_file}\"",
            )
            proc.check_returncode()
        elif self.platform == "linux":
            conf_file = PurePosixPath("/tmp") / (tunnel_name + ".conf")
            self._run(f"cat >\"{conf_file}\" <<EOF\n{str(wg_quick_conf)}\nEOF", check=True)
            proc = self._run(f"wg-quick up \"{conf_file}\"")
            proc.check_returncode()
        else:
            raise NotImplementedError()
        
        self.wait_on_interface(tunnel_name, timeout_s=timeout_s)

        # add firewall rule for interface
        if self.platform == "windows":
            logger.info("Reseting windows firewall rule 'nilrt-snac-test-wg'")
            proc = self._run("netsh advfirewall firewall delete rule name=nilrt-snac-test-wg")
            proc = self._run(f"netsh advfirewall firewall add rule name=nilrt-snac-test-wg dir=in action=allow protocol=ANY localip={ip_address} profile=any")
            proc.check_returncode()


    def genkey(self) -> str:
        """Have wireguard generate a new private key.
        
        Returns: The generated private key as a `str`.
        """
        proc = self._run("wg genkey")
        return str(proc.stdout).splitlines()[0].strip()
    
    def get_client_hostname(self):
        """Return the client's ipv4 address."""
        if self.connection is None:  # local client
            return gethostname()
        
        # remote client
        return self.connection.transport.getpeername()[0]

    def get_listen_port(self, tunnel_name: str) -> int:
        """Get the tunnel interface's listen-port attribute."""
        return int(self.show(tunnel_name, "listen-port"))

    def get_peers(self, tunnel_name: str) -> list[str]:
        """Return a list of peers, identified by public key."""
        proc = self._run(f"wg show {tunnel_name} peers")
        proc.check_returncode()

        peers = []
        for line in str(proc.stdout).splitlines():
            line = line.strip()
            if len(line) == 0:
                continue
            peers.append(line)
        return peers

    def get_public_key(self, tunnel_name: str) -> str:
        """Get the tunnel interface's public-key attribute."""
        return self.show(tunnel_name, "public-key").splitlines()[0].strip()

    def guess_platform(self) -> str:
        """Heuristically determine the platform type that is client is running on.
        
        Returns: One of: "windows" or "linux".
        """
        # If not running remotely, just have python tell us.
        if self.connection is None:
            return platform.system().lower()
        # Otherwise, interrogate the filesystem.
        proc = self._run("cat /etc/os-release")
        if proc.returncode > 0:
            # probably windows
            return "windows"
        else:
            return "linux"
        
    def is_online(self, tunnel_name: str) -> bool:
        """Check if a wireguard tunnel interface is online (present).
        
        Returns: True, if the tunnel interface is present; False otherwise.
        """
        proc = self._run(f"wg show {tunnel_name}")
        if proc.returncode == 0:
            return True
        else:
            return False

    def remove_peer(self, tunnel_name: str, public_key: str):
        """Remove a peer from the tunnel by pubkey."""
        proc = self._run(f"wg set {tunnel_name} peer {public_key} remove")
        if public_key in self.get_peers(tunnel_name):
            raise RuntimeError(f"Failed to remove peer {public_key} from {tunnel_name}.")
        
    def remove_all_peers(self, tunnel_name: str):
        """Remove all peer definitions for a tunnel."""
        for peer in self.get_peers(tunnel_name):
            self.remove_peer(tunnel_name, peer)
        
    def remove_tunnel(self, tunnel_name: str):
        """Remove a tunnel interface from the system."""
        if not self.is_online(tunnel_name):
            logger.info(f"Tunnel {tunnel_name} not online. Nothing to do.")
            return
        
        logger.info(f"Removing tunnel {tunnel_name}")
        if self.platform == "windows":
            self._run(f"wireguard.exe /uninstalltunnelservice {tunnel_name}")
        elif self.platform == "linux":
            self._run(f"wg-quick down {tunnel_name}")
        else:
            raise NotImplementedError("Unsupported platform.")
        self.wait_on_interface(tunnel_name, online=False)

        # add firewall rule for interface
        if self.platform == "windows":
            logger.info("Removing windows firewall rule 'nilrt-snac-test-wg'")
            proc = self._run("netsh advfirewall firewall delete rule name=nilrt-snac-test-wg")
            proc.check_returncode()

    def _run(
        self,
        argv: str | list[str],
        *args,
        **kwargs,
    ) -> sp.CompletedProcess:
        """Run a shell command either on the local machine, or remotely via SSH.

        Args:
            argv: Either a shell command string to execute, or a list of shell command arguments.
        
        Returns: A subprocess.CompletedProcess object describing the completed process.
        """
        if isinstance(argv, list):
            argv = " ".join(['"' + a + '"' for a in argv])
        # common defaults
        kwargs.setdefault("encoding", "utf-8")
        kwargs.setdefault("timeout", 30)

        if self.connection is None:  # local processes
            kwargs.setdefault("capture_output", "True")
            proc = sp.run(argv, shell=True, *args, **kwargs)
            logger.debug(str(proc))
            return proc

        if self.connection:  # remote processes
            invoke_kwargs = {
                "encoding": kwargs["encoding"],
                "timeout": kwargs["timeout"],
                "hide": True,
                "warn": True,
            }
            proc = self.connection.run(argv, **invoke_kwargs)
            logger.debug(str(proc))
            if kwargs.get("check", False) and proc.exited > 0:
                raise sp.CalledProcessError(proc.exited, proc.command, proc.stdout, proc.stderr)

            return sp.CompletedProcess(proc.command, proc.exited, proc.stdout, proc.stderr)
        
    def pubkey(self, private_key: str) -> str:
        """Calculate the public expression of a wireguard private key string.
        
        Args:
            private_key: str. A string representation of the wireguard private key.
            
        Returns: The public key expression as a str.
        """
        proc = self._run(f"echo {private_key} | wg pubkey")
        proc.check_returncode()
        return str(proc.stdout).splitlines()[0].strip()
    
    def show(self, tunnel_name: str, attribute: str) -> str:
        """Return a property of the tunnel interface, as through 'wg show'."""
        proc = self._run(f"wg show {tunnel_name} {attribute}")
        proc.check_returncode()
        return str(proc.stdout)
    
    def wait_on_interface(
            self,
            tunnel_name: str,
            online: bool = True,
            timeout_s: int = 5,
        ) -> bool:
        """Asynchronously wait for a wireguard tunnel interface to come online or offline.

        This method uses the 'wg show' command on the backend. If the interface is present, it is "online". If it is missing, it is "offline".
        
        Args:
            tunnel_name: str. The tunnel interface name to wait on.
            online: bool. If True, wait until the interface comes online. If False, wait until it goes offline.
            timeout_s: int. The number of seconds to wait, before timing out.
        
        Raises: TimeoutError when the interface does not reach the desired state before timeout_s.
        """
        if online:
            print(f"Waiting for tunnel {tunnel_name} to come online.")
        else:
            print(f"Waiting for tunnel {tunnel_name} to go offline.")

        def is_correct():
            if online:
                return self.is_online(tunnel_name)
            else:
                return not self.is_online(tunnel_name)

        found_correct = is_correct()
        check_start = datetime.now()
        check_latest = check_start
        while not found_correct and (check_latest - check_start) < timedelta(seconds=timeout_s):
            found_correct = is_correct()
            check_latest = datetime.now()
            sleep(1)
        
        if found_correct == False:
            raise TimeoutError("Timeout exceeded waiting for interface.")
