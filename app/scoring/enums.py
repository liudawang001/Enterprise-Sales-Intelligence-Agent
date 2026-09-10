from enum import StrEnum


class MissingFieldPolicy(StrEnum):
    ZERO = "ZERO"
    NEUTRAL = "NEUTRAL"
    REWEIGHT = "REWEIGHT"


class LeadRankStatus(StrEnum):
    SCORED = "SCORED"
    PARTIAL_SCORE = "PARTIAL_SCORE"
    NOT_SCORABLE = "NOT_SCORABLE"
