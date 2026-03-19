"""
Tenantbox SDK — Utility helpers.

Byte size constants to make quota configuration readable.

Usage:
    from tenantbox.utils import KB, MB, GB, TB

    client.set_limit("user_123", MB(100))   # 100 megabytes
    client.set_limit("user_123", GB(2))     # 2 gigabytes
"""


def KB(n: float) -> int:
    """Convert kilobytes to bytes."""
    return int(n * 1024)


def MB(n: float) -> int:
    """Convert megabytes to bytes."""
    return int(n * 1024 * 1024)


def GB(n: float) -> int:
    """Convert gigabytes to bytes."""
    return int(n * 1024 * 1024 * 1024)


def TB(n: float) -> int:
    """Convert terabytes to bytes."""
    return int(n * 1024 * 1024 * 1024 * 1024)


def human_readable_bytes(n: int) -> str:
    """
    Convert a byte count to a human-readable string.

    Examples:
        human_readable_bytes(1024)          → "1.0 KB"
        human_readable_bytes(1536)          → "1.5 KB"
        human_readable_bytes(5_242_880)     → "5.0 MB"
        human_readable_bytes(1_073_741_824) → "1.0 GB"
    """
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"