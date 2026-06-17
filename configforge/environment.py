import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from copy import deepcopy


class EnvironmentManager:
    def __init__(self, environments_dir: Path):
        self.environments_dir = Path(environments_dir)
        self.environments_dir.mkdir(parents=True, exist_ok=True)

    def list_environments(self) -> List[str]:
        if not self.environments_dir.exists():
            return []
        envs = []
        for f in sorted(self.environments_dir.glob("*.yaml")):
            envs.append(f.stem)
        for f in sorted(self.environments_dir.glob("*.yml")):
            if f.stem not in envs:
                envs.append(f.stem)
        return envs

    def get_environment(self, env_name: str) -> Optional[Dict[str, Any]]:
        env_file = self.environments_dir / f"{env_name}.yaml"
        if not env_file.exists():
            env_file = self.environments_dir / f"{env_name}.yml"
        if not env_file.exists():
            return None
        
        with open(env_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def save_environment(self, env_name: str, data: Dict[str, Any]):
        env_file = self.environments_dir / f"{env_name}.yaml"
        env_file.parent.mkdir(parents=True, exist_ok=True)
        with open(env_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    def create_environment(self, env_name: str, base_env: str = None, data: Dict[str, Any] = None) -> Dict[str, Any]:
        env_file = self.environments_dir / f"{env_name}.yaml"
        if env_file.exists():
            raise FileExistsError(f"Environment '{env_name}' already exists.")
        
        env_data = {}
        if base_env:
            base_data = self.get_environment(base_env)
            if base_data:
                env_data = deepcopy(base_data)
        
        if data:
            env_data.update(data)
        
        self.save_environment(env_name, env_data)
        return env_data

    def delete_environment(self, env_name: str) -> bool:
        env_file = self.environments_dir / f"{env_name}.yaml"
        if env_file.exists():
            env_file.unlink()
            return True
        env_file = self.environments_dir / f"{env_name}.yml"
        if env_file.exists():
            env_file.unlink()
            return True
        return False

    def compare_environments(self, env1: str, env2: str) -> Dict[str, Any]:
        data1 = self.get_environment(env1)
        data2 = self.get_environment(env2)
        
        if data1 is None:
            raise ValueError(f"Environment '{env1}' not found.")
        if data2 is None:
            raise ValueError(f"Environment '{env2}' not found.")
        
        diffs = {
            "only_in_first": {},
            "only_in_second": {},
            "different": {},
            "same": {},
        }
        
        all_keys = set(data1.keys()) | set(data2.keys())
        
        for key in sorted(all_keys):
            if key not in data2:
                diffs["only_in_first"][key] = data1[key]
            elif key not in data1:
                diffs["only_in_second"][key] = data2[key]
            elif data1[key] != data2[key]:
                diffs["different"][key] = {
                    env1: data1[key],
                    env2: data2[key],
                }
            else:
                diffs["same"][key] = data1[key]
        
        return diffs


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result
