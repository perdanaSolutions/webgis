const express = require("express");
const cors = require("cors");
const fs = require("fs");
const path = require("path");

const app = express();
const PORT = 4000;

app.use(cors());
app.use(express.json());

function safeString(value) {
  if (value === null || value === undefined) return "";
  return String(value).trim();
}

function safeNumber(value) {
  const numberValue = Number(value);
  return Number.isFinite(numberValue) ? numberValue : 0;
}

function getFeatureValue(properties, keys, fallback = "") {
  for (const key of keys) {
    const value = safeString(properties[key]);
    if (value) return value;
  }
  return fallback;
}

function buildDrainase(properties) {
  return (
    safeNumber(properties.DrnCanal) +
    safeNumber(properties.DrnMD) +
    safeNumber(properties.DrnCD) +
    safeNumber(properties.DrnFD)
  );
}

function uniqueSorted(values) {
  return Array.from(new Set(values.filter(Boolean))).sort((a, b) =>
    a.localeCompare(b),
  );
}

const GEOJSON_PATH = path.resolve(
  __dirname,
  "../gis-dashboard/datas/TPA_SGA_2026.geojson",
);

let normalizedFeatures = [];

function normalizeFeature(feature) {
  const properties = feature?.properties || {};

  return {
    feature,
    pt: getFeatureValue(properties, ["PT", "PT_1"]),
    estate: getFeatureValue(properties, ["Estate", "Estate_1"]),
    afdeling: getFeatureValue(properties, ["Afdeling", "Afdeling_1"]),
    blok: getFeatureValue(properties, [
      "Blok",
      "Blok_1",
      "Kode_Blok",
      "GlobalID",
    ]),
    tahunTanam: getFeatureValue(properties, ["TT", "TT_1"]),
    statusTanam: getFeatureValue(properties, ["Status", "Status_1"]),
    jenisBibit: getFeatureValue(properties, ["JenisBibit", "Bibit"]),
    luasTanam: safeNumber(properties.LTanam_1 ?? properties.LTanam),
    totalPokok: safeNumber(properties.Pokok_1 ?? properties.Pokok),
    jalan: safeNumber(properties.Jalan),
    drainase: buildDrainase(properties),
    jembatan: safeNumber(properties.Jembatan),
  };
}

function loadGeoJSONFromFile() {
  const fileContent = fs.readFileSync(GEOJSON_PATH, "utf8");
  const parsed = JSON.parse(fileContent);
  const incomingFeatures = parsed?.features || [];
  normalizedFeatures = incomingFeatures.map(normalizeFeature);
}

function applyFilters(items, query) {
  return items.filter((item) => {
    if (query.pt && item.pt !== query.pt) return false;
    if (query.estate && item.estate !== query.estate) return false;
    if (query.afdeling && item.afdeling !== query.afdeling) return false;
    if (query.blok && item.blok !== query.blok) return false;
    if (query.tahunTanam && item.tahunTanam !== query.tahunTanam) return false;
    if (query.statusTanam && item.statusTanam !== query.statusTanam)
      return false;
    if (query.jenisBibit && item.jenisBibit !== query.jenisBibit) return false;
    return true;
  });
}

function buildFilterOptions(query) {
  const baseFiltered = normalizedFeatures.filter((item) => {
    if (query.pt && item.pt !== query.pt) return false;
    if (query.estate && item.estate !== query.estate) return false;
    if (query.afdeling && item.afdeling !== query.afdeling) return false;
    return true;
  });

  const fullyFiltered = applyFilters(baseFiltered, query);

  return {
    pt: uniqueSorted(normalizedFeatures.map((item) => item.pt)),
    estate: uniqueSorted(baseFiltered.map((item) => item.estate)),
    afdeling: uniqueSorted(baseFiltered.map((item) => item.afdeling)),
    blok: uniqueSorted(baseFiltered.map((item) => item.blok)),
    tahunTanam: uniqueSorted(fullyFiltered.map((item) => item.tahunTanam)),
    statusTanam: uniqueSorted(fullyFiltered.map((item) => item.statusTanam)),
    jenisBibit: uniqueSorted(fullyFiltered.map((item) => item.jenisBibit)),
  };
}

function buildSummary(items) {
  return items.reduce(
    (acc, item) => {
      acc.totalBlok += 1;
      acc.totalLuasTanam += item.luasTanam;
      acc.totalPokok += item.totalPokok;
      acc.totalJalan += item.jalan;
      acc.totalDrainase += item.drainase;
      acc.totalJembatan += item.jembatan;
      return acc;
    },
    {
      totalBlok: 0,
      totalLuasTanam: 0,
      totalPokok: 0,
      totalJalan: 0,
      totalDrainase: 0,
      totalJembatan: 0,
    },
  );
}

app.get("/health", (req, res) => {
  res.json({
    ok: true,
    message: "GIS Dashboard API is running",
    totalFeatures: normalizedFeatures.length,
  });
});

app.get("/filters", (req, res) => {
  const options = buildFilterOptions(req.query);
  res.json(options);
});

app.get("/features", (req, res) => {
  const filtered = applyFilters(normalizedFeatures, req.query);
  res.json({
    type: "FeatureCollection",
    features: filtered.map((item) => item.feature),
  });
});

app.get("/summary", (req, res) => {
  const filtered = applyFilters(normalizedFeatures, req.query);
  res.json(buildSummary(filtered));
});

try {
  loadGeoJSONFromFile();
  app.listen(PORT, () => {
    console.log(`GIS Dashboard API running on http://localhost:${PORT}`);
    console.log(`GeoJSON loaded from ${GEOJSON_PATH}`);
    console.log(`Total normalized features: ${normalizedFeatures.length}`);
  });
} catch (error) {
  console.error("Failed to start API server:", error);
  process.exit(1);
}
