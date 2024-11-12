from typing import List

from nilrt_snac._configs._base_config import _BaseConfig
from nilrt_snac._configs._console_config import _ConsoleConfig
from nilrt_snac._configs._cryptsetup_config import _CryptSetupConfig
from nilrt_snac._configs._faillock_config import _FaillockConfig
from nilrt_snac._configs._firewall_config import _FirewallConfig
from nilrt_snac._configs._niauth_config import _NIAuthConfig
from nilrt_snac._configs._ntp_config import _NTPConfig
from nilrt_snac._configs._opkg_config import _OPKGConfig
from nilrt_snac._configs._pwquality_config import _PWQualityConfig
from nilrt_snac._configs._ssh_config import _SshConfig
from nilrt_snac._configs._sudo_config import _SudoConfig
from nilrt_snac._configs._sysapi_config import _SysAPIConfig
from nilrt_snac._configs._tmux_config import _TmuxConfig
from nilrt_snac._configs._wifi_config import _WIFIConfig
from nilrt_snac._configs._wireguard_config import _WireguardConfig
from nilrt_snac._configs._x11_config import _X11Config

# USBGuard is not supported for 1.0, but may be added in the future
# from nilrt_snac._configs._usbguard_config import _USBGuardConfig

CONFIGS: List[_BaseConfig] = [
    _NTPConfig(),
    _OPKGConfig(),
    _WireguardConfig(),
    _CryptSetupConfig(),
    _NIAuthConfig(),
    _WIFIConfig(),
    _FaillockConfig(),
    _X11Config(),
    _ConsoleConfig(),
    _SysAPIConfig(),
    _TmuxConfig(),
    _PWQualityConfig(),
    _SshConfig(),
    _SudoConfig(),
    _FirewallConfig(),
]
