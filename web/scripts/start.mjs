import { cp, mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const root = new URL("../", import.meta.url);
const standalone = new URL(".next/standalone/", root);
const portArgument = process.argv.indexOf("--port");
const port = portArgument >= 0 ? process.argv[portArgument + 1] : process.env.PORT || "3000";
if (!/^\d+$/.test(port || "") || Number(port) < 1 || Number(port) > 65535) {
  throw new Error("Specify a valid --port between 1 and 65535.");
}
await mkdir(new URL(".next/", standalone), { recursive: true });
await cp(new URL(".next/static/", root), new URL(".next/static/", standalone), { recursive: true });
await cp(new URL("public/", root), new URL("public/", standalone), { recursive: true });
process.env.PORT = port;
process.env.HOSTNAME ||= "127.0.0.1";
process.chdir(fileURLToPath(standalone));
await import(new URL("server.js", standalone).href);
