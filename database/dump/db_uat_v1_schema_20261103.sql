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
-- Name: auth; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA auth;


--
-- Name: master; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA master;


--
-- Name: quarantine; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA quarantine;


--
-- Name: ref; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA ref;


--
-- Name: spatial; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA spatial;


--
-- Name: trx; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA trx;


--
-- Name: postgis; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public;


--
-- Name: EXTENSION postgis; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION postgis IS 'PostGIS geometry and geography spatial types and functions';


--
-- Name: month_period; Type: DOMAIN; Schema: ref; Owner: -
--

CREATE DOMAIN ref.month_period AS date
	CONSTRAINT month_period_check CHECK ((VALUE = (date_trunc('month'::text, (VALUE)::timestamp with time zone))::date));


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
    CONSTRAINT upload_jobs_kind_check CHECK (((kind)::text = ANY (ARRAY[('analyze'::character varying)::text, ('execute'::character varying)::text]))),
    CONSTRAINT upload_jobs_status_check CHECK (((status)::text = ANY (ARRAY[('queued'::character varying)::text, ('running'::character varying)::text, ('succeeded'::character varying)::text, ('failed'::character varying)::text, ('cancelled'::character varying)::text])))
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
-- Name: menus; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.menus (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    title character varying(100) NOT NULL,
    description text,
    bg_class character varying(50) DEFAULT 'bg-blue-50'::character varying,
    icon_class character varying(50) DEFAULT 'text-blue-500'::character varying,
    arrow_class character varying(50) DEFAULT 'text-blue-500'::character varying,
    route character varying(255) NOT NULL,
    icon character varying(50) NOT NULL,
    order_position integer DEFAULT 0 NOT NULL,
    parent_id uuid,
    level integer DEFAULT 1 NOT NULL,
    is_favorite boolean DEFAULT false NOT NULL,
    CONSTRAINT menus_level_check CHECK (((level >= 1) AND (level <= 3)))
);


--
-- Name: permissions; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.permissions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code character varying(100) NOT NULL,
    resource character varying(50) NOT NULL,
    action character varying(20) NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT permissions_check CHECK (((code)::text = (((resource)::text || ':'::text) || (action)::text)))
);


--
-- Name: role_data_scopes; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.role_data_scopes (
    id bigint NOT NULL,
    role_id uuid NOT NULL,
    area_id bigint,
    company_id bigint,
    estate_id bigint,
    division_id bigint,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    group_id bigint,
    CONSTRAINT role_data_scopes_check CHECK ((num_nonnulls(group_id, area_id, company_id, estate_id, division_id) = 1))
);


--
-- Name: role_data_scopes_id_seq; Type: SEQUENCE; Schema: auth; Owner: -
--

