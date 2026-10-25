from app.database import connection, queue_firebase_sync, utc_now


def compute_summary(conn) -> dict:
    row = conn.execute(
        """SELECT
           SUM(CASE WHEN status != 'RESOLVED' THEN 1 ELSE 0 END) AS active_alerts,
           SUM(CASE WHEN status != 'RESOLVED' AND severity = 'S3' THEN 1 ELSE 0 END) AS critical_s3,
           SUM(CASE WHEN status != 'RESOLVED' AND severity = 'S2' THEN 1 ELSE 0 END) AS moderate_s2,
           SUM(CASE WHEN status != 'RESOLVED' AND severity = 'S1' THEN 1 ELSE 0 END) AS minor_s1
           FROM alert JOIN defect USING(defect_id)"""
    ).fetchone()
    pending = conn.execute(
        "SELECT COUNT(*) FROM maintenance_task WHERE status != 'COMPLETED'"
    ).fetchone()[0]
    devices = conn.execute(
        "SELECT COUNT(*) AS total, SUM(CASE WHEN status='ONLINE' THEN 1 ELSE 0 END) AS online FROM device"
    ).fetchone()
    return {
        "active_alerts": row["active_alerts"] or 0,
        "critical_s3": row["critical_s3"] or 0,
        "moderate_s2": row["moderate_s2"] or 0,
        "minor_s1": row["minor_s1"] or 0,
        "pending_repairs": pending,
        "total_devices": devices["total"] or 0,
        "online_devices": devices["online"] or 0,
        "updated_at": utc_now(),
    }


def sync_summary(conn) -> None:
    summary = compute_summary(conn)
    queue_firebase_sync(conn, "/dashboard_summary", summary)


def get_summary() -> dict:
    with connection() as conn:
        return compute_summary(conn)

