"""Interpolated Cypher labels must be validated independently of Python optimization flags."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from app import repository


@pytest.mark.parametrize("label", ["Unknown", "Person) DETACH DELETE n //", "", None])
def test_invalid_node_labels_never_reach_the_database(label):
    transaction = Mock()
    with pytest.raises(ValueError, match="Unknown organisation node type"):
        repository.create_node(transaction, label, {})
    transaction.run.assert_not_called()


def test_valid_node_properties_remain_parameterized():
    transaction = Mock()
    props = {"name": "Synthetic user"}
    repository.create_node(transaction, "Person", props)
    transaction.run.assert_called_once_with("CREATE (n:OrgNode:Person) SET n = $props",
                                            props=props)


def test_node_label_validation_survives_python_optimization():
    program = (
        "from app.repository import create_node\n"
        "import sys\n"
        "try:\n"
        "    create_node(None, 'Person) DETACH DELETE n //', {})\n"
        "except ValueError:\n"
        "    sys.exit(0)\n"
        "sys.exit('invalid label was accepted')\n"
    )
    result = subprocess.run([sys.executable, "-O", "-c", program],
                            cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
