"""Opt-in local P101 prediction CLI. Never called by setup/bootstrap or on import."""

import argparse
from datetime import datetime, timezone
import json
from uuid import uuid4

from app.p101_local_demo.contracts import CUTOFFS, CalculationContext
from app.p101_local_demo.prediction_mapping import PredictionError
from app.p101_local_demo.prediction_persistence import run_predictions
from app.p101_local_demo.setup_config import ROOT, load_settings
from app.p101_persistence.contracts import CALCULATION_REVISION


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--instance', required=True)
    args = parser.parse_args(argv)
    try:
        settings = load_settings(args.config)
        now = datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')
        context = CalculationContext(str(uuid4()), now, CALCULATION_REVISION, CUTOFFS)
        reference = json.loads((ROOT / 'tests/p101_anomaly/fixtures/p101-temperature-v1.json').read_text(encoding='utf-8'))
        result = run_predictions(settings, reference, context, execute=args.execute, instance=args.instance)
        print(json.dumps(dict(disposition=result.disposition,
            predictions=[dict(id=r['id'], measurement_id=r['measurement_id'], score=r['score'],
                              is_alert=r['is_alert'], created_at=r['created_at']) for r in result.records])))
        return 0
    except PredictionError as exc:
        print(exc.code)
    except Exception:
        print('EXPLICIT_LOCAL_PREDICTION_RUN_REJECTED')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
