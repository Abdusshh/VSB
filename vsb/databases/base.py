from abc import ABC, abstractmethod
from enum import Enum, auto

from vsb.vsb_types import Record, SearchRequest


class Namespace(ABC):
    """Abstract class with represents a set of one or more vector records
    grouped together by some logical association (e.g. a single tenant / user).
    A Database consists of one or more Namespaces, and each record exists
    in exactly one namespace.
    Specific implementations should subclass this and implement all abstract
    methods.
    Instance of this (derived) class are typically created via the corresponding
    (concrete) DB get_namespace() method.
    """

    @abstractmethod
    def upsert(self, key, vector, metadata):
        raise NotImplementedError

    @abstractmethod
    def upsert_batch(self, batch: list[Record]):
        raise NotImplementedError

    @abstractmethod
    def search(self, request: SearchRequest) -> list[str]:
        raise NotImplementedError


class DB(ABC):
    """Abstract class which represents a vector database made up of one or more
    Namespaces, where each Namespace contains one or more records.

    Specific Vector DB implementations should subclass this and implement all abstract methods.
    """

    @abstractmethod
    def get_namespace(self, namespace_name: str) -> Namespace:
        raise NotImplementedError
