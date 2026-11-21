"""Memory tests."""

from forgekit.services.system_service import get_memory_info


def test_memory_fields():
    m = get_memory_info()
    assert m.total > 0
    assert m.swap_total >= 0


def test_memory_percent_range():
    m = get_memory_info()
    assert 0 <= m.percent <= 100
