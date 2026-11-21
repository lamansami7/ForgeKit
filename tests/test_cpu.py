"""CPU tests."""

from forgekit.services.system_service import get_cpu_info


def test_cpu_info_fields():
    info = get_cpu_info()
    assert info.model
    assert info.architecture
    assert info.usage_percent >= 0


def test_cpu_per_core():
    info = get_cpu_info()
    assert isinstance(info.per_core_percent, list)
