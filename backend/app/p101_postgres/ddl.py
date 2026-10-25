"""Static function bodies shared by migration files and catalog fingerprint checks.

Nothing in this module executes SQL. PostgreSQL validation belongs to B-2.
"""

CANONICAL_BODY = r"""
DECLARE r record; result jsonb; item jsonb;
BEGIN
  CASE jsonb_typeof(v)
    WHEN 'object' THEN
      result := '{}'::jsonb;
      FOR r IN SELECT * FROM jsonb_each(v) LOOP
        result := result || jsonb_build_object(normalize(r.key, NFC), p101_pilot.canonical_value(r.value));
      END LOOP;
      RETURN result;
    WHEN 'array' THEN
      result := '[]'::jsonb;
      FOR item IN SELECT value FROM jsonb_array_elements(v) LOOP
        result := result || jsonb_build_array(p101_pilot.canonical_value(item));
      END LOOP;
      RETURN result;
    WHEN 'number' THEN RETURN to_jsonb(trim_scale((v #>> '{}')::numeric)::text);
    WHEN 'string' THEN RETURN to_jsonb(normalize(v #>> '{}', NFC));
    ELSE RETURN v;
  END CASE;
END
"""

SHAPE_BODY = r"""
DECLARE writer name;
BEGIN
  SELECT writer_role INTO STRICT writer FROM p101_pilot.environment_guard WHERE singleton;
  IF session_user = writer THEN
    IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'P101 history is immutable'; END IF;
    IF NEW.prediction_type IS DISTINCT FROM 'anomaly'
      OR NEW.model_name IS DISTINCT FROM 'statistical_deviation'
      OR NEW.model_version IS DISTINCT FROM 'p101-stat-v1'
      OR NEW.score IS NULL OR NEW.score NOT IN (0,1)
      OR NEW.is_alert IS DISTINCT FROM (NEW.score = 1)
      OR NEW.level IS NOT NULL OR NEW.horizon_hours IS NOT NULL
      OR NEW.sensor_id IS NULL OR NEW.measurement_id IS NULL
      OR NEW.details IS NULL OR octet_length(NEW.details::text) > 6000
      OR (NEW.details::jsonb -> 'synthetic') IS DISTINCT FROM 'true'::jsonb
      OR NEW.details::jsonb ->> 'schema_version' IS DISTINCT FROM 'p101-anomaly-details-v1'
      OR NEW.details::jsonb #>> '{producer,code_revision}' IS DISTINCT FROM 'b6b4d521b9c9456c160433e9343efd48d3c0168d'
      OR NEW.details::jsonb #>> '{producer,revision_status}' IS NOT NULL
    THEN RAISE EXCEPTION 'P101 row shape rejected'; END IF;
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END
"""

