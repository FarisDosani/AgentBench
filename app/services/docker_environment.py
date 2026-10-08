import subprocess
import time
from pathlib import Path

from app.models.docker_result import DockerCommandResult


class DockerEnvironment:
    def __init__(
        self,
        workspace_path: str | Path,
        image: str = "agentbench-python",
        timeout_seconds: int = 300,
    ) -> None:
        workspace = Path(workspace_path)
        if not workspace.exists():
            raise FileNotFoundError(workspace)
        if not workspace.is_dir():
            raise ValueError("Docker workspace must be a directory")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        self.workspace_path = workspace.resolve()
        self.image = image
        self.timeout_seconds = timeout_seconds

    def is_docker_available(self) -> bool:
        try:
            completed = subprocess.run(
                ["docker", "version"],
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout_seconds,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return completed.returncode == 0

    def build_image(self) -> None:
        if not self.is_docker_available():
            raise RuntimeError("Docker is unavailable")
        project_root = Path(__file__).resolve().parents[2]
        dockerfile = project_root / "docker" / "agentbench-python.Dockerfile"
        completed = subprocess.run(
            [
                "docker",
                "build",
                "-f",
                str(dockerfile),
                "-t",
                self.image,
                str(project_root),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=self.timeout_seconds,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"Docker image build failed: {completed.stderr}")

    def run_command(self, command: list[str]) -> DockerCommandResult:
        docker_command = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--memory",
            "512m",
            "--cpus",
            "1",
            "--mount",
            f"type=bind,source={self.workspace_path},target=/workspace",
            "--workdir",
            "/workspace",
            self.image,
            *command,
        ]
        started_at = time.perf_counter()
        try:
            completed = subprocess.run(
                docker_command,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exception:
            return DockerCommandResult(
                exit_code=-1,
                stdout=self._timeout_text(exception.stdout),
                stderr=self._timeout_text(exception.stderr),
                timed_out=True,
                duration_ms=(time.perf_counter() - started_at) * 1000,
            )

        return DockerCommandResult(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            timed_out=False,
            duration_ms=(time.perf_counter() - started_at) * 1000,
        )

    @staticmethod
    def _timeout_text(value: str | bytes | None) -> str:
        if value is None:
            return ""
        return value.decode(errors="replace") if isinstance(value, bytes) else value
