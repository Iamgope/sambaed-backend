from enum import Enum

class DebateStatus(Enum):
    MATCHED = 'MATCHED'
    ONGOING = 'ONGOING'
    JUDGING = 'JUDGING'
    COMPLETED = 'COMPLETED'
    DISPUTED = 'DISPUTED'

    @property
    def label(self):
        return [(item.value, item.name) for item in self]


class RoundType(Enum):
    OPENING = 'OPENING'
    REBUTTAL = 'REBUTTAL'
    CLOSING = 'CLOSING'

    @property
    def label(self):
        return [(item.value, item.name) for item in self]


class MatchQueueStatus(Enum):
    PENDING = 'PENDING'
    MATCHED = 'MATCHED'
    CANCELLED = 'CANCELLED'

    @property
    def label(self):
        return [(item.value, item.name) for item in self]
