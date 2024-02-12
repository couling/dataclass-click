import pytest
import uuid
from datetime import datetime
from pathlib import Path

_TYPE_INFERENCES = {
    int: 10,
    str: "hello",
    float: 12.4,
    bool: True,
    uuid.UUID: uuid.uuid4(),
    datetime: datetime.now().replace(microsecond=0),
    Path: Path(".."),
}


@pytest.fixture(params=_TYPE_INFERENCES, ids=lambda claz: claz.__name__)
def inferrable_type(request):
    return request.param


@pytest.fixture()
def example_value_for_inferrable_type(inferrable_type):
    return _TYPE_INFERENCES[inferrable_type]
