import os
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

PARAMIKO_AVAILABLE = None
_paramiko = None
_SSHException = None


def _ensure_paramiko():
    global PARAMIKO_AVAILABLE, _paramiko, _SSHException
    if PARAMIKO_AVAILABLE is not None:
        return PARAMIKO_AVAILABLE
    try:
        import paramiko
        from paramiko.ssh_exception import SSHException
        _paramiko = paramiko
        _SSHException = SSHException
        PARAMIKO_AVAILABLE = True
    except ImportError:
        PARAMIKO_AVAILABLE = False
    return PARAMIKO_AVAILABLE


class DeployTarget:
    def __init__(self, config: Dict[str, Any]):
        self.name = config.get("name", "unknown")
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 22)
        self.username = config.get("username", os.getenv("USER", "root"))
        self.password = config.get("password")
        self.private_key = config.get("private_key")
        self.private_key_path = config.get("private_key_path")
        self.remote_path = config.get("remote_path", "/etc/config")
        self.files = config.get("files", [])
        self.backup = config.get("backup", True)
        self.backup_dir = config.get("backup_dir", "/etc/config/backups")
        self.pre_deploy = config.get("pre_deploy", [])
        self.post_deploy = config.get("post_deploy", [])


class DeployManager:
    def __init__(self, targets_dir: Path = None):
        self.targets_dir = Path(targets_dir) if targets_dir else None

    def list_targets(self) -> List[str]:
        if not self.targets_dir or not self.targets_dir.exists():
            return []
        targets = []
        for f in sorted(self.targets_dir.glob("*.yaml")):
            targets.append(f.stem)
        for f in sorted(self.targets_dir.glob("*.yml")):
            if f.stem not in targets:
                targets.append(f.stem)
        return targets

    def load_target(self, target_name: str) -> Optional[DeployTarget]:
        if not self.targets_dir:
            return None
        target_file = self.targets_dir / f"{target_name}.yaml"
        if not target_file.exists():
            target_file = self.targets_dir / f"{target_name}.yml"
        if not target_file.exists():
            return None
        
        with open(target_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        
        return DeployTarget(config)

    def deploy_files(
        self,
        target: DeployTarget,
        local_files: Dict[str, Path],
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        result = {
            "success": False,
            "target": target.name,
            "host": target.host,
            "files_deployed": [],
            "files_failed": [],
            "backups": [],
            "output": [],
            "errors": [],
        }

        if not _ensure_paramiko():
            result["errors"].append("paramiko is not installed. Run 'pip install paramiko' to enable deployment.")
            return result

        ssh = None
        sftp = None
        paramiko = _paramiko
        SSHException = _SSHException

        if dry_run:
            result["output"].append(f"[DRY RUN] Would connect to {target.username}@{target.host}:{target.port}")
            for remote_name, local_path in local_files.items():
                remote_full = f"{target.remote_path}/{remote_name}"
                result["output"].append(f"[DRY RUN] Would upload {local_path} -> {remote_full}")
                result["files_deployed"].append(remote_name)
                if target.backup:
                    backup_path = f"{target.backup_dir}/{remote_name}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
                    result["backups"].append(backup_path)
                    result["output"].append(f"[DRY RUN] Would backup to {backup_path}")
            result["success"] = True
            return result

        ssh = None
        sftp = None

        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            connect_kwargs = {
                "hostname": target.host,
                "port": target.port,
                "username": target.username,
                "timeout": 30,
            }

            if target.private_key_path:
                key_path = os.path.expanduser(target.private_key_path)
                connect_kwargs["key_filename"] = key_path
            elif target.private_key:
                key = paramiko.RSAKey.from_private_key_file(target.private_key)
                connect_kwargs["pkey"] = key
            elif target.password:
                connect_kwargs["password"] = target.password

            ssh.connect(**connect_kwargs)
            result["output"].append(f"Connected to {target.username}@{target.host}")

            sftp = ssh.open_sftp()

            self._ensure_remote_dir(sftp, target.remote_path)
            if target.backup:
                self._ensure_remote_dir(sftp, target.backup_dir)

            for remote_name, local_path in local_files.items():
                local_path = Path(local_path)
                if not local_path.exists():
                    result["files_failed"].append(remote_name)
                    result["errors"].append(f"Local file not found: {local_path}")
                    continue

                remote_full = f"{target.remote_path}/{remote_name}"

                if target.backup:
                    try:
                        backup_name = f"{remote_name}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
                        backup_path = f"{target.backup_dir}/{backup_name}"
                        try:
                            sftp.stat(remote_full)
                            sftp.rename(remote_full, backup_path)
                            result["backups"].append(backup_path)
                            result["output"].append(f"Backed up {remote_full} -> {backup_path}")
                        except IOError:
                            pass
                    except Exception as e:
                        result["errors"].append(f"Backup failed for {remote_name}: {e}")

                try:
                    sftp.put(str(local_path), remote_full)
                    result["files_deployed"].append(remote_name)
                    result["output"].append(f"Deployed {remote_name} -> {remote_full}")
                except Exception as e:
                    result["files_failed"].append(remote_name)
                    result["errors"].append(f"Failed to deploy {remote_name}: {e}")

            for cmd in target.pre_deploy:
                result["output"].append(f"Executing pre-deploy: {cmd}")
                stdin, stdout, stderr = ssh.exec_command(cmd)
                out = stdout.read().decode().strip()
                err = stderr.read().decode().strip()
                if out:
                    result["output"].append(f"  stdout: {out}")
                if err:
                    result["errors"].append(f"  stderr: {err}")

            for cmd in target.post_deploy:
                result["output"].append(f"Executing post-deploy: {cmd}")
                stdin, stdout, stderr = ssh.exec_command(cmd)
                out = stdout.read().decode().strip()
                err = stderr.read().decode().strip()
                if out:
                    result["output"].append(f"  stdout: {out}")
                if err:
                    result["errors"].append(f"  stderr: {err}")

            result["success"] = len(result["files_failed"]) == 0

        except SSHException as e:
            result["errors"].append(f"SSH connection failed: {e}")
        except Exception as e:
            result["errors"].append(f"Deployment error: {e}")
        finally:
            if sftp:
                sftp.close()
            if ssh:
                ssh.close()

        return result

    def _ensure_remote_dir(self, sftp, remote_path: str):
        try:
            sftp.stat(remote_path)
        except IOError:
            parent = "/".join(remote_path.rstrip("/").split("/")[:-1])
            if parent and parent != "/":
                self._ensure_remote_dir(sftp, parent)
            sftp.mkdir(remote_path)
