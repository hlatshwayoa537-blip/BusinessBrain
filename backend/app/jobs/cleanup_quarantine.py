import json
import logging

from app.db import SessionLocal
from app.services.quarantine_cleanup import cleanup_expired_quarantine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    db = SessionLocal()
    try:
        result = cleanup_expired_quarantine(db)
        logger.info("VEXION quarantine cleanup result: %s", json.dumps(result, sort_keys=True))
        return 1 if result["delete_failures"] else 0
    except Exception:
        logger.exception("VEXION quarantine cleanup failed.")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
