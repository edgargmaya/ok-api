import { spawn } from "child_process";
import { readFile } from "fs/promises";

type CommandResult = {
  exitCode: number;
  stdout: string;
  stderr: string;
};






const bashScript = String.raw`
set -euo pipefail

kubectl exec -i -n ${namespace} ${pod} -- bash <<'POD_SCRIPT'
set -euo pipefail

DB_NAME="${database}"

VERSION_NUM=$(su - postgres -c "psql -d \"$DB_NAME\" -t -A -c 'show server_version_num;'")
VERSION_NUM=$(echo "$VERSION_NUM" | tr -d '[:space:]')

echo "Detected PostgreSQL server_version_num: $VERSION_NUM"

if [ "$VERSION_NUM" -ge 100000 ]; then
  echo "Executing pg_switch_wal()..."
  su - postgres -c "psql -d \"$DB_NAME\" -c 'select pg_switch_wal();'"
else
  echo "Executing pg_switch_xlog()..."
  su - postgres -c "psql -d \"$DB_NAME\" -c 'select pg_switch_xlog();'"
fi
POD_SCRIPT
`;




const bashScript = String.raw`
set -euo pipefail

kubectl exec -i -n ${namespace} ${pod} -- bash <<'POD_SCRIPT'
set -euo pipefail

su - postgres -c "psql <<'SQL'
select *
from my_table
where state = 'active';
SQL"

POD_SCRIPT
`;





import { spawn } from "child_process";

type CommandResult = {
  exitCode: number;
  stdout: string;
  stderr: string;
};

function runLocalBash(
  bashScript: string
): Promise<CommandResult> {
  return new Promise((resolve, reject) => {
    const child = spawn("bash", ["-s"], {
      stdio: ["pipe", "pipe", "pipe"]
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (data) => {
      stdout += data.toString();
    });

    child.stderr.on("data", (data) => {
      stderr += data.toString();
    });

    child.on("error", (error) => {
      reject(error);
    });

    child.on("close", (code) => {
      resolve({
        exitCode: code ?? 1,
        stdout,
        stderr
      });
    });

    child.stdin.write(bashScript);
    child.stdin.end();
  });
}








async function readLinesFromFile(filePath: string): Promise<string[]> {
  const content = await readFile(filePath, "utf8");

  return content
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .filter((line) => !line.startsWith("#"));
}

function runBashOverDoubleSsh(
  jumpHost: string,
  targetHost: string,
  bashScript: string
): Promise<CommandResult> {
  return new Promise((resolve, reject) => {
    const child = spawn("ssh", [
      "-A",
      jumpHost,
      "ssh",
      targetHost,
      "bash -s"
    ], {
      stdio: ["pipe", "pipe", "pipe"]
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (data) => {
      stdout += data.toString();
    });

    child.stderr.on("data", (data) => {
      stderr += data.toString();
    });

    child.on("error", (error) => {
      reject(error);
    });

    child.on("close", (code) => {
      resolve({
        exitCode: code ?? 1,
        stdout,
        stderr
      });
    });

    child.stdin.write(bashScript);
    child.stdin.end();
  });
}

async function main() {

  const lines = await readLinesFromFile(inputFile);

  console.log(`Total de líneas válidas: ${lines.length}`);

  for (const line of lines) {
    console.log(`Línea: ${line}`);
  }
  
  const jumpHost = "ssh1-den";
  const targetHost = "den-r17-u14";

  const script = `
echo "Host actual:"
hostname

echo "Usuario actual:"
whoami

echo "Validando kubectl:"
command -v kubectl

echo "Listando pods:"
kubectl get po -A
`;

  console.log("Ejecutando script remoto...");

  const result = await runBashOverDoubleSsh(jumpHost, targetHost, script);

  console.log("Exit code:", result.exitCode);

  if (result.stderr.trim()) {
    console.log("STDERR:");
    console.log(result.stderr);
  }

  if (result.stdout.trim()) {
    console.log("STDOUT:");
    console.log(result.stdout);
  }
}

main().catch((error) => {
  console.error("Error inesperado:");
  console.error(error);
  process.exit(1);
});
