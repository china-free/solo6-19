import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ConfigForgeConfig:
    work_dir: Path = field(default_factory=lambda: Path.cwd())
    templates_dir: Path = field(default_factory=lambda: Path.cwd() / "templates")
    environments_dir: Path = field(default_factory=lambda: Path.cwd() / "environments")
    output_dir: Path = field(default_factory=lambda: Path.cwd() / "dist")
    secrets_dir: Path = field(default_factory=lambda: Path.cwd() / ".secrets")
    env_file: str = ".env"
    master_key_env: str = "CONFIGFORGE_MASTER_KEY"

    @classmethod
    def load(cls) -> "ConfigForgeConfig":
        config = cls()
        config_file = Path.cwd() / "configforge.yaml"
        if config_file.exists():
            import yaml
            with open(config_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            if "templates_dir" in data:
                config.templates_dir = Path(data["templates_dir"])
            if "environments_dir" in data:
                config.environments_dir = Path(data["environments_dir"])
            if "output_dir" in data:
                config.output_dir = Path(data["output_dir"])
            if "secrets_dir" in data:
                config.secrets_dir = Path(data["secrets_dir"])
            if "env_file" in data:
                config.env_file = data["env_file"]
            if "master_key_env" in data:
                config.master_key_env = data["master_key_env"]
        return config

    def ensure_dirs(self):
        for d in [self.templates_dir, self.environments_dir, self.output_dir, self.secrets_dir]:
            d.mkdir(parents=True, exist_ok=True)


def get_config() -> ConfigForgeConfig:
    return ConfigForgeConfig.load()
