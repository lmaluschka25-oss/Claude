"""Tactical analysis built strictly from on-screen observations.

Every function here consumes only ``Detection`` records — themselves derived
from visible pixels — and never any privileged game state. The outputs
(last-known positions, rotation likelihoods, site pressure) are coaching
inferences a human reviewer could draw from the same footage.
"""
