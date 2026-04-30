# files_i_use.md

document-review 的文件权限地图。

## 可读取

- `suri-agent/memory/ai-dev-memory/*`
- `group/*/memories/*`
- `group/*/*.md`
- `suri-agent/**/*.md`
- `suri-agent/**/*.py`

## 可写入（需用户审批）

- `suri-agent/memory/ai-dev-memory/*.md`
- `group/*/memories/role.db`

## 不可写入

- `suri-agent/**/*.py`（代码文件，由 suri-dev 维护）
- `.env`、`config.yaml`
