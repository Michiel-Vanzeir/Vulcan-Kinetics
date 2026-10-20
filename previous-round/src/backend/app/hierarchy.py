"""Hierarchy rules. Levels strictly increase going up, so cycles are impossible by construction."""

NODE_TYPES = ("Department", "Project", "Team", "Subteam", "Person")

# child type -> allowed parent types
ALLOWED_PARENTS = {
    "Department": set(),
    "Project": {"Department"},
    "Team": {"Project"},
    "Subteam": {"Team"},
    "Person": {"Subteam", "Team"},
}
