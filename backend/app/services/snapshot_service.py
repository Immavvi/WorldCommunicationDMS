from app.models.master_data import Loa, Project, RailwayDivision, RailwayZone


def gst_snapshot_values(record) -> dict | None:
    if record is None:
        return None
    return {
        "gstin": record.gstin,
        "registered_name": record.registered_name,
        "state": record.state,
        "state_code": record.state_code,
    }


def contract_snapshot_values(
    project: Project | None,
    loa: Loa | None,
    zone: RailwayZone | None,
    division: RailwayDivision | None,
) -> dict:
    """Return explicit, searchable contract presentation values captured by a transaction."""
    return {
        "project_name_snapshot": project.name if project else None,
        "project_work_reference_snapshot": project.work_reference if project else None,
        "loa_number_snapshot": loa.loa_number if loa else None,
        "loa_date_snapshot": loa.loa_date if loa else None,
        "railway_zone_snapshot": f"{zone.code} - {zone.name}" if zone else None,
        "railway_division_snapshot": (f"{division.code} - {division.name}" if division else None),
    }
