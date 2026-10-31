import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";

const root = fileURLToPath(new URL("../../", import.meta.url));
const python = resolve(root, process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python");
const child = spawn(python, ["-u", fileURLToPath(new URL("./test_backend.py", import.meta.url))], { stdio: "inherit", windowsHide: true });
child.on("exit", code => process.exit(code ?? 1));
function stop() {
  if (process.platform === "win32") spawn("taskkill", ["/pid", String(child.pid), "/T", "/F"], { windowsHide: true, stdio: "ignore" });
  else child.kill("SIGTERM");
}
process.on("SIGTERM", stop); process.on("SIGINT", stop);
