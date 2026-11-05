--
-- PostgreSQL database dump
--

-- Dumped from database version 16.4 (Debian 16.4-1.pgdg110+2)
-- Dumped by pg_dump version 16.4 (Debian 16.4-1.pgdg110+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: audit; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA audit;


--
-- Name: quarantine; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA quarantine;


--
-- Name: spatial; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA spatial;


--
-- Name: trx; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA trx;


--
-- Name: actor_user_id(); Type: FUNCTION; Schema: audit; Owner: -
--

CREATE FUNCTION audit.actor_user_id() RETURNS uuid
    LANGUAGE plpgsql STABLE
    AS $$
BEGIN
	RETURN nullif(current_setting('app.user_id', true), '')::uuid;
EXCEPTION WHEN invalid_text_representation THEN
	RETURN NULL;
END $$;


--
-- Name: deny_modification(); Type: FUNCTION; Schema: audit; Owner: -
--

CREATE FUNCTION audit.deny_modification() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
	RAISE EXCEPTION '%.% is append-only', TG_TABLE_SCHEMA, TG_TABLE_NAME;
END $$;


--
-- Name: log_row_change(); Type: FUNCTION; Schema: audit; Owner: -
--

CREATE FUNCTION audit.log_row_change() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'pg_catalog', 'public'
    AS $_$
DECLARE
    o jsonb;
    n jsonb;
    cols text[];
    attrs text[];
    geoms text[];
    geom_changed text[];
BEGIN
    SELECT array_agg(a.attname ORDER BY a.attnum) FILTER (WHERE t.typname NOT IN ('geometry', 'geography')),
           array_agg(a.attname ORDER BY a.attnum) FILTER (WHERE t.typname IN ('geometry', 'geography'))
      INTO attrs, geoms
      FROM pg_attribute a
      JOIN pg_type t ON t.oid = a.atttypid
     WHERE a.attrelid = TG_RELID AND a.attnum > 0 AND NOT a.attisdropped;

    IF geoms IS NULL THEN
        IF TG_OP IN ('UPDATE', 'DELETE') THEN o := to_jsonb(OLD); END IF;
        IF TG_OP IN ('UPDATE', 'INSERT') THEN n := to_jsonb(NEW); END IF;
    ELSE
        IF TG_OP IN ('UPDATE', 'DELETE') THEN o := audit.row_json_columns(OLD, attrs); END IF;
        IF TG_OP IN ('UPDATE', 'INSERT') THEN n := audit.row_json_columns(NEW, attrs); END IF;
    END IF;

    IF TG_OP = 'UPDATE' THEN
        SELECT array_agg(k ORDER BY k) INTO cols
          FROM jsonb_object_keys(n) k
         WHERE n -> k IS DISTINCT FROM o -> k;
        IF geoms IS NOT NULL THEN
            EXECUTE 'SELECT array_remove(ARRAY[' ||
                    (SELECT string_agg('CASE WHEN ($1).' || quote_ident(g) || ' IS DISTINCT FROM ($2).' || quote_ident(g) || ' THEN ' || quote_literal(g) || ' END', ', ')
                       FROM unnest(geoms) AS g) || ']::text[], NULL)'
                INTO geom_changed USING OLD, NEW;
            IF coalesce(array_length(geom_changed, 1), 0) > 0 THEN
                SELECT array_agg(k ORDER BY k) INTO cols FROM unnest(coalesce(cols, '{}') || geom_changed) AS k;
            END IF;
        END IF;
    END IF;

    INSERT INTO audit.change_logs (schema_name, table_name, operation, old_data, new_data, changed_cols,
                                   actor_user_id, application)
    VALUES (TG_TABLE_SCHEMA, TG_TABLE_NAME, TG_OP, o, n, cols,
            audit.actor_user_id(), nullif(current_setting('application_name', true), ''));
    RETURN NULL;
END $_$;


--
-- Name: log_truncate(); Type: FUNCTION; Schema: audit; Owner: -
--

CREATE FUNCTION audit.log_truncate() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'pg_catalog', 'public'
    AS $$
BEGIN
	INSERT INTO audit.change_logs (schema_name, table_name, operation, actor_user_id, application)
	VALUES (TG_TABLE_SCHEMA, TG_TABLE_NAME, 'TRUNCATE', audit.actor_user_id(), nullif(current_setting('application_name', true), ''));
	RETURN NULL;
END $$;


--
-- Name: require_activity_ip(); Type: FUNCTION; Schema: audit; Owner: -
--

CREATE FUNCTION audit.require_activity_ip() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF NEW.ip_address IS NULL THEN
        RAISE EXCEPTION 'audit.user_activities.ip_address wajib diisi';
    END IF;
    RETURN NEW;
END;
$$;


--
-- Name: row_json_columns(anyelement, text[]); Type: FUNCTION; Schema: audit; Owner: -
--

CREATE FUNCTION audit.row_json_columns(r anyelement, attrs text[]) RETURNS jsonb
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $_$
DECLARE
    result jsonb := '{}'::jsonb;
    part jsonb;
    i int := 1;
BEGIN
    WHILE attrs IS NOT NULL AND i <= array_length(attrs, 1) LOOP
        EXECUTE 'SELECT jsonb_build_object(' ||
                (SELECT string_agg(quote_literal(k) || ', ($1).' || quote_ident(k), ', ') FROM unnest(attrs[i:i + 39]) AS k) || ')'
            INTO part USING r;
        result := result || part;
        i := i + 40;
    END LOOP;
    RETURN result;
END $_$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: change_logs; Type: TABLE; Schema: audit; Owner: -
--

CREATE TABLE audit.change_logs (
    id bigint NOT NULL,
    changed_at timestamp with time zone DEFAULT now() NOT NULL,
    schema_name character varying(63) NOT NULL,
    table_name character varying(63) NOT NULL,
    operation character varying(10) NOT NULL,
    old_data jsonb,
    new_data jsonb,
    changed_cols text[],
    actor_user_id uuid,
    actor_db_user text DEFAULT SESSION_USER NOT NULL,
    application text,
    txid bigint DEFAULT txid_current() NOT NULL,
    CONSTRAINT change_logs_operation_check CHECK (((operation)::text = ANY (ARRAY[('INSERT'::character varying)::text, ('UPDATE'::character varying)::text, ('DELETE'::character varying)::text, ('TRUNCATE'::character varying)::text, ('MIGRATION'::character varying)::text])))
);


--
-- Name: change_logs_id_seq; Type: SEQUENCE; Schema: audit; Owner: -
--

ALTER TABLE audit.change_logs ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME audit.change_logs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: data_store_versions; Type: TABLE; Schema: audit; Owner: -
--

CREATE TABLE audit.data_store_versions (
    domain text NOT NULL,
    version bigint DEFAULT 0 NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: legacy_id_maps; Type: TABLE; Schema: audit; Owner: -
--

CREATE TABLE audit.legacy_id_maps (
    table_name character varying(127) NOT NULL,
    legacy_id text NOT NULL,
    new_id text NOT NULL
);


--
-- Name: upload_batches; Type: TABLE; Schema: audit; Owner: -
--

CREATE TABLE audit.upload_batches (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    source_type character varying(20) NOT NULL,
    target_table character varying(127) NOT NULL,
    source_name character varying(255),
    uploaded_by uuid,
    period ref.month_period,
    record_count integer DEFAULT 0 NOT NULL,
    status character varying(20) DEFAULT 'IN_PROGRESS'::character varying NOT NULL,
    error_message text,
    metadata jsonb,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    finished_at timestamp with time zone,
    CONSTRAINT upload_batches_check CHECK ((((status)::text = 'IN_PROGRESS'::text) = (finished_at IS NULL))),
    CONSTRAINT upload_batches_record_count_check CHECK ((record_count >= 0)),
    CONSTRAINT upload_batches_status_check CHECK (((status)::text = ANY (ARRAY[('IN_PROGRESS'::character varying)::text, ('SUCCESS'::character varying)::text, ('PARTIAL_SUCCESS'::character varying)::text, ('FAILED'::character varying)::text, ('ABANDONED'::character varying)::text])))
);


--
-- Name: upload_jobs; Type: TABLE; Schema: audit; Owner: -
--

CREATE TABLE audit.upload_jobs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid,
    kind character varying(10) NOT NULL,
    layer character varying(63) NOT NULL,
    bulan smallint NOT NULL,
    tahun smallint NOT NULL,
    filename character varying(255),
    file_size integer NOT NULL,
    content bytea,
    status character varying(10) DEFAULT 'queued'::character varying NOT NULL,
    stage character varying(40),
    message text,
    progress_current integer,
    progress_total integer,
    result jsonb,
    error_message text,
    batch_id uuid,
    cancel_requested boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    started_at timestamp with time zone,
    heartbeat_at timestamp with time zone,
    finished_at timestamp with time zone,
    upload_group_id uuid,
    part_index integer,
    part_total integer,
    feature_offset integer DEFAULT 0 NOT NULL,
    CONSTRAINT upload_jobs_bulan_check CHECK (((bulan >= 1) AND (bulan <= 12))),
    CONSTRAINT upload_jobs_kind_check CHECK (((kind)::text = ANY ((ARRAY['analyze'::character varying, 'execute'::character varying])::text[]))),
    CONSTRAINT upload_jobs_status_check CHECK (((status)::text = ANY ((ARRAY['queued'::character varying, 'running'::character varying, 'succeeded'::character varying, 'failed'::character varying, 'cancelled'::character varying])::text[])))
);


--
-- Name: user_activities; Type: TABLE; Schema: audit; Owner: -
--

CREATE TABLE audit.user_activities (
    id bigint NOT NULL,
    user_id uuid,
    action character varying(100) NOT NULL,
    resource character varying(100) NOT NULL,
    record_id text,
    ip_address inet,
    status character varying(10) NOT NULL,
    detail jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT user_activities_status_check CHECK (((status)::text = ANY (ARRAY[('SUCCESS'::character varying)::text, ('FAILED'::character varying)::text])))
);


--
-- Name: user_activities_id_seq; Type: SEQUENCE; Schema: audit; Owner: -
--

ALTER TABLE audit.user_activities ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME audit.user_activities_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: rows; Type: TABLE; Schema: quarantine; Owner: -
--

CREATE TABLE quarantine.rows (
    id bigint NOT NULL,
    source_table character varying(63) NOT NULL,
    source_id text,
    reason text NOT NULL,
    action character varying(30) NOT NULL,
    data jsonb NOT NULL,
    quarantined_at timestamp with time zone DEFAULT now() NOT NULL,
    upload_batch_id uuid,
    reason_code character varying(50),
    CONSTRAINT rows_action_check CHECK (((action)::text = 'NOT_LOADED'::text))
);


--
-- Name: rows_id_seq; Type: SEQUENCE; Schema: quarantine; Owner: -
--

ALTER TABLE quarantine.rows ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME quarantine.rows_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: block_boundaries; Type: TABLE; Schema: spatial; Owner: -
--

CREATE TABLE spatial.block_boundaries (
    block_id bigint NOT NULL,
    period ref.month_period NOT NULL,
    geom public.geometry(MultiPolygon,4326) NOT NULL,
    upload_batch_id uuid,
    CONSTRAINT block_boundaries_geom_check CHECK (public.st_isvalid(geom))
);


--
-- Name: bridges; Type: TABLE; Schema: spatial; Owner: -
--

CREATE TABLE spatial.bridges (
    id bigint NOT NULL,
    block_id bigint NOT NULL,
    period ref.month_period NOT NULL,
    objectid bigint,
    category character varying(100),
    geom public.geometry(Point,4326) NOT NULL,
    upload_batch_id uuid
);


--
-- Name: bridges_id_seq; Type: SEQUENCE; Schema: spatial; Owner: -
--

ALTER TABLE spatial.bridges ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME spatial.bridges_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: division_boundaries; Type: TABLE; Schema: spatial; Owner: -
--

CREATE TABLE spatial.division_boundaries (
    id bigint NOT NULL,
    division_id bigint NOT NULL,
    estate_id bigint,
    period date NOT NULL,
    geom public.geometry(MultiPolygon,4326) NOT NULL,
    geom_display public.geometry(MultiPolygon,4326),
    n_blok integer DEFAULT 0 NOT NULL,
    luas_ha numeric(14,4),
    source character varying(16) DEFAULT 'derived'::character varying NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT division_boundaries_source_check CHECK (((source)::text = ANY ((ARRAY['derived'::character varying, 'official'::character varying])::text[])))
);


--
-- Name: division_boundaries_id_seq; Type: SEQUENCE; Schema: spatial; Owner: -
--

CREATE SEQUENCE spatial.division_boundaries_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: division_boundaries_id_seq; Type: SEQUENCE OWNED BY; Schema: spatial; Owner: -
--

ALTER SEQUENCE spatial.division_boundaries_id_seq OWNED BY spatial.division_boundaries.id;


--
-- Name: drainage_points; Type: TABLE; Schema: spatial; Owner: -
--

CREATE TABLE spatial.drainage_points (
    id bigint NOT NULL,
    block_id bigint NOT NULL,
    period ref.month_period NOT NULL,
    objectid bigint,
    category text,
    geom public.geometry(Point,4326) NOT NULL,
    upload_batch_id uuid
);


--
-- Name: drainage_points_id_seq; Type: SEQUENCE; Schema: spatial; Owner: -
--

ALTER TABLE spatial.drainage_points ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME spatial.drainage_points_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: landuse_polygons; Type: TABLE; Schema: spatial; Owner: -
--

CREATE TABLE spatial.landuse_polygons (
    id bigint NOT NULL,
    block_id bigint NOT NULL,
    period ref.month_period NOT NULL,
    objectid bigint,
    landuse character varying(100),
    landuse_class character varying(100),
    ownership text,
    geom public.geometry(MultiPolygon,4326) NOT NULL,
    upload_batch_id uuid
);


--
-- Name: landuse_polygons_id_seq; Type: SEQUENCE; Schema: spatial; Owner: -
--

ALTER TABLE spatial.landuse_polygons ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME spatial.landuse_polygons_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: layer_types; Type: TABLE; Schema: spatial; Owner: -
--

CREATE TABLE spatial.layer_types (
    id integer NOT NULL,
    code character varying(63) NOT NULL,
    name character varying(150) NOT NULL,
    description text,
    table_name character varying(127) NOT NULL,
    geometry_type character varying(20) NOT NULL,
    has_block boolean DEFAULT true NOT NULL,
    column_schema jsonb DEFAULT '[]'::jsonb NOT NULL,
    endpoints jsonb,
    handler_type character varying(20) DEFAULT 'GENERIC'::character varying NOT NULL,
    status character varying(20) DEFAULT 'ACTIVE'::character varying NOT NULL,
    created_by character varying(100),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT layer_types_geometry_type_check CHECK (((geometry_type)::text = ANY (ARRAY[('POINT'::character varying)::text, ('MULTIPOINT'::character varying)::text, ('LINESTRING'::character varying)::text, ('MULTILINESTRING'::character varying)::text, ('POLYGON'::character varying)::text, ('MULTIPOLYGON'::character varying)::text]))),
    CONSTRAINT layer_types_handler_type_check CHECK (((handler_type)::text = ANY (ARRAY[('GENERIC'::character varying)::text, ('LEGACY'::character varying)::text]))),
    CONSTRAINT layer_types_status_check CHECK (((status)::text = ANY (ARRAY[('ACTIVE'::character varying)::text, ('INACTIVE'::character varying)::text])))
);


--
-- Name: layer_types_id_seq; Type: SEQUENCE; Schema: spatial; Owner: -
--

ALTER TABLE spatial.layer_types ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME spatial.layer_types_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: palm_trees; Type: TABLE; Schema: spatial; Owner: -
--

CREATE TABLE spatial.palm_trees (
    id bigint NOT NULL,
    objectid bigint NOT NULL,
    geom public.geometry(Point,4326) NOT NULL
);


--
-- Name: palm_trees_id_seq; Type: SEQUENCE; Schema: spatial; Owner: -
--

ALTER TABLE spatial.palm_trees ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME spatial.palm_trees_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: roads; Type: TABLE; Schema: spatial; Owner: -
--

CREATE TABLE spatial.roads (
    id bigint NOT NULL,
    block_id bigint NOT NULL,
    period ref.month_period NOT NULL,
    objectid bigint,
    category character varying(100),
    width_m double precision,
    ownership character varying(50),
    geom public.geometry(MultiLineString,4326) NOT NULL,
    upload_batch_id uuid,
    CONSTRAINT roads_width_m_check CHECK ((width_m >= (0)::double precision))
);


--
-- Name: roads_id_seq; Type: SEQUENCE; Schema: spatial; Owner: -
--

ALTER TABLE spatial.roads ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME spatial.roads_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: slope_polygons; Type: TABLE; Schema: spatial; Owner: -
--

CREATE TABLE spatial.slope_polygons (
    id bigint NOT NULL,
    block_id bigint NOT NULL,
    period ref.month_period NOT NULL,
    objectid bigint,
    category character varying(100),
    slope_class character varying(50),
    geom public.geometry(MultiPolygon,4326) NOT NULL,
    upload_batch_id uuid
);


--
-- Name: slope_polygons_id_seq; Type: SEQUENCE; Schema: spatial; Owner: -
--

ALTER TABLE spatial.slope_polygons ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME spatial.slope_polygons_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: tph_points; Type: TABLE; Schema: spatial; Owner: -
--

CREATE TABLE spatial.tph_points (
    id bigint NOT NULL,
    block_id bigint NOT NULL,
    period ref.month_period NOT NULL,
    category_id smallint,
    geom public.geometry(Point,4326) NOT NULL,
    upload_batch_id uuid
);


--
-- Name: tph_points_id_seq; Type: SEQUENCE; Schema: spatial; Owner: -
--

ALTER TABLE spatial.tph_points ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME spatial.tph_points_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: tree_censuses; Type: TABLE; Schema: spatial; Owner: -
--

CREATE TABLE spatial.tree_censuses (
    palm_tree_id bigint NOT NULL,
    period ref.month_period NOT NULL,
    block_id bigint NOT NULL,
    category_id smallint NOT NULL,
    diameter double precision,
    spacing double precision,
    upload_batch_id uuid,
    CONSTRAINT tree_censuses_diameter_check CHECK ((diameter >= (0)::double precision)),
    CONSTRAINT tree_censuses_spacing_check CHECK ((spacing >= (0)::double precision))
);


--
-- Name: v_block_boundary_changes; Type: VIEW; Schema: spatial; Owner: -
--

CREATE VIEW spatial.v_block_boundary_changes AS
 SELECT block_id,
    period,
    lag(period) OVER w AS previous_period,
    round(((public.st_area((geom)::public.geography) / (10000)::double precision))::numeric, 4) AS area_ha,
    round((((public.st_area((geom)::public.geography) - public.st_area((lag(geom) OVER w)::public.geography)) / (10000)::double precision))::numeric, 4) AS area_change_ha,
        CASE
            WHEN (lag(geom) OVER w IS NULL) THEN NULL::boolean
            ELSE (NOT public.st_equals(geom, lag(geom) OVER w))
        END AS boundary_changed
   FROM spatial.block_boundaries b
  WINDOW w AS (PARTITION BY block_id ORDER BY period);


--
-- Name: area_statement_seed_varieties; Type: TABLE; Schema: trx; Owner: -
--

CREATE TABLE trx.area_statement_seed_varieties (
    area_statement_id bigint NOT NULL,
    seed_variety_id smallint NOT NULL
);


--
-- Name: area_statements; Type: TABLE; Schema: trx; Owner: -
--

CREATE TABLE trx.area_statements (
    id bigint NOT NULL,
    block_id bigint NOT NULL,
    period ref.month_period NOT NULL,
    area_id bigint NOT NULL,
    planting_status_id smallint NOT NULL,
    planting_year smallint,
    planting_month smallint,
    soil_type_id smallint,
    topography_type_id smallint,
    planted_area_ha numeric,
    land_area_ha numeric,
    tree_count numeric,
    sph numeric,
    pct_flat smallint,
    pct_hilly smallint,
    pct_undulating smallint,
    pct_steep smallint,
    upload_batch_id uuid,
    CONSTRAINT area_statements_check CHECK (((planting_month IS NULL) OR (planting_year IS NOT NULL))),
    CONSTRAINT area_statements_check1 CHECK (((((COALESCE((pct_flat)::integer, 0) + COALESCE((pct_hilly)::integer, 0)) + COALESCE((pct_undulating)::integer, 0)) + COALESCE((pct_steep)::integer, 0)) <= 100)),
    CONSTRAINT area_statements_land_area_ha_check CHECK ((land_area_ha >= (0)::numeric)),
    CONSTRAINT area_statements_pct_flat_check CHECK (((pct_flat >= 0) AND (pct_flat <= 100))),
    CONSTRAINT area_statements_pct_hilly_check CHECK (((pct_hilly >= 0) AND (pct_hilly <= 100))),
    CONSTRAINT area_statements_pct_steep_check CHECK (((pct_steep >= 0) AND (pct_steep <= 100))),
    CONSTRAINT area_statements_pct_undulating_check CHECK (((pct_undulating >= 0) AND (pct_undulating <= 100))),
    CONSTRAINT area_statements_planted_area_ha_check CHECK ((planted_area_ha >= (0)::numeric)),
    CONSTRAINT area_statements_planting_month_check CHECK (((planting_month >= 1) AND (planting_month <= 12))),
    CONSTRAINT area_statements_planting_year_check CHECK (((planting_year >= 1900) AND (planting_year <= 2100))),
    CONSTRAINT area_statements_sph_check CHECK ((sph >= (0)::numeric)),
    CONSTRAINT area_statements_tree_count_check CHECK ((tree_count >= (0)::numeric))
);


--
-- Name: area_statements_id_seq; Type: SEQUENCE; Schema: trx; Owner: -
--

ALTER TABLE trx.area_statements ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME trx.area_statements_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: block_productions; Type: TABLE; Schema: trx; Owner: -
--

CREATE TABLE trx.block_productions (
    id bigint NOT NULL,
    block_id bigint NOT NULL,
    period ref.month_period NOT NULL,
    ffb_actual_kg numeric,
    ffb_budget_kg numeric,
    ffb_census_kg numeric,
    bunches_actual integer,
    bunches_budget numeric,
    bunches_census numeric,
    bjr_actual numeric,
    bjr_budget numeric,
    bjr_census numeric,
    upload_batch_id uuid,
    CONSTRAINT block_productions_bjr_actual_check CHECK ((bjr_actual >= (0)::numeric)),
    CONSTRAINT block_productions_bjr_budget_check CHECK ((bjr_budget >= (0)::numeric)),
    CONSTRAINT block_productions_bjr_census_check CHECK ((bjr_census >= (0)::numeric)),
    CONSTRAINT block_productions_bunches_actual_check CHECK ((bunches_actual >= 0)),
    CONSTRAINT block_productions_bunches_budget_check CHECK ((bunches_budget >= (0)::numeric)),
    CONSTRAINT block_productions_bunches_census_check CHECK ((bunches_census >= (0)::numeric)),
    CONSTRAINT block_productions_ffb_actual_kg_check CHECK ((ffb_actual_kg >= (0)::numeric)),
    CONSTRAINT block_productions_ffb_budget_kg_check CHECK ((ffb_budget_kg >= (0)::numeric)),
    CONSTRAINT block_productions_ffb_census_kg_check CHECK ((ffb_census_kg >= (0)::numeric))
);


--
-- Name: block_productions_id_seq; Type: SEQUENCE; Schema: trx; Owner: -
--

ALTER TABLE trx.block_productions ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME trx.block_productions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: harvest_rotations; Type: TABLE; Schema: trx; Owner: -
--

CREATE TABLE trx.harvest_rotations (
    id bigint NOT NULL,
    block_id bigint NOT NULL,
    period ref.month_period NOT NULL,
    area_ha numeric,
    tree_count integer,
    rotation_no numeric,
    interval_days integer,
    rotation_status_id smallint,
    upload_batch_id uuid,
    CONSTRAINT harvest_rotations_area_ha_check CHECK ((area_ha >= (0)::numeric)),
    CONSTRAINT harvest_rotations_interval_days_check CHECK ((interval_days >= 0)),
    CONSTRAINT harvest_rotations_rotation_no_check CHECK ((rotation_no >= (0)::numeric)),
    CONSTRAINT harvest_rotations_tree_count_check CHECK ((tree_count >= 0))
);


--
-- Name: harvest_rotations_id_seq; Type: SEQUENCE; Schema: trx; Owner: -
--

ALTER TABLE trx.harvest_rotations ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME trx.harvest_rotations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: v_block_production_facts; Type: VIEW; Schema: trx; Owner: -
--

CREATE VIEW trx.v_block_production_facts AS
 SELECT p.block_id,
    p.period,
    a.area_id,
    a.planted_area_ha,
    a.tree_count,
    p.ffb_actual_kg,
    p.ffb_budget_kg,
    p.ffb_census_kg,
    p.bunches_actual,
    p.bunches_budget,
    p.bunches_census,
    (p.ffb_actual_kg / (NULLIF(p.bunches_actual, 0))::numeric) AS bjr_actual_calc,
    ((p.ffb_actual_kg / (1000)::numeric) / NULLIF(a.planted_area_ha, (0)::numeric)) AS ffb_actual_ton_per_ha
   FROM (trx.block_productions p
     LEFT JOIN trx.area_statements a ON (((a.block_id = p.block_id) AND ((a.period)::date = (p.period)::date))));


--
-- Name: division_boundaries id; Type: DEFAULT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.division_boundaries ALTER COLUMN id SET DEFAULT nextval('spatial.division_boundaries_id_seq'::regclass);


--
-- Name: change_logs change_logs_pkey; Type: CONSTRAINT; Schema: audit; Owner: -
--

ALTER TABLE ONLY audit.change_logs
    ADD CONSTRAINT change_logs_pkey PRIMARY KEY (id);


--
-- Name: data_store_versions data_store_versions_pkey; Type: CONSTRAINT; Schema: audit; Owner: -
--

ALTER TABLE ONLY audit.data_store_versions
    ADD CONSTRAINT data_store_versions_pkey PRIMARY KEY (domain);


--
-- Name: legacy_id_maps legacy_id_maps_pkey; Type: CONSTRAINT; Schema: audit; Owner: -
--

ALTER TABLE ONLY audit.legacy_id_maps
    ADD CONSTRAINT legacy_id_maps_pkey PRIMARY KEY (table_name, legacy_id);


--
-- Name: upload_batches upload_batches_pkey; Type: CONSTRAINT; Schema: audit; Owner: -
--

ALTER TABLE ONLY audit.upload_batches
    ADD CONSTRAINT upload_batches_pkey PRIMARY KEY (id);


--
-- Name: upload_jobs upload_jobs_pkey; Type: CONSTRAINT; Schema: audit; Owner: -
--

ALTER TABLE ONLY audit.upload_jobs
    ADD CONSTRAINT upload_jobs_pkey PRIMARY KEY (id);


--
-- Name: user_activities user_activities_pkey; Type: CONSTRAINT; Schema: audit; Owner: -
--

ALTER TABLE ONLY audit.user_activities
    ADD CONSTRAINT user_activities_pkey PRIMARY KEY (id);


--
-- Name: rows rows_pkey; Type: CONSTRAINT; Schema: quarantine; Owner: -
--

ALTER TABLE ONLY quarantine.rows
    ADD CONSTRAINT rows_pkey PRIMARY KEY (id);


--
-- Name: block_boundaries block_boundaries_pkey; Type: CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.block_boundaries
    ADD CONSTRAINT block_boundaries_pkey PRIMARY KEY (block_id, period);


--
-- Name: bridges bridges_period_objectid_key; Type: CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.bridges
    ADD CONSTRAINT bridges_period_objectid_key UNIQUE (period, objectid);


--
-- Name: bridges bridges_pkey; Type: CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.bridges
    ADD CONSTRAINT bridges_pkey PRIMARY KEY (id);


--
-- Name: division_boundaries division_boundaries_division_period_source_key; Type: CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.division_boundaries
    ADD CONSTRAINT division_boundaries_division_period_source_key UNIQUE (division_id, period, source);


--
-- Name: division_boundaries division_boundaries_pkey; Type: CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.division_boundaries
    ADD CONSTRAINT division_boundaries_pkey PRIMARY KEY (id);


--
-- Name: drainage_points drainage_points_period_objectid_key; Type: CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.drainage_points
    ADD CONSTRAINT drainage_points_period_objectid_key UNIQUE (period, objectid);


--
-- Name: drainage_points drainage_points_pkey; Type: CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.drainage_points
    ADD CONSTRAINT drainage_points_pkey PRIMARY KEY (id);


--
-- Name: landuse_polygons landuse_polygons_pkey; Type: CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.landuse_polygons
    ADD CONSTRAINT landuse_polygons_pkey PRIMARY KEY (id);


--
-- Name: layer_types layer_types_code_key; Type: CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.layer_types
    ADD CONSTRAINT layer_types_code_key UNIQUE (code);


--
-- Name: layer_types layer_types_pkey; Type: CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.layer_types
    ADD CONSTRAINT layer_types_pkey PRIMARY KEY (id);


--
-- Name: layer_types layer_types_table_name_key; Type: CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.layer_types
    ADD CONSTRAINT layer_types_table_name_key UNIQUE (table_name);


--
-- Name: palm_trees palm_trees_objectid_key; Type: CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.palm_trees
    ADD CONSTRAINT palm_trees_objectid_key UNIQUE (objectid);


--
-- Name: palm_trees palm_trees_pkey; Type: CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.palm_trees
    ADD CONSTRAINT palm_trees_pkey PRIMARY KEY (id);


--
-- Name: roads roads_period_objectid_key; Type: CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.roads
    ADD CONSTRAINT roads_period_objectid_key UNIQUE (period, objectid);


--
-- Name: roads roads_pkey; Type: CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.roads
    ADD CONSTRAINT roads_pkey PRIMARY KEY (id);


--
-- Name: slope_polygons slope_polygons_period_objectid_key; Type: CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.slope_polygons
    ADD CONSTRAINT slope_polygons_period_objectid_key UNIQUE (period, objectid);


--
-- Name: slope_polygons slope_polygons_pkey; Type: CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.slope_polygons
    ADD CONSTRAINT slope_polygons_pkey PRIMARY KEY (id);


--
-- Name: tph_points tph_points_pkey; Type: CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.tph_points
    ADD CONSTRAINT tph_points_pkey PRIMARY KEY (id);


--
-- Name: tree_censuses tree_censuses_pkey; Type: CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.tree_censuses
    ADD CONSTRAINT tree_censuses_pkey PRIMARY KEY (palm_tree_id, period);


--
-- Name: area_statement_seed_varieties area_statement_seed_varieties_pkey; Type: CONSTRAINT; Schema: trx; Owner: -
--

ALTER TABLE ONLY trx.area_statement_seed_varieties
    ADD CONSTRAINT area_statement_seed_varieties_pkey PRIMARY KEY (area_statement_id, seed_variety_id);


--
-- Name: area_statements area_statements_block_id_period_key; Type: CONSTRAINT; Schema: trx; Owner: -
--

ALTER TABLE ONLY trx.area_statements
    ADD CONSTRAINT area_statements_block_id_period_key UNIQUE (block_id, period);


--
-- Name: area_statements area_statements_pkey; Type: CONSTRAINT; Schema: trx; Owner: -
--

ALTER TABLE ONLY trx.area_statements
    ADD CONSTRAINT area_statements_pkey PRIMARY KEY (id);


--
-- Name: block_productions block_productions_block_id_period_key; Type: CONSTRAINT; Schema: trx; Owner: -
--

ALTER TABLE ONLY trx.block_productions
    ADD CONSTRAINT block_productions_block_id_period_key UNIQUE (block_id, period);


--
-- Name: block_productions block_productions_pkey; Type: CONSTRAINT; Schema: trx; Owner: -
--

ALTER TABLE ONLY trx.block_productions
    ADD CONSTRAINT block_productions_pkey PRIMARY KEY (id);


--
-- Name: harvest_rotations harvest_rotations_block_id_period_key; Type: CONSTRAINT; Schema: trx; Owner: -
--

ALTER TABLE ONLY trx.harvest_rotations
    ADD CONSTRAINT harvest_rotations_block_id_period_key UNIQUE (block_id, period);


--
-- Name: harvest_rotations harvest_rotations_pkey; Type: CONSTRAINT; Schema: trx; Owner: -
--

ALTER TABLE ONLY trx.harvest_rotations
    ADD CONSTRAINT harvest_rotations_pkey PRIMARY KEY (id);


--
-- Name: change_logs_actor_user_id_changed_at_idx; Type: INDEX; Schema: audit; Owner: -
--

CREATE INDEX change_logs_actor_user_id_changed_at_idx ON audit.change_logs USING btree (actor_user_id, changed_at);


--
-- Name: change_logs_new_data_idx; Type: INDEX; Schema: audit; Owner: -
--

CREATE INDEX change_logs_new_data_idx ON audit.change_logs USING gin (new_data jsonb_path_ops);


--
-- Name: change_logs_old_data_idx; Type: INDEX; Schema: audit; Owner: -
--

CREATE INDEX change_logs_old_data_idx ON audit.change_logs USING gin (old_data jsonb_path_ops);


--
-- Name: change_logs_schema_name_table_name_changed_at_idx; Type: INDEX; Schema: audit; Owner: -
--

CREATE INDEX change_logs_schema_name_table_name_changed_at_idx ON audit.change_logs USING btree (schema_name, table_name, changed_at);


--
-- Name: ix_upload_jobs_group; Type: INDEX; Schema: audit; Owner: -
--

CREATE INDEX ix_upload_jobs_group ON audit.upload_jobs USING btree (upload_group_id, part_index) WHERE (upload_group_id IS NOT NULL);


--
-- Name: ix_upload_jobs_queue; Type: INDEX; Schema: audit; Owner: -
--

CREATE INDEX ix_upload_jobs_queue ON audit.upload_jobs USING btree (created_at) WHERE ((status)::text = 'queued'::text);


--
-- Name: ix_upload_jobs_running; Type: INDEX; Schema: audit; Owner: -
--

CREATE INDEX ix_upload_jobs_running ON audit.upload_jobs USING btree (heartbeat_at) WHERE ((status)::text = 'running'::text);


--
-- Name: ix_upload_jobs_user; Type: INDEX; Schema: audit; Owner: -
--

CREATE INDEX ix_upload_jobs_user ON audit.upload_jobs USING btree (user_id, created_at DESC);


--
-- Name: upload_batches_target_table_status_idx; Type: INDEX; Schema: audit; Owner: -
--

CREATE INDEX upload_batches_target_table_status_idx ON audit.upload_batches USING btree (target_table, status);


--
-- Name: user_activities_user_id_created_at_idx; Type: INDEX; Schema: audit; Owner: -
--

CREATE INDEX user_activities_user_id_created_at_idx ON audit.user_activities USING btree (user_id, created_at);


--
-- Name: ix_quarantine_rows_quarantined_at; Type: INDEX; Schema: quarantine; Owner: -
--

CREATE INDEX ix_quarantine_rows_quarantined_at ON quarantine.rows USING btree (quarantined_at DESC);


--
-- Name: ix_quarantine_rows_upload_batch; Type: INDEX; Schema: quarantine; Owner: -
--

CREATE INDEX ix_quarantine_rows_upload_batch ON quarantine.rows USING btree (upload_batch_id) WHERE (upload_batch_id IS NOT NULL);


--
-- Name: rows_source_table_action_idx; Type: INDEX; Schema: quarantine; Owner: -
--

CREATE INDEX rows_source_table_action_idx ON quarantine.rows USING btree (source_table, action);


--
-- Name: block_boundaries_geom_idx; Type: INDEX; Schema: spatial; Owner: -
--

CREATE INDEX block_boundaries_geom_idx ON spatial.block_boundaries USING gist (geom);


--
-- Name: block_boundaries_period_idx; Type: INDEX; Schema: spatial; Owner: -
--

CREATE INDEX block_boundaries_period_idx ON spatial.block_boundaries USING btree (period);


--
-- Name: bridges_block_id_period_idx; Type: INDEX; Schema: spatial; Owner: -
--

CREATE INDEX bridges_block_id_period_idx ON spatial.bridges USING btree (block_id, period);


--
-- Name: bridges_geom_idx; Type: INDEX; Schema: spatial; Owner: -
--

CREATE INDEX bridges_geom_idx ON spatial.bridges USING gist (geom);


--
-- Name: division_boundaries_estate_idx; Type: INDEX; Schema: spatial; Owner: -
--

CREATE INDEX division_boundaries_estate_idx ON spatial.division_boundaries USING btree (estate_id);


--
-- Name: division_boundaries_geom_display_gix; Type: INDEX; Schema: spatial; Owner: -
--

CREATE INDEX division_boundaries_geom_display_gix ON spatial.division_boundaries USING gist (geom_display);


--
-- Name: division_boundaries_geom_gix; Type: INDEX; Schema: spatial; Owner: -
--

CREATE INDEX division_boundaries_geom_gix ON spatial.division_boundaries USING gist (geom);


--
-- Name: division_boundaries_period_idx; Type: INDEX; Schema: spatial; Owner: -
--

CREATE INDEX division_boundaries_period_idx ON spatial.division_boundaries USING btree (period);


--
-- Name: drainage_points_block_id_period_idx; Type: INDEX; Schema: spatial; Owner: -
--

CREATE INDEX drainage_points_block_id_period_idx ON spatial.drainage_points USING btree (block_id, period);


--
-- Name: drainage_points_geom_idx; Type: INDEX; Schema: spatial; Owner: -
--

CREATE INDEX drainage_points_geom_idx ON spatial.drainage_points USING gist (geom);


--
-- Name: ix_landuse_polygons_block_period; Type: INDEX; Schema: spatial; Owner: -
--

CREATE INDEX ix_landuse_polygons_block_period ON spatial.landuse_polygons USING btree (block_id, period);


--
-- Name: landuse_polygons_block_id_period_idx; Type: INDEX; Schema: spatial; Owner: -
--

CREATE INDEX landuse_polygons_block_id_period_idx ON spatial.landuse_polygons USING btree (block_id, period);


--
-- Name: landuse_polygons_geom_idx; Type: INDEX; Schema: spatial; Owner: -
--

CREATE INDEX landuse_polygons_geom_idx ON spatial.landuse_polygons USING gist (geom);


--
-- Name: palm_trees_geom_idx; Type: INDEX; Schema: spatial; Owner: -
--

CREATE INDEX palm_trees_geom_idx ON spatial.palm_trees USING gist (geom);


--
-- Name: roads_block_id_period_idx; Type: INDEX; Schema: spatial; Owner: -
--

CREATE INDEX roads_block_id_period_idx ON spatial.roads USING btree (block_id, period);


--
-- Name: roads_geom_idx; Type: INDEX; Schema: spatial; Owner: -
--

CREATE INDEX roads_geom_idx ON spatial.roads USING gist (geom);


--
-- Name: slope_polygons_block_id_period_idx; Type: INDEX; Schema: spatial; Owner: -
--

CREATE INDEX slope_polygons_block_id_period_idx ON spatial.slope_polygons USING btree (block_id, period);


--
-- Name: slope_polygons_geom_idx; Type: INDEX; Schema: spatial; Owner: -
--

CREATE INDEX slope_polygons_geom_idx ON spatial.slope_polygons USING gist (geom);


--
-- Name: tph_points_block_id_period_idx; Type: INDEX; Schema: spatial; Owner: -
--

CREATE INDEX tph_points_block_id_period_idx ON spatial.tph_points USING btree (block_id, period);


--
-- Name: tph_points_geom_idx; Type: INDEX; Schema: spatial; Owner: -
--

CREATE INDEX tph_points_geom_idx ON spatial.tph_points USING gist (geom);


--
-- Name: tree_censuses_block_id_period_idx; Type: INDEX; Schema: spatial; Owner: -
--

CREATE INDEX tree_censuses_block_id_period_idx ON spatial.tree_censuses USING btree (block_id, period);


--
-- Name: tree_censuses_period_category_id_idx; Type: INDEX; Schema: spatial; Owner: -
--

CREATE INDEX tree_censuses_period_category_id_idx ON spatial.tree_censuses USING btree (period, category_id);


--
-- Name: area_statement_seed_varieties_seed_variety_id_idx; Type: INDEX; Schema: trx; Owner: -
--

CREATE INDEX area_statement_seed_varieties_seed_variety_id_idx ON trx.area_statement_seed_varieties USING btree (seed_variety_id);


--
-- Name: area_statements_area_id_period_idx; Type: INDEX; Schema: trx; Owner: -
--

CREATE INDEX area_statements_area_id_period_idx ON trx.area_statements USING btree (area_id, period);


--
-- Name: area_statements_period_idx; Type: INDEX; Schema: trx; Owner: -
--

CREATE INDEX area_statements_period_idx ON trx.area_statements USING btree (period);


--
-- Name: block_productions_period_idx; Type: INDEX; Schema: trx; Owner: -
--

CREATE INDEX block_productions_period_idx ON trx.block_productions USING btree (period);


--
-- Name: harvest_rotations_period_idx; Type: INDEX; Schema: trx; Owner: -
--

CREATE INDEX harvest_rotations_period_idx ON trx.harvest_rotations USING btree (period);


--
-- Name: legacy_id_maps audit_row; Type: TRIGGER; Schema: audit; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON audit.legacy_id_maps FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: upload_batches audit_row; Type: TRIGGER; Schema: audit; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON audit.upload_batches FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: legacy_id_maps audit_row_update; Type: TRIGGER; Schema: audit; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON audit.legacy_id_maps FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: upload_batches audit_row_update; Type: TRIGGER; Schema: audit; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON audit.upload_batches FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: legacy_id_maps audit_truncate; Type: TRIGGER; Schema: audit; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON audit.legacy_id_maps FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: upload_batches audit_truncate; Type: TRIGGER; Schema: audit; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON audit.upload_batches FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: change_logs change_logs_append_only; Type: TRIGGER; Schema: audit; Owner: -
--

CREATE TRIGGER change_logs_append_only BEFORE DELETE OR UPDATE ON audit.change_logs FOR EACH ROW EXECUTE FUNCTION audit.deny_modification();


--
-- Name: change_logs change_logs_no_truncate; Type: TRIGGER; Schema: audit; Owner: -
--

CREATE TRIGGER change_logs_no_truncate BEFORE TRUNCATE ON audit.change_logs FOR EACH STATEMENT EXECUTE FUNCTION audit.deny_modification();


--
-- Name: user_activities user_activities_append_only; Type: TRIGGER; Schema: audit; Owner: -
--

CREATE TRIGGER user_activities_append_only BEFORE DELETE OR UPDATE ON audit.user_activities FOR EACH ROW EXECUTE FUNCTION audit.deny_modification();


--
-- Name: user_activities user_activities_no_truncate; Type: TRIGGER; Schema: audit; Owner: -
--

CREATE TRIGGER user_activities_no_truncate BEFORE TRUNCATE ON audit.user_activities FOR EACH STATEMENT EXECUTE FUNCTION audit.deny_modification();


--
-- Name: user_activities user_activities_require_ip; Type: TRIGGER; Schema: audit; Owner: -
--

CREATE TRIGGER user_activities_require_ip BEFORE INSERT ON audit.user_activities FOR EACH ROW EXECUTE FUNCTION audit.require_activity_ip();


--
-- Name: rows audit_row; Type: TRIGGER; Schema: quarantine; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON quarantine.rows FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: rows audit_row_update; Type: TRIGGER; Schema: quarantine; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON quarantine.rows FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: rows audit_truncate; Type: TRIGGER; Schema: quarantine; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON quarantine.rows FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: block_boundaries audit_row; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON spatial.block_boundaries FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: bridges audit_row; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON spatial.bridges FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: drainage_points audit_row; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON spatial.drainage_points FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: landuse_polygons audit_row; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON spatial.landuse_polygons FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: layer_types audit_row; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON spatial.layer_types FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: palm_trees audit_row; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON spatial.palm_trees FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: roads audit_row; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON spatial.roads FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: slope_polygons audit_row; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON spatial.slope_polygons FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: tph_points audit_row; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON spatial.tph_points FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: tree_censuses audit_row; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON spatial.tree_censuses FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: block_boundaries audit_row_update; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON spatial.block_boundaries FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: bridges audit_row_update; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON spatial.bridges FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: drainage_points audit_row_update; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON spatial.drainage_points FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: landuse_polygons audit_row_update; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON spatial.landuse_polygons FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: layer_types audit_row_update; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON spatial.layer_types FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: palm_trees audit_row_update; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON spatial.palm_trees FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: roads audit_row_update; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON spatial.roads FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: slope_polygons audit_row_update; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON spatial.slope_polygons FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: tph_points audit_row_update; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON spatial.tph_points FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: tree_censuses audit_row_update; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON spatial.tree_censuses FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: block_boundaries audit_truncate; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON spatial.block_boundaries FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: bridges audit_truncate; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON spatial.bridges FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: drainage_points audit_truncate; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON spatial.drainage_points FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: landuse_polygons audit_truncate; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON spatial.landuse_polygons FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: layer_types audit_truncate; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON spatial.layer_types FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: palm_trees audit_truncate; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON spatial.palm_trees FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: roads audit_truncate; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON spatial.roads FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: slope_polygons audit_truncate; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON spatial.slope_polygons FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: tph_points audit_truncate; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON spatial.tph_points FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: tree_censuses audit_truncate; Type: TRIGGER; Schema: spatial; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON spatial.tree_censuses FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: area_statement_seed_varieties audit_row; Type: TRIGGER; Schema: trx; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON trx.area_statement_seed_varieties FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: area_statements audit_row; Type: TRIGGER; Schema: trx; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON trx.area_statements FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: block_productions audit_row; Type: TRIGGER; Schema: trx; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON trx.block_productions FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: harvest_rotations audit_row; Type: TRIGGER; Schema: trx; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON trx.harvest_rotations FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: area_statement_seed_varieties audit_row_update; Type: TRIGGER; Schema: trx; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON trx.area_statement_seed_varieties FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: area_statements audit_row_update; Type: TRIGGER; Schema: trx; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON trx.area_statements FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: block_productions audit_row_update; Type: TRIGGER; Schema: trx; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON trx.block_productions FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: harvest_rotations audit_row_update; Type: TRIGGER; Schema: trx; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON trx.harvest_rotations FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: area_statement_seed_varieties audit_truncate; Type: TRIGGER; Schema: trx; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON trx.area_statement_seed_varieties FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: area_statements audit_truncate; Type: TRIGGER; Schema: trx; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON trx.area_statements FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: block_productions audit_truncate; Type: TRIGGER; Schema: trx; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON trx.block_productions FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: harvest_rotations audit_truncate; Type: TRIGGER; Schema: trx; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON trx.harvest_rotations FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: upload_batches upload_batches_uploaded_by_fkey; Type: FK CONSTRAINT; Schema: audit; Owner: -
--

ALTER TABLE ONLY audit.upload_batches
    ADD CONSTRAINT upload_batches_uploaded_by_fkey FOREIGN KEY (uploaded_by) REFERENCES auth.users(id) ON DELETE SET NULL;


--
-- Name: upload_jobs upload_jobs_batch_id_fkey; Type: FK CONSTRAINT; Schema: audit; Owner: -
--

ALTER TABLE ONLY audit.upload_jobs
    ADD CONSTRAINT upload_jobs_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES audit.upload_batches(id) ON DELETE SET NULL;


--
-- Name: upload_jobs upload_jobs_user_id_fkey; Type: FK CONSTRAINT; Schema: audit; Owner: -
--

ALTER TABLE ONLY audit.upload_jobs
    ADD CONSTRAINT upload_jobs_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE SET NULL;


--
-- Name: user_activities user_activities_user_id_fkey; Type: FK CONSTRAINT; Schema: audit; Owner: -
--

ALTER TABLE ONLY audit.user_activities
    ADD CONSTRAINT user_activities_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE SET NULL;


--
-- Name: rows rows_upload_batch_id_fkey; Type: FK CONSTRAINT; Schema: quarantine; Owner: -
--

ALTER TABLE ONLY quarantine.rows
    ADD CONSTRAINT rows_upload_batch_id_fkey FOREIGN KEY (upload_batch_id) REFERENCES audit.upload_batches(id) ON DELETE CASCADE;


--
-- Name: block_boundaries block_boundaries_block_id_fkey; Type: FK CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.block_boundaries
    ADD CONSTRAINT block_boundaries_block_id_fkey FOREIGN KEY (block_id) REFERENCES master.blocks(id);


--
-- Name: block_boundaries block_boundaries_upload_batch_id_fkey; Type: FK CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.block_boundaries
    ADD CONSTRAINT block_boundaries_upload_batch_id_fkey FOREIGN KEY (upload_batch_id) REFERENCES audit.upload_batches(id);


--
-- Name: bridges bridges_block_id_fkey; Type: FK CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.bridges
    ADD CONSTRAINT bridges_block_id_fkey FOREIGN KEY (block_id) REFERENCES master.blocks(id);


--
-- Name: bridges bridges_upload_batch_id_fkey; Type: FK CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.bridges
    ADD CONSTRAINT bridges_upload_batch_id_fkey FOREIGN KEY (upload_batch_id) REFERENCES audit.upload_batches(id);


--
-- Name: division_boundaries division_boundaries_division_id_fkey; Type: FK CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.division_boundaries
    ADD CONSTRAINT division_boundaries_division_id_fkey FOREIGN KEY (division_id) REFERENCES master.divisions(id);


--
-- Name: division_boundaries division_boundaries_estate_id_fkey; Type: FK CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.division_boundaries
    ADD CONSTRAINT division_boundaries_estate_id_fkey FOREIGN KEY (estate_id) REFERENCES master.estates(id);


--
-- Name: drainage_points drainage_points_block_id_fkey; Type: FK CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.drainage_points
    ADD CONSTRAINT drainage_points_block_id_fkey FOREIGN KEY (block_id) REFERENCES master.blocks(id);


--
-- Name: drainage_points drainage_points_upload_batch_id_fkey; Type: FK CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.drainage_points
    ADD CONSTRAINT drainage_points_upload_batch_id_fkey FOREIGN KEY (upload_batch_id) REFERENCES audit.upload_batches(id);


--
-- Name: landuse_polygons landuse_polygons_block_id_fkey; Type: FK CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.landuse_polygons
    ADD CONSTRAINT landuse_polygons_block_id_fkey FOREIGN KEY (block_id) REFERENCES master.blocks(id);


--
-- Name: landuse_polygons landuse_polygons_upload_batch_id_fkey; Type: FK CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.landuse_polygons
    ADD CONSTRAINT landuse_polygons_upload_batch_id_fkey FOREIGN KEY (upload_batch_id) REFERENCES audit.upload_batches(id);


--
-- Name: roads roads_block_id_fkey; Type: FK CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.roads
    ADD CONSTRAINT roads_block_id_fkey FOREIGN KEY (block_id) REFERENCES master.blocks(id);


--
-- Name: roads roads_upload_batch_id_fkey; Type: FK CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.roads
    ADD CONSTRAINT roads_upload_batch_id_fkey FOREIGN KEY (upload_batch_id) REFERENCES audit.upload_batches(id);


--
-- Name: slope_polygons slope_polygons_block_id_fkey; Type: FK CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.slope_polygons
    ADD CONSTRAINT slope_polygons_block_id_fkey FOREIGN KEY (block_id) REFERENCES master.blocks(id);


--
-- Name: slope_polygons slope_polygons_upload_batch_id_fkey; Type: FK CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.slope_polygons
    ADD CONSTRAINT slope_polygons_upload_batch_id_fkey FOREIGN KEY (upload_batch_id) REFERENCES audit.upload_batches(id);


--
-- Name: tph_points tph_points_block_id_fkey; Type: FK CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.tph_points
    ADD CONSTRAINT tph_points_block_id_fkey FOREIGN KEY (block_id) REFERENCES master.blocks(id);


--
-- Name: tph_points tph_points_category_id_fkey; Type: FK CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.tph_points
    ADD CONSTRAINT tph_points_category_id_fkey FOREIGN KEY (category_id) REFERENCES ref.tph_categories(id);


--
-- Name: tph_points tph_points_upload_batch_id_fkey; Type: FK CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.tph_points
    ADD CONSTRAINT tph_points_upload_batch_id_fkey FOREIGN KEY (upload_batch_id) REFERENCES audit.upload_batches(id);


--
-- Name: tree_censuses tree_censuses_block_id_fkey; Type: FK CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.tree_censuses
    ADD CONSTRAINT tree_censuses_block_id_fkey FOREIGN KEY (block_id) REFERENCES master.blocks(id);


--
-- Name: tree_censuses tree_censuses_category_id_fkey; Type: FK CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.tree_censuses
    ADD CONSTRAINT tree_censuses_category_id_fkey FOREIGN KEY (category_id) REFERENCES ref.tree_categories(id);


--
-- Name: tree_censuses tree_censuses_palm_tree_id_fkey; Type: FK CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.tree_censuses
    ADD CONSTRAINT tree_censuses_palm_tree_id_fkey FOREIGN KEY (palm_tree_id) REFERENCES spatial.palm_trees(id);


--
-- Name: tree_censuses tree_censuses_upload_batch_id_fkey; Type: FK CONSTRAINT; Schema: spatial; Owner: -
--

ALTER TABLE ONLY spatial.tree_censuses
    ADD CONSTRAINT tree_censuses_upload_batch_id_fkey FOREIGN KEY (upload_batch_id) REFERENCES audit.upload_batches(id);


--
-- Name: area_statement_seed_varieties area_statement_seed_varieties_area_statement_id_fkey; Type: FK CONSTRAINT; Schema: trx; Owner: -
--

ALTER TABLE ONLY trx.area_statement_seed_varieties
    ADD CONSTRAINT area_statement_seed_varieties_area_statement_id_fkey FOREIGN KEY (area_statement_id) REFERENCES trx.area_statements(id) ON DELETE CASCADE;


--
-- Name: area_statement_seed_varieties area_statement_seed_varieties_seed_variety_id_fkey; Type: FK CONSTRAINT; Schema: trx; Owner: -
--

ALTER TABLE ONLY trx.area_statement_seed_varieties
    ADD CONSTRAINT area_statement_seed_varieties_seed_variety_id_fkey FOREIGN KEY (seed_variety_id) REFERENCES ref.seed_varieties(id);


--
-- Name: area_statements area_statements_area_id_fkey; Type: FK CONSTRAINT; Schema: trx; Owner: -
--

ALTER TABLE ONLY trx.area_statements
    ADD CONSTRAINT area_statements_area_id_fkey FOREIGN KEY (area_id) REFERENCES master.areas(id);


--
-- Name: area_statements area_statements_block_id_fkey; Type: FK CONSTRAINT; Schema: trx; Owner: -
--

ALTER TABLE ONLY trx.area_statements
    ADD CONSTRAINT area_statements_block_id_fkey FOREIGN KEY (block_id) REFERENCES master.blocks(id);


--
-- Name: area_statements area_statements_planting_status_id_fkey; Type: FK CONSTRAINT; Schema: trx; Owner: -
--

ALTER TABLE ONLY trx.area_statements
    ADD CONSTRAINT area_statements_planting_status_id_fkey FOREIGN KEY (planting_status_id) REFERENCES ref.planting_statuses(id);


--
-- Name: area_statements area_statements_soil_type_id_fkey; Type: FK CONSTRAINT; Schema: trx; Owner: -
--

ALTER TABLE ONLY trx.area_statements
    ADD CONSTRAINT area_statements_soil_type_id_fkey FOREIGN KEY (soil_type_id) REFERENCES ref.soil_types(id);


--
-- Name: area_statements area_statements_topography_type_id_fkey; Type: FK CONSTRAINT; Schema: trx; Owner: -
--

ALTER TABLE ONLY trx.area_statements
    ADD CONSTRAINT area_statements_topography_type_id_fkey FOREIGN KEY (topography_type_id) REFERENCES ref.topography_types(id);


--
-- Name: area_statements area_statements_upload_batch_id_fkey; Type: FK CONSTRAINT; Schema: trx; Owner: -
--

ALTER TABLE ONLY trx.area_statements
    ADD CONSTRAINT area_statements_upload_batch_id_fkey FOREIGN KEY (upload_batch_id) REFERENCES audit.upload_batches(id);


--
-- Name: block_productions block_productions_block_id_fkey; Type: FK CONSTRAINT; Schema: trx; Owner: -
--

ALTER TABLE ONLY trx.block_productions
    ADD CONSTRAINT block_productions_block_id_fkey FOREIGN KEY (block_id) REFERENCES master.blocks(id);


--
-- Name: block_productions block_productions_upload_batch_id_fkey; Type: FK CONSTRAINT; Schema: trx; Owner: -
--

ALTER TABLE ONLY trx.block_productions
    ADD CONSTRAINT block_productions_upload_batch_id_fkey FOREIGN KEY (upload_batch_id) REFERENCES audit.upload_batches(id);


--
-- Name: harvest_rotations harvest_rotations_block_id_fkey; Type: FK CONSTRAINT; Schema: trx; Owner: -
--

ALTER TABLE ONLY trx.harvest_rotations
    ADD CONSTRAINT harvest_rotations_block_id_fkey FOREIGN KEY (block_id) REFERENCES master.blocks(id);


--
-- Name: harvest_rotations harvest_rotations_rotation_status_id_fkey; Type: FK CONSTRAINT; Schema: trx; Owner: -
--

ALTER TABLE ONLY trx.harvest_rotations
    ADD CONSTRAINT harvest_rotations_rotation_status_id_fkey FOREIGN KEY (rotation_status_id) REFERENCES ref.rotation_statuses(id);


--
-- Name: harvest_rotations harvest_rotations_upload_batch_id_fkey; Type: FK CONSTRAINT; Schema: trx; Owner: -
--

ALTER TABLE ONLY trx.harvest_rotations
    ADD CONSTRAINT harvest_rotations_upload_batch_id_fkey FOREIGN KEY (upload_batch_id) REFERENCES audit.upload_batches(id);


--
-- PostgreSQL database dump complete
--

