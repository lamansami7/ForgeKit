"""Disk tests."""

from forgekit.services.system_service import get_disk_info


def test_disk_partitions():
    d = get_disk_info()
    assert isinstance(d.partitions, list)
    for p in d.partitions:
        assert p.mountpoint
        assert p.total >= 0
