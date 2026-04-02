"""Network utilities for IP/CIDR validation and allowlist checks."""

import ipaddress
from typing import List, Union


def parse_allowed_networks(
    hosts_str: str,
) -> List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]:
    """Parse comma-separated list of IPs/CIDRs into network objects.
    
    Silently skips invalid entries (logs warnings expected to happen upstream).
    
    Args:
        hosts_str: Comma-separated string like "127.0.0.1,192.168.0.0/16,10.0.0.0/8"
        
    Returns:
        List of IPv4Network or IPv6Network objects
        
    Example:
        >>> networks = parse_allowed_networks("127.0.0.1,192.168.0.0/16")
        >>> len(networks)
        2
        >>> networks[1]
        IPv4Network('192.168.0.0/16')
    """
    networks: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]] = []
    
    for entry in hosts_str.split(","):
        entry = entry.strip()
        if entry:
            try:
                networks.append(ipaddress.ip_network(entry, strict=False))
            except ValueError:
                # Silently skip invalid entries; caller should log if needed
                pass
    
    return networks


def is_allowed_ip(
    client_ip: str,
    allowed_networks: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]],
) -> bool:
    """Check if a client IP falls within any of the allowed networks.
    
    Args:
        client_ip: IP address as string (e.g., "192.168.1.100")
        allowed_networks: List of IPv4Network/IPv6Network objects
        
    Returns:
        True if client_ip is within any allowed network, False otherwise
        
    Example:
        >>> networks = parse_allowed_networks("127.0.0.1,192.168.0.0/16")
        >>> is_allowed_ip("127.0.0.1", networks)
        True
        >>> is_allowed_ip("192.168.5.10", networks)
        True
        >>> is_allowed_ip("8.8.8.8", networks)
        False
    """
    try:
        addr = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    
    return any(addr in net for net in allowed_networks)
