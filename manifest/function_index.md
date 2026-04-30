---
version: "0.1.0"
description: 部门职能索引，用于需求归属匹配与跨部门协作定位
last_updated: 2026-04-30

departments:
  - id: central
    name: 独立中枢
    function: 平台调度、需求解析、任务分发、异常处理、用户交互
    lead_role: suri
    members:
      - suri
    group_chat: "@shushi_central_group"
    collaboration: []

  - id: design
    name: 设计部
    function: 视觉设计、图像生成、视频生成、艺术指导、创意策划、质量审核
    lead_role: art_director
    members:
      - art_director
      - image_gen
      - video_gen
    group_chat: "@shushi_design_group"
    collaboration:
      - target: engineering
        relation: 开发部将设计稿转化为可运行代码，设计部需提供规范和资源
      - target: resource
        relation: 资源部管理设计素材的存储与归档

  - id: engineering
    name: 开发部
    function: 程序开发、脚本编写、后台架构、代码审查、部署发布、工具研发
    lead_role: dev_lead
    members:
      - dev_lead
      - script_dev
      - backend_dev
      - deploy_dev
    group_chat: "@shushi_eng_group"
    collaboration:
      - target: design
        relation: 按设计规范实现功能，向设计部反馈技术可行性
      - target: ops
        relation: 代码提交后由运维部进行安全审查与部署
      - target: resource
        relation: 工具开发完成后在资源部注册

  - id: ops
    name: 运维部
    function: 系统运维、安全审批、流程管理、配置维护、Git管理、监控告警
    lead_role: ops_admin
    members:
      - ops_admin
      - security_admin
      - workflow_admin
      - config_admin
      - git_admin
    group_chat: "@shushi_ops_group"
    collaboration:
      - target: engineering
        relation: 审查开发部代码变更，管理部署流程
      - target: central
        relation: 向 suri 提供调度规则与安全策略支持

  - id: resource
    name: 资源部
    function: 文件资源管理、存储优化、归档清理、素材库维护
    lead_role: file_admin
    members:
      - file_admin
    group_chat: "@shushi_resource_group"
    collaboration:
      - target: design
        relation: 为设计部提供素材存储与管理服务
      - target: engineering
        relation: 管理工具库与脚本资源的归档

  - id: hr
    name: 人力资源部
    function: 角色创建、角色注销、角色配置更新、组织架构维护
    lead_role: hr_admin
    members:
      - hr_admin
    group_chat: "@shushi_hr_group"
    collaboration:
      - target: ops
        relation: 角色创建/注销涉及安全审批，需同步 security_admin
      - target: central
        relation: 角色变更后需更新 function_index 与 roles_mapping

---

# 角色黄页速查

| 角色 ID | 昵称 | 职位 | 部门 | Telegram |
|---------|------|------|------|----------|
| suri | Suri | 调度总监 | 独立中枢 | @shushi_hermesbot |
| art_director | 香奈儿 | 艺术总监 | 设计部 | （待配置） |
| image_gen | 莫奈 | 图像生成师 | 设计部 | （待配置） |
| video_gen | 卢米埃尔 | 视频生成师 | 设计部 | （待配置） |
| dev_lead | 达芬奇 | 开发组长 | 开发部 | （待配置） |
| script_dev | 图灵 | 脚本开发 | 开发部 | （待配置） |
| backend_dev | 冯·诺依曼 | 后台开发 | 开发部 | （待配置） |
| deploy_dev | 卡尼 | 部署工程师 | 开发部 | （待配置） |
| ops_admin | 居里 | 运维主管 | 运维部 | （待配置） |
| security_admin | 瓦特 | 安全管理员 | 运维部 | （待配置） |
| workflow_admin | 泰勒 | 流程管理员 | 运维部 | （待配置） |
| config_admin | 张衡 | 配置管理员 | 运维部 | （待配置） |
| git_admin | 李纳斯 | Git管理员 | 运维部 | （待配置） |
| file_admin | 卡夫卡 | 资源主管 | 资源部 | （待配置） |
| hr_admin | 玛丽安 | 角色管理员 | 人力资源部 | （待配置） |
