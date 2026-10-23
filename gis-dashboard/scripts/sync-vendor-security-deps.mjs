import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

/** Replace hoisted security aliases after npm overrides (fixes broken nested symlinks). */
const VENDOR_PACKAGES = [
  { name: "node-forge", vendorDir: "node-forge" },
  { name: "braces", vendorDir: "braces" },
];

function copyVendor(name, vendorDir) {
  const src = path.join(root, "vendor", vendorDir);
  const dest = path.join(root, "node_modules", name);
  if (!fs.existsSync(src)) {
    throw new Error(`Missing vendor source: ${src}`);
  }
  fs.rmSync(dest, { recursive: true, force: true });
  fs.cpSync(src, dest, { recursive: true, dereference: true });
}

for (const { name, vendorDir } of VENDOR_PACKAGES) {
  copyVendor(name, vendorDir);
}

function replaceNestedBraces(dir) {
  if (!fs.existsSync(dir)) return;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "node_modules") {
        const bracesPath = path.join(full, "braces");
        if (fs.existsSync(bracesPath)) {
          const pkgPath = path.join(bracesPath, "package.json");
          let shouldReplace = false;
          try {
            const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
            shouldReplace = pkg.name === "braces";
          } catch {
            shouldReplace = true;
          }
          if (shouldReplace) {
            fs.rmSync(bracesPath, { recursive: true, force: true });
            fs.cpSync(path.join(root, "vendor", "braces"), bracesPath, { recursive: true });
          }
        }
      }
      replaceNestedBraces(full);
    }
  }
}

replaceNestedBraces(path.join(root, "node_modules"));
