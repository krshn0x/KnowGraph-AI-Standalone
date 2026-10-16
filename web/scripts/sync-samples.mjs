import { copyFileSync, mkdirSync } from "node:fs";

const output = new URL("../public/samples/", import.meta.url);
mkdirSync(output, { recursive: true });
for (const name of ["demo.json", "nodes.csv", "edges.csv", "resolution_update.json"]) {
  copyFileSync(new URL(`../../data/${name}`, import.meta.url), new URL(name, output));
}
