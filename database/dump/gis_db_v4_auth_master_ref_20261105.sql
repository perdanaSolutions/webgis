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
-- Name: auth; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA auth;


--
-- Name: master; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA master;


--
-- Name: ref; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA ref;


--
-- Name: month_period; Type: DOMAIN; Schema: ref; Owner: -
--

CREATE DOMAIN ref.month_period AS date
	CONSTRAINT month_period_check CHECK ((VALUE = (date_trunc('month'::text, (VALUE)::timestamp with time zone))::date));


SET default_tablespace = '';

SET default_table_access_method = heap;

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
-- Data for Name: menus; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.menus (id, title, description, bg_class, icon_class, arrow_class, route, icon, order_position, parent_id, level, is_favorite) FROM stdin;
7a492664-a24b-41cd-b6fe-11b0501b993b	Dashboard	Peta Interaktif Blok Area	bg-[#4D392A]	text-white	text-white		statistik	0	\N	1	t
41e09784-9c0e-4228-8799-82edbc02394a	Blok Profile	Informasi Blok Profile	bg-[#638840]	text-white	text-[#638840]	/map	grafik	0	7a492664-a24b-41cd-b6fe-11b0501b993b	2	t
8667f078-1b71-488b-9492-0fba72037441	Setting	Setting Master Data	bg-[#638840]	text-white	text-[#638840]		setelan	2	\N	1	f
7f76ca82-2b79-481f-bcf1-0d1405f95b84	Menu Management	-	bg-[#4D392A]	text-white	text-[#4D392A]	/menus	modul	1	8667f078-1b71-488b-9492-0fba72037441	2	f
336ad581-e9fe-4e45-bb36-c20c3329f7b2	Upload Transaksi	Transaksi Areal Statement & Transaksi Rotasi	bg-[#638840]	text-white	text-[#638840]	/transaski	unggah	2	8667f078-1b71-488b-9492-0fba72037441	2	f
10e98ba6-949d-472d-b183-3d310af696de	Upload GeoJSON	Unggah data spasial GeoJSON (blok, TPH, sawit, jalan, dll) per periode	bg-[#4D392A]	text-white	text-[#4D392A]	/document	dokumen	4	8667f078-1b71-488b-9492-0fba72037441	2	t
373d2961-947c-4736-a229-42f82b6c43b3	Users Management	Management User TPTS	bg-[#4D392A]	text-white	text-[#4D392A]	/users	pengguna	0	8667f078-1b71-488b-9492-0fba72037441	2	f
4eb3fd6e-4918-4185-b7e3-0f92f0811334	Pengumuman	Management Pengumuman Untuk Semua User	bg-[#638840]	text-white	text-[#638840]	/pengumuman	pengumuman	5	8667f078-1b71-488b-9492-0fba72037441	2	f
\.


--
-- Data for Name: permissions; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.permissions (id, code, resource, action, description, created_at) FROM stdin;
ad43da12-464a-45e8-b46c-a184aab5db97	blok:read	blok	read	Melihat data blok	2026-07-04 07:05:17.744897+00
8eda6295-fb0a-42e5-adad-642b13bcf433	blok:write	blok	write	Menambah/mengubah data blok	2026-07-04 07:05:17.744897+00
664a64e6-3c1c-4102-ab6d-688dee5fd448	blok:delete	blok	delete	Menghapus data blok	2026-07-04 07:05:17.744897+00
923d51d4-dd7b-47d0-bca6-8edcc709ad21	produksi:read	produksi	read	Melihat data produksi	2026-07-04 07:05:17.744897+00
efd869cc-f634-4504-a05c-08baeb261722	produksi:write	produksi	write	Menginput data produksi	2026-07-04 07:05:17.744897+00
9ebc7236-6c37-4bd7-ac7d-a4829a08aafc	user:read	user	read	Melihat data user	2026-07-04 07:05:17.744897+00
40768285-03c8-4201-8142-51679b4976a0	user:write	user	write	Mengelola data user	2026-07-04 07:05:17.744897+00
a57a03c8-da07-4eca-acb1-d087e42b2505	upload:geojson	upload	geojson	Unggah, analisis, dan hapus per periode data spasial GeoJSON	2026-09-26 15:08:57.776698+00
b7889f42-0ee5-44ad-a82c-5f375f00dfb5	trx.area_statement_seed_varieties:read	trx.area_statement_seed_varieties	read	Akses baca tabel trx.area_statement_seed_varieties	2026-09-26 15:20:13.172764+00
ed97e547-471f-40ff-b17f-fde807440b49	trx.area_statements:read	trx.area_statements	read	Akses baca tabel trx.area_statements	2026-09-26 15:20:13.185317+00
e3c658f6-7ab5-4d95-bd33-49a64b28624b	trx.block_productions:read	trx.block_productions	read	Akses baca tabel trx.block_productions	2026-09-26 15:20:13.194963+00
bfc73224-a556-49e9-a998-f9727ef28cf8	trx.harvest_rotations:read	trx.harvest_rotations	read	Akses baca tabel trx.harvest_rotations	2026-09-26 15:20:13.205396+00
31894cc2-476e-4ff0-925e-0d0111b781a0	spatial.bridges:read	spatial.bridges	read	Akses baca tabel spatial.bridges	2026-09-27 16:18:49.163625+00
601a1f89-4f28-405e-b6f3-f0b420da8258	spatial.roads:read	spatial.roads	read	Akses baca tabel spatial.roads	2026-09-27 16:18:49.163299+00
4d1d22c9-f37b-41ed-87ad-e3dab88ab09c	spatial.block_boundaries:read	spatial.block_boundaries	read	Akses baca tabel spatial.block_boundaries	2026-09-27 16:18:49.168512+00
6f9c5302-1a1a-42cf-b08a-3f64076db727	spatial.drainage_points:read	spatial.drainage_points	read	Akses baca tabel spatial.drainage_points	2026-09-27 16:18:49.245016+00
efce489d-63f1-4b17-b783-9c52ac10f751	spatial.landuse_polygons:read	spatial.landuse_polygons	read	Akses baca tabel spatial.landuse_polygons	2026-09-27 16:18:49.37382+00
921f44a1-5b65-402e-99f1-37e2fff90837	spatial.tree_censuses:read	spatial.tree_censuses	read	Akses baca tabel spatial.tree_censuses	2026-09-27 16:18:49.37897+00
2e097ef4-3e12-4ab5-afe2-38fb7b9152ae	spatial.tph_points:read	spatial.tph_points	read	Akses baca tabel spatial.tph_points	2026-09-27 16:18:49.444712+00
70a3cb84-4734-4355-a7d1-eaf4fef0b4e0	spatial.slope_polygons:read	spatial.slope_polygons	read	Akses baca tabel spatial.slope_polygons	2026-09-27 16:18:49.451146+00
67693469-ef81-46e2-b127-0e58527e22cb	pengumuman:write	pengumuman	write	Tambah, ubah, dan hapus pengumuman	2026-10-08 06:05:14.103863+00
\.


--
-- Data for Name: role_data_scopes; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.role_data_scopes (id, role_id, area_id, company_id, estate_id, division_id, created_at, group_id) FROM stdin;
1	35c6109e-e73b-44b1-b796-77f1b26aaeda	\N	\N	\N	6	2026-09-26 15:20:13.384769+00	\N
2	35c6109e-e73b-44b1-b796-77f1b26aaeda	\N	\N	\N	8	2026-09-26 15:20:13.384769+00	\N
3	35c6109e-e73b-44b1-b796-77f1b26aaeda	\N	\N	\N	14	2026-09-26 15:20:13.384769+00	\N
4	35c6109e-e73b-44b1-b796-77f1b26aaeda	\N	\N	\N	26	2026-09-26 15:20:13.384769+00	\N
5	35c6109e-e73b-44b1-b796-77f1b26aaeda	\N	\N	\N	32	2026-09-26 15:20:13.384769+00	\N
6	35c6109e-e73b-44b1-b796-77f1b26aaeda	\N	\N	\N	46	2026-09-26 15:20:13.384769+00	\N
810	c9327d37-ea13-45de-bb8b-9b8a7855a47f	\N	\N	3	\N	2026-10-17 02:53:09.596931+00	\N
811	c9327d37-ea13-45de-bb8b-9b8a7855a47f	\N	\N	16	\N	2026-10-17 02:53:09.596931+00	\N
822	d86fa349-0225-449f-b5ea-a4b2b120c814	\N	2	\N	\N	2026-10-27 04:02:29.944059+00	\N
823	d86fa349-0225-449f-b5ea-a4b2b120c814	\N	9	\N	\N	2026-10-27 04:02:29.944059+00	\N
824	d86fa349-0225-449f-b5ea-a4b2b120c814	\N	1	\N	\N	2026-10-27 04:02:29.944059+00	\N
825	d86fa349-0225-449f-b5ea-a4b2b120c814	\N	3	\N	\N	2026-10-27 04:02:29.944059+00	\N
826	d86fa349-0225-449f-b5ea-a4b2b120c814	\N	6	\N	\N	2026-10-27 04:02:29.944059+00	\N
329	126cd6a8-4209-4813-a280-40f4b344c702	\N	\N	\N	8	2026-09-30 04:00:09.902086+00	\N
330	126cd6a8-4209-4813-a280-40f4b344c702	\N	\N	\N	9	2026-09-30 04:00:09.902086+00	\N
331	126cd6a8-4209-4813-a280-40f4b344c702	\N	\N	\N	10	2026-09-30 04:00:09.902086+00	\N
776	87d4f3e9-696b-495c-b8a9-6ef2a95c50ca	\N	\N	\N	8	2026-10-10 23:32:42.728296+00	\N
777	87d4f3e9-696b-495c-b8a9-6ef2a95c50ca	\N	\N	\N	9	2026-10-10 23:32:42.728296+00	\N
778	87d4f3e9-696b-495c-b8a9-6ef2a95c50ca	\N	\N	\N	10	2026-10-10 23:32:42.728296+00	\N
739	c08fffe2-dbc2-4744-8441-bfca63e78f98	\N	\N	\N	71	2026-10-01 13:12:08.927771+00	\N
740	c08fffe2-dbc2-4744-8441-bfca63e78f98	\N	\N	\N	72	2026-10-01 13:12:08.927771+00	\N
741	c08fffe2-dbc2-4744-8441-bfca63e78f98	\N	\N	\N	73	2026-10-01 13:12:08.927771+00	\N
742	c08fffe2-dbc2-4744-8441-bfca63e78f98	\N	\N	\N	74	2026-10-01 13:12:08.927771+00	\N
743	c08fffe2-dbc2-4744-8441-bfca63e78f98	\N	\N	\N	75	2026-10-01 13:12:08.927771+00	\N
744	c08fffe2-dbc2-4744-8441-bfca63e78f98	\N	\N	\N	76	2026-10-01 13:12:08.927771+00	\N
745	c08fffe2-dbc2-4744-8441-bfca63e78f98	\N	\N	\N	77	2026-10-01 13:12:08.927771+00	\N
746	c08fffe2-dbc2-4744-8441-bfca63e78f98	\N	\N	\N	78	2026-10-01 13:12:08.927771+00	\N
747	c08fffe2-dbc2-4744-8441-bfca63e78f98	\N	\N	\N	79	2026-10-01 13:12:08.927771+00	\N
748	c08fffe2-dbc2-4744-8441-bfca63e78f98	\N	\N	\N	80	2026-10-01 13:12:08.927771+00	\N
749	c08fffe2-dbc2-4744-8441-bfca63e78f98	\N	\N	\N	81	2026-10-01 13:12:08.927771+00	\N
750	c08fffe2-dbc2-4744-8441-bfca63e78f98	\N	\N	\N	82	2026-10-01 13:12:08.927771+00	\N
751	c08fffe2-dbc2-4744-8441-bfca63e78f98	\N	\N	\N	83	2026-10-01 13:12:08.927771+00	\N
752	c08fffe2-dbc2-4744-8441-bfca63e78f98	\N	\N	\N	84	2026-10-01 13:12:08.927771+00	\N
753	c08fffe2-dbc2-4744-8441-bfca63e78f98	\N	\N	\N	85	2026-10-01 13:12:08.927771+00	\N
754	c08fffe2-dbc2-4744-8441-bfca63e78f98	\N	\N	\N	86	2026-10-01 13:12:08.927771+00	\N
755	c08fffe2-dbc2-4744-8441-bfca63e78f98	\N	\N	\N	87	2026-10-01 13:12:08.927771+00	\N
820	57692e61-bab0-4d6a-986f-d5741349842d	\N	\N	\N	\N	2026-10-26 08:07:13.411878+00	2
821	57692e61-bab0-4d6a-986f-d5741349842d	\N	\N	\N	\N	2026-10-26 08:07:13.411878+00	1
\.


--
-- Data for Name: role_menus; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.role_menus (role_id, menu_id, created_at) FROM stdin;
35c6109e-e73b-44b1-b796-77f1b26aaeda	10e98ba6-949d-472d-b183-3d310af696de	2026-09-26 15:20:13.146554+00
126cd6a8-4209-4813-a280-40f4b344c702	7a492664-a24b-41cd-b6fe-11b0501b993b	2026-09-30 04:00:09.902086+00
c08fffe2-dbc2-4744-8441-bfca63e78f98	7a492664-a24b-41cd-b6fe-11b0501b993b	2026-10-01 13:12:08.927771+00
c08fffe2-dbc2-4744-8441-bfca63e78f98	41e09784-9c0e-4228-8799-82edbc02394a	2026-10-01 13:12:08.927771+00
87d4f3e9-696b-495c-b8a9-6ef2a95c50ca	7a492664-a24b-41cd-b6fe-11b0501b993b	2026-10-10 23:32:42.728296+00
87d4f3e9-696b-495c-b8a9-6ef2a95c50ca	41e09784-9c0e-4228-8799-82edbc02394a	2026-10-10 23:32:42.728296+00
c9327d37-ea13-45de-bb8b-9b8a7855a47f	7a492664-a24b-41cd-b6fe-11b0501b993b	2026-10-17 02:53:09.596931+00
c9327d37-ea13-45de-bb8b-9b8a7855a47f	41e09784-9c0e-4228-8799-82edbc02394a	2026-10-17 02:53:09.596931+00
57692e61-bab0-4d6a-986f-d5741349842d	7a492664-a24b-41cd-b6fe-11b0501b993b	2026-10-26 08:07:13.411878+00
57692e61-bab0-4d6a-986f-d5741349842d	41e09784-9c0e-4228-8799-82edbc02394a	2026-10-26 08:07:13.411878+00
57692e61-bab0-4d6a-986f-d5741349842d	8667f078-1b71-488b-9492-0fba72037441	2026-10-26 08:07:13.411878+00
57692e61-bab0-4d6a-986f-d5741349842d	373d2961-947c-4736-a229-42f82b6c43b3	2026-10-26 08:07:13.411878+00
57692e61-bab0-4d6a-986f-d5741349842d	10e98ba6-949d-472d-b183-3d310af696de	2026-10-26 08:07:13.411878+00
57692e61-bab0-4d6a-986f-d5741349842d	7f76ca82-2b79-481f-bcf1-0d1405f95b84	2026-10-26 08:07:13.411878+00
57692e61-bab0-4d6a-986f-d5741349842d	4eb3fd6e-4918-4185-b7e3-0f92f0811334	2026-10-26 08:07:13.411878+00
57692e61-bab0-4d6a-986f-d5741349842d	336ad581-e9fe-4e45-bb36-c20c3329f7b2	2026-10-26 08:07:13.411878+00
\.


--
-- Data for Name: role_permissions; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.role_permissions (role_id, permission_id, created_at) FROM stdin;
57692e61-bab0-4d6a-986f-d5741349842d	efd869cc-f634-4504-a05c-08baeb261722	2026-07-04 07:05:17.782421+00
57692e61-bab0-4d6a-986f-d5741349842d	ad43da12-464a-45e8-b46c-a184aab5db97	2026-07-04 07:05:17.782421+00
57692e61-bab0-4d6a-986f-d5741349842d	9ebc7236-6c37-4bd7-ac7d-a4829a08aafc	2026-07-04 07:05:17.782421+00
57692e61-bab0-4d6a-986f-d5741349842d	8eda6295-fb0a-42e5-adad-642b13bcf433	2026-07-04 07:05:17.782421+00
57692e61-bab0-4d6a-986f-d5741349842d	40768285-03c8-4201-8142-51679b4976a0	2026-07-04 07:05:17.782421+00
57692e61-bab0-4d6a-986f-d5741349842d	664a64e6-3c1c-4102-ab6d-688dee5fd448	2026-07-04 07:05:17.782421+00
57692e61-bab0-4d6a-986f-d5741349842d	923d51d4-dd7b-47d0-bca6-8edcc709ad21	2026-07-04 07:05:17.782421+00
35c6109e-e73b-44b1-b796-77f1b26aaeda	a57a03c8-da07-4eca-acb1-d087e42b2505	2026-09-26 15:08:57.776698+00
35c6109e-e73b-44b1-b796-77f1b26aaeda	b7889f42-0ee5-44ad-a82c-5f375f00dfb5	2026-09-26 15:20:13.172764+00
35c6109e-e73b-44b1-b796-77f1b26aaeda	ed97e547-471f-40ff-b17f-fde807440b49	2026-09-26 15:20:13.185317+00
35c6109e-e73b-44b1-b796-77f1b26aaeda	e3c658f6-7ab5-4d95-bd33-49a64b28624b	2026-09-26 15:20:13.194963+00
35c6109e-e73b-44b1-b796-77f1b26aaeda	bfc73224-a556-49e9-a998-f9727ef28cf8	2026-09-26 15:20:13.205396+00
35c6109e-e73b-44b1-b796-77f1b26aaeda	ad43da12-464a-45e8-b46c-a184aab5db97	2026-09-26 15:20:21.882967+00
35c6109e-e73b-44b1-b796-77f1b26aaeda	8eda6295-fb0a-42e5-adad-642b13bcf433	2026-09-26 15:20:21.882967+00
35c6109e-e73b-44b1-b796-77f1b26aaeda	923d51d4-dd7b-47d0-bca6-8edcc709ad21	2026-09-26 15:20:21.882967+00
35c6109e-e73b-44b1-b796-77f1b26aaeda	efd869cc-f634-4504-a05c-08baeb261722	2026-09-26 15:20:21.882967+00
35c6109e-e73b-44b1-b796-77f1b26aaeda	9ebc7236-6c37-4bd7-ac7d-a4829a08aafc	2026-09-26 15:20:21.882967+00
35c6109e-e73b-44b1-b796-77f1b26aaeda	40768285-03c8-4201-8142-51679b4976a0	2026-09-26 15:20:21.882967+00
126cd6a8-4209-4813-a280-40f4b344c702	31894cc2-476e-4ff0-925e-0d0111b781a0	2026-09-30 04:00:09.902086+00
126cd6a8-4209-4813-a280-40f4b344c702	601a1f89-4f28-405e-b6f3-f0b420da8258	2026-09-30 04:00:09.902086+00
126cd6a8-4209-4813-a280-40f4b344c702	4d1d22c9-f37b-41ed-87ad-e3dab88ab09c	2026-09-30 04:00:09.902086+00
126cd6a8-4209-4813-a280-40f4b344c702	6f9c5302-1a1a-42cf-b08a-3f64076db727	2026-09-30 04:00:09.902086+00
126cd6a8-4209-4813-a280-40f4b344c702	efce489d-63f1-4b17-b783-9c52ac10f751	2026-09-30 04:00:09.902086+00
126cd6a8-4209-4813-a280-40f4b344c702	921f44a1-5b65-402e-99f1-37e2fff90837	2026-09-30 04:00:09.902086+00
126cd6a8-4209-4813-a280-40f4b344c702	2e097ef4-3e12-4ab5-afe2-38fb7b9152ae	2026-09-30 04:00:09.902086+00
126cd6a8-4209-4813-a280-40f4b344c702	70a3cb84-4734-4355-a7d1-eaf4fef0b4e0	2026-09-30 04:00:09.902086+00
c08fffe2-dbc2-4744-8441-bfca63e78f98	e3c658f6-7ab5-4d95-bd33-49a64b28624b	2026-10-01 13:12:08.927771+00
c08fffe2-dbc2-4744-8441-bfca63e78f98	4d1d22c9-f37b-41ed-87ad-e3dab88ab09c	2026-10-01 13:12:08.927771+00
c08fffe2-dbc2-4744-8441-bfca63e78f98	2e097ef4-3e12-4ab5-afe2-38fb7b9152ae	2026-10-01 13:12:08.927771+00
35c6109e-e73b-44b1-b796-77f1b26aaeda	67693469-ef81-46e2-b127-0e58527e22cb	2026-10-08 06:05:14.121323+00
87d4f3e9-696b-495c-b8a9-6ef2a95c50ca	ed97e547-471f-40ff-b17f-fde807440b49	2026-10-10 23:32:42.728296+00
87d4f3e9-696b-495c-b8a9-6ef2a95c50ca	4d1d22c9-f37b-41ed-87ad-e3dab88ab09c	2026-10-10 23:32:42.728296+00
87d4f3e9-696b-495c-b8a9-6ef2a95c50ca	70a3cb84-4734-4355-a7d1-eaf4fef0b4e0	2026-10-10 23:32:42.728296+00
c9327d37-ea13-45de-bb8b-9b8a7855a47f	bfc73224-a556-49e9-a998-f9727ef28cf8	2026-10-17 02:53:09.596931+00
c9327d37-ea13-45de-bb8b-9b8a7855a47f	4d1d22c9-f37b-41ed-87ad-e3dab88ab09c	2026-10-17 02:53:09.596931+00
c9327d37-ea13-45de-bb8b-9b8a7855a47f	921f44a1-5b65-402e-99f1-37e2fff90837	2026-10-17 02:53:09.596931+00
c9327d37-ea13-45de-bb8b-9b8a7855a47f	2e097ef4-3e12-4ab5-afe2-38fb7b9152ae	2026-10-17 02:53:09.596931+00
57692e61-bab0-4d6a-986f-d5741349842d	ed97e547-471f-40ff-b17f-fde807440b49	2026-10-26 08:07:13.411878+00
57692e61-bab0-4d6a-986f-d5741349842d	e3c658f6-7ab5-4d95-bd33-49a64b28624b	2026-10-26 08:07:13.411878+00
57692e61-bab0-4d6a-986f-d5741349842d	bfc73224-a556-49e9-a998-f9727ef28cf8	2026-10-26 08:07:13.411878+00
57692e61-bab0-4d6a-986f-d5741349842d	31894cc2-476e-4ff0-925e-0d0111b781a0	2026-10-26 08:07:13.411878+00
57692e61-bab0-4d6a-986f-d5741349842d	601a1f89-4f28-405e-b6f3-f0b420da8258	2026-10-26 08:07:13.411878+00
57692e61-bab0-4d6a-986f-d5741349842d	4d1d22c9-f37b-41ed-87ad-e3dab88ab09c	2026-10-26 08:07:13.411878+00
57692e61-bab0-4d6a-986f-d5741349842d	6f9c5302-1a1a-42cf-b08a-3f64076db727	2026-10-26 08:07:13.411878+00
57692e61-bab0-4d6a-986f-d5741349842d	efce489d-63f1-4b17-b783-9c52ac10f751	2026-10-26 08:07:13.411878+00
57692e61-bab0-4d6a-986f-d5741349842d	921f44a1-5b65-402e-99f1-37e2fff90837	2026-10-26 08:07:13.411878+00
57692e61-bab0-4d6a-986f-d5741349842d	2e097ef4-3e12-4ab5-afe2-38fb7b9152ae	2026-10-26 08:07:13.411878+00
57692e61-bab0-4d6a-986f-d5741349842d	70a3cb84-4734-4355-a7d1-eaf4fef0b4e0	2026-10-26 08:07:13.411878+00
d86fa349-0225-449f-b5ea-a4b2b120c814	ed97e547-471f-40ff-b17f-fde807440b49	2026-10-27 04:02:29.944059+00
d86fa349-0225-449f-b5ea-a4b2b120c814	4d1d22c9-f37b-41ed-87ad-e3dab88ab09c	2026-10-27 04:02:29.944059+00
\.


--
-- Data for Name: roles; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.roles (id, name, description, created_at) FROM stdin;
35c6109e-e73b-44b1-b796-77f1b26aaeda	admin	Kelola user & data, scope area tertentu	2026-07-04 07:05:17.771044+00
57692e61-bab0-4d6a-986f-d5741349842d	superadmin	AKSES PENUH SEMUA FITUR & SEMUA AREA	2026-07-04 07:05:17.771044+00
126cd6a8-4209-4813-a280-40f4b344c702	EM BTE	USER EM BTE	2026-09-30 04:00:09.902086+00
c9327d37-ea13-45de-bb8b-9b8a7855a47f	berau 1 staff 2	MANAGE ESTATE BERAU	2026-09-28 01:20:05.884361+00
87d4f3e9-696b-495c-b8a9-6ef2a95c50ca	berau 1 staff 1	MANAGE ESTATE	2026-09-28 01:19:12.886556+00
c08fffe2-dbc2-4744-8441-bfca63e78f98	berau 1 staff 3	MANAGE ESTATE BERAU	2026-09-30 17:35:09.874137+00
d86fa349-0225-449f-b5ea-a4b2b120c814	berau 1 staff 4	--	2026-10-02 05:19:15.194441+00
\.


--
-- Data for Name: user_roles; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.user_roles (user_id, role_id, created_at) FROM stdin;
34a9b928-fdf5-493e-be96-31f26dabe38a	57692e61-bab0-4d6a-986f-d5741349842d	2026-09-26 22:53:37.372642+00
df17cfc4-d204-4726-8485-a44fdf902909	35c6109e-e73b-44b1-b796-77f1b26aaeda	2026-09-26 22:53:37.372642+00
5a1cef4a-1d09-4c79-92eb-fa67c0871ca1	87d4f3e9-696b-495c-b8a9-6ef2a95c50ca	2026-09-28 01:20:49.265788+00
8b6b6977-2df1-402b-81db-aabdaed58df8	126cd6a8-4209-4813-a280-40f4b344c702	2026-09-30 04:01:00.560757+00
6d7f3d16-311a-4fb9-be96-8681a39f2b1f	d86fa349-0225-449f-b5ea-a4b2b120c814	2026-10-02 05:21:47.051009+00
5a1cef4a-1d09-4c79-92eb-fa67c0871ca1	c9327d37-ea13-45de-bb8b-9b8a7855a47f	2026-10-11 00:56:28.048596+00
1ca1c58c-a4e1-4a5f-aba1-af9b07304438	87d4f3e9-696b-495c-b8a9-6ef2a95c50ca	2026-10-26 02:28:25.682332+00
a18af0c2-2f4b-471e-9da7-dad31d9934a9	87d4f3e9-696b-495c-b8a9-6ef2a95c50ca	2026-10-27 23:33:54.850838+00
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.users (id, full_name, username, email, hashed_password, is_active, created_at, is_service_account, token_expires_at, token_version, failed_login_attempts, locked_at) FROM stdin;
df17cfc4-d204-4726-8485-a44fdf902909	Admin Kebun	admin.kebun	admin.kebun@plantation.com	$2b$12$ud0d1P479QHfDeTpmgyhU.j4cpCIh4GJtsANS/UnLZGOvCp7yaYAK	t	2026-09-26 15:20:13.475413+00	f	\N	1	0	\N
8b6b6977-2df1-402b-81db-aabdaed58df8	EM_BTE	em_bte	embte@plantation.com	$2b$12$ZwEzkJz01NU0FYy5qZmPQe4t0qoBFXCEPwLIAmSrw35hvOcbpHpMK	t	2026-09-30 04:01:00.560757+00	f	\N	1	0	\N
a18af0c2-2f4b-471e-9da7-dad31d9934a9	Bayu Hardiansyah	bayu	bayuhardiansyah73@teladanprima.com	$2b$12$C82YaX.NnMxInbgsyPYMke9ZBHyXxr8HXQEFP9tJplPe/mVJ6B.fm	t	2026-10-27 23:33:54.850838+00	f	\N	1	0	\N
34a9b928-fdf5-493e-be96-31f26dabe38a	Super Administrator	superadmin	superadmin@plantation.com	$2b$12$WqFO47QbprxydAsyExb.PO4mVa3vEl/GZXR81ob/k9tc59PA0qj.i	t	2026-07-04 07:07:22.881929+00	f	\N	1	0	\N
5a1cef4a-1d09-4c79-92eb-fa67c0871ca1	Berau Staff 1	staff berau 1	berau1@mail.id	$2b$12$zzYSSAL6QOEmlmiZ81aTWudGECjKxIH6NvogS0fwWD/DEFSiNG3je	t	2026-09-28 01:20:49.265788+00	f	\N	1	0	\N
1ca1c58c-a4e1-4a5f-aba1-af9b07304438	Kutim Satu	kutim satu	kutim1@plantation.com	$2b$12$Tiu/arv13lzkesF/IEZTj.EmLOzG9y9KdjTjRy3aRx8zqa720NF8a	t	2026-10-26 02:28:25.682332+00	f	\N	1	0	\N
6d7f3d16-311a-4fb9-be96-8681a39f2b1f	Staff 4 Berau 1 (Delete nanti)	staff4.berau1	staff4berau1@plantation.com	$2b$12$b6FZt1bUzXCweJtZTkOlIO7LgGCoeluO101XGRfd5pLx6tgHrg.je	t	2026-10-02 05:21:47.051009+00	f	\N	1	0	\N
\.


--
-- Data for Name: announcement_reads; Type: TABLE DATA; Schema: master; Owner: -
--

COPY master.announcement_reads (id, user_id, announcement_id, read_at) FROM stdin;
ec2370ba-2ee6-4627-8bce-846b6e26b110	34a9b928-fdf5-493e-be96-31f26dabe38a	9c0ab316-b383-4ad3-914e-ffbab273181c	2026-10-26 20:25:14.945107+00
d37c1e39-3bf3-4532-8d0f-f5c8e6f88a56	34a9b928-fdf5-493e-be96-31f26dabe38a	26826c95-af1e-4256-9a40-61ca871107c0	2026-10-26 20:25:18.00358+00
9254f06a-5b92-4721-ab7c-ceb21c19422d	5a1cef4a-1d09-4c79-92eb-fa67c0871ca1	26826c95-af1e-4256-9a40-61ca871107c0	2026-10-26 23:16:45.523983+00
\.


--
-- Data for Name: announcements; Type: TABLE DATA; Schema: master; Owner: -
--

COPY master.announcements (id, title, content, is_active, start_at, end_at, created_by, created_at, updated_at) FROM stdin;
f5b1720d-65e0-4e50-a7c5-ed9532afd1e8	Pengumuman	Diberitahukan kepada seluruh karyawan bahwa jam 14:00 akan di adakan meeting online	t	2026-10-15 17:00:00+00	2026-10-16 16:00:00+00	34a9b928-fdf5-493e-be96-31f26dabe38a	2026-10-08 06:13:31.856935+00	2026-10-13 13:33:23.317333+00
9c0ab316-b383-4ad3-914e-ffbab273181c	Data Update	Data akan update pada bulan November 2026, jam 12:00 \nData akan update pada bulan November 2026, jam 12:00 \nData akan update pada bulan November 2026, jam 12:00 \nData akan update pada bulan November 2026, jam 12:00 \nData akan update pada bulan November 2026, jam 12:00 Data akan update pada bulan November 2026, jam 12:00 Data akan update pada bulan November 2026, jam 12:00 Data akan update pada bulan November 2026, jam 12:00	t	2026-10-26 03:17:00+00	2026-11-30 03:17:00+00	34a9b928-fdf5-493e-be96-31f26dabe38a	2026-10-26 03:17:27.213314+00	2026-10-26 03:18:12.761799+00
189295ed-3fe5-4492-b385-aa8d62f05a90	Pengumuman Minggu Depan	Pengumuman Minggu Depan	t	2026-11-02 03:25:00+00	2026-11-07 03:25:00+00	34a9b928-fdf5-493e-be96-31f26dabe38a	2026-10-26 03:25:39.82658+00	2026-10-26 03:25:39.82658+00
b251a62b-923b-47b2-ba29-9f881b10092b	Pengumuman Lewat Tanggal	Pengumuman Lewat Tanggal	t	2026-10-12 03:26:00+00	2026-10-13 03:26:00+00	34a9b928-fdf5-493e-be96-31f26dabe38a	2026-10-26 03:27:00.285083+00	2026-10-26 03:27:00.285083+00
26826c95-af1e-4256-9a40-61ca871107c0	Perbaikan website	Besok website tidak bisa diakses karena ada perbaikan	t	2026-10-25 13:37:00+00	2026-10-30 13:37:00+00	34a9b928-fdf5-493e-be96-31f26dabe38a	2026-10-13 13:37:15.586258+00	2026-10-26 03:29:48.585891+00
\.


--
-- Data for Name: app_settings; Type: TABLE DATA; Schema: master; Owner: -
--

COPY master.app_settings (key, value, description, updated_at, updated_by) FROM stdin;
maintenance_message		Pesan tambahan di halaman maintenance (kosong = pesan bawaan).	2026-10-27 02:08:46.312324+00	\N
maintenance_mode	false	true = website menampilkan halaman "Website Sedang Dalam Perbaikan" dan API menolak request (503).	2026-10-27 02:08:46.312324+00	\N
\.


--
-- Data for Name: areas; Type: TABLE DATA; Schema: master; Owner: -
--

COPY master.areas (id, code, name) FROM stdin;
1	BERAU	BERAU
2	BERAU2	BERAU2
3	KUKAR	KUKAR
4	KUTIM1	KUTIM1
5	KUTIM2	KUTIM2
6	KUTIM3	KUTIM3
7	KUTIM4	KUTIM4
8	PASER	PASER
\.


--
-- Data for Name: blocks; Type: TABLE DATA; Schema: master; Owner: -
--

COPY master.blocks (id, division_id, code, block_type_id) FROM stdin;
1	1	F016	1
2	1	G007	1
3	1	G008	1
4	1	G009	1
5	1	G010	1
6	1	G011	1
7	1	G012	1
8	1	G013	1
9	1	G014	1
10	1	G015	1
11	1	H006	1
12	1	H007	1
13	1	H008	1
14	1	H009	1
15	1	H010	1
16	1	H011	1
17	1	H012	1
18	1	H013	1
19	1	H014	1
20	1	I009	1
21	1	I010	1
22	1	I011	1
23	1	I012	1
24	1	I013	1
25	1	I014	1
26	1	I015	1
27	1	J009	1
28	1	J010	1
29	1	J011	1
30	1	J012	1
31	1	J013	1
32	1	J014	1
33	1	J015	1
34	1	K012	1
35	1	K013	1
36	2	F017	1
37	2	F018	1
38	2	F019	1
39	2	F020	1
40	2	F021	1
41	2	F022	1
42	2	F023	1
43	2	G016	1
44	2	G019	1
45	2	G020	1
46	2	G021	1
47	2	G022	1
48	2	G023	1
49	2	H015	1
50	2	H016	1
51	2	H017	1
52	2	H018	1
53	2	H019	1
54	2	H020	1
55	2	H021	1
56	2	H022	1
57	2	H023	1
58	2	I016	1
59	2	I017	1
60	2	I018	1
61	2	I019	1
62	2	I020	1
63	2	I021	1
64	2	I022	1
65	2	I023	1
66	2	I024	1
67	2	J016	1
68	3	E025	1
69	3	E026	1
70	3	E027	1
71	3	E028	1
72	3	E029	1
73	3	E030	1
74	3	F024	1
75	3	F025	1
76	3	F026	1
77	3	F027	1
78	3	F028	1
79	3	F029	1
80	3	F030	1
81	3	G024	1
82	3	G025	1
83	3	G026	1
84	3	G027	1
85	3	G028	1
86	3	H024	1
87	3	H025	1
88	3	H026	1
89	3	H027	1
90	3	H028	1
91	3	H029	1
92	3	H030	1
93	3	H031	1
94	3	H032	1
95	3	H033	1
96	3	I025	1
97	3	I026	1
98	3	I027	1
99	3	I028	1
100	4	E031	1
101	4	E032	1
102	4	E033	1
103	4	E034	1
104	4	F031	1
105	4	F032	1
106	4	F033	1
107	4	F034	1
108	4	F035	1
109	4	F036	1
110	4	F037	1
111	4	F038	1
112	4	F039	1
113	4	F040	1
114	4	F041	1
115	4	F042	1
116	4	F043	1
117	4	G031	1
118	4	G032	1
119	4	G033	1
120	4	G034	1
121	4	G035	1
122	4	G036	1
123	4	G037	1
124	4	G038	1
125	4	G039	1
126	4	G040	1
127	4	G041	1
128	4	G042	1
129	4	H034	1
130	4	H035	1
131	4	H036	1
132	4	H037	1
133	5	C043	1
134	5	C044	1
135	5	D030	1
136	5	D031	1
137	5	D032	1
138	5	D033	1
139	5	D034	1
140	5	D035	1
141	5	D036	1
142	5	D037	1
143	5	D038	1
144	5	D039	1
145	5	D040	1
146	5	D041	1
147	5	D042	1
148	5	D043	1
149	5	D044	1
150	5	D045	1
151	5	D046	1
152	5	D047	1
153	5	E035	1
154	5	E036	1
155	5	E037	1
156	5	E038	1
157	5	E039	1
158	5	E040	1
159	5	E041	1
160	5	E042	1
161	5	E043	1
162	5	E044	1
163	5	E045	1
164	5	E046	1
165	5	E047	1
166	6	B046	1
167	6	B047	1
168	6	B048	1
169	6	B049	1
170	6	B050	1
171	6	B051	1
172	6	B052	1
173	6	C046	1
174	6	C047	1
175	6	C048	1
176	6	C049	1
177	6	C050	1
178	6	C051	1
179	6	C052	1
180	6	C053	1
181	6	C054	1
182	6	D048	1
183	6	D049	1
184	6	D050	1
185	6	D051	1
186	6	D052	1
187	6	D053	1
188	6	D054	1
189	6	D055	1
190	6	E048	1
191	6	E049	1
192	6	E050	1
193	6	E051	1
194	6	E052	1
195	6	E053	1
196	6	F050	1
197	7	B116	1
198	7	B117	1
199	7	B119	1
200	7	B120	1
201	7	B121	1
202	7	B122	1
203	7	B123	1
204	7	B124	1
205	7	B125	1
206	7	B126	1
207	7	C116	1
208	7	C117	1
209	7	C118	1
210	7	C119	1
211	7	C120	1
212	7	C121	1
213	7	C122	1
214	7	C123	1
215	7	D115	1
216	7	D116	1
217	7	D117	1
218	7	D118	1
219	7	D119	1
220	7	D120	1
221	7	D121	1
222	7	D122	1
223	7	D136	1
224	7	D139	1
225	7	E125	1
226	7	E131	1
227	7	E132	1
228	7	E133	1
229	7	E134	1
230	7	E135	1
231	7	E136	1
232	7	E137	1
233	7	F132	1
234	8	B013	1
235	8	C013	1
236	8	C014	1
237	8	C015	1
238	8	C016	1
239	8	C017	1
240	8	C018	1
241	8	C019	1
242	8	C020	1
243	8	D013	1
244	8	D014	1
245	8	D015	1
246	8	D016	1
247	8	D017	1
248	8	D018	1
249	8	D019	1
250	8	D020	1
251	8	D021	1
252	8	D028	1
253	8	E013	1
254	8	E014	1
255	8	E015	1
256	8	E016	1
257	8	E018	1
258	8	E019	1
259	8	E027	1
260	8	E028	1
261	8	E029	1
262	8	F027	1
263	8	F028	1
264	9	B003	1
265	9	B006	1
266	9	B008	1
267	9	B010	1
268	9	B012	1
269	9	C002	1
270	9	C003	1
271	9	C004	1
272	9	C005	1
273	9	C006	1
274	9	C007	1
275	9	C008	1
276	9	C010	1
277	9	C011	1
278	9	C012	1
279	9	D005	1
280	9	D008	1
281	9	D009	1
282	9	D010	1
283	9	D011	1
284	9	D012	1
285	10	C057	1
286	10	C059	1
287	10	C062	1
288	10	C063	1
289	10	C064	1
290	10	C065	1
291	10	C068	1
292	10	D058	1
293	10	D059	1
294	10	D060	1
295	10	D061	1
296	10	D062	1
297	10	D063	1
298	10	D064	1
299	10	D065	1
300	10	D066	1
301	10	D067	1
302	10	D068	1
303	10	D069	1
304	10	D070	1
305	10	D071	1
306	10	D072	1
307	10	D073	1
308	10	E063	1
309	10	H106	1
310	10	H107	1
311	10	H108	1
312	10	H109	1
313	10	I102	1
314	10	I103	1
315	10	I104	1
316	10	I105	1
317	10	I106	1
318	10	I107	1
319	10	I108	1
320	10	I109	1
321	11	C012	1
322	11	C013	1
323	11	C014	1
324	11	C015	1
325	11	C016	1
326	11	C017	1
327	11	C018	1
328	11	C019	1
329	11	C020	1
330	11	C021	1
331	11	C036	1
332	11	C041	1
333	11	C044	1
334	11	C045	1
335	11	D012	1
336	11	D014	1
337	11	D015	1
338	11	D017	1
339	11	D026	1
340	11	D027	1
341	11	D043	1
342	11	D044	1
343	11	D045	1
344	11	E012	1
345	11	E013	1
346	11	E015	1
347	11	E017	1
348	11	E018	1
349	11	E019	1
350	11	E020	1
351	11	E021	1
352	11	E026	1
353	12	A009	1
354	12	A010	1
355	12	A011	1
356	12	A012	1
357	12	A013	1
358	12	A014	1
359	12	A015	1
360	12	A016	1
361	12	A018	1
362	12	A019	1
363	12	A020	1
364	12	A021	1
365	12	B008	1
366	12	B009	1
367	12	B010	1
368	12	B011	1
369	12	B012	1
370	12	B013	1
371	12	B014	1
372	12	B015	1
373	12	B016	1
374	12	B017	1
375	12	B018	1
376	12	B019	1
377	12	B020	1
378	12	B021	1
379	13	F007	1
380	13	F008	1
381	13	F009	1
382	13	F010	1
383	13	F012	1
384	13	F013	1
385	13	F014	1
386	13	G007	1
387	13	G008	1
388	13	G009	1
389	13	G010	1
390	13	G013	1
391	13	G014	1
392	13	H007	1
393	13	H008	1
394	13	H009	1
395	13	H010	1
396	13	H011	1
397	13	H012	1
398	13	H013	1
399	13	I009	1
400	13	I010	1
401	13	I011	1
402	13	I012	1
403	13	I013	1
404	14	F015	1
405	14	F016	1
406	14	F017	1
407	14	F018	1
408	14	F019	1
409	14	G015	1
410	14	G016	1
411	14	G017	1
412	14	G018	1
413	14	G019	1
414	14	H014	1
415	14	H015	1
416	14	H016	1
417	14	H017	1
418	14	H018	1
419	14	H019	1
420	14	I014	1
421	14	I015	1
422	14	I016	1
423	14	I017	1
424	14	I018	1
425	14	I019	1
426	15	B022	1
427	15	B023	1
428	15	C018	1
429	15	C019	1
430	15	C020	1
431	15	C021	1
432	15	C022	1
433	15	C023	1
434	15	C024	1
435	15	C025	1
436	15	C026	1
437	15	D018	1
438	15	D019	1
439	15	D020	1
440	15	D021	1
441	15	D022	1
442	15	D024	1
443	15	D025	1
444	15	E018	1
445	15	E019	1
446	15	E020	1
447	15	E021	1
448	15	E022	1
449	15	E023	1
450	15	E024	1
451	15	E025	1
452	16	C006	1
453	16	C007	1
454	16	C008	1
455	16	C009	1
456	16	C010	1
457	16	D005	1
458	16	D006	1
459	16	D007	1
460	16	D008	1
461	16	D009	1
462	16	D010	1
463	16	E001	1
464	16	E002	1
465	16	E003	1
466	16	E004	1
467	16	E005	1
468	16	E006	1
469	16	E007	1
470	16	E008	1
471	16	E009	1
472	16	E010	1
473	17	C011	1
474	17	C012	1
475	17	C013	1
476	17	C014	1
477	17	C015	1
478	17	C016	1
479	17	C017	1
480	17	D011	1
481	17	D012	1
482	17	D013	1
483	17	D014	1
484	17	D015	1
485	17	D016	1
486	17	D017	1
487	17	E011	1
488	17	E012	1
489	17	E013	1
490	17	E014	1
491	17	E015	1
492	17	E016	1
493	17	E017	1
494	18	A013	1
495	18	A014	1
496	18	A015	1
497	18	A016	1
498	18	A017	1
499	18	A018	1
500	18	B013	1
501	18	B014	1
502	18	B015	1
503	18	B016	1
504	18	B017	1
505	18	B018	1
506	18	B019	1
507	18	B020	1
508	18	B021	1
509	19	A002	1
510	19	A003	1
511	19	A004	1
512	19	A005	1
513	19	A006	1
514	19	A007	1
515	19	A008	1
516	19	A009	1
517	19	A010	1
518	19	A011	1
519	19	A012	1
520	19	B006	1
521	19	B007	1
522	19	B008	1
523	19	B009	1
524	19	B010	1
525	19	B011	1
526	19	B012	1
527	20	N027	1
528	20	N028	1
529	20	N029	1
530	20	N030	1
531	20	N034	1
532	20	O026	1
533	20	O027	1
534	20	O028	1
535	20	O029	1
536	20	O030	1
537	20	O031	1
538	20	O032	1
539	20	O033	1
540	20	O034	1
541	20	O035	1
542	20	P029	1
543	20	P030	1
544	20	P031	1
545	20	P032	1
546	20	P033	1
547	20	P034	1
548	20	P035	1
549	20	Q031	1
550	20	Q032	1
551	20	Q033	1
552	20	Q034	1
553	20	Q035	1
554	20	Q036	1
555	21	K037	1
556	21	K038	1
557	21	K039	1
558	21	K040	1
559	21	K041	1
560	21	K042	1
561	21	K043	1
562	21	L037	1
563	21	L038	1
564	21	L039	1
565	21	L040	1
566	21	L041	1
567	21	L042	1
568	21	L043	1
569	21	L044	1
570	21	L045	1
571	21	L046	1
572	21	L047	1
573	21	L048	1
574	21	M039	1
575	21	M040	1
576	21	M041	1
577	21	M042	1
578	21	M043	1
579	21	M044	1
580	21	M045	1
581	22	M035	1
582	22	M036	1
583	22	M037	1
584	22	M038	1
585	22	N035	1
586	22	N036	1
587	22	N037	1
588	22	N038	1
589	22	N039	1
590	22	N040	1
591	22	N041	1
592	22	N042	1
593	22	N043	1
594	22	N044	1
595	22	N045	1
596	22	N046	1
597	22	O037	1
598	22	O038	1
599	22	O039	1
600	22	O040	1
601	22	O041	1
602	22	O042	1
603	22	P036	1
604	22	P037	1
605	22	P038	1
606	22	P039	1
607	23	F028	1
608	23	F029	1
609	23	F030	1
610	23	G028	1
611	23	G029	1
612	23	G030	1
613	23	G036	1
614	23	H028	1
615	23	H029	1
616	23	H030	1
617	23	H031	1
618	23	H032	1
619	23	H033	1
620	23	H034	1
621	23	H035	1
622	23	H036	1
623	23	I028	1
624	23	I029	1
625	23	I030	1
626	23	I031	1
627	23	I032	1
628	23	I033	1
629	23	I034	1
630	23	I035	1
631	23	I036	1
632	23	J028	1
633	23	J029	1
634	23	J030	1
635	24	F023	1
636	24	F024	1
637	24	F025	1
638	24	F026	1
639	24	F027	1
640	24	G023	1
641	24	G024	1
642	24	G025	1
643	24	G026	1
644	24	G027	1
645	24	H023	1
646	24	H024	1
647	24	H025	1
648	24	H026	1
649	24	H027	1
650	24	I023	1
651	24	I024	1
652	24	I025	1
653	24	I026	1
654	24	I027	1
655	24	J023	1
656	24	J024	1
657	24	J025	1
658	24	J027	1
659	25	F014	1
660	25	F015	1
661	25	F016	1
662	25	F017	1
663	25	F018	1
664	25	F019	1
665	25	F020	1
666	25	F021	1
667	25	F022	1
668	25	G014	1
669	25	G015	1
670	25	G016	1
671	25	G017	1
672	25	G018	1
673	25	G019	1
674	25	G020	1
675	25	G021	1
676	25	G022	1
677	25	H015	1
678	25	H016	1
679	25	H017	1
680	25	H018	1
681	25	H019	1
682	25	H020	1
683	25	H021	1
684	25	H022	1
685	25	I019	1
686	25	I020	1
687	25	I021	1
688	25	I022	1
689	26	I010	1
690	26	I011	1
691	26	I012	1
692	26	I013	1
693	26	J010	1
694	26	J011	1
695	26	J012	1
696	26	J013	1
697	26	J014	1
698	26	J015	1
699	26	J016	1
700	26	J017	1
701	26	J018	1
702	26	J019	1
703	26	K010	1
704	26	K011	1
705	26	K012	1
706	26	K013	1
707	26	K014	1
708	26	K015	1
709	26	K016	1
710	26	K017	1
711	26	K018	1
712	26	K019	1
713	26	K020	1
714	26	K021	1
715	26	K022	1
716	26	L010	1
717	26	L011	1
718	26	L012	1
719	26	L013	1
720	26	L014	1
721	26	L015	1
722	26	L016	1
723	26	L017	1
724	26	L018	1
725	27	O012	1
726	27	O013	1
727	27	O014	1
728	27	O015	1
729	27	O016	1
730	27	O017	1
731	27	O018	1
732	27	P011	1
733	27	P012	1
734	27	P013	1
735	27	P014	1
736	27	P015	1
737	27	P016	1
738	27	P017	1
739	27	P018	1
740	27	Q012	1
741	27	Q013	1
742	27	Q014	1
743	27	Q015	1
744	27	Q016	1
745	27	Q017	1
746	28	O019	1
747	28	O020	1
748	28	O021	1
749	28	O022	1
750	28	O023	1
751	28	P019	1
752	28	P020	1
753	28	P021	1
754	28	P022	1
755	28	P023	1
756	28	P024	1
757	28	Q018	1
758	28	Q019	1
759	28	Q020	1
760	28	Q021	1
761	28	Q022	1
762	28	Q023	1
763	28	Q024	1
764	28	Q025	1
765	29	O027	1
766	29	O028	1
767	29	O029	1
768	29	O030	1
769	29	O031	1
770	29	O032	1
771	29	P025	1
772	29	P026	1
773	29	P027	1
774	29	P028	1
775	29	P029	1
776	29	P030	1
777	29	P031	1
778	29	P032	1
779	29	Q026	1
780	29	Q027	1
781	29	Q028	1
782	29	Q029	1
783	29	Q030	1
784	29	Q031	1
785	30	O011	1
786	30	O012	1
787	30	O013	1
788	30	O014	1
789	30	O015	1
790	30	O016	1
791	30	O017	1
792	30	O018	1
793	30	O019	1
794	30	O020	1
795	30	P011	1
796	30	P012	1
797	30	P013	1
798	30	P014	1
799	30	P016	1
800	30	P017	1
801	30	P018	1
802	30	P019	1
803	30	P020	1
804	30	R011	1
805	30	R012	1
806	30	R013	1
807	30	R014	1
808	30	R015	1
809	30	R016	1
810	30	R017	1
811	31	O021	1
812	31	O022	1
813	31	O023	1
814	31	O024	1
815	31	O025	1
816	31	O026	1
817	31	O027	1
818	31	O028	1
819	31	O029	1
820	31	O030	1
821	31	O031	1
822	31	O032	1
823	31	P021	1
824	31	P022	1
825	31	P023	1
826	31	P024	1
827	31	P025	1
828	31	P026	1
829	31	P027	1
830	31	P028	1
831	31	P029	1
832	31	P030	1
833	32	O033	1
834	32	O034	1
835	32	O035	1
836	32	O036	1
837	32	O037	1
838	32	O038	1
839	32	O039	1
840	32	O040	1
841	32	P031	1
842	32	P032	1
843	32	P033	1
844	32	P034	1
845	32	P035	1
846	32	P036	1
847	32	P037	1
848	32	P038	1
849	32	P039	1
850	32	P040	1
851	32	P041	1
852	32	Q033	1
853	32	Q034	1
854	32	Q035	1
855	32	Q036	1
856	32	Q037	1
857	32	Q038	1
858	32	Q039	1
859	32	R033	1
860	33	Q019	1
861	33	Q020	1
862	33	Q021	1
863	33	Q022	1
864	33	Q023	1
865	33	Q024	1
866	33	Q025	1
867	33	Q026	1
868	33	Q027	1
869	33	Q028	1
870	33	Q029	1
871	33	Q030	1
872	33	Q031	1
873	33	Q032	1
874	33	R022	1
875	33	R023	1
876	33	R024	1
877	33	R025	1
878	33	R026	1
879	33	R027	1
880	33	R028	1
881	33	R029	1
882	33	R030	1
883	33	R031	1
884	33	R032	1
885	33	S022	1
886	33	S023	1
887	33	S024	1
888	33	S025	1
889	33	S026	1
890	33	S027	1
891	33	S028	1
892	34	G038	1
893	34	G039	1
894	34	G040	1
895	34	G041	1
896	34	G042	1
897	34	G043	1
898	34	G044	1
899	34	G045	1
900	34	G046	1
901	34	G047	1
902	34	G048	1
903	34	H033	1
904	34	H034	1
905	34	H035	1
906	34	H036	1
907	34	H037	1
908	34	H038	1
909	34	H039	1
910	34	H040	1
911	34	H041	1
912	34	H042	1
913	34	H043	1
914	34	H044	1
915	34	H045	1
916	34	H046	1
917	34	H047	1
918	34	H048	1
919	34	H049	1
920	34	H050	1
921	35	I033	1
922	35	I034	1
923	35	I035	1
924	35	I036	1
925	35	I037	1
926	35	I038	1
927	35	I039	1
928	35	I040	1
929	35	I041	1
930	35	I042	1
931	35	I043	1
932	35	I044	1
933	35	I045	1
934	35	I046	1
935	35	I047	1
936	35	J035	1
937	35	J036	1
938	35	J037	1
939	35	J038	1
940	35	J039	1
941	35	J040	1
942	35	J041	1
943	35	J042	1
944	35	J043	1
945	35	J044	1
946	35	J045	1
947	35	J046	1
948	35	J047	1
949	35	K044	1
950	35	K045	1
951	35	K046	1
952	35	K047	1
953	36	H053	1
954	36	I046	1
955	36	I047	1
956	36	I048	1
957	36	I049	1
958	36	I050	1
959	36	I051	1
960	36	I052	1
961	36	I053	1
962	36	I054	1
963	36	I055	1
964	36	I056	1
965	36	I057	1
966	36	J046	1
967	36	J047	1
968	36	J048	1
969	36	J049	1
970	36	J050	1
971	36	J051	1
972	36	J052	1
973	36	J053	1
974	36	J054	1
975	36	J055	1
976	36	J056	1
977	36	J057	1
978	36	J058	1
979	36	K046	1
980	36	K047	1
981	36	K048	1
982	36	K049	1
983	36	K050	1
984	36	K051	1
985	36	K052	1
986	36	K053	1
987	36	K054	1
988	36	K055	1
989	36	K056	1
990	36	K057	1
991	36	K058	1
992	36	L048	1
993	36	L049	1
994	37	H053	1
995	37	I052	1
996	37	I053	1
997	37	I054	1
998	37	I055	1
999	37	I056	1
1000	37	I057	1
1001	37	J052	1
1002	37	J053	1
1003	37	J054	1
1004	37	J055	1
1005	37	J056	1
1006	37	J057	1
1007	37	J058	1
1008	37	K052	1
1009	37	K053	1
1010	37	K054	1
1011	37	K055	1
1012	37	K056	1
1013	37	K057	1
1014	37	K058	1
1015	38	A050	1
1016	38	A051	1
1017	38	A052	1
1018	38	A053	1
1019	38	A054	1
1020	38	A055	1
1021	38	A056	1
1022	38	A057	1
1023	38	B049	1
1024	38	B050	1
1025	38	B051	1
1026	38	B052	1
1027	38	B053	1
1028	38	B054	1
1029	38	B055	1
1030	38	B056	1
1031	38	C051	1
1032	38	C052	1
1033	38	C054	1
1034	38	D050	1
1035	38	D051	1
1036	39	A044	1
1037	39	A045	1
1038	39	A046	1
1039	39	A047	1
1040	39	A048	1
1041	39	A049	1
1042	39	B043	1
1043	39	B044	1
1044	39	B045	1
1045	39	B046	1
1046	39	B047	1
1047	39	B048	1
1048	39	C042	1
1049	39	C043	1
1050	39	C044	1
1051	39	C046	1
1052	39	C047	1
1053	39	C048	1
1054	39	C049	1
1055	39	C050	1
1056	39	D048	1
1057	39	D049	1
1058	39	E048	1
1059	39	E049	1
1060	40	C036	1
1061	40	C037	1
1062	40	C038	1
1063	40	C039	1
1064	40	D039	1
1065	40	D040	1
1066	40	D041	1
1067	40	D042	1
1068	40	D043	1
1069	40	D044	1
1070	40	D045	1
1071	40	E041	1
1072	40	E042	1
1073	40	E043	1
1074	40	E044	1
1075	40	E045	1
1076	40	F041	1
1077	40	F042	1
1078	40	F043	1
1079	40	F044	1
1080	40	G042	1
1081	40	G043	1
1082	40	G044	1
1083	40	G045	1
1084	40	G046	1
1085	40	H043	1
1086	41	G030	1
1087	41	G031	1
1088	41	G032	1
1089	41	G033	1
1090	41	H030	1
1091	41	H031	1
1092	41	H032	1
1093	41	H033	1
1094	41	I030	1
1095	41	I031	1
1096	41	I032	1
1097	41	I033	1
1098	41	I034	1
1099	41	J024	1
1100	41	J025	1
1101	41	J026	1
1102	41	J027	1
1103	41	J028	1
1104	41	J029	1
1105	41	J030	1
1106	41	J031	1
1107	41	J032	1
1108	41	J039	1
1109	41	L020	1
1110	41	L021	1
1111	41	L022	1
1112	41	L023	1
1113	41	L024	1
1114	41	L025	1
1115	41	L026	1
1116	41	L027	1
1117	41	L028	1
1118	41	L029	1
1119	41	L030	1
1120	41	L031	1
1121	41	L032	1
1122	41	L034	1
1123	41	L035	1
1124	41	L036	1
1125	41	M020	1
1126	41	M021	1
1127	41	M022	1
1128	41	M023	1
1129	42	F025	1
1130	42	M024	1
1131	42	M025	1
1132	42	M026	1
1133	42	M027	1
1134	42	M028	1
1135	42	M029	1
1136	42	M030	1
1137	42	M031	1
1138	42	M032	1
1139	42	M033	1
1140	42	M034	1
1141	42	M035	1
1142	42	N023	1
1143	42	N024	1
1144	42	N025	1
1145	42	N026	1
1146	42	N028	1
1147	42	N029	1
1148	42	N030	1
1149	42	N032	1
1150	42	N033	1
1151	42	N034	1
1152	42	N035	1
1153	42	N036	1
1154	42	O023	1
1155	42	O024	1
1156	42	O025	1
1157	42	O026	1
1158	42	O027	1
1159	42	O028	1
1160	42	O029	1
1161	42	O031	1
1162	42	P027	1
1163	42	P029	1
1164	42	P030	1
1165	43	K023	1
1166	43	L020	1
1167	43	L022	1
1168	43	L023	1
1169	43	L024	1
1170	43	L025	1
1171	43	L030	1
1172	43	M021	1
1173	43	M023	1
1174	43	M024	1
1175	43	M025	1
1176	43	M026	1
1177	43	M028	1
1178	43	M029	1
1179	43	M030	1
1180	43	M031	1
1181	43	N025	1
1182	43	N028	1
1183	43	N029	1
1184	44	L052	\N
1185	44	P034	1
1186	44	P038	1
1187	44	P039	1
1188	44	Q034	1
1189	44	Q037	1
1190	44	Q038	1
1191	44	Q039	1
1192	44	Q040	1
1193	44	Q041	1
1194	44	Q042	1
1195	44	R038	1
1196	44	R039	1
1197	44	R040	1
1198	44	R041	1
1199	44	R042	1
1200	44	R043	1
1201	44	R044	1
1202	44	R045	1
1203	44	R046	1
1204	44	R047	1
1205	44	R048	1
1206	44	S038	1
1207	44	S041	1
1208	44	S042	1
1209	44	S044	1
1210	44	S045	1
1211	44	S046	1
1212	44	S047	1
1213	44	S048	1
1214	44	S049	1
1215	45	T038	1
1216	45	T039	1
1217	45	T040	1
1218	45	T041	1
1219	45	T043	1
1220	45	T044	1
1221	45	T045	1
1222	45	T046	1
1223	45	T048	1
1224	45	T049	1
1225	45	T050	1
1226	45	U038	1
1227	45	U040	1
1228	45	U042	1
1229	45	U044	1
1230	45	U046	1
1231	45	U048	1
1232	45	U049	1
1233	45	U050	1
1234	46	N043	1
1235	46	N044	1
1236	46	N045	1
1237	46	N046	1
1238	46	O044	1
1239	46	O045	1
1240	46	O046	1
1241	46	O047	1
1242	46	O048	1
1243	46	P044	1
1244	46	P045	1
1245	46	P046	1
1246	46	P047	1
1247	46	P048	1
1248	46	P049	1
1249	46	P050	1
1250	46	P051	1
1251	46	P052	1
1252	46	Q048	1
1253	46	Q049	1
1254	46	Q050	1
1255	46	Q051	1
1256	46	Q052	1
1257	46	Q053	1
1258	46	Q054	1
1259	46	Q055	1
1260	46	R052	1
1261	46	R055	1
1262	46	R056	1
1263	46	S053	1
1264	46	S054	1
1265	46	S056	1
1266	46	T056	1
1267	47	E042	1
1268	47	E043	1
1269	47	E044	1
1270	47	E045	1
1271	47	F040	1
1272	47	F041	1
1273	47	F042	1
1274	47	F043	1
1275	47	F044	1
1276	47	F045	1
1277	47	G031	1
1278	47	G034	1
1279	47	G035	1
1280	47	G039	1
1281	47	G040	1
1282	47	G041	1
1283	47	G042	1
1284	47	G043	1
1285	47	G044	1
1286	47	G045	1
1287	47	H031	1
1288	47	H032	1
1289	47	H033	1
1290	47	H034	1
1291	47	H036	1
1292	47	H037	1
1293	47	H038	1
1294	47	H039	1
1295	47	H040	1
1296	47	H041	1
1297	47	H042	1
1298	47	H043	1
1299	47	I038	1
1300	47	I039	1
1301	47	I040	1
1302	47	I041	1
1303	48	G029	1
1304	48	G030	1
1305	48	H029	1
1306	48	H030	1
1307	48	I025	1
1308	48	I026	1
1309	48	I029	1
1310	48	I030	1
1311	48	I031	1
1312	48	I032	1
1313	48	I033	1
1314	48	I034	1
1315	48	I035	1
1316	48	I036	1
1317	48	J025	1
1318	48	J026	1
1319	48	J027	1
1320	48	J028	1
1321	48	J029	1
1322	48	J030	1
1323	48	J032	1
1324	48	J034	1
1325	48	J035	1
1326	48	J036	1
1327	48	J040	1
1328	48	J041	1
1329	48	K035	1
1330	48	K038	1
1331	48	K039	1
1332	48	K040	1
1333	48	K041	1
1334	48	L034	1
1335	48	L040	1
1336	48	L041	1
1337	48	M041	1
1338	48	M042	1
1339	48	M044	1
1340	48	M045	1
1341	48	M047	1
1342	49	O039	1
1343	49	P038	1
1344	49	P039	1
1345	49	P040	1
1346	49	P041	1
1347	49	Q038	1
1348	49	Q039	1
1349	49	Q040	1
1350	49	Q041	1
1351	49	Q043	1
1352	49	Q044	1
1353	49	Q046	1
1354	49	R038	1
1355	49	R039	1
1356	49	S034	1
1357	49	S035	1
1358	49	S036	1
1359	49	S037	1
1360	49	S038	1
1361	49	T035	1
1362	49	T037	1
1363	49	T038	1
1364	49	T039	1
1365	49	U031	1
1366	49	U032	1
1367	49	U033	1
1368	49	U034	1
1369	49	U035	1
1370	49	U036	1
1371	49	U037	1
1372	49	U038	1
1373	49	U039	1
1374	49	U040	1
1375	49	V033	1
1376	49	V035	1
1377	49	V037	1
1378	49	V038	1
1379	50	K051	1
1380	50	K052	1
1381	50	L042	1
1382	50	L043	1
1383	50	L044	1
1384	50	L045	1
1385	50	L048	1
1386	50	L049	1
1387	50	L050	1
1388	50	L051	1
1389	50	L052	1
1390	50	M040	1
1391	50	M041	1
1392	50	M042	1
1393	50	M043	1
1394	50	M044	1
1395	50	M045	1
1396	50	M046	1
1397	50	M047	1
1398	50	M048	1
1399	50	M049	1
1400	50	M050	1
1401	50	M051	1
1402	50	N048	1
1403	50	N049	1
1404	50	N050	1
1405	50	N051	1
1406	50	O048	1
1407	50	O049	1
1408	50	O050	1
1409	50	O051	1
1410	50	P048	1
1411	50	P049	1
1412	50	P050	1
1413	50	P051	1
1414	50	P052	1
1415	51	M052	1
1416	51	M053	1
1417	51	M054	1
1418	51	M055	1
1419	51	M056	1
1420	51	M057	1
1421	51	M058	1
1422	51	N052	1
1423	51	N053	1
1424	51	N054	1
1425	51	N055	1
1426	51	N056	1
1427	51	N057	1
1428	51	N058	1
1429	51	O052	1
1430	51	O053	1
1431	51	O054	1
1432	51	O055	1
1433	51	O056	1
1434	51	O057	1
1435	51	O058	1
1436	51	P053	1
1437	51	P054	1
1438	51	P055	1
1439	51	P056	1
1440	51	P057	1
1441	51	P058	1
1442	51	Q053	1
1443	51	Q054	1
1444	51	Q055	1
1445	51	Q056	1
1446	51	R054	1
1447	52	H060	1
1448	52	H061	1
1449	52	H062	1
1450	52	H063	1
1451	52	H064	1
1452	52	H065	1
1453	52	I060	1
1454	52	I061	1
1455	52	I062	1
1456	52	I063	1
1457	52	I064	1
1458	52	J058	1
1459	52	J059	1
1460	52	J060	1
1461	52	J061	1
1462	52	J062	1
1463	52	J063	1
1464	52	J064	1
1465	52	J065	1
1466	52	J067	1
1467	52	J068	1
1468	52	J069	1
1469	52	J070	1
1470	52	J071	1
1471	52	J072	1
1472	52	K053	1
1473	52	K054	1
1474	52	K055	1
1475	52	K056	1
1476	52	K059	1
1477	52	K060	1
1478	52	K061	1
1479	52	K062	1
1480	52	K063	1
1481	52	K064	1
1482	52	L053	1
1483	52	L054	1
1484	52	L055	1
1485	52	L056	1
1486	52	L057	1
1487	52	L058	1
1488	52	L059	1
1489	53	D075	1
1490	53	E077	1
1491	53	F061	1
1492	53	F062	1
1493	53	F063	1
1494	53	F064	1
1495	53	F065	1
1496	53	F066	1
1497	53	F067	1
1498	53	F068	1
1499	53	F069	1
1500	53	F070	1
1501	53	F071	1
1502	53	F077	1
1503	53	G059	1
1504	53	G060	1
1505	53	G061	1
1506	53	G062	1
1507	53	G063	1
1508	53	G064	1
1509	53	G065	1
1510	53	G066	1
1511	53	G067	1
1512	53	G068	1
1513	53	G069	1
1514	53	G070	1
1515	53	G071	1
1516	53	G072	1
1517	53	G073	1
1518	53	G074	1
1519	53	H066	1
1520	53	H068	1
1521	53	H069	1
1522	53	H070	1
1523	53	H071	1
1524	53	H072	1
1525	53	H073	1
1526	54	O020	1
1527	54	O021	1
1528	54	O022	1
1529	54	O023	1
1530	54	O026	1
1531	54	P018	1
1532	54	P019	1
1533	54	P020	1
1534	54	P021	1
1535	54	P022	1
1536	54	P023	1
1537	54	P024	1
1538	54	P025	1
1539	54	P028	1
1540	54	Q018	1
1541	54	Q019	1
1542	54	Q020	1
1543	54	Q021	1
1544	54	Q022	1
1545	54	Q023	1
1546	54	Q024	1
1547	54	Q025	1
1548	54	Q026	1
1549	54	Q027	1
1550	54	Q028	1
1551	54	R021	1
1552	54	R022	1
1553	54	R023	1
1554	54	R024	1
1555	54	R025	1
1556	54	R026	1
1557	54	R027	1
1558	54	R028	1
1559	54	S023	1
1560	54	S024	1
1561	54	S025	1
1562	54	S026	1
1563	54	S027	1
1564	54	S028	1
1565	55	P001	1
1566	55	P002	1
1567	55	P003	1
1568	55	P004	1
1569	55	P005	1
1570	55	P006	1
1571	55	P007	1
1572	55	P008	1
1573	55	P009	1
1574	55	P010	1
1575	55	P011	1
1576	55	P012	1
1577	55	P013	1
1578	55	P014	1
1579	55	Q001	1
1580	55	Q002	1
1581	55	Q013	1
1582	55	Q014	1
1583	55	Q015	1
1584	55	Q016	1
1585	55	R013	1
1586	55	R014	1
1587	55	R015	1
1588	55	R016	1
1589	55	R017	1
1590	55	R018	1
1591	55	R019	1
1592	55	S017	1
1593	55	S018	1
1594	55	S019	1
1595	56	K008	1
1596	56	K009	1
1597	56	K010	1
1598	56	K011	1
1599	56	L005	1
1600	56	L006	1
1601	56	L007	1
1602	56	L008	1
1603	56	L009	1
1604	56	L010	1
1605	56	M005	1
1606	56	M006	1
1607	56	M007	1
1608	56	M008	1
1609	56	M009	1
1610	56	M010	1
1611	56	M011	1
1612	56	N005	1
1613	56	N006	1
1614	56	N007	1
1615	56	N008	1
1616	56	N009	1
1617	56	N010	1
1618	56	N011	1
1619	56	O003	1
1620	56	O004	1
1621	56	O005	1
1622	56	O006	1
1623	56	O007	1
1624	56	O008	1
1625	57	K012	1
1626	57	K013	1
1627	57	K014	1
1628	57	K015	1
1629	57	K016	1
1630	57	K017	1
1631	57	L011	1
1632	57	L013	1
1633	57	L014	1
1634	57	L015	1
1635	57	L016	1
1636	57	L017	1
1637	57	L018	1
1638	57	M012	1
1639	57	M014	1
1640	57	M015	1
1641	57	M016	1
1642	57	M017	1
1643	57	M019	1
1644	57	N012	1
1645	57	N013	1
1646	57	N014	1
1647	57	N015	1
1648	57	N016	1
1649	57	N017	1
1650	57	N018	1
1651	57	O012	1
1652	57	O013	1
1653	57	O014	1
1654	57	O015	1
1655	57	O016	1
1656	57	O017	1
1657	57	O018	1
1658	57	O019	1
1659	58	G028	1
1660	58	H026	1
1661	58	H027	1
1662	58	H028	1
1663	58	I022	1
1664	58	I024	1
1665	58	I025	1
1666	58	I026	1
1667	58	I027	1
1668	58	I028	1
1669	58	I029	1
1670	58	J020	1
1671	58	J021	1
1672	58	J022	1
1673	58	J023	1
1674	58	J024	1
1675	58	J025	1
1676	58	J026	1
1677	58	J027	1
1678	58	J028	1
1679	58	K021	1
1680	58	K022	1
1681	58	K023	1
1682	58	K024	1
1683	58	K025	1
1684	58	L026	1
1685	58	M026	1
1686	59	G014	1
1687	59	G015	1
1688	59	G016	1
1689	59	G017	1
1690	59	G018	1
1691	59	G021	1
1692	59	G022	1
1693	59	G023	1
1694	59	H014	1
1695	59	H015	1
1696	59	H016	1
1697	59	H017	1
1698	59	H018	1
1699	59	H019	1
1700	59	H021	1
1701	59	H022	1
1702	59	I014	1
1703	59	I015	1
1704	59	I016	1
1705	59	I017	1
1706	59	I018	1
1707	59	I019	1
1708	59	I021	1
1709	59	J014	1
1710	59	J015	1
1711	59	J016	1
1712	59	J017	1
1713	59	J018	1
1714	59	J019	1
1715	60	E013	1
1716	60	F011	1
1717	60	F012	1
1718	60	F013	1
1719	60	F014	1
1720	60	G010	1
1721	60	G011	1
1722	60	G012	1
1723	60	G013	1
1724	60	H008	1
1725	60	H009	1
1726	60	H010	1
1727	60	H011	1
1728	60	H012	1
1729	60	H013	1
1730	60	I008	1
1731	60	I009	1
1732	60	I010	1
1733	60	I011	1
1734	60	I012	1
1735	60	I013	1
1736	60	J008	1
1737	60	J009	1
1738	60	J010	1
1739	60	J011	1
1740	60	J012	1
1741	60	J013	1
1742	61	M038	1
1743	61	M039	1
1744	61	N038	1
1745	61	N039	1
1746	61	N040	1
1747	61	N041	1
1748	61	N042	1
1749	61	N043	1
1750	61	N044	1
1751	61	N045	1
1752	61	O038	1
1753	61	O039	1
1754	61	O040	1
1755	61	O041	1
1756	61	O042	1
1757	61	O043	1
1758	61	O044	1
1759	61	O045	1
1760	61	O046	1
1761	61	P038	1
1762	61	P039	1
1763	61	P040	1
1764	61	P041	1
1765	61	P042	1
1766	61	P043	1
1767	61	P044	1
1768	61	P045	1
1769	61	P046	1
1770	62	L055	1
1771	62	M054	1
1772	62	M055	1
1773	62	M056	1
1774	62	N053	1
1775	62	N054	1
1776	62	N055	1
1777	62	N056	1
1778	62	O047	1
1779	62	O048	1
1780	62	O049	1
1781	62	O050	1
1782	62	O051	1
1783	62	O052	1
1784	62	O053	1
1785	62	O054	1
1786	62	O055	1
1787	62	O056	1
1788	62	P047	1
1789	62	P048	1
1790	62	P049	1
1791	62	P050	1
1792	62	P051	1
1793	62	P052	1
1794	62	P053	1
1795	62	P054	1
1796	62	P055	1
1797	62	P056	1
1798	63	L057	1
1799	63	L058	1
1800	63	L059	1
1801	63	M057	1
1802	63	M058	1
1803	63	M059	1
1804	63	M060	1
1805	63	M061	1
1806	63	M062	1
1807	63	M063	1
1808	63	M064	1
1809	63	N057	1
1810	63	N058	1
1811	63	N059	1
1812	63	N060	1
1813	63	N061	1
1814	63	N062	1
1815	63	N063	1
1816	63	N064	1
1817	63	O057	1
1818	63	O058	1
1819	63	O059	1
1820	63	O060	1
1821	63	O061	1
1822	63	O062	1
1823	63	O063	1
1824	63	O064	1
1825	63	P057	1
1826	63	P058	1
1827	63	P059	1
1828	64	L065	1
1829	64	L066	1
1830	64	L067	1
1831	64	L068	1
1832	64	L069	1
1833	64	M065	1
1834	64	M066	1
1835	64	M067	1
1836	64	M068	1
1837	64	M069	1
1838	64	M070	1
1839	64	M071	1
1840	64	M072	1
1841	64	M073	1
1842	64	M074	1
1843	64	N065	1
1844	64	N066	1
1845	64	N067	1
1846	64	N068	1
1847	64	N069	1
1848	64	N070	1
1849	64	N071	1
1850	64	N072	1
1851	64	N073	1
1852	64	N074	1
1853	64	O065	1
1854	64	O066	1
1855	64	O067	1
1856	64	O068	1
1857	64	O069	1
1858	64	O070	1
1859	64	O071	1
1860	64	O072	1
1861	64	O073	1
1862	64	O074	1
1863	65	L075	1
1864	65	L076	1
1865	65	L077	1
1866	65	M075	1
1867	65	M076	1
1868	65	M077	1
1869	65	M078	1
1870	65	M079	1
1871	65	M080	1
1872	65	M081	1
1873	65	M082	1
1874	65	M083	1
1875	65	N075	1
1876	65	N076	1
1877	65	N077	1
1878	65	N078	1
1879	65	N079	1
1880	65	N080	1
1881	65	N081	1
1882	65	N082	1
1883	65	N083	1
1884	65	O075	1
1885	65	O076	1
1886	65	O077	1
1887	65	O078	1
1888	65	O079	1
1889	65	O080	1
1890	65	O081	1
1891	65	O082	1
1892	65	O083	1
1893	65	P078	1
1894	65	P079	1
1895	65	P080	1
1896	65	P081	1
1897	65	P082	1
1898	65	P083	1
1899	66	A006	1
1900	66	B006	1
1901	66	B007	1
1902	66	B008	1
1903	66	B009	1
1904	66	C001	1
1905	66	C002	1
1906	66	C004	1
1907	66	C005	1
1908	66	C006	1
1909	66	C007	1
1910	66	C008	1
1911	66	C009	1
1912	66	D001	1
1913	66	D002	1
1914	66	D004	1
1915	66	D005	1
1916	66	D006	1
1917	66	D007	1
1918	66	D008	1
1919	66	D009	1
1920	66	E003	1
1921	66	E004	1
1922	66	E005	1
1923	66	E006	1
1924	66	E007	1
1925	66	E008	1
1926	66	E009	1
1927	66	F005	1
1928	66	F006	1
1929	66	F007	1
1930	66	F008	1
1931	66	F009	1
1932	66	G009	1
1933	67	H004	1
1934	67	H005	1
1935	67	H006	1
1936	67	I002	1
1937	67	I003	1
1938	67	I004	1
1939	67	I005	1
1940	67	I006	1
1941	67	I007	1
1942	67	I008	1
1943	67	I009	1
1944	67	I010	1
1945	67	I011	1
1946	67	I012	1
1947	67	I013	1
1948	67	I014	1
1949	67	I015	1
1950	67	J006	1
1951	67	J007	1
1952	67	J008	1
1953	67	J009	1
1954	67	J010	1
1955	67	J011	1
1956	67	J012	1
1957	67	J013	1
1958	67	J014	1
1959	67	J015	1
1960	67	J016	1
1961	67	J017	1
1962	67	K012	1
1963	67	K013	1
1964	67	K014	1
1965	67	K015	1
1966	67	K016	1
1967	68	J018	1
1968	68	K017	1
1969	68	K018	1
1970	68	K019	1
1971	68	K020	1
1972	68	L017	1
1973	68	L018	1
1974	68	L019	1
1975	68	L020	1
1976	68	L021	1
1977	68	M019	1
1978	68	M020	1
1979	68	M021	1
1980	68	M022	1
1981	68	M023	1
1982	68	M024	1
1983	68	M025	1
1984	68	M026	1
1985	68	M027	1
1986	68	N020	1
1987	68	N021	1
1988	68	N022	1
1989	68	N023	1
1990	68	N024	1
1991	68	N025	1
1992	68	N026	1
1993	68	N027	1
1994	68	O023	1
1995	68	O024	1
1996	68	O025	1
1997	68	O026	1
1998	68	O027	1
1999	69	M028	1
2000	69	M029	1
2001	69	M030	1
2002	69	M031	1
2003	69	M032	1
2004	69	M033	1
2005	69	M034	1
2006	69	M035	1
2007	69	M036	1
2008	69	M037	1
2009	69	N028	1
2010	69	N029	1
2011	69	N030	1
2012	69	N031	1
2013	69	N032	1
2014	69	N033	1
2015	69	N034	1
2016	69	N035	1
2017	69	N036	1
2018	69	N037	1
2019	69	O028	1
2020	69	O029	1
2021	69	O030	1
2022	69	O031	1
2023	69	O032	1
2024	69	O033	1
2025	69	O034	1
2026	69	O035	1
2027	69	O036	1
2028	69	O037	1
2029	69	P035	1
2030	69	P036	1
2031	69	P037	1
2032	70	L030	1
2033	70	L031	1
2034	70	L032	1
2035	70	M040	1
2036	70	M041	1
2037	70	M042	1
2038	70	M043	1
2039	70	M044	1
2040	70	M045	1
2041	70	M046	1
2042	71	F003	2
2043	71	G002	2
2044	71	G003	2
2045	71	G004	2
2046	71	H002	2
2047	71	H003	2
2048	71	H004	2
2049	71	I003	2
2050	71	I004	2
2051	71	I005	2
2052	71	I006	2
2053	71	I007	2
2054	72	L013	2
2055	72	L015	2
2056	72	L017	2
2057	72	L019	2
2058	73	D006	2
2059	73	D007	2
2060	73	D008	2
2061	73	D009	2
2062	73	D010	2
2063	73	D011	2
2064	73	D012	2
2065	73	D016	2
2066	73	D017	2
2067	73	D018	2
2068	73	E013	2
2069	73	E016	2
2070	73	E017	2
2071	73	F012	2
2072	73	F013	2
2073	74	C043	2
2074	74	C044	2
2075	74	C046	2
2076	74	D042	2
2077	74	D043	2
2078	74	D044	2
2079	74	D045	2
2080	74	D046	2
2081	75	D040	2
2082	75	D041	2
2083	76	B039	2
2084	76	B040	2
2085	76	B041	2
2086	76	B042	2
2087	76	C033	2
2088	76	C034	2
2089	76	C035	2
2090	76	C036	2
2091	76	C037	2
2092	76	C038	2
2093	76	C039	2
2094	76	C040	2
2095	76	C041	2
2096	76	C042	2
2097	77	F044	2
2098	77	F045	2
2099	77	F046	2
2100	77	F047	2
2101	77	F048	2
2102	77	F049	2
2103	77	G044	2
2104	78	A059	2
2105	78	A060	2
2106	78	A061	2
2107	78	B056	2
2108	78	B057	2
2109	78	B058	2
2110	78	B059	2
2111	78	B060	2
2112	79	A058	2
2113	79	A062	2
2114	79	A063	2
2115	79	A066	2
2116	79	A067	2
2117	79	A068	2
2118	79	A069	2
2119	79	A071	2
2120	79	A072	2
2121	79	A073	2
2122	79	A074	2
2123	79	B061	2
2124	79	B062	2
2125	79	B063	2
2126	79	B064	2
2127	79	B065	2
2128	79	B066	2
2129	79	B067	2
2130	79	B068	2
2131	79	B069	2
2132	79	B070	2
2133	79	B071	2
2134	79	B072	2
2135	79	B073	2
2136	79	E066	2
2137	79	E067	2
2138	79	E068	2
2139	80	D051	2
2140	80	D052	2
2141	80	D053	2
2142	80	D054	2
2143	81	H019	2
2144	81	I016	2
2145	81	J014	2
2146	81	J015	2
2147	81	J016	2
2148	81	J017	2
2149	81	J018	2
2150	81	J019	2
2151	81	J020	2
2152	81	J021	2
2153	81	J022	2
2154	82	E114	2
2155	82	E116	2
2156	82	E117	2
2157	82	E118	2
2158	82	E119	2
2159	82	E120	2
2160	82	E121	2
2161	82	E122	2
2162	82	E124	2
2163	82	F113	2
2164	82	F125	2
2165	82	F126	2
2166	82	F127	2
2167	83	J005	2
2168	83	J006	2
2169	83	J007	2
2170	83	J008	2
2171	83	J009	2
2172	83	J010	2
2173	83	J011	2
2174	83	J012	2
2175	83	J013	2
2176	84	B009	2
2177	84	C007	2
2178	84	C008	2
2179	84	C009	2
2180	84	C010	2
2181	84	C011	2
2182	84	D013	2
2183	85	B020	2
2184	85	B021	2
2185	85	B022	2
2186	85	B025	2
2187	85	C021	2
2188	85	C022	2
2189	85	C023	2
2190	85	C024	2
2191	85	C025	2
2192	85	C027	2
2193	85	D022	2
2194	85	D023	2
2195	85	D024	2
2196	86	A009	2
2197	86	D001	2
2198	86	D002	2
2199	86	D003	2
2200	86	D004	2
2201	86	E002	2
2202	86	E003	2
2203	86	E004	2
2204	86	E005	2
2205	86	E006	2
2206	86	E007	2
2207	86	E008	2
2208	86	F009	2
2209	87	D005	2
2210	87	E009	2
2211	87	E010	2
2212	87	E011	2
2213	87	E012	2
2214	87	F014	2
2215	87	F015	2
2216	87	F016	2
2217	87	F017	2
2218	88	A022	2
2219	88	A023	2
2220	88	A024	2
2221	88	B022	2
2222	88	B023	2
2223	88	B024	2
2224	88	B025	2
2225	88	D020	2
2226	88	D021	2
2227	88	D022	2
2228	89	D042	2
2229	90	Q011	2
2230	90	Q013	2
2231	90	Q015	2
2232	90	Q017	2
2233	90	Q018	2
2234	90	R018	2
2235	90	R019	2
2236	90	R020	2
2237	90	R021	2
2238	90	S019	2
2239	90	S021	2
2240	90	T015	2
2241	90	T016	2
2242	90	T017	2
2243	90	T018	2
2244	90	T019	2
2245	90	T020	2
2246	90	T021	2
2247	90	T022	2
2248	90	T023	2
2249	90	T024	2
2250	90	T025	2
2251	90	T026	2
2252	90	T027	2
2253	90	T028	2
2254	90	U017	2
2255	90	U026	2
2256	91	G001	2
2257	91	G002	2
2258	91	H001	2
2259	91	H002	2
2260	91	H003	2
2261	91	H004	2
2262	91	H005	2
2263	91	M001	2
2264	91	M002	2
2265	91	M003	2
2266	91	M004	2
2267	91	M005	2
2268	91	M006	2
2269	91	M007	2
2270	91	M008	2
2271	91	M009	2
2272	91	M010	2
2273	91	M011	2
2274	91	M012	2
2275	91	M013	2
2276	91	M014	2
2277	91	M015	2
2278	91	M016	2
2279	91	M017	2
2280	91	M018	2
2281	91	M019	2
2282	91	M020	2
2283	91	M021	2
2284	91	N002	2
2285	91	N003	2
2286	91	N004	2
2287	91	N005	2
2288	91	N006	2
2289	91	N007	2
2290	91	N008	2
2291	91	N012	2
2292	91	N017	2
2293	91	N018	2
2294	91	N019	2
2295	91	N020	2
2296	91	N022	2
2297	92	G003	2
2298	92	G004	2
2299	92	G005	2
2300	92	J031	2
2301	92	J032	2
2302	92	J033	2
2303	92	J034	2
2304	92	J035	2
2305	92	J036	2
2306	92	J037	2
2307	93	H020	2
2308	93	H021	2
2309	93	H022	2
2310	93	H023	2
2311	93	H030	2
2312	93	H031	2
2313	93	I020	2
2314	93	I021	2
2315	93	I022	2
2316	93	I023	2
2317	93	I029	2
2318	93	I030	2
2319	93	I031	2
2320	93	J020	2
2321	93	J021	2
2322	93	J022	2
2323	93	J023	2
2324	93	J024	2
2325	93	J025	2
2326	93	J026	2
2327	93	J027	2
2328	93	J028	2
2329	93	J029	2
2330	93	K022	2
2331	93	K023	2
2332	93	K027	2
2333	94	D032	2
2334	94	D033	2
2335	94	D034	2
2336	94	D035	2
2337	94	D036	2
2338	94	D037	2
2339	94	D041	2
2340	94	D042	2
2341	94	E032	2
2342	94	E033	2
2343	94	E034	2
2344	94	E035	2
2345	94	E043	2
2346	94	F035	2
2347	94	F036	2
2348	94	F039	2
2349	94	F040	2
2350	94	F041	2
2351	94	F042	2
2352	94	F043	2
2353	94	F044	2
2354	94	F045	2
2355	95	M034	2
2356	95	N031	2
2357	95	N032	2
2358	95	N033	2
2359	96	L036	2
2360	96	M031	2
2361	96	M032	2
2362	96	M033	2
2363	97	D054	2
2364	97	D055	2
2365	97	D056	2
2366	97	D057	2
2367	97	D058	2
2368	97	D059	2
2369	97	E054	2
2370	97	E055	2
2371	97	E056	2
2372	97	E057	2
2373	97	E058	2
2374	97	F054	2
2375	97	F055	2
2376	97	F056	2
2377	97	F057	2
2378	97	F058	2
2379	97	F059	2
2380	97	G054	2
2381	97	G055	2
2382	97	G056	2
2383	97	G057	2
2384	97	G058	2
2385	97	G059	2
2386	97	H054	2
2387	97	H055	2
2388	97	H056	2
2389	97	H057	2
2390	97	H058	2
2391	97	H059	2
2392	97	I058	2
2393	97	I059	2
2394	98	G054	2
2395	98	G055	2
2396	98	G056	2
2397	98	G057	2
2398	98	G058	2
2399	98	G059	2
2400	98	H054	2
2401	98	H055	2
2402	98	H056	2
2403	98	H057	2
2404	98	H058	2
2405	98	H059	2
2406	98	I058	2
2407	98	I059	2
2408	99	G022	2
2409	99	K023	2
2410	99	K024	2
2411	99	K025	2
2412	99	K026	2
2413	99	K027	2
2414	99	K028	2
2415	99	K029	2
2416	99	K030	2
2417	99	K031	2
2418	99	K032	2
2419	99	K033	2
2420	99	K034	2
2421	99	K035	2
2422	99	K036	2
2423	99	K037	2
2424	99	K038	2
2425	99	K039	2
2426	100	H021	2
2427	100	H022	2
2428	100	H023	2
2429	100	H024	2
2430	101	O019	2
2431	101	O020	2
2432	101	O021	2
2433	101	O022	2
2434	101	P023	2
2435	101	P024	2
2436	101	P025	2
2437	101	Q020	2
2438	101	Q021	2
2439	102	G037	2
2440	102	G038	2
2441	102	G039	2
2442	102	G040	2
2443	102	G041	2
2444	102	H039	2
2445	102	H040	2
2446	102	H041	2
2447	102	I038	2
2448	103	E034	2
2449	103	E035	2
2450	103	E037	2
2451	103	E038	2
2452	103	E039	2
2453	103	E040	2
2454	103	F038	2
2455	103	F039	2
2456	103	F040	2
2457	104	A040	2
2458	104	A041	2
2459	104	A042	2
2460	104	A043	2
2461	105	B032	2
2462	105	C030	2
2463	105	C031	2
2464	105	C032	2
2465	105	C033	2
2466	105	C034	2
2467	105	C035	2
2468	105	D034	2
2469	105	D035	2
2470	106	A058	2
2471	106	B057	2
2472	106	C056	2
2473	106	D053	2
2474	106	E024	2
2475	106	E025	2
2476	106	E026	2
2477	106	E027	2
2478	107	I062	\N
2479	107	J068	\N
2480	107	K056	\N
2481	108	I065	2
2482	108	I066	2
2483	108	I067	2
2484	108	I068	2
2485	108	I069	2
2486	108	I070	2
2487	108	I071	2
2488	108	I072	2
2489	108	J075	2
2490	108	J076	2
2491	108	J077	2
2492	108	J078	2
2493	109	D064	2
2494	109	E064	2
2495	109	E065	2
2496	109	E066	2
2497	109	J055	2
2498	109	K065	2
2499	109	L062	2
2500	109	N059	2
2501	109	P059	2
2502	109	R059	2
2503	110	E067	2
2504	110	E068	2
2505	110	E076	2
2506	111	E061	2
2507	111	E063	2
2508	111	J073	2
2509	111	J092	2
2510	111	J093	2
2511	111	J094	2
2512	111	J095	2
2513	111	J096	2
2514	111	J097	2
2515	111	J098	2
2516	112	D062	2
2517	112	D063	2
2518	113	T022	2
2519	113	T023	2
2520	113	T024	2
2521	113	T025	2
2522	113	T027	2
2523	113	T029	2
2524	113	T030	2
2525	113	T031	2
2526	113	T032	2
2527	114	N041	2
2528	114	N042	2
2529	114	N043	2
2530	114	N044	2
2531	114	N045	2
2532	114	N046	2
2533	114	N047	2
2534	114	O041	2
2535	114	O042	2
2536	114	O043	2
2537	114	O044	2
2538	114	O045	2
2539	114	O046	2
2540	114	O047	2
2541	114	P036	2
2542	114	P043	2
2543	114	P044	2
2544	114	P045	2
2545	114	P046	2
2546	114	P047	2
2547	114	P137	2
2548	115	R034	2
2549	115	S025	2
2550	115	S026	2
2551	115	S027	2
2552	115	S031	2
2553	116	R043	2
2554	117	K049	2
2555	117	Q136	2
2556	118	F047	2
2557	118	H047	2
2558	118	I044	2
2559	119	L036	2
2560	120	M052	2
2561	120	M053	2
2562	120	M056	2
2563	121	M055	2
2564	122	K043	2
2565	123	J043	2
2566	123	L043	2
2567	124	W031	2
2568	124	W032	2
2569	124	W033	2
2570	124	W037	2
2571	124	X035	2
2572	124	X036	2
2573	124	Y035	2
2574	124	Y036	2
2575	124	Z036	2
2576	124	Z037	2
2577	124	Z038	2
2578	125	N026	2
2579	125	N027	2
2580	125	N030	2
2581	125	N031	2
2582	125	O027	2
2583	125	O030	2
2584	125	O031	2
2585	125	O032	2
2586	125	O036	2
2587	125	O037	2
2588	125	P031	2
2589	125	P035	2
2590	125	P037	2
2591	126	V040	2
2592	126	V041	2
2593	126	V042	2
2594	126	V043	2
2595	126	V044	2
2596	126	V045	2
2597	126	V046	2
2598	126	V047	2
2599	127	N024	2
2600	128	J037	2
2601	128	J039	2
2602	128	J041	2
2603	128	K037	2
2604	128	N032	2
2605	128	O029	2
2606	128	O033	2
2607	128	O034	2
2608	128	P033	2
2609	128	Q030	2
2610	128	Q031	2
2611	128	Q032	2
2612	128	Q033	2
2613	128	Q035	2
2614	128	Q036	2
2615	128	R035	2
2616	128	R036	2
2617	128	S036	2
2618	128	S037	2
2619	128	S039	2
2620	129	E161	2
2621	130	I090	2
2622	130	I091	2
2623	130	I092	2
2624	130	I093	2
2625	130	I094	2
2626	131	Q004	2
2627	131	Q005	2
2628	131	Q006	2
2629	131	Q007	2
2630	131	Q008	2
2631	131	Q009	2
2632	131	Q010	2
2633	131	Q011	2
2634	131	Q012	2
2635	131	R004	2
2636	131	R005	2
2637	131	R006	2
2638	131	R007	2
2639	131	R008	2
2640	131	R009	2
2641	131	R010	2
2642	131	R011	2
2643	131	R012	2
2644	132	L022	2
2645	132	L023	2
2646	132	L024	2
2647	132	L025	2
2648	132	M020	2
2649	132	M021	2
2650	132	M022	2
2651	132	M023	2
2652	132	M024	2
2653	132	M025	2
2654	132	N021	2
2655	132	N022	2
2656	132	N023	2
2657	132	N024	2
2658	132	N025	2
2659	132	N026	2
2660	132	O024	2
2661	132	O025	2
2662	133	C024	2
2663	133	C025	2
2664	133	C026	2
2665	133	C027	2
2666	133	C028	2
2667	133	C029	2
2668	133	D026	2
2669	133	D027	2
2670	133	D028	2
2671	133	D029	2
2672	133	E027	2
2673	133	E028	2
2674	133	E029	2
2675	133	E030	2
2676	133	G029	2
2677	133	H029	2
2678	133	I030	2
2679	133	J029	2
2680	133	J030	2
2681	134	A029	2
2682	134	A030	2
2683	134	A031	2
2684	134	A032	2
2685	134	A033	2
2686	134	A034	2
2687	134	A035	2
2688	134	A036	2
2689	134	B024	2
2690	134	B025	2
2691	134	B026	2
2692	134	B027	2
2693	134	B028	2
2694	134	B029	2
2695	134	B030	2
2696	134	B031	2
2697	134	B033	2
2698	134	B034	2
2699	134	B035	2
2700	134	B036	2
2701	135	C004	1
2702	135	D002	1
2703	135	D003	1
2704	135	D004	1
2705	135	D005	1
2706	135	E004	1
2707	135	E005	1
2708	135	L025	1
2709	135	L026	1
2710	135	L027	1
2711	135	L028	1
2712	135	L029	1
2713	135	L030	1
2714	135	L031	1
2715	135	M025	1
2716	135	M026	1
2717	135	M027	1
2718	135	M028	1
2719	135	M029	1
2720	135	M030	1
2721	135	M031	1
2722	135	N025	1
2723	135	N026	1
2724	135	N027	1
2725	135	N028	1
2726	135	N029	1
2727	135	N030	1
2728	135	N031	1
2729	136	C006	1
2730	136	C007	1
2731	136	C008	1
2732	136	C009	1
2733	136	C010	1
2734	136	C011	1
2735	136	C012	1
2736	136	K034	1
2737	136	K035	1
2738	136	K036	1
2739	136	L032	1
2740	136	L033	1
2741	136	L034	1
2742	136	L035	1
2743	136	L036	1
2744	136	L037	1
2745	136	L038	1
2746	136	M032	1
2747	136	M033	1
2748	136	M034	1
2749	136	M035	1
2750	136	M036	1
2751	136	M037	1
2752	136	M038	1
2753	136	N032	1
2754	137	D006	1
2755	137	D007	1
2756	137	D008	1
2757	137	D009	1
2758	137	D010	1
2759	137	D011	1
2760	137	D012	1
2761	137	E006	1
2762	137	E007	1
2763	137	E008	1
2764	137	E009	1
2765	137	E010	1
2766	137	E011	1
2767	137	E012	1
2768	137	F006	1
2769	137	F007	1
2770	137	F008	1
2771	137	F009	1
2772	137	F010	1
2773	137	F011	1
2774	137	G008	1
2775	137	G009	1
2776	137	G010	1
2777	137	G011	1
2778	138	A018	1
2779	138	B013	1
2780	138	B014	1
2781	138	B015	1
2782	138	B016	1
2783	138	B017	1
2784	138	B018	1
2785	138	B019	1
2786	138	C013	1
2787	138	C014	1
2788	138	C015	1
2789	138	C016	1
2790	138	C017	1
2791	138	C018	1
2792	138	C019	1
2793	138	D013	1
2794	138	D014	1
2795	138	D015	1
2796	138	D016	1
2797	138	D017	1
2798	138	D018	1
2799	138	D019	1
2800	138	L039	1
2801	138	M039	1
2802	138	M040	1
2803	139	E013	1
2804	139	E014	1
2805	139	E015	1
2806	139	E016	1
2807	139	E017	1
2808	139	E018	1
2809	139	E019	1
2810	139	F014	1
2811	139	F015	1
2812	139	F016	1
2813	139	F017	1
2814	139	F018	1
2815	139	F019	1
2816	139	G014	1
2817	139	G015	1
2818	139	G016	1
2819	139	G017	1
2820	139	G018	1
2821	139	G019	1
2822	140	A020	1
2823	140	A021	1
2824	140	A022	1
2825	140	A023	1
2826	140	B020	1
2827	140	B021	1
2828	140	B022	1
2829	140	B023	1
2830	140	C020	1
2831	140	C021	1
2832	140	C022	1
2833	140	C023	1
2834	140	D020	1
2835	140	D021	1
2836	140	D022	1
2837	140	D023	1
2838	140	E020	1
2839	140	E021	1
2840	140	E022	1
2841	140	E023	1
2842	140	F020	1
2843	140	F021	1
2844	140	F022	1
2845	140	F023	1
2846	140	G020	1
2847	140	G021	1
2848	140	G022	1
2849	140	G023	1
2850	141	D024	1
2851	141	D025	1
2852	141	D026	1
2853	141	E024	1
2854	141	E025	1
2855	141	E026	1
2856	141	E027	1
2857	141	E028	1
2858	141	E029	1
2859	141	E030	1
2860	141	E031	1
2861	141	F024	1
2862	141	F025	1
2863	141	F026	1
2864	141	F027	1
2865	141	F028	1
2866	141	F029	1
2867	141	F030	1
2868	141	F033	1
2869	141	G024	1
2870	141	G025	1
2871	141	G026	1
2872	141	G027	1
2873	141	G028	1
2874	141	G029	1
2875	141	G030	1
2876	141	G031	1
2877	141	G032	1
2878	141	G033	1
2879	141	G034	1
2880	142	H027	1
2881	142	H028	1
2882	142	H029	1
2883	142	H030	1
2884	142	H031	1
2885	142	H032	1
2886	142	H033	1
2887	142	H034	1
2888	142	H035	1
2889	142	I027	1
2890	142	I028	1
2891	142	I029	1
2892	142	I030	1
2893	142	I031	1
2894	142	I032	1
2895	142	I033	1
2896	142	I034	1
2897	142	I035	1
2898	142	I036	1
2899	142	J032	1
2900	142	J033	1
2901	142	J034	1
2902	142	J035	1
2903	142	J036	1
2904	142	J037	1
2905	142	J038	1
2906	143	J027	1
2907	143	J028	1
2908	143	J029	1
2909	143	J030	1
2910	143	J031	1
2911	143	K027	1
2912	143	K028	1
2913	143	K029	1
2914	143	K030	1
2915	143	K031	1
2916	143	K032	1
2917	143	K033	1
2918	143	L027	1
2919	143	L028	1
2920	143	L029	1
2921	143	L030	1
2922	143	L031	1
2923	143	L032	1
2924	143	L033	1
2925	143	M027	1
2926	143	M028	1
2927	143	M029	1
2928	143	M030	1
2929	143	M031	1
2930	143	M032	1
2931	143	M033	1
2932	144	H020	1
2933	144	H021	1
2934	144	H022	1
2935	144	H023	1
2936	144	H024	1
2937	144	H025	1
2938	144	H026	1
2939	144	I020	1
2940	144	I021	1
2941	144	I022	1
2942	144	I023	1
2943	144	I024	1
2944	144	I025	1
2945	144	I026	1
2946	144	J020	1
2947	144	J021	1
2948	144	J022	1
2949	144	J023	1
2950	144	J024	1
2951	144	J025	1
2952	144	J026	1
2953	144	K020	1
2954	144	K021	1
2955	144	K022	1
2956	144	K023	1
2957	144	K024	1
2958	144	K025	1
2959	144	K026	1
2960	145	H010	1
2961	145	H011	1
2962	145	H014	1
2963	145	H015	1
2964	145	H016	1
2965	145	H017	1
2966	145	H018	1
2967	145	H019	1
2968	145	I014	1
2969	145	I015	1
2970	145	I016	1
2971	145	I017	1
2972	145	I018	1
2973	145	I019	1
2974	145	J014	1
2975	145	J015	1
2976	145	J016	1
2977	145	J017	1
2978	145	J018	1
2979	145	J019	1
2980	145	K016	1
2981	145	K017	1
2982	145	K018	1
2983	145	K019	1
2984	145	L018	1
2985	145	L019	1
2986	145	L020	1
2987	146	L021	1
2988	146	L022	1
2989	146	L023	1
2990	146	L024	1
2991	146	L025	1
2992	146	L026	1
2993	146	M020	1
2994	146	M021	1
2995	146	M022	1
2996	146	M023	1
2997	146	M024	1
2998	146	M025	1
2999	146	M026	1
3000	146	N022	1
3001	146	N023	1
3002	146	N024	1
3003	146	N025	1
3004	146	N026	1
3005	146	N027	1
3006	146	N028	1
3007	146	N029	1
3008	146	N030	1
3009	146	N031	1
3010	146	N032	1
3011	146	N033	1
3012	146	O024	1
3013	146	O025	1
3014	146	O026	1
3015	146	P026	1
3016	147	K034	1
3017	147	K035	1
3018	147	K036	1
3019	147	K037	1
3020	147	K038	1
3021	147	K039	1
3022	147	K040	1
3023	147	K041	1
3024	147	L034	1
3025	147	L035	1
3026	147	L036	1
3027	147	L037	1
3028	147	L038	1
3029	147	L039	1
3030	147	L040	1
3031	147	L041	1
3032	147	L042	1
3033	147	L043	1
3034	147	M034	1
3035	147	M035	1
3036	147	M036	1
3037	147	M037	1
3038	147	M038	1
3039	147	M039	1
3040	147	M040	1
3041	147	M041	1
3042	147	M042	1
3043	147	N027	1
3044	147	N028	1
3045	147	N029	1
3046	147	N030	1
3047	147	N031	1
3048	147	N032	1
3049	147	N033	1
3050	147	N040	1
3051	147	N041	1
3052	147	O030	1
3053	147	O031	1
3054	147	O032	1
3055	147	O033	1
3056	148	K034	1
3057	148	K035	1
3058	148	K036	1
3059	148	K037	1
3060	148	K038	1
3061	148	K039	1
3062	148	K040	1
3063	148	K041	1
3064	148	L034	1
3065	148	L035	1
3066	148	L036	1
3067	148	L037	1
3068	148	L038	1
3069	148	L039	1
3070	148	L040	1
3071	148	L041	1
3072	148	L042	1
3073	148	L043	1
3074	148	M034	1
3075	148	M035	1
3076	148	M036	1
3077	148	M037	1
3078	148	M038	1
3079	148	M039	1
3080	148	M040	1
3081	148	M041	1
3082	148	M042	1
3083	148	N034	1
3084	148	N035	1
3085	148	N036	1
3086	148	N037	1
3087	148	N038	1
3088	148	N039	1
3089	148	N040	1
3090	148	N041	1
3091	148	O034	1
3092	148	O035	1
3093	148	O036	1
3094	148	O037	1
3095	148	O038	1
3096	148	O039	1
3097	148	O040	1
3098	148	O041	1
3099	148	O042	1
3100	148	O043	1
3101	148	O044	1
3102	148	P036	1
3103	148	P037	1
3104	148	P038	1
3105	148	P041	1
3106	148	P042	1
3107	148	P043	1
3108	148	P044	1
3109	148	P045	1
3110	148	P046	1
3111	148	P047	1
3112	148	P048	1
3113	148	Q045	1
3114	148	Q046	1
3115	148	Q047	1
3116	148	Q048	1
3117	149	N034	1
3118	149	N035	1
3119	149	N036	1
3120	149	N037	1
3121	149	N038	1
3122	149	N039	1
3123	149	O034	1
3124	149	O035	1
3125	149	O036	1
3126	149	O037	1
3127	149	O038	1
3128	149	O039	1
3129	149	P036	1
3130	149	P037	1
3131	149	P038	1
3132	149	P039	1
3133	149	P040	1
3134	149	P049	1
3135	149	P050	1
3136	149	P051	1
3137	149	P052	1
3138	149	P053	1
3139	149	Q038	1
3140	149	Q039	1
3141	149	Q040	1
3142	149	Q041	1
3143	149	Q042	1
3144	149	Q043	1
3145	149	Q044	1
3146	149	Q049	1
3147	149	Q050	1
3148	149	R042	1
3149	149	R043	1
3150	149	R044	1
3151	149	R045	1
3152	149	R046	1
3153	149	R047	1
3154	149	R048	1
3155	149	R049	1
3156	150	O027	1
3157	150	O028	1
3158	150	O029	1
3159	150	O030	1
3160	150	O031	1
3161	150	O032	1
3162	150	O033	1
3163	150	O040	1
3164	150	O041	1
3165	150	O042	1
3166	150	O043	1
3167	150	O044	1
3168	150	P027	1
3169	150	P028	1
3170	150	P029	1
3171	150	P030	1
3172	150	P031	1
3173	150	P032	1
3174	150	P033	1
3175	150	P034	1
3176	150	P035	1
3177	150	P041	1
3178	150	P042	1
3179	150	P043	1
3180	150	P044	1
3181	150	P045	1
3182	150	P046	1
3183	150	P047	1
3184	150	P048	1
3185	150	Q028	1
3186	150	Q045	1
3187	150	Q046	1
3188	150	Q047	1
3189	150	R045	1
3190	150	R046	1
3191	150	R047	1
3192	150	R048	1
3193	150	R049	1
3194	151	B002	1
3195	151	B003	1
3196	151	B004	1
3197	151	B005	1
3198	151	B006	1
3199	151	B007	1
3200	151	B008	1
3201	151	B009	1
3202	151	C003	1
3203	151	C004	1
3204	151	C005	1
3205	151	C006	1
3206	151	C007	1
3207	151	C008	1
3208	151	C009	1
3209	151	D004	1
3210	151	D005	1
3211	151	D006	1
3212	151	D007	1
3213	151	D008	1
3214	151	D009	1
3215	151	E006	1
3216	151	E007	1
3217	151	E008	1
3218	151	E009	1
3219	151	F007	1
3220	151	F008	1
3221	151	F009	1
3222	151	G009	1
3223	152	C010	1
3224	152	C011	1
3225	152	C012	1
3226	152	D010	1
3227	152	D011	1
3228	152	D012	1
3229	152	D013	1
3230	152	D014	1
3231	152	E010	1
3232	152	E011	1
3233	152	E012	1
3234	152	E013	1
3235	152	E014	1
3236	152	E015	1
3237	152	F010	1
3238	152	F011	1
3239	152	F012	1
3240	152	F013	1
3241	152	F014	1
3242	152	F015	1
3243	152	G010	1
3244	152	G011	1
3245	152	G012	1
3246	152	G013	1
3247	152	G014	1
3248	152	G015	1
3249	152	G016	1
3250	152	G017	1
3251	153	H009	1
3252	153	H010	1
3253	153	H011	1
3254	153	H012	1
3255	153	H013	1
3256	153	H014	1
3257	153	H015	1
3258	153	H016	1
3259	153	H017	1
3260	153	I010	1
3261	153	I011	1
3262	153	I012	1
3263	153	I013	1
3264	153	I014	1
3265	153	I015	1
3266	153	I016	1
3267	153	I017	1
3268	153	J011	1
3269	153	J012	1
3270	153	J013	1
3271	153	J014	1
3272	153	J015	1
3273	153	J016	1
3274	153	J017	1
3275	153	K014	1
3276	153	K015	1
3277	153	K016	1
3278	153	K017	1
3279	153	L017	1
3280	154	H018	1
3281	154	H019	1
3282	154	H020	1
3283	154	I018	1
3284	154	I019	1
3285	154	I020	1
3286	154	I021	1
3287	154	I022	1
3288	154	J018	1
3289	154	J019	1
3290	154	J020	1
3291	154	J021	1
3292	154	J022	1
3293	154	K018	1
3294	154	K019	1
3295	154	K020	1
3296	154	K021	1
3297	154	K022	1
3298	154	L018	1
3299	154	L019	1
3300	154	L020	1
3301	154	L021	1
3302	154	L022	1
3303	154	L023	1
3304	154	L024	1
3305	154	M021	1
3306	154	M022	1
3307	154	M023	1
3308	154	M024	1
3309	155	H024	1
3310	155	I023	1
3311	155	I024	1
3312	155	I025	1
3313	155	I026	1
3314	155	I027	1
3315	155	J023	1
3316	155	J024	1
3317	155	J025	1
3318	155	J026	1
3319	155	J027	1
3320	155	J028	1
3321	155	J029	1
3322	155	J030	1
3323	155	J031	1
3324	155	J032	1
3325	155	K023	1
3326	155	K024	1
3327	155	K025	1
3328	155	K026	1
3329	155	K027	1
3330	155	K028	1
3331	155	K029	1
3332	155	K030	1
3333	155	K031	1
3334	155	K032	1
3335	155	K033	1
3336	156	C013	2
3337	156	C014	2
3338	156	C015	2
3339	156	C016	2
3340	156	D014	2
3341	156	D015	2
3342	156	D016	2
3343	156	D017	2
3344	156	D018	2
3345	156	D019	2
3346	156	D020	2
3347	156	E016	2
3348	156	E017	2
3349	156	E018	2
3350	156	E019	2
3351	156	E020	2
3352	156	E021	2
3353	156	E022	2
3354	156	E023	2
3355	156	E024	2
3356	156	F016	2
3357	156	F017	2
3358	157	F018	2
3359	157	F019	2
3360	157	F020	2
3361	157	F021	2
3362	157	F022	2
3363	157	F023	2
3364	157	F024	2
3365	157	G017	2
3366	157	G018	2
3367	157	G019	2
3368	157	G020	2
3369	157	G021	2
3370	157	G022	2
3371	157	G023	2
3372	157	G024	2
3373	157	H020	2
3374	157	H021	2
3375	157	H022	2
3376	157	H023	2
3377	158	A024	2
3378	158	A025	2
3379	158	A026	2
3380	158	A027	2
3381	158	A028	2
3382	158	A037	2
3383	158	B024	2
3384	158	B025	2
3385	158	B026	2
3386	158	B027	2
3387	158	B028	2
3388	158	B036	2
3389	158	C024	2
3390	158	C025	2
3391	158	C026	2
3392	158	C027	2
3393	158	C028	2
3394	158	C029	2
3395	158	C030	2
3396	158	C031	2
3397	158	D024	2
3398	158	D025	2
3399	158	D026	2
3400	158	D027	2
3401	158	D028	2
3402	158	D029	2
3403	158	D030	2
3404	158	D031	2
3405	158	D032	2
3406	158	D033	2
3407	158	E033	2
3408	158	X026	2
3409	158	X027	2
3410	158	X028	2
3411	158	X029	2
3412	158	X030	2
3413	158	X031	2
3414	159	A029	2
3415	159	A031	2
3416	159	A032	2
3417	159	A033	2
3418	159	A034	2
3419	159	B029	2
3420	159	B031	2
3421	159	B032	2
3422	159	B033	2
3423	159	B034	2
3424	159	B037	2
3425	159	C032	2
3426	159	C033	2
3427	159	C034	2
3428	159	C035	2
3429	159	C037	2
3430	159	D034	2
3431	159	D035	2
3432	159	D038	2
3433	159	D039	2
3434	159	E034	2
3435	159	E035	2
3436	159	X032	2
3437	159	X033	2
3438	160	Y001	2
3439	160	Y002	2
3440	160	Y003	2
3441	160	Y004	2
3442	160	Y005	2
3443	160	Y006	2
3444	160	Y007	2
3445	160	Y008	2
3446	161	E004	2
3447	161	E005	2
3448	161	E006	2
3449	161	F008	2
3450	161	F009	2
3451	161	F010	2
3452	161	G009	2
3453	161	G010	2
3454	161	G011	2
3455	161	G012	2
3456	162	D013	1
3457	162	E009	1
3458	162	E010	1
3459	162	E011	1
3460	162	E012	1
3461	162	F011	1
3462	162	F012	1
3463	162	F013	1
3464	162	F014	1
3465	162	F015	1
3466	162	G011	1
3467	162	G012	1
3468	162	G013	1
3469	162	G014	1
3470	162	G015	1
3471	162	G016	1
3472	162	G017	1
3473	162	H011	1
3474	162	H012	1
3475	162	H013	1
3476	162	H014	1
3477	162	H015	1
3478	162	H016	1
3479	162	H017	1
3480	162	P009	1
3481	162	P010	1
3482	163	H015	1
3483	163	H016	1
3484	163	H017	1
3485	163	H018	1
3486	163	H019	1
3487	163	I013	1
3488	163	I014	1
3489	163	I015	1
3490	163	I016	1
3491	163	I017	1
3492	163	I018	1
3493	163	I019	1
3494	163	I020	1
3495	163	I021	1
3496	163	J014	1
3497	163	J016	1
3498	163	J017	1
3499	163	J018	1
3500	163	J019	1
3501	163	J020	1
3502	163	J021	1
3503	163	J022	1
3504	163	J023	1
3505	163	L011	1
3506	163	L012	1
3507	163	L013	1
3508	163	L014	1
3509	163	L015	1
3510	163	L016	1
3511	163	L017	1
3512	163	L018	1
3513	163	L019	1
3514	163	M011	1
3515	163	M012	1
3516	163	M013	1
3517	163	M015	1
3518	163	M016	1
3519	163	M017	1
3520	163	M018	1
3521	163	M019	1
3522	163	N011	1
3523	163	N012	1
3524	164	A001	1
3525	164	A002	1
3526	164	A003	1
3527	164	A004	1
3528	164	A005	1
3529	164	A006	1
3530	164	A007	1
3531	164	A008	1
3532	164	A009	1
3533	164	B001	1
3534	164	B002	1
3535	164	B003	1
3536	164	B004	1
3537	164	B005	1
3538	164	B006	1
3539	164	B007	1
3540	164	B008	1
3541	164	B009	1
3542	164	C001	1
3543	164	C002	1
3544	164	C003	1
3545	164	C004	1
3546	164	C005	1
3547	164	C006	1
3548	164	C007	1
3549	164	C008	1
3550	164	L011	1
3551	164	L012	1
3552	164	L013	1
3553	164	L014	1
3554	164	L015	1
3555	164	L016	1
3556	164	L017	1
3557	164	L018	1
3558	164	L019	1
3559	164	M011	1
3560	164	M012	1
3561	164	M013	1
3562	164	M015	1
3563	164	M016	1
3564	164	M017	1
3565	164	M018	1
3566	164	M019	1
3567	164	N011	1
3568	164	N012	1
3569	165	A001	1
3570	165	A002	1
3571	165	A003	1
3572	165	A004	1
3573	165	A005	1
3574	165	A006	1
3575	165	A007	1
3576	165	A008	1
3577	165	A009	1
3578	165	A010	1
3579	165	A011	1
3580	165	A012	1
3581	165	A013	1
3582	165	A014	1
3583	165	A015	1
3584	165	B001	1
3585	165	B002	1
3586	165	B003	1
3587	165	B004	1
3588	165	B005	1
3589	165	B006	1
3590	165	B007	1
3591	165	B008	1
3592	165	B009	1
3593	165	B010	1
3594	165	B011	1
3595	165	B012	1
3596	165	B013	1
3597	165	B014	1
3598	165	B015	1
3599	165	B016	1
3600	165	C001	1
3601	165	C002	1
3602	165	C003	1
3603	165	C004	1
3604	165	C005	1
3605	165	C006	1
3606	165	C007	1
3607	165	C008	1
3608	165	C009	1
3609	165	C010	1
3610	165	C011	1
3611	165	C012	1
3612	165	C013	1
3613	165	C014	1
3614	165	C015	1
3615	165	D009	1
3616	165	D010	1
3617	165	D011	1
3618	166	A011	1
3619	166	A012	1
3620	166	A013	1
3621	166	A014	1
3622	166	A015	1
3623	166	A016	1
3624	166	A017	1
3625	166	A018	1
3626	166	A019	1
3627	166	A020	1
3628	166	A021	1
3629	166	A022	1
3630	166	A023	1
3631	166	A024	1
3632	166	B011	1
3633	166	B012	1
3634	166	B013	1
3635	166	B014	1
3636	166	B015	1
3637	166	B016	1
3638	166	B017	1
3639	166	B018	1
3640	166	B019	1
3641	166	B020	1
3642	166	B021	1
3643	166	B022	1
3644	166	B023	1
3645	166	B024	1
3646	166	B025	1
3647	166	B026	1
3648	166	C009	1
3649	166	C010	1
3650	166	C011	1
3651	166	C012	1
3652	166	C013	1
3653	166	C014	1
3654	166	C015	1
3655	166	C016	1
3656	166	C017	1
3657	166	C018	1
3658	166	C019	1
3659	166	C020	1
3660	166	C021	1
3661	166	C022	1
3662	166	D009	1
3663	166	D010	1
3664	166	D011	1
3665	166	D012	1
3666	167	A018	1
3667	167	A019	1
3668	167	A020	1
3669	167	A021	1
3670	167	A022	1
3671	167	A023	1
3672	167	A024	1
3673	167	B017	1
3674	167	B018	1
3675	167	B019	1
3676	167	B020	1
3677	167	B021	1
3678	167	B022	1
3679	167	B023	1
3680	167	B024	1
3681	167	B025	1
3682	167	B026	1
3683	167	C019	1
3684	167	C020	1
3685	167	C021	1
3686	167	C022	1
3687	167	D012	1
3688	168	B002	2
3689	168	B003	2
3690	168	B004	2
3691	168	B005	2
3692	168	C002	2
3693	168	C003	2
3694	168	C004	2
3695	168	C005	2
3696	168	C006	2
3697	168	C007	2
3698	168	C009	2
3699	168	D004	2
3700	168	D005	2
3701	168	D006	2
3702	168	D010	2
3703	169	J013	2
3704	169	K011	2
3705	169	K013	2
3706	169	K014	2
3707	169	K015	2
3708	169	K016	2
3709	169	K017	2
3710	169	K018	2
3711	169	L011	2
3712	170	A025	2
3713	170	A026	2
3714	170	A027	2
3715	170	A028	2
3716	170	A029	2
3717	170	A030	2
3718	170	A031	2
3719	170	A032	2
3720	170	B027	2
3721	170	B028	2
3722	170	B029	2
3723	170	B030	2
3724	170	B031	2
3725	170	B032	2
3726	170	B033	2
3727	170	B034	2
3728	171	D008	2
3729	171	D009	2
3730	171	E007	2
3731	171	E008	2
3732	171	F006	2
3733	172	D001	1
3734	172	E001	1
3735	172	F001	1
3736	172	G001	1
3737	172	H001	1
3738	172	I001	1
3739	172	J001	1
3740	172	J002	1
3741	172	K001	1
3742	172	L001	1
3743	172	M001	1
3744	173	F010	1
3745	173	G010	1
3746	173	H006	1
3747	173	H007	1
3748	173	J004	1
3749	173	J010	1
3750	173	J011	1
3751	173	K003	1
3752	173	K004	1
3753	173	K005	1
3754	173	L004	1
3755	173	L005	1
3756	173	L006	1
3757	173	L007	1
3758	173	L008	1
3759	173	L009	1
3760	173	L010	1
3761	173	M008	1
3762	173	M009	1
3763	173	M010	1
3764	173	M011	1
3765	173	M012	1
3766	173	N010	1
3767	173	N011	1
3768	174	B033	2
3769	175	C042	1
3770	175	C043	1
3771	175	C044	1
3772	175	C045	1
3773	175	C046	1
3774	175	C047	1
3775	175	C048	1
3776	175	C049	1
3777	175	C050	1
3778	175	C052	1
3779	175	C053	1
3780	175	D042	1
3781	175	D043	1
3782	175	D045	1
3783	175	D046	1
3784	175	D047	1
3785	175	D048	1
3786	175	D049	1
3787	175	D050	1
3788	175	E043	1
3789	175	E045	1
3790	175	E046	1
3791	175	E047	1
3792	175	E048	1
3793	175	E049	1
3794	175	E050	1
3795	175	E051	1
3796	175	E052	1
3797	175	F044	1
3798	175	F045	1
3799	175	F046	1
3800	175	F047	1
3801	175	F048	1
3802	176	C032	1
3803	176	C033	1
3804	176	C034	1
3805	176	C036	1
3806	176	C037	1
3807	176	C039	1
3808	176	C040	1
3809	176	C041	1
3810	176	D032	1
3811	176	D033	1
3812	176	D034	1
3813	176	D035	1
3814	176	D036	1
3815	176	D037	1
3816	176	D038	1
3817	176	D039	1
3818	176	D040	1
3819	176	D041	1
3820	176	E031	1
3821	176	E032	1
3822	176	E033	1
3823	176	E034	1
3824	176	E035	1
3825	176	E036	1
3826	176	E037	1
3827	176	F030	1
3828	176	F031	1
3829	176	F032	1
3830	176	F033	1
3831	177	C020	1
3832	177	C021	1
3833	177	C022	1
3834	177	C023	1
3835	177	C024	1
3836	177	C025	1
3837	177	C026	1
3838	177	C027	1
3839	177	C029	1
3840	177	D020	1
3841	177	D021	1
3842	177	D022	1
3843	177	D023	1
3844	177	D024	1
3845	177	D025	1
3846	177	D026	1
3847	177	D027	1
3848	177	D028	1
3849	177	D029	1
3850	177	E021	1
3851	177	E022	1
3852	177	E023	1
3853	177	E024	1
3854	177	E025	1
3855	177	E026	1
3856	177	E027	1
3857	177	E028	1
3858	177	E029	1
3859	177	F023	1
3860	177	F026	1
3861	177	F027	1
3862	178	B004	1
3863	178	B005	1
3864	178	B006	1
3865	178	B007	1
3866	178	C001	1
3867	178	C002	1
3868	178	C003	1
3869	178	C004	1
3870	178	C005	1
3871	178	C006	1
3872	178	C007	1
3873	178	C008	1
3874	178	C009	1
3875	178	C010	1
3876	178	D001	1
3877	178	D002	1
3878	178	D003	1
3879	178	D004	1
3880	178	D005	1
3881	178	D006	1
3882	178	D007	1
3883	178	D008	1
3884	178	D009	1
3885	179	C011	1
3886	179	C012	1
3887	179	C013	1
3888	179	D010	1
3889	179	D011	1
3890	179	D012	1
3891	179	D013	1
3892	179	D014	1
3893	179	D015	1
3894	179	E001	1
3895	179	E002	1
3896	179	E003	1
3897	179	E004	1
3898	179	E005	1
3899	179	E006	1
3900	179	E007	1
3901	179	E008	1
3902	179	E009	1
3903	179	E010	1
3904	179	E011	1
3905	179	E012	1
3906	179	E013	1
3907	179	E014	1
3908	180	O020	1
3909	180	P011	1
3910	180	P012	1
3911	180	P014	1
3912	180	P015	1
3913	180	P016	1
3914	180	P017	1
3915	180	P019	1
3916	180	P020	1
3917	180	P024	1
3918	180	Q010	1
3919	180	Q013	1
3920	180	Q015	1
3921	180	Q016	1
3922	180	Q018	1
3923	181	P022	1
3924	181	P025	1
3925	181	P026	1
3926	181	Q022	1
3927	181	Q023	1
3928	181	Q024	1
3929	181	Q026	1
3930	182	M040	1
3931	182	M041	1
3932	182	M042	1
3933	182	M043	1
3934	182	M044	1
3935	182	M045	1
3936	182	M046	1
3937	182	N036	1
3938	182	N037	1
3939	182	N038	1
3940	182	N039	1
3941	182	N040	1
3942	182	N041	1
3943	182	N042	1
3944	182	N043	1
3945	182	N044	1
3946	182	N045	1
3947	182	N046	1
3948	182	O034	1
3949	182	O035	1
3950	182	O036	1
3951	182	O037	1
3952	183	R047	1
3953	183	R048	1
3954	183	S029	1
3955	183	S030	1
3956	183	S044	1
3957	183	S045	1
3958	183	S046	1
3959	183	S047	1
3960	183	S048	1
3961	183	T031	1
3962	183	T044	1
3963	183	T045	1
3964	183	T046	1
3965	183	T047	1
3966	183	T048	1
3967	183	T049	1
3968	183	T050	1
3969	183	U043	1
3970	183	U044	1
3971	183	U045	1
3972	183	U046	1
3973	183	U047	1
3974	183	V039	1
3975	183	V040	1
3976	183	V041	1
3977	184	O038	2
3978	184	O039	2
3979	184	O040	2
3980	184	P023	2
3981	184	P028	2
3982	184	P029	2
3983	184	P038	2
3984	184	P039	2
3985	184	P040	2
3986	184	P041	2
3987	184	Q028	2
3988	184	Q029	2
3989	184	Q031	2
3990	184	Q040	2
3991	184	R028	2
3992	184	R030	2
3993	184	U036	2
3994	184	V036	2
3995	184	V037	2
3996	185	M047	2
3997	185	M048	2
3998	185	M049	2
3999	185	Q034	2
4000	185	U038	2
4001	185	V042	2
4002	106	J022	2
4003	186	I008	2
4004	186	I007	2
4005	186	G020	2
4006	186	I006	2
4007	186	I024	2
4008	186	D026	2
4009	186	C027	2
4010	186	O025	2
4011	186	P028	2
4012	186	Q037	2
4013	31	O020	1
4014	31	P020	1
4015	32	O032	1
4016	150	O024	1
4017	150	O025	1
4018	150	O026	1
4019	150	P026	1
4020	150	N028	1
4021	146	O032	1
4022	146	O033	1
4023	149	P041	1
4024	149	P048	1
4025	149	Q047	1
4026	127	N025	2
4027	105	J023	2
\.


--
-- Data for Name: companies; Type: TABLE DATA; Schema: master; Owner: -
--

COPY master.companies (id, code, name, group_id, short_name) FROM stdin;
9	1900	\N	1	\N
12	3300	\N	2	\N
1	1100	PT. TANJUNG BUYU PERKASA PLANTATION	1	TBP
10	3100	\N	2	SSS
11	3200	\N	2	PCS
2	1200	\N	1	INK
3	1300	PT. TELEN	1	TEL
4	1400	\N	1	SPN
5	1500	\N	1	GSA
6	1600	PT. TELEN PRIMA SAWIT	1	TPS
7	1610	\N	1	MJA
8	1800	\N	1	CAP
\.


--
-- Data for Name: divisions; Type: TABLE DATA; Schema: master; Owner: -
--

COPY master.divisions (id, estate_id, code) FROM stdin;
1	1	AFDI01
2	1	AFDI02
3	1	AFDI03
4	1	AFDI04
5	1	AFDI05
6	1	AFDI06
7	1	AFDI07
8	2	AFDI01
9	2	AFDI02
10	2	AFDI03
11	3	AFDI01
12	3	AFDI02
13	4	AFDI01
14	4	AFDI02
15	4	AFDI03
16	5	AFDI01
17	5	AFDI02
18	5	AFDI03
19	5	AFDI04
20	6	AFDI01
21	6	AFDI02
22	6	AFDI03
23	7	AFDI01
24	7	AFDI02
25	7	AFDI03
26	7	AFDI04
27	7	AFDI05
28	7	AFDI06
29	7	AFDI07
30	8	AFDI01
31	8	AFDI02
32	8	AFDI03
33	8	AFDI04
34	9	AFDI01
35	9	AFDI02
36	9	AFDI03
37	9	AFDI04
38	10	AFDI01
39	10	AFDI02
40	10	AFDI03
41	10	AFDI04
42	10	AFDI05
43	11	AFDI01
44	11	AFDI02
45	11	AFDI03
46	11	AFDI04
47	11	AFDI05
48	11	AFDI06
49	12	AFDI01
50	12	AFDI02
51	12	AFDI03
52	12	AFDI04
53	12	AFDI05
54	13	AFDI01
55	13	AFDI02
56	13	AFDI03
57	13	AFDI04
58	13	AFDI05
59	13	AFDI06
60	13	AFDI07
61	14	AFDI01
62	14	AFDI02
63	14	AFDI03
64	14	AFDI04
65	14	AFDI05
66	15	AFDI01
67	15	AFDI02
68	15	AFDI03
69	15	AFDI04
70	15	AFDI05
71	16	AFDP01
72	16	AFDP02
73	16	AFDP03
74	16	AFDP04
75	16	AFDP05
76	16	AFDP06
77	16	AFDP07
78	16	AFDP08
79	16	AFDP09
80	16	AFDP10
81	16	AFDP11
82	16	AFDP12
83	16	AFDP13
84	16	AFDP15
85	16	AFDP16
86	16	AFDP17
87	16	AFDP18
88	17	AFDP01
89	17	AFDP02
90	18	AFDP01
91	18	AFDP02
92	18	AFDP03
93	18	AFDP04
94	18	AFDP05
95	18	AFDP06
96	18	AFDP07
97	19	AFDP08
98	19	AFDP09
99	20	AFDP01
100	20	AFDP02
101	20	AFDP03
102	20	AFDP04
103	20	AFDP05
104	20	AFDP06
105	20	AFDP07
106	20	AFDP08
107	21	AFDI04
108	21	AFDP01
109	21	AFDP02
110	21	AFDP03
111	21	AFDP04
112	21	AFDP05
113	21	AFDP06
114	21	AFDP07
115	21	AFDP08
116	21	AFDP09
117	21	AFDP10
118	21	AFDP11
119	21	AFDP12
120	21	AFDP13
121	21	AFDP14
122	21	AFDP15
123	21	AFDP16
124	21	AFDP17
125	21	AFDP18
126	21	AFDP19
127	21	AFDP20
128	21	AFDP21
129	21	AFDP22
130	21	AFDP23
131	22	AFDP01
132	22	AFDP02
133	22	AFDP03
134	22	AFDP04
135	23	AFDI01
136	23	AFDI02
137	23	AFDI03
138	23	AFDI04
139	23	AFDI05
140	23	AFDI06
141	24	AFDI01
142	24	AFDI02
143	24	AFDI03
144	24	AFDI04
145	24	AFDI05
146	25	AFDI01
147	25	AFDI02
148	25	AFDI03
149	25	AFDI04
150	25	AFDI05
151	26	AFDI01
152	26	AFDI02
153	26	AFDI03
154	26	AFDI04
155	26	AFDI05
156	27	AFDP01
157	27	AFDP02
158	27	AFDP03
159	27	AFDP04
160	27	AFDP05
161	27	AFDP06
162	28	AFDI01
163	28	AFDI02
164	28	AFDI03
165	28	AFDI04
166	28	AFDI05
167	28	AFDI06
168	29	AFDP01
169	29	AFDP02
170	29	AFDP03
171	29	AFDP04
172	30	AFDI01
173	30	AFDI02
174	31	AFDP01
175	32	AFDI01
176	32	AFDI02
177	32	AFDI03
178	32	AFDI04
179	32	AFDI05
180	33	AFDI01
181	33	AFDI02
182	33	AFDI03
183	33	AFDI04
184	34	AFDP01
185	34	AFDP02
186	18	AFDP10
\.


--
-- Data for Name: estates; Type: TABLE DATA; Schema: master; Owner: -
--

COPY master.estates (id, company_id, code, name, short_name, area_id) FROM stdin;
1	1	E001	Talisayan 1 Estate	TS1	1
2	1	E004	Biatan Estate	BTE	1
3	2	E005	Ampen Medang Estate	AME	1
4	3	E006	Bukit Permata 1 Estate	BP1	4
5	3	E007	Bukit Permata 2 Estate	BP2	4
6	3	E008	Layang - Layang Estate	LYE	4
7	3	E009	Pengadan Baay 1 Estate	PB1	4
8	3	E011	Sei Karangan Estate	SKE	4
9	4	E012	Mata Air Estate	MAE	4
10	5	E013	Long Mesangat Estate	LME	5
11	6	E014	Muara Bengkal 1 Estate	MB1	5
12	6	E017	Benua Baru 2 Estate	BB2	5
13	7	E018	Tanjung Harapan Estate 1	TH1	8
14	8	E020	SEA GUNTUNG ESTATE	SGE	3
15	8	E021	FELIZA ESTATE	FLE	3
16	1	E022	Plasma TBP Estate	PBP	1
17	2	E023	Plasma INK Estate	PNK	1
18	3	E024	Plasma TLN Estate	PLN	4
19	4	E025	Plasma SPN Estate	PPN	4
20	5	E026	Plasma GSA Estate	PSA	5
21	6	E027	Plasma TPS Estate	PPS	5
22	7	E028	Plasma MJA Estate	PJA	8
23	10	E029	Senyiur Estate	SNE	6
24	10	E030	Muara Ancalong Estate	MGE	6
25	10	E031	Loa Ketiau Estate	LKE	6
26	10	E032	Kedang Kepala Estate	KKE	6
27	10	E033	Plasma SSS	PSS	6
28	11	E034	Mentelang 1 Estate	MT1	6
29	11	E035	Plasma PCS	PPC	6
30	12	E036	Tanjung Perepat Estate	TPE	2
31	12	E037	Plasma TAN Estate	PAN	2
32	9	E038	Kelinjau Estate	KLE	7
33	9	E039	Long Mesangat 2 Estate	LM2	7
34	9	E040	Plasma CDM Estate	PDM	7
\.


--
-- Data for Name: groups; Type: TABLE DATA; Schema: master; Owner: -
--

COPY master.groups (id, code, name) FROM stdin;
1	TPA	\N
2	SGA	\N
\.


--
-- Data for Name: block_types; Type: TABLE DATA; Schema: ref; Owner: -
--

COPY ref.block_types (id, name) FROM stdin;
1	Inti
2	Plasma
\.


--
-- Data for Name: planting_statuses; Type: TABLE DATA; Schema: ref; Owner: -
--

COPY ref.planting_statuses (id, code) FROM stdin;
1	LC
2	TBM
3	TM
\.


--
-- Data for Name: rotation_statuses; Type: TABLE DATA; Schema: ref; Owner: -
--

COPY ref.rotation_statuses (id, name) FROM stdin;
1	Normal
2	Sedang
3	Buruk
\.


--
-- Data for Name: seed_varieties; Type: TABLE DATA; Schema: ref; Owner: -
--

COPY ref.seed_varieties (id, name) FROM stdin;
1	BSM
2	Bah lias
3	COSTARIKA
4	DP SAIN
5	Dami Mas
6	FELDA
7	FELDA 3WAY
8	LONS
9	Londsum
10	Lonsum
11	Marihat
12	Nigeria
13	PPKS
14	SPRING
15	Socfin
16	Socfindo
17	Topaz
18	Verdant
19	0
\.


--
-- Data for Name: soil_types; Type: TABLE DATA; Schema: ref; Owner: -
--

COPY ref.soil_types (id, name) FROM stdin;
1	RAWA
2	TANAH GAMBUT AV
3	TANAH MINERAL
4	Tanah
5	Tanah Organosol - Gambut
6	Tanah Pasir
7	0
\.


--
-- Data for Name: topography_types; Type: TABLE DATA; Schema: ref; Owner: -
--

COPY ref.topography_types (id, name) FROM stdin;
1	BERGELOMBANG
2	BUKIT
3	DATAR
4	GELOMBANG
5	0
\.


--
-- Data for Name: tph_categories; Type: TABLE DATA; Schema: ref; Owner: -
--

COPY ref.tph_categories (id, name) FROM stdin;
1	Estimasi
\.


--
-- Data for Name: tree_categories; Type: TABLE DATA; Schema: ref; Owner: -
--

COPY ref.tree_categories (id, name) FROM stdin;
1	Kuning
2	Mati
3	Normal
\.


--
-- Data for Name: value_aliases; Type: TABLE DATA; Schema: ref; Owner: -
--

COPY ref.value_aliases (ref_table, alias, canonical, evidence) FROM stdin;
seed_varieties	CSTR	COSTARIKA	21 blocks switch between CSTR and COSTARIKA from one month to the next
soil_types	PASIR	Tanah Pasir	183 blocks switch between PASIR and Tanah Pasir from one month to the next
soil_types	TANAH PASIR	Tanah Pasir	case variant of Tanah Pasir
\.


--
-- Name: role_data_scopes_id_seq; Type: SEQUENCE SET; Schema: auth; Owner: -
--

SELECT pg_catalog.setval('auth.role_data_scopes_id_seq', 826, true);


--
-- Name: areas_id_seq; Type: SEQUENCE SET; Schema: master; Owner: -
--

SELECT pg_catalog.setval('master.areas_id_seq', 8, true);


--
-- Name: blocks_id_seq; Type: SEQUENCE SET; Schema: master; Owner: -
--

SELECT pg_catalog.setval('master.blocks_id_seq', 4027, true);


--
-- Name: companies_id_seq; Type: SEQUENCE SET; Schema: master; Owner: -
--

SELECT pg_catalog.setval('master.companies_id_seq', 12, true);


--
-- Name: divisions_id_seq; Type: SEQUENCE SET; Schema: master; Owner: -
--

SELECT pg_catalog.setval('master.divisions_id_seq', 186, true);


--
-- Name: estates_id_seq; Type: SEQUENCE SET; Schema: master; Owner: -
--

SELECT pg_catalog.setval('master.estates_id_seq', 34, true);


--
-- Name: groups_id_seq; Type: SEQUENCE SET; Schema: master; Owner: -
--

SELECT pg_catalog.setval('master.groups_id_seq', 88, true);


--
-- Name: block_types_id_seq; Type: SEQUENCE SET; Schema: ref; Owner: -
--

SELECT pg_catalog.setval('ref.block_types_id_seq', 2, true);


--
-- Name: planting_statuses_id_seq; Type: SEQUENCE SET; Schema: ref; Owner: -
--

SELECT pg_catalog.setval('ref.planting_statuses_id_seq', 3, true);


--
-- Name: rotation_statuses_id_seq; Type: SEQUENCE SET; Schema: ref; Owner: -
--

SELECT pg_catalog.setval('ref.rotation_statuses_id_seq', 3, true);


--
-- Name: seed_varieties_id_seq; Type: SEQUENCE SET; Schema: ref; Owner: -
--

SELECT pg_catalog.setval('ref.seed_varieties_id_seq', 19, true);


--
-- Name: soil_types_id_seq; Type: SEQUENCE SET; Schema: ref; Owner: -
--

SELECT pg_catalog.setval('ref.soil_types_id_seq', 7, true);


--
-- Name: topography_types_id_seq; Type: SEQUENCE SET; Schema: ref; Owner: -
--

SELECT pg_catalog.setval('ref.topography_types_id_seq', 5, true);


--
-- Name: tph_categories_id_seq; Type: SEQUENCE SET; Schema: ref; Owner: -
--

SELECT pg_catalog.setval('ref.tph_categories_id_seq', 1, true);


--
-- Name: tree_categories_id_seq; Type: SEQUENCE SET; Schema: ref; Owner: -
--

SELECT pg_catalog.setval('ref.tree_categories_id_seq', 3, true);


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
-- Name: users_email_lower_key; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX users_email_lower_key ON auth.users USING btree (lower((email)::text));


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
-- PostgreSQL database dump complete
--

