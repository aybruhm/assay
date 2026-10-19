from planner.jurisdictions.base import Jurisdiction
from planner.jurisdictions.gb import GB
from planner.jurisdictions.ng import NG

# One line per country. Adding a country changes this file only.
REGISTRY: dict[str, Jurisdiction] = {
    jurisdiction.code: jurisdiction for jurisdiction in (GB, NG)
}