LINK_BODY = r"""
DECLARE pid integer; p record; r record; d jsonb; refs jsonb; content jsonb; k jsonb;
BEGIN
  IF TG_TABLE_SCHEMA = 'p101_pilot' THEN
    IF TG_OP = 'DELETE' THEN pid := OLD.prediction_id; ELSE pid := NEW.prediction_id; END IF;
  ELSE
    IF TG_OP = 'DELETE' THEN pid := OLD.id; ELSE pid := NEW.id; END IF;
    IF TG_OP = 'INSERT' AND NEW.model_name IS DISTINCT FROM 'statistical_deviation' THEN RETURN NULL; END IF;
    IF TG_OP = 'UPDATE' AND NEW.model_name IS DISTINCT FROM 'statistical_deviation'
      AND OLD.model_name IS DISTINCT FROM 'statistical_deviation' THEN RETURN NULL; END IF;
    IF TG_OP = 'DELETE' AND OLD.model_name IS DISTINCT FROM 'statistical_deviation' THEN RETURN NULL; END IF;
  END IF;
  SELECT * INTO p FROM public.prediction_records WHERE id = pid;
  IF NOT FOUND THEN
    IF EXISTS (SELECT 1 FROM p101_pilot.idempotency_records WHERE prediction_id = pid)
      THEN RAISE EXCEPTION 'Orphan P101 registry'; END IF;
    RETURN NULL;
  END IF;
  SELECT * INTO STRICT r FROM p101_pilot.idempotency_records WHERE prediction_id = pid;
  d := p.details::jsonb;
  k := r.key_canonical::jsonb;
  IF p.prediction_type IS DISTINCT FROM 'anomaly' OR p.model_name IS DISTINCT FROM 'statistical_deviation'
    OR p.model_version IS DISTINCT FROM 'p101-stat-v1' OR p.score IS NULL OR p.score NOT IN (0,1)
    OR p.is_alert IS DISTINCT FROM (p.score=1) OR p.level IS NOT NULL OR p.horizon_hours IS NOT NULL
    OR r.first_created_at IS DISTINCT FROM p.created_at
    OR r.idempotency_key IS DISTINCT FROM d ->> 'idempotency_key'
    OR encode(sha256(convert_to(r.key_canonical,'UTF8')),'hex') IS DISTINCT FROM r.idempotency_key
    OR encode(sha256(convert_to(r.content_canonical,'UTF8')),'hex') IS DISTINCT FROM r.content_sha256
    OR (d #>> '{asset,equipment_id}')::integer IS DISTINCT FROM p.equipment_id
    OR (d #>> '{asset,sensor_id}')::integer IS DISTINCT FROM p.sensor_id
    OR (d #>> '{target,measurement_id}')::integer IS DISTINCT FROM p.measurement_id
    OR (d #>> '{target,timestamp}')::timestamptz IS DISTINCT FROM p.predicted_at
    OR k ->> 'schema_version' IS DISTINCT FROM 'p101-idempotency-v1'
    OR k ->> 'target_id' IS DISTINCT FROM d #>> '{target,fixture_id}'
    OR k ->> 'dataset_sha256' IS DISTINCT FROM d #>> '{dataset,sha256}'
    OR k ->> 'reference_sha256' IS DISTINCT FROM d #>> '{reference,sha256}'
    OR k ->> 'code_revision' IS DISTINCT FROM d #>> '{producer,code_revision}'
    OR k ->> 'cutoff_utc' IS DISTINCT FROM d ->> 'cutoff_utc'
    OR k ->> 'predicted_at' IS DISTINCT FROM d #>> '{target,timestamp}'
    OR k ->> 'model_name' IS DISTINCT FROM p.model_name
    OR k ->> 'model_version' IS DISTINCT FROM p.model_version
    OR k ->> 'prediction_type' IS DISTINCT FROM 'anomaly'
    OR k ->> 'equipment_code' IS DISTINCT FROM 'MLDEMO-EQ-P101'
    OR k ->> 'sensor_code' IS DISTINCT FROM 'MLDEMO-SEN-P101-TEMP'
    OR k ->> 'window_count' IS DISTINCT FROM '10' OR k ->> 'ddof' IS DISTINCT FROM '1'
    OR k ->> 'cadence_seconds' IS DISTINCT FROM '86400' OR k ->> 'multiplier' IS DISTINCT FROM '3'
    OR k ->> 'comparison' IS DISTINCT FROM 'absolute_deviation>threshold'
    OR k ->> 'instance_uuid' IS DISTINCT FROM
       (SELECT instance_uuid::text FROM p101_pilot.environment_guard WHERE singleton)
    THEN RAISE EXCEPTION 'P101 registry/prediction conflict'; END IF;
  SELECT jsonb_agg(value - 'measurement_id' ORDER BY ordinality) INTO refs
    FROM jsonb_array_elements(d #> '{reference,observations}') WITH ORDINALITY;
  IF jsonb_array_length(refs) IS DISTINCT FROM 10 THEN RAISE EXCEPTION 'Ten P101 references required'; END IF;
  d := d - 'run_id' - 'prepared_at' - 'idempotency_key';
  d := jsonb_set(d, '{asset}', jsonb_build_object(
    'company_id','DEMO-COMP-001','company_code','MLDEMO-COMP-P101',
    'site_id','DEMO-SITE-001','site_code','MLDEMO-SITE-P101',
    'equipment_id','DEMO-EQ-001','equipment_code','MLDEMO-EQ-P101',
    'sensor_id','DEMO-SEN-001','sensor_code','MLDEMO-SEN-P101-TEMP'));
  d := jsonb_set(d, '{target}', (d -> 'target') - 'measurement_id');
  d := jsonb_set(d, '{reference,observations}', refs);
  content := jsonb_build_object('schema_version','p101-business-content-v1',
    'prediction',jsonb_build_object('equipment_fixture_id','DEMO-EQ-001',
      'sensor_fixture_id','DEMO-SEN-001','measurement_fixture_id',d #>> '{target,fixture_id}',
      'prediction_type',p.prediction_type,'score',p.score,'is_alert',p.is_alert,
      'level',p.level,'horizon_hours',p.horizon_hours,'model_name',p.model_name,
      'model_version',p.model_version,'predicted_at',d #>> '{target,timestamp}'), 'details',d);
  IF p101_pilot.canonical_value(content) IS DISTINCT FROM r.content_canonical::jsonb
    THEN RAISE EXCEPTION 'P101 canonical content conflict'; END IF;
  RETURN NULL;
END
"""

