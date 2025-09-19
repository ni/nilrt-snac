import argparse
from abc import ABC, abstractmethod


class _BaseConfig(ABC):

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def configure(self, args: argparse.Namespace) -> None:
        raise NotImplementedError

    @abstractmethod
    def verify(self, args: argparse.Namespace) -> bool:
        raise NotImplementedError
