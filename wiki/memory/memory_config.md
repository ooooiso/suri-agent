# 记忆策略配置

---
memory_config:
  version: "1.0"
  retention_days: 90
  archive_threshold: 1000
---

## 策略说明

- **保留期**: 90 天内的消息默认保留
- **归档阈值**: 单角色消息超过 1000 条时触发归档
- **自动遗忘**: 超过保留期的消息自动归档到 `_archived/` 目录
