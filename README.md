# ConfigForge - 配置管理命令行工具

一个功能强大的配置管理 CLI 工具，支持配置模板管理、环境变量替换、敏感字段加密、
多环境分发、Git 集成追踪、配置校验、一键部署。

## 功能特性

- 📋 **配置模板管理** - 创建、查看、删除配置模板，支持 YAML/JSON/Jinja2
- 🔄 **环境变量替换** - 支持 `${VAR}` 和 `$VAR` 语法，自动从 .env 文件和系统环境变量读取
- 🔐 **敏感字段加密** - 基于 Fernet 对称加密，自动识别密码、密钥等敏感字段
- 🎯 **多环境分发** - dev/staging/prod 多环境配置，深度合并模板和差异对比
- 📜 **Git 集成** - 追踪配置变更历史，查看差异对比，版本标签
- ✅ **配置校验** - JSON Schema 校验、必需字段检查、明文密钥检测
- 🚀 **一键部署** - SSH/SCP 部署到目标服务器，支持备份、前置/后置命令

## 安装

```bash
pip install -e .
```

或者直接运行：

```bash
pip install click pyyaml python-dotenv cryptography jsonschema GitPython paramiko rich jinja2
```

## 快速开始

### 1. 初始化项目

```bash
configforge init project
```

### 2. 生成主密钥

```bash
configforge crypto gen-key
```

设置环境变量：

```bash
export CONFIGFORGE_MASTER_KEY="your-generated-key"
```

### 3. 管理模板

```bash
# 列出所有模板
configforge template list

# 查看模板内容
configforge template show appconfig.yaml

# 创建新模板
configforge template create new-config.yaml
```

### 4. 管理环境

```bash
# 列出所有环境
configforge env list

# 查看环境配置
configforge env show dev

# 创建新环境（基于已有环境）
configforge env create testing --base dev

# 设置环境变量
configforge env set dev database.host 127.0.0.0.1

# 加密存储敏感字段
configforge env set dev database.password secret123 --encrypt

# 比较两个环境
configforge env diff dev staging
```

### 5. 构建配置

```bash
# 构建单个环境
configforge build one appconfig.yaml dev

# 构建所有环境
configforge build all

# 构建并解密输出
configforge build one appconfig.yaml prod --decrypt

# 比较不同环境构建结果
configforge build diff appconfig.yaml dev prod
```

### 6. 加密解密

```bash
# 加密单个值
configforge crypto encrypt "my-secret-password"

# 解密单个值
configforge crypto decrypt "ENC:gAAAAABh..."

# 加密配置文件中的敏感字段
configforge crypto encrypt-file environments/prod.yaml

# 解密配置文件
configforge crypto decrypt-file environments/prod.yaml
```

### 7. 配置校验

```bash
# 基本校验
configforge validate config dist/prod/appconfig.prod.yaml

# 使用 JSON Schema 校验
configforge validate config dist/prod/appconfig.prod.yaml --schema templates/schema.json

# 检查必需字段
configforge validate config config.yaml -r database.host -r database.port
```

### 8. Git 集成

```bash
# 初始化 Git 仓库
configforge git init

# 查看状态
configforge git status

# 提交变更
configforge git commit "Update prod config"

# 查看历史
configforge git history
```

### 9. 部署配置

```bash
# 列出部署目标
configforge deploy list

# 试运行部署
configforge deploy run prod-server-1 --env prod --dry-run

# 正式部署
configforge deploy run prod-server-1 --env prod
```

## 目录结构

```
your-project/
├── configforge.yaml       # 工具配置文件
├── templates/            # 配置模板目录
│   ├── appconfig.yaml
│   └── schema.json
├── environments/       # 环境配置目录
│   ├── dev.yaml
│   ├── staging.yaml
│   ├── prod.yaml
│   └── deploy/        # 部署目标配置
│       └── prod-server-1.yaml
├── dist/               # 构建输出目录
│   ├── dev/
│   ├── staging/
│   └── prod/
├── .secrets/          # 密钥文件目录
└── .env               # 环境变量文件
```

## 配置文件格式

### 模板文件

模板中可以使用 Jinja2 语法和环境变量：

```yaml
app:
  name: ${APP_NAME:default_value}
  env: {{ environment }}
```

### 环境变量替换

支持以下格式：
- `${VAR_NAME}` - 标准格式
- `$VAR_NAME` - 简写格式
- `${VAR_NAME:default}` - 带默认值

### 敏感字段自动识别

包含以下关键词的字段会被自动加密：
- password, passwd, pwd
- secret, token, key
- private, credential, auth

## 安全说明

- 主密钥请妥善保管，丢失将无法解密数据
- 建议将 .env 文件和 .secrets 目录添加到 .gitignore
- 生产环境使用环境变量传递主密钥，不要硬编码
