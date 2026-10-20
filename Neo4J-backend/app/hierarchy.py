"""Hierarchy rules. Levels strictly increase going up, so cycles are impossible by construction."""

NODE_TYPES = ("Department", "Project", "Team", "Subteam", "Person", "Client")

# child type -> allowed parent types
ALLOWED_PARENTS = {
    "Department": set(),
    "Project": {"Department"},
    "Team": {"Project"},
    "Subteam": {"Team"},
    "Person": {"Subteam", "Team"},
    "Client": set(),  # outside the PART_OF tree; reached via SERVES / ABOUT only
}

# org node types that may SERVE a client (Knowledge links via ABOUT separately)
CLIENT_LINKABLE = {"Project"}