ALTER TABLE auth.role_data_scopes ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME auth.role_data_scopes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: role_menus; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.role_menus (
    role_id uuid NOT NULL,
    menu_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: role_permissions; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.role_permissions (
    role_id uuid NOT NULL,
    permission_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: roles; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.roles (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(50) NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT roles_name_check CHECK ((((name)::text = btrim((name)::text)) AND ((name)::text <> ''::text)))
);


--
-- Name: user_roles; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.user_roles (
    user_id uuid NOT NULL,
    role_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: users; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.users (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    full_name character varying(150) NOT NULL,
    username character varying(50) NOT NULL,
    email character varying(100) NOT NULL,
    hashed_password character varying(255) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    is_service_account boolean DEFAULT false NOT NULL,
    token_expires_at timestamp with time zone,
    token_version integer DEFAULT 1 NOT NULL,
    failed_login_attempts integer DEFAULT 0 NOT NULL,
    locked_at timestamp with time zone
);


--
-- Name: announcement_reads; Type: TABLE; Schema: master; Owner: -
--

CREATE TABLE master.announcement_reads (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    announcement_id uuid NOT NULL,
    read_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: announcements; Type: TABLE; Schema: master; Owner: -
--

CREATE TABLE master.announcements (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    title character varying(200) NOT NULL,
    content text NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    start_at timestamp with time zone,
    end_at timestamp with time zone,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT announcements_period_chk CHECK (((end_at IS NULL) OR (start_at IS NULL) OR (end_at >= start_at)))
);


--
-- Name: app_settings; Type: TABLE; Schema: master; Owner: -
--

CREATE TABLE master.app_settings (
    key text NOT NULL,
    value text NOT NULL,
    description text,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by text
);


--
-- Name: areas; Type: TABLE; Schema: master; Owner: -
--

CREATE TABLE master.areas (
    id bigint NOT NULL,
    code character varying(50) NOT NULL,
    name character varying(150) NOT NULL
);


--
-- Name: areas_id_seq; Type: SEQUENCE; Schema: master; Owner: -
--

ALTER TABLE master.areas ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME master.areas_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: blocks; Type: TABLE; Schema: master; Owner: -
--

CREATE TABLE master.blocks (
    id bigint NOT NULL,
    division_id bigint NOT NULL,
    code character varying(20) NOT NULL,
    block_type_id smallint
);


--
-- Name: blocks_id_seq; Type: SEQUENCE; Schema: master; Owner: -
--

ALTER TABLE master.blocks ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME master.blocks_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: companies; Type: TABLE; Schema: master; Owner: -
--

CREATE TABLE master.companies (
    id bigint NOT NULL,
    code character varying(20) NOT NULL,
    name character varying(150),
    group_id bigint,
    short_name character varying(50)
);


--
-- Name: companies_id_seq; Type: SEQUENCE; Schema: master; Owner: -
--

ALTER TABLE master.companies ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME master.companies_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: divisions; Type: TABLE; Schema: master; Owner: -
--

CREATE TABLE master.divisions (
    id bigint NOT NULL,
    estate_id bigint NOT NULL,
    code character varying(20) NOT NULL
);


--
-- Name: divisions_id_seq; Type: SEQUENCE; Schema: master; Owner: -
--

ALTER TABLE master.divisions ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME master.divisions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: estates; Type: TABLE; Schema: master; Owner: -
--

CREATE TABLE master.estates (
    id bigint NOT NULL,
    company_id bigint NOT NULL,
    code character varying(20) NOT NULL,
    name character varying(100) NOT NULL,
    short_name character varying(20),
    area_id bigint
);


--
-- Name: estates_id_seq; Type: SEQUENCE; Schema: master; Owner: -
--

ALTER TABLE master.estates ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME master.estates_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: groups; Type: TABLE; Schema: master; Owner: -
--

CREATE TABLE master.groups (
    id bigint NOT NULL,
    code character varying(20) NOT NULL,
    name character varying(150)
);


--
-- Name: groups_id_seq; Type: SEQUENCE; Schema: master; Owner: -
--

ALTER TABLE master.groups ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME master.groups_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: block_types; Type: TABLE; Schema: ref; Owner: -
--

CREATE TABLE ref.block_types (
    id smallint NOT NULL,
    name character varying(50) NOT NULL,
    CONSTRAINT block_types_name_check CHECK ((((name)::text = btrim((name)::text)) AND ((name)::text <> ''::text)))
);


--
-- Name: v_block_hierarchy; Type: VIEW; Schema: master; Owner: -
--

CREATE VIEW master.v_block_hierarchy AS
 SELECT bl.id AS block_id,
    bl.code AS block_code,
    bt.name AS block_type,
    dv.id AS division_id,
    dv.code AS division_code,
    es.id AS estate_id,
    es.code AS estate_code,
    es.name AS estate_name,
    es.short_name AS estate_short_name,
    co.id AS company_id,
    co.code AS company_code,
    co.name AS company_name,
    ar.id AS area_id,
    ar.code AS area_code,
    gr.id AS group_id,
    gr.code AS group_code,
    gr.name AS group_name
   FROM ((((((master.blocks bl
     JOIN master.divisions dv ON ((dv.id = bl.division_id)))
     JOIN master.estates es ON ((es.id = dv.estate_id)))
     JOIN master.companies co ON ((co.id = es.company_id)))
     LEFT JOIN ref.block_types bt ON ((bt.id = bl.block_type_id)))
     LEFT JOIN master.areas ar ON ((ar.id = es.area_id)))
     LEFT JOIN master.groups gr ON ((gr.id = co.group_id)));


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
-- Name: block_types_id_seq; Type: SEQUENCE; Schema: ref; Owner: -
--

ALTER TABLE ref.block_types ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ref.block_types_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: planting_statuses; Type: TABLE; Schema: ref; Owner: -
--

CREATE TABLE ref.planting_statuses (
    id smallint NOT NULL,
    code character varying(10) NOT NULL,
    CONSTRAINT planting_statuses_code_check CHECK ((((code)::text = btrim((code)::text)) AND ((code)::text <> ''::text)))
);


--
-- Name: planting_statuses_id_seq; Type: SEQUENCE; Schema: ref; Owner: -
--

ALTER TABLE ref.planting_statuses ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ref.planting_statuses_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: rotation_statuses; Type: TABLE; Schema: ref; Owner: -
--

CREATE TABLE ref.rotation_statuses (
    id smallint NOT NULL,
    name character varying(20) NOT NULL,
    CONSTRAINT rotation_statuses_name_check CHECK ((((name)::text = btrim((name)::text)) AND ((name)::text <> ''::text)))
);


--
-- Name: rotation_statuses_id_seq; Type: SEQUENCE; Schema: ref; Owner: -
--

ALTER TABLE ref.rotation_statuses ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ref.rotation_statuses_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: seed_varieties; Type: TABLE; Schema: ref; Owner: -
--

CREATE TABLE ref.seed_varieties (
    id smallint NOT NULL,
    name character varying(100) NOT NULL,
    CONSTRAINT seed_varieties_name_check CHECK ((((name)::text = btrim((name)::text)) AND ((name)::text <> ''::text)))
);


--
-- Name: seed_varieties_id_seq; Type: SEQUENCE; Schema: ref; Owner: -
--

ALTER TABLE ref.seed_varieties ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ref.seed_varieties_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: soil_types; Type: TABLE; Schema: ref; Owner: -
--

CREATE TABLE ref.soil_types (
    id smallint NOT NULL,
    name character varying(100) NOT NULL,
    CONSTRAINT soil_types_name_check CHECK ((((name)::text = btrim((name)::text)) AND ((name)::text <> ''::text)))
);


--
-- Name: soil_types_id_seq; Type: SEQUENCE; Schema: ref; Owner: -
--

ALTER TABLE ref.soil_types ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ref.soil_types_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: topography_types; Type: TABLE; Schema: ref; Owner: -
--

CREATE TABLE ref.topography_types (
    id smallint NOT NULL,
    name character varying(100) NOT NULL,
    CONSTRAINT topography_types_name_check CHECK ((((name)::text = btrim((name)::text)) AND ((name)::text <> ''::text)))
);


--
-- Name: topography_types_id_seq; Type: SEQUENCE; Schema: ref; Owner: -
--

ALTER TABLE ref.topography_types ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ref.topography_types_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: tph_categories; Type: TABLE; Schema: ref; Owner: -
--

CREATE TABLE ref.tph_categories (
    id smallint NOT NULL,
    name character varying(50) NOT NULL,
    CONSTRAINT tph_categories_name_check CHECK ((((name)::text = btrim((name)::text)) AND ((name)::text <> ''::text)))
);


--
-- Name: tph_categories_id_seq; Type: SEQUENCE; Schema: ref; Owner: -
--

ALTER TABLE ref.tph_categories ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ref.tph_categories_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: tree_categories; Type: TABLE; Schema: ref; Owner: -
--

CREATE TABLE ref.tree_categories (
    id smallint NOT NULL,
    name character varying(20) NOT NULL,
    CONSTRAINT tree_categories_name_check CHECK ((((name)::text = btrim((name)::text)) AND ((name)::text <> ''::text)))
);


--
-- Name: tree_categories_id_seq; Type: SEQUENCE; Schema: ref; Owner: -
--

ALTER TABLE ref.tree_categories ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ref.tree_categories_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: value_aliases; Type: TABLE; Schema: ref; Owner: -
--

CREATE TABLE ref.value_aliases (
    ref_table character varying(63) NOT NULL,
    alias character varying(100) NOT NULL,
    canonical character varying(100) NOT NULL,
    evidence text NOT NULL,
    CONSTRAINT value_aliases_ref_table_check CHECK (((ref_table)::text = ANY (ARRAY[('seed_varieties'::character varying)::text, ('soil_types'::character varying)::text, ('topography_types'::character varying)::text, ('rotation_statuses'::character varying)::text])))
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
-- Name: menus menus_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.menus
    ADD CONSTRAINT menus_pkey PRIMARY KEY (id);


--
-- Name: permissions permissions_code_key; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.permissions
    ADD CONSTRAINT permissions_code_key UNIQUE (code);


--
-- Name: permissions permissions_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.permissions
    ADD CONSTRAINT permissions_pkey PRIMARY KEY (id);


--
-- Name: permissions permissions_resource_action_key; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.permissions
    ADD CONSTRAINT permissions_resource_action_key UNIQUE (resource, action);


--
-- Name: role_data_scopes role_data_scopes_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.role_data_scopes
    ADD CONSTRAINT role_data_scopes_pkey PRIMARY KEY (id);


--
-- Name: role_menus role_menus_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.role_menus
    ADD CONSTRAINT role_menus_pkey PRIMARY KEY (role_id, menu_id);


--
-- Name: role_permissions role_permissions_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.role_permissions
    ADD CONSTRAINT role_permissions_pkey PRIMARY KEY (role_id, permission_id);


--
-- Name: roles roles_name_key; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.roles
    ADD CONSTRAINT roles_name_key UNIQUE (name);


--
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (id);


--
-- Name: user_roles user_roles_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.user_roles
    ADD CONSTRAINT user_roles_pkey PRIMARY KEY (user_id, role_id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: announcement_reads announcement_reads_pkey; Type: CONSTRAINT; Schema: master; Owner: -
--

ALTER TABLE ONLY master.announcement_reads
    ADD CONSTRAINT announcement_reads_pkey PRIMARY KEY (id);


--
-- Name: announcements announcements_pkey; Type: CONSTRAINT; Schema: master; Owner: -
--

ALTER TABLE ONLY master.announcements
    ADD CONSTRAINT announcements_pkey PRIMARY KEY (id);


--
-- Name: app_settings app_settings_pkey; Type: CONSTRAINT; Schema: master; Owner: -
--

ALTER TABLE ONLY master.app_settings
    ADD CONSTRAINT app_settings_pkey PRIMARY KEY (key);


--
-- Name: areas areas_code_key; Type: CONSTRAINT; Schema: master; Owner: -
--

ALTER TABLE ONLY master.areas
    ADD CONSTRAINT areas_code_key UNIQUE (code);


--
-- Name: areas areas_pkey; Type: CONSTRAINT; Schema: master; Owner: -
--

ALTER TABLE ONLY master.areas
    ADD CONSTRAINT areas_pkey PRIMARY KEY (id);


--
-- Name: blocks blocks_division_id_code_key; Type: CONSTRAINT; Schema: master; Owner: -
--

ALTER TABLE ONLY master.blocks
    ADD CONSTRAINT blocks_division_id_code_key UNIQUE (division_id, code);


--
-- Name: blocks blocks_pkey; Type: CONSTRAINT; Schema: master; Owner: -
--

ALTER TABLE ONLY master.blocks
    ADD CONSTRAINT blocks_pkey PRIMARY KEY (id);


--
-- Name: companies companies_code_key; Type: CONSTRAINT; Schema: master; Owner: -
--

ALTER TABLE ONLY master.companies
    ADD CONSTRAINT companies_code_key UNIQUE (code);


--
-- Name: companies companies_pkey; Type: CONSTRAINT; Schema: master; Owner: -
--

ALTER TABLE ONLY master.companies
    ADD CONSTRAINT companies_pkey PRIMARY KEY (id);


--
-- Name: divisions divisions_estate_id_code_key; Type: CONSTRAINT; Schema: master; Owner: -
--

ALTER TABLE ONLY master.divisions
    ADD CONSTRAINT divisions_estate_id_code_key UNIQUE (estate_id, code);


--
-- Name: divisions divisions_pkey; Type: CONSTRAINT; Schema: master; Owner: -
--

ALTER TABLE ONLY master.divisions
    ADD CONSTRAINT divisions_pkey PRIMARY KEY (id);


--
-- Name: estates estates_code_key; Type: CONSTRAINT; Schema: master; Owner: -
--

ALTER TABLE ONLY master.estates
    ADD CONSTRAINT estates_code_key UNIQUE (code);


--
-- Name: estates estates_pkey; Type: CONSTRAINT; Schema: master; Owner: -
--

ALTER TABLE ONLY master.estates
    ADD CONSTRAINT estates_pkey PRIMARY KEY (id);


--
-- Name: groups groups_code_key; Type: CONSTRAINT; Schema: master; Owner: -
--

ALTER TABLE ONLY master.groups
    ADD CONSTRAINT groups_code_key UNIQUE (code);


--
-- Name: groups groups_pkey; Type: CONSTRAINT; Schema: master; Owner: -
--

ALTER TABLE ONLY master.groups
    ADD CONSTRAINT groups_pkey PRIMARY KEY (id);


--
-- Name: announcement_reads uq_announcement_reads_user_announcement; Type: CONSTRAINT; Schema: master; Owner: -
--

ALTER TABLE ONLY master.announcement_reads
    ADD CONSTRAINT uq_announcement_reads_user_announcement UNIQUE (user_id, announcement_id);


--
-- Name: rows rows_pkey; Type: CONSTRAINT; Schema: quarantine; Owner: -
--

ALTER TABLE ONLY quarantine.rows
    ADD CONSTRAINT rows_pkey PRIMARY KEY (id);


--
-- Name: block_types block_types_name_key; Type: CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.block_types
    ADD CONSTRAINT block_types_name_key UNIQUE (name);


--
-- Name: block_types block_types_pkey; Type: CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.block_types
    ADD CONSTRAINT block_types_pkey PRIMARY KEY (id);


--
-- Name: planting_statuses planting_statuses_code_key; Type: CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.planting_statuses
    ADD CONSTRAINT planting_statuses_code_key UNIQUE (code);


--
-- Name: planting_statuses planting_statuses_pkey; Type: CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.planting_statuses
    ADD CONSTRAINT planting_statuses_pkey PRIMARY KEY (id);


--
-- Name: rotation_statuses rotation_statuses_name_key; Type: CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.rotation_statuses
    ADD CONSTRAINT rotation_statuses_name_key UNIQUE (name);


--
-- Name: rotation_statuses rotation_statuses_pkey; Type: CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.rotation_statuses
    ADD CONSTRAINT rotation_statuses_pkey PRIMARY KEY (id);


--
-- Name: seed_varieties seed_varieties_name_key; Type: CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.seed_varieties
    ADD CONSTRAINT seed_varieties_name_key UNIQUE (name);


--
-- Name: seed_varieties seed_varieties_pkey; Type: CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.seed_varieties
    ADD CONSTRAINT seed_varieties_pkey PRIMARY KEY (id);


--
-- Name: soil_types soil_types_name_key; Type: CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.soil_types
    ADD CONSTRAINT soil_types_name_key UNIQUE (name);


--
-- Name: soil_types soil_types_pkey; Type: CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.soil_types
    ADD CONSTRAINT soil_types_pkey PRIMARY KEY (id);


--
-- Name: topography_types topography_types_name_key; Type: CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.topography_types
    ADD CONSTRAINT topography_types_name_key UNIQUE (name);


--
-- Name: topography_types topography_types_pkey; Type: CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.topography_types
    ADD CONSTRAINT topography_types_pkey PRIMARY KEY (id);


--
-- Name: tph_categories tph_categories_name_key; Type: CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.tph_categories
    ADD CONSTRAINT tph_categories_name_key UNIQUE (name);


--
-- Name: tph_categories tph_categories_pkey; Type: CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.tph_categories
    ADD CONSTRAINT tph_categories_pkey PRIMARY KEY (id);


--
-- Name: tree_categories tree_categories_name_key; Type: CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.tree_categories
    ADD CONSTRAINT tree_categories_name_key UNIQUE (name);


--
-- Name: tree_categories tree_categories_pkey; Type: CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.tree_categories
    ADD CONSTRAINT tree_categories_pkey PRIMARY KEY (id);


--
-- Name: value_aliases value_aliases_pkey; Type: CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.value_aliases
    ADD CONSTRAINT value_aliases_pkey PRIMARY KEY (ref_table, alias);


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
-- Name: menus_parent_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX menus_parent_id_idx ON auth.menus USING btree (parent_id);


--
-- Name: role_menus_menu_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX role_menus_menu_id_idx ON auth.role_menus USING btree (menu_id);


--
-- Name: role_permissions_permission_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX role_permissions_permission_id_idx ON auth.role_permissions USING btree (permission_id);


--
-- Name: ux_role_data_scopes_node; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX ux_role_data_scopes_node ON auth.role_data_scopes USING btree (role_id, group_id, area_id, company_id, estate_id, division_id) NULLS NOT DISTINCT;


--
-- Name: ux_roles_name_lower; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX ux_roles_name_lower ON auth.roles USING btree (lower((name)::text));


--
-- Name: estates_company_id_idx; Type: INDEX; Schema: master; Owner: -
--

CREATE INDEX estates_company_id_idx ON master.estates USING btree (company_id);


--
-- Name: ix_announcement_reads_announcement_id; Type: INDEX; Schema: master; Owner: -
--

CREATE INDEX ix_announcement_reads_announcement_id ON master.announcement_reads USING btree (announcement_id);


--
-- Name: ix_announcement_reads_user_id; Type: INDEX; Schema: master; Owner: -
--

CREATE INDEX ix_announcement_reads_user_id ON master.announcement_reads USING btree (user_id);


--
-- Name: ix_announcements_created_at; Type: INDEX; Schema: master; Owner: -
--

CREATE INDEX ix_announcements_created_at ON master.announcements USING btree (created_at DESC);


--
-- Name: ix_companies_group_id; Type: INDEX; Schema: master; Owner: -
--

CREATE INDEX ix_companies_group_id ON master.companies USING btree (group_id);


--
-- Name: ix_estates_area_id; Type: INDEX; Schema: master; Owner: -
--

CREATE INDEX ix_estates_area_id ON master.estates USING btree (area_id);


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
-- Name: menus audit_row; Type: TRIGGER; Schema: auth; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON auth.menus FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: permissions audit_row; Type: TRIGGER; Schema: auth; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON auth.permissions FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: role_data_scopes audit_row; Type: TRIGGER; Schema: auth; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON auth.role_data_scopes FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: role_menus audit_row; Type: TRIGGER; Schema: auth; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON auth.role_menus FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: role_permissions audit_row; Type: TRIGGER; Schema: auth; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON auth.role_permissions FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: roles audit_row; Type: TRIGGER; Schema: auth; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON auth.roles FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: users audit_row; Type: TRIGGER; Schema: auth; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON auth.users FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: menus audit_row_update; Type: TRIGGER; Schema: auth; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON auth.menus FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: permissions audit_row_update; Type: TRIGGER; Schema: auth; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON auth.permissions FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: role_data_scopes audit_row_update; Type: TRIGGER; Schema: auth; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON auth.role_data_scopes FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: role_menus audit_row_update; Type: TRIGGER; Schema: auth; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON auth.role_menus FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: role_permissions audit_row_update; Type: TRIGGER; Schema: auth; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON auth.role_permissions FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: roles audit_row_update; Type: TRIGGER; Schema: auth; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON auth.roles FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: users audit_row_update; Type: TRIGGER; Schema: auth; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON auth.users FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: menus audit_truncate; Type: TRIGGER; Schema: auth; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON auth.menus FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: permissions audit_truncate; Type: TRIGGER; Schema: auth; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON auth.permissions FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: role_data_scopes audit_truncate; Type: TRIGGER; Schema: auth; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON auth.role_data_scopes FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: role_menus audit_truncate; Type: TRIGGER; Schema: auth; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON auth.role_menus FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: role_permissions audit_truncate; Type: TRIGGER; Schema: auth; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON auth.role_permissions FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: roles audit_truncate; Type: TRIGGER; Schema: auth; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON auth.roles FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: users audit_truncate; Type: TRIGGER; Schema: auth; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON auth.users FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: areas audit_row; Type: TRIGGER; Schema: master; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON master.areas FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: blocks audit_row; Type: TRIGGER; Schema: master; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON master.blocks FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: companies audit_row; Type: TRIGGER; Schema: master; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON master.companies FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: divisions audit_row; Type: TRIGGER; Schema: master; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON master.divisions FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: estates audit_row; Type: TRIGGER; Schema: master; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON master.estates FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: areas audit_row_update; Type: TRIGGER; Schema: master; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON master.areas FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: blocks audit_row_update; Type: TRIGGER; Schema: master; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON master.blocks FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: companies audit_row_update; Type: TRIGGER; Schema: master; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON master.companies FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: divisions audit_row_update; Type: TRIGGER; Schema: master; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON master.divisions FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: estates audit_row_update; Type: TRIGGER; Schema: master; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON master.estates FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: areas audit_truncate; Type: TRIGGER; Schema: master; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON master.areas FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: blocks audit_truncate; Type: TRIGGER; Schema: master; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON master.blocks FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: companies audit_truncate; Type: TRIGGER; Schema: master; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON master.companies FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: divisions audit_truncate; Type: TRIGGER; Schema: master; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON master.divisions FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: estates audit_truncate; Type: TRIGGER; Schema: master; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON master.estates FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


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
-- Name: block_types audit_row; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON ref.block_types FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: planting_statuses audit_row; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON ref.planting_statuses FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: rotation_statuses audit_row; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON ref.rotation_statuses FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: seed_varieties audit_row; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON ref.seed_varieties FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: soil_types audit_row; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON ref.soil_types FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: topography_types audit_row; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON ref.topography_types FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: tph_categories audit_row; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON ref.tph_categories FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: tree_categories audit_row; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON ref.tree_categories FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: value_aliases audit_row; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON ref.value_aliases FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();


--
-- Name: block_types audit_row_update; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON ref.block_types FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: planting_statuses audit_row_update; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON ref.planting_statuses FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: rotation_statuses audit_row_update; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON ref.rotation_statuses FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: seed_varieties audit_row_update; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON ref.seed_varieties FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: soil_types audit_row_update; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON ref.soil_types FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: topography_types audit_row_update; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON ref.topography_types FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: tph_categories audit_row_update; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON ref.tph_categories FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: tree_categories audit_row_update; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON ref.tree_categories FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: value_aliases audit_row_update; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER audit_row_update AFTER UPDATE ON ref.value_aliases FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION audit.log_row_change();


--
-- Name: block_types audit_truncate; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON ref.block_types FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: planting_statuses audit_truncate; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON ref.planting_statuses FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: rotation_statuses audit_truncate; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON ref.rotation_statuses FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: seed_varieties audit_truncate; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON ref.seed_varieties FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: soil_types audit_truncate; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON ref.soil_types FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: topography_types audit_truncate; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON ref.topography_types FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: tph_categories audit_truncate; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON ref.tph_categories FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: tree_categories audit_truncate; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON ref.tree_categories FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


--
-- Name: value_aliases audit_truncate; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER audit_truncate AFTER TRUNCATE ON ref.value_aliases FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate();


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
-- Name: menus menus_parent_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.menus
    ADD CONSTRAINT menus_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES auth.menus(id) ON DELETE RESTRICT;


--
-- Name: role_data_scopes role_data_scopes_area_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.role_data_scopes
    ADD CONSTRAINT role_data_scopes_area_id_fkey FOREIGN KEY (area_id) REFERENCES master.areas(id);


--
-- Name: role_data_scopes role_data_scopes_company_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.role_data_scopes
    ADD CONSTRAINT role_data_scopes_company_id_fkey FOREIGN KEY (company_id) REFERENCES master.companies(id);


--
-- Name: role_data_scopes role_data_scopes_division_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.role_data_scopes
    ADD CONSTRAINT role_data_scopes_division_id_fkey FOREIGN KEY (division_id) REFERENCES master.divisions(id);


--
-- Name: role_data_scopes role_data_scopes_estate_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.role_data_scopes
    ADD CONSTRAINT role_data_scopes_estate_id_fkey FOREIGN KEY (estate_id) REFERENCES master.estates(id);


--
-- Name: role_data_scopes role_data_scopes_group_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.role_data_scopes
    ADD CONSTRAINT role_data_scopes_group_id_fkey FOREIGN KEY (group_id) REFERENCES master.groups(id) ON DELETE CASCADE;


--
-- Name: role_data_scopes role_data_scopes_role_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.role_data_scopes
    ADD CONSTRAINT role_data_scopes_role_id_fkey FOREIGN KEY (role_id) REFERENCES auth.roles(id) ON DELETE CASCADE;


--
-- Name: role_menus role_menus_menu_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.role_menus
    ADD CONSTRAINT role_menus_menu_id_fkey FOREIGN KEY (menu_id) REFERENCES auth.menus(id) ON DELETE CASCADE;


--
-- Name: role_menus role_menus_role_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.role_menus
    ADD CONSTRAINT role_menus_role_id_fkey FOREIGN KEY (role_id) REFERENCES auth.roles(id) ON DELETE CASCADE;


--
-- Name: role_permissions role_permissions_permission_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.role_permissions
    ADD CONSTRAINT role_permissions_permission_id_fkey FOREIGN KEY (permission_id) REFERENCES auth.permissions(id) ON DELETE CASCADE;


--
-- Name: role_permissions role_permissions_role_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.role_permissions
    ADD CONSTRAINT role_permissions_role_id_fkey FOREIGN KEY (role_id) REFERENCES auth.roles(id) ON DELETE CASCADE;


--
-- Name: user_roles user_roles_role_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.user_roles
    ADD CONSTRAINT user_roles_role_id_fkey FOREIGN KEY (role_id) REFERENCES auth.roles(id) ON DELETE RESTRICT;


--
-- Name: user_roles user_roles_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.user_roles
    ADD CONSTRAINT user_roles_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: announcement_reads announcement_reads_announcement_id_fkey; Type: FK CONSTRAINT; Schema: master; Owner: -
--

ALTER TABLE ONLY master.announcement_reads
    ADD CONSTRAINT announcement_reads_announcement_id_fkey FOREIGN KEY (announcement_id) REFERENCES master.announcements(id) ON DELETE CASCADE;


--
-- Name: announcement_reads announcement_reads_user_id_fkey; Type: FK CONSTRAINT; Schema: master; Owner: -
--

ALTER TABLE ONLY master.announcement_reads
    ADD CONSTRAINT announcement_reads_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: announcements announcements_created_by_fkey; Type: FK CONSTRAINT; Schema: master; Owner: -
--

ALTER TABLE ONLY master.announcements
    ADD CONSTRAINT announcements_created_by_fkey FOREIGN KEY (created_by) REFERENCES auth.users(id) ON DELETE SET NULL;


--
-- Name: blocks blocks_block_type_id_fkey; Type: FK CONSTRAINT; Schema: master; Owner: -
--

ALTER TABLE ONLY master.blocks
    ADD CONSTRAINT blocks_block_type_id_fkey FOREIGN KEY (block_type_id) REFERENCES ref.block_types(id);


--
-- Name: blocks blocks_division_id_fkey; Type: FK CONSTRAINT; Schema: master; Owner: -
--

ALTER TABLE ONLY master.blocks
    ADD CONSTRAINT blocks_division_id_fkey FOREIGN KEY (division_id) REFERENCES master.divisions(id);


--
-- Name: companies companies_group_id_fkey; Type: FK CONSTRAINT; Schema: master; Owner: -
--

ALTER TABLE ONLY master.companies
    ADD CONSTRAINT companies_group_id_fkey FOREIGN KEY (group_id) REFERENCES master.groups(id);


--
-- Name: divisions divisions_estate_id_fkey; Type: FK CONSTRAINT; Schema: master; Owner: -
--

ALTER TABLE ONLY master.divisions
    ADD CONSTRAINT divisions_estate_id_fkey FOREIGN KEY (estate_id) REFERENCES master.estates(id);


--
-- Name: estates estates_area_id_fkey; Type: FK CONSTRAINT; Schema: master; Owner: -
--

ALTER TABLE ONLY master.estates
    ADD CONSTRAINT estates_area_id_fkey FOREIGN KEY (area_id) REFERENCES master.areas(id);


--
-- Name: estates estates_company_id_fkey; Type: FK CONSTRAINT; Schema: master; Owner: -
--

ALTER TABLE ONLY master.estates
    ADD CONSTRAINT estates_company_id_fkey FOREIGN KEY (company_id) REFERENCES master.companies(id);


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

