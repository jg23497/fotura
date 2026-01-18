import pytest

from fotura.importing.synchronized_counter import SynchronizedCounter

# Fixtures


@pytest.fixture
def counter():
    return SynchronizedCounter()


@pytest.fixture
def populated_counter():
    return SynchronizedCounter({"errors": 0, "moved": 1, "skipped": 2})


# Initialization


def test_initializes_with_empty_dict(counter):
    snapshot = counter.get_snapshot()
    assert snapshot == {}


def test_initializes_with_initial_values(populated_counter):
    snapshot = populated_counter.get_snapshot()

    assert snapshot == {"errors": 0, "moved": 1, "skipped": 2}


def test_initializes_with_empty_dictionary():
    counter = SynchronizedCounter({})

    snapshot = counter.get_snapshot()

    assert snapshot == {}


# increment


def test_increment_adds_new_key_with_value_of_one_for_non_existent_key(counter):
    counter.increment("foo")

    snapshot = counter.get_snapshot()

    assert snapshot == {"foo": 1}


def test_increment_increments_an_existing_key_value(populated_counter):
    populated_counter.increment("errors")

    snapshot = populated_counter.get_snapshot()

    assert snapshot == {"errors": 1, "moved": 1, "skipped": 2}


def test_increment_multiple_times(counter):
    counter.increment("a")
    counter.increment("a")
    counter.increment("b")

    snapshot = counter.get_snapshot()

    assert snapshot == {"a": 2, "b": 1}


# get_snapshot


def test_get_snapshot_returns_copy_of_backing_dictionary(populated_counter):
    first_snapshot = populated_counter.get_snapshot()
    populated_counter.increment("errors")
    second_snapshot = populated_counter.get_snapshot()

    assert first_snapshot == {"errors": 0, "moved": 1, "skipped": 2}
    assert second_snapshot == {"errors": 1, "moved": 1, "skipped": 2}


def test_get_snapshot_return_value_changes_do_not_affect_counter_instance(
    populated_counter,
):
    first_snapshot = populated_counter.get_snapshot()
    first_snapshot["new_key"] = 1
    second_snapshot = populated_counter.get_snapshot()

    assert "new_key" not in second_snapshot
