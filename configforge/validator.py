import json
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from jsonschema import validate, ValidationError, SchemaError


class ConfigValidator:
    def __init__(self, schema_dir: Path = None):
        self.schema_dir = Path(schema_dir) if schema_dir else None

    def validate_yaml_structure(self, data: Dict[str, Any]) -> List[str]:
        errors = []
        if not isinstance(data, dict):
            return ["Configuration must be a YAML mapping (dictionary)."]
        return errors

    def validate_with_schema(self, data: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
        errors = []
        try:
            validate(instance=data, schema=schema)
        except ValidationError as e:
            errors.append(f"Schema validation failed: {e.message}")
            if e.path:
                errors.append(f"  Path: {'.'.join(str(p) for p in e.path)}")
        except SchemaError as e:
            errors.append(f"Invalid schema: {e.message}")
        return errors

    def validate_schema_file(self, data: Dict[str, Any], schema_path: Path) -> List[str]:
        schema_path = Path(schema_path)
        if not schema_path.exists():
            return [f"Schema file not found: {schema_path}"]
        
        ext = schema_path.suffix.lower()
        if ext in (".yaml", ".yml"):
            with open(schema_path, "r", encoding="utf-8") as f:
                schema = yaml.safe_load(f)
        elif ext == ".json":
            with open(schema_path, "r", encoding="utf-8") as f:
                schema = json.load(f)
        else:
            return [f"Unsupported schema format: {ext}"]
        
        return self.validate_with_schema(data, schema)

    def validate_required_fields(self, data: Dict[str, Any], required_fields: List[str]) -> List[str]:
        errors = []
        for field in required_fields:
            keys = field.split(".")
            current = data
            found = True
            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    found = False
                    break
            if not found:
                errors.append(f"Missing required field: {field}")
        return errors

    def validate_env_file_format(self, content: str) -> List[str]:
        errors = []
        lines = content.splitlines()
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                errors.append(f"Line {i}: Invalid format, missing '=' separator")
                continue
            key = line.split("=", 1)[0].strip()
            if not key:
                errors.append(f"Line {i}: Empty variable name")
            elif not key.replace("_", "").isalnum():
                errors.append(f"Line {i}: Invalid variable name '{key}'")
        return errors

    def validate_no_plain_secrets(self, data: Dict[str, Any], secret_patterns: List[str] = None) -> List[str]:
        errors = []
        secret_patterns = secret_patterns or [
            "password", "secret", "token", "key", "private_key",
            "credential", "auth_token", "access_key"
        ]
        
        def _check_recursive(obj, path: str = ""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    current_path = f"{path}.{k}" if path else k
                    if any(s in k.lower() for s in secret_patterns):
                        if isinstance(v, str) and v and not v.startswith("ENC:"):
                            errors.append(f"Potential plaintext secret at '{current_path}'")
                    _check_recursive(v, current_path)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    _check_recursive(item, f"{path}[{i}]")
        
        _check_recursive(data)
        return errors

    def comprehensive_validate(
        self,
        data: Dict[str, Any],
        schema_path: Path = None,
        required_fields: List[str] = None,
        check_secrets: bool = True,
    ) -> Dict[str, Any]:
        results = {
            "valid": True,
            "errors": [],
            "warnings": [],
        }
        
        structure_errors = self.validate_yaml_structure(data)
        results["errors"].extend(structure_errors)
        
        if schema_path:
            schema_errors = self.validate_schema_file(data, schema_path)
            results["errors"].extend(schema_errors)
        
        if required_fields:
            field_errors = self.validate_required_fields(data, required_fields)
            results["errors"].extend(field_errors)
        
        if check_secrets:
            secret_warnings = self.validate_no_plain_secrets(data)
            results["warnings"].extend(secret_warnings)
        
        results["valid"] = len(results["errors"]) == 0
        return results