LOCK_BODY = r"""
DECLARE c record; s record; e record; n record; m record;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM p101_pilot.environment_guard
     WHERE singleton AND writer_role = session_user AND provisioning_closed)
    THEN RAISE EXCEPTION 'P101 source access not authorized'; END IF;
  PERFORM pg_advisory_xact_lock_shared(1010042);
  SELECT * INTO STRICT c FROM public.companies WHERE code='MLDEMO-COMP-P101' FOR SHARE;
  SELECT * INTO STRICT s FROM public.sites WHERE code='MLDEMO-SITE-P101' AND company_id=c.id FOR SHARE;
  SELECT * INTO STRICT e FROM public.equipments WHERE code='MLDEMO-EQ-P101' AND site_id=s.id FOR SHARE;
  SELECT * INTO STRICT n FROM public.sensors WHERE code='MLDEMO-SEN-P101-TEMP' AND equipment_id=e.id FOR SHARE;
  kind := 'company'; id := c.id; payload := to_jsonb(c); RETURN NEXT;
  kind := 'site'; id := s.id; payload := to_jsonb(s); RETURN NEXT;
  kind := 'equipment'; id := e.id; payload := to_jsonb(e); RETURN NEXT;
  kind := 'sensor'; id := n.id; payload := to_jsonb(n); RETURN NEXT;
  IF (SELECT count(*) FROM public.measurements q WHERE q.sensor_id=n.id) <> 12
    THEN RAISE EXCEPTION 'Exactly twelve synthetic measurements required'; END IF;
  FOR m IN SELECT q.* FROM public.measurements q WHERE q.sensor_id=n.id
             ORDER BY q.timestamp,q.id FOR SHARE LOOP
    kind := 'measurement'; id := m.id; payload := to_jsonb(m); RETURN NEXT;
  END LOOP;
END
"""

FUNCTIONS = {
    "canonical_value": ("v jsonb", "jsonb", CANONICAL_BODY, "IMMUTABLE"),
    "enforce_shape": ("", "trigger", SHAPE_BODY, "VOLATILE"),
    "enforce_link": ("", "trigger", LINK_BODY, "VOLATILE"),
    "lock_sources": ("", "TABLE(kind text,id integer,payload jsonb)", LOCK_BODY, "VOLATILE"),
}


def function_ddl(name):
    args, result, body, volatility = FUNCTIONS[name]
    return (f"CREATE FUNCTION p101_pilot.{name}({args}) RETURNS {result} "
            f"LANGUAGE plpgsql {volatility} SECURITY DEFINER SET search_path=pg_catalog "
            f"AS $p101${body}$p101$")
