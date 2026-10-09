import pytest
import torch

from app.services.reranker_service import RerankerService


def test_auto_device_selection():
    expected = "cuda" if torch.cuda.is_available() else "cpu"

    assert RerankerService._resolve_device("auto") == expected


def test_cpu_device_selection():
    assert RerankerService._resolve_device("cpu") == "cpu"


def test_invalid_device_rejected():
    with pytest.raises(ValueError):
        RerankerService._resolve_device("invalid")


def test_cuda_requires_cuda():
    if torch.cuda.is_available():
        assert RerankerService._resolve_device("cuda") == "cuda"
    else:
        with pytest.raises(RuntimeError):
            RerankerService._resolve_device("cuda")