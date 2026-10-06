"""
Central import point so the rest of the app writes `from models import User, Resume`
regardless of which file a model actually lives in.

When you add a new model (e.g. Job, Application), create its own file in this
folder and add one import line here. This file is the only place a new
teammate's model-addition touches, and it's a one-line append — low risk of
a merge conflict even if two people add a model in the same sprint.
"""

from .user import User
from .resume import Resume

__all__ = ["User", "Resume"]
