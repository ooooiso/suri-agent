# role/

角色管理层：调度角色之间的协同、通信，以及角色搭建规则。

## 功能

- **coordinator.py** — 角色协同调度器。协调多角色任务分配、跨部门协作、角色依赖管理。
  - 支持从 ConfigService 动态读取角色 `capabilities`，新增角色无需修改代码
- **messenger.py** — 角色通信管理器。角色间消息路由、格式校验、跨部门通信权限检查、消息留存。
  - 支持从 ConfigService 动态读取角色 `department`，新增角色无需修改代码
- **builder.py** — 角色搭建规则执行器。角色创建、Soul 文件格式验证、目录结构初始化、能力分析。

## 事件记录

- 初始创建
- **P0 调度规则改造**：`RoleCoordinator` 和 `RoleMessenger` 改为从 ConfigService 动态读取角色元数据，消除硬编码
