import { spawn } from "child_process";

type CommandResult = {
  exitCode: number;
  stdout: string;
  stderr: string;
};

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
