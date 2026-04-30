"""
工作流执行器

职责：
- 标准任务调度（接收→解析→匹配→下发→执行→交付）
- 跨部门协作协调
- 异常处理与升级
- 用户决策回流
- 能力缺口处理
- 技能沉淀
- 自优化上报
"""

from typing import Any, Dict, List, Optional
from process.base import BaseProcess


class WorkflowProcess(BaseProcess):
    """工作流与自优化流程执行器"""
    
    process_id = "workflow"
    name = "工作流与自优化流程"
    owner = "workflow_admin"
    
    # 重试配置
    MAX_RETRIES = 3
    RETRY_INTERVALS = [0, 30, 120]  # 秒
    DIRECTOR_OFFLINE_THRESHOLD = 300  # 5分钟
    SYNC_INTERVAL = 1800  # 30分钟
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """根据场景执行对应流程"""
        scenario = context.get("scenario", "standard")
        
        handlers = {
            "standard": self._standard_task_flow,
            "cross_department": self._cross_department_flow,
            "exception": self._exception_flow,
            "user_decision": self._user_decision_loop,
            "capability_gap": self._capability_gap_flow,
            "skill沉淀": self._skill沉淀_flow,
            "self_optimize": self._self_optimize_flow,
        }
        
        handler = handlers.get(scenario)
        if not handler:
            return {"success": False, "error": f"unknown_scenario: {scenario}"}
        
        return handler(context)
    
    def _standard_task_flow(self, context: Dict) -> Dict:
        """标准任务流：用户 → suri → 总监 → 成员 → 交付"""
        return {
            "success": True,
            "scenario": "standard",
            "steps": [
                "suri 接收需求，生成 task_id",
                "suri 解析需求，匹配责任部门和总监",
                "suri 向总监发送结构化任务消息",
                "总监在部门群内拆解任务，指派给成员",
                "成员按技能执行任务，可向总监请求协助",
                "成员完成后向总监汇报，总监审核质量",
                "总监向 suri 交付最终结果",
                "suri 汇总（多部门则整合），向用户呈现",
            ],
            "next_role": "department_director",
        }
    
    def _cross_department_flow(self, context: Dict) -> Dict:
        """跨部门协作流"""
        departments = context.get("departments", [])
        return {
            "success": True,
            "scenario": "cross_department",
            "steps": [
                "suri 确定所有涉及部门",
                "需求方总监向提供方总监发起私聊请求（抄送 suri）",
                "双方各自在部门内分派任务",
                f"每 {self.SYNC_INTERVAL // 60} 分钟同步进度至 suri",
                "suri 整合后交付用户",
            ],
            "rules": [
                "必须由需求方总监向提供方总监发起",
                "私聊内容必须抄送中枢调度群",
                "任何一方进度延迟，suri 自动介入协调",
            ],
            "departments_involved": [d.get("id") for d in departments],
        }
    
    def _exception_flow(self, context: Dict) -> Dict:
        """异常处理流"""
        retry_count = context.get("retry_count", 0)
        
        if retry_count < self.MAX_RETRIES:
            return {
                "success": True,
                "action": "retry",
                "retry_count": retry_count + 1,
                "wait_seconds": self.RETRY_INTERVALS[min(retry_count, len(self.RETRY_INTERVALS) - 1)],
            }
        
        return {
            "success": True,
            "action": "escalate_to_user",
            "steps": [
                "成员失败，重试已耗尽",
                "汇报总监，总监无法解决",
                "汇报 suri",
                "suri 向用户汇报失败原因，请求重新规划或取消",
            ],
        }
    
    def _user_decision_loop(self, context: Dict) -> Dict:
        """用户决策回路"""
        return {
            "success": True,
            "scenario": "user_decision",
            "steps": [
                "开发人员遇到问题，向总监汇报",
                "总监尝试解决，无法解决则向 suri 汇报",
                "suri 整理问题上下文 + 2-3 个可选方案",
                "回流给用户判断",
                "用户给出决策指令（方案 A / 方案 B / 重新规划 / 取消）",
                "suri 将决策下发给开发人员继续执行",
            ],
            "constraints": [
                "回流必须带上下文：已尝试方案、卡住的技术点、可选方向",
                "suri 不替用户决策，只整理和呈现",
                "用户指令需明确：采用方案 X 或按以下方式实现",
            ],
        }
    
    def _capability_gap_flow(self, context: Dict) -> Dict:
        """能力缺口处理流"""
        return {
            "success": True,
            "scenario": "capability_gap",
            "steps": [
                "suri 读取部门职能索引，遍历所有部门 function 字段",
                "匹配失败（无任何重叠）",
                "suri 向用户汇报能力缺口，列出所有部门及职能摘要",
                "询问用户是否需要新建部门/角色",
                "用户确认后，suri 收集扩展需求（部门名称、职能、所需角色及技能）",
                "suri 向 suri-hr 发起组织扩展请求",
                "suri-hr 按角色生命周期规则执行创建",
                "新部门/角色上线，suri 更新职能索引",
                "suri 重新调度原需求至新部门",
            ],
            "constraints": [
                "缺口必须明确展示，让用户判断是需求不清还是确实需要新能力",
                "只有用户明确确认后才触发创建",
                "创建完成后立即启用，原需求重新调度",
            ],
        }
    
    def _skill沉淀_flow(self, context: Dict) -> Dict:
        """技能沉淀流"""
        return {
            "success": True,
            "scenario": "skill沉淀",
            "steps": [
                "任务完成，开发人员撰写技能总结",
                "提交给 suri",
                "suri 提交 workflow_admin 审核",
                "审核通过 → suri 向用户确认",
                "用户回复是",
                "suri-hr 协助将技能写入角色 skills/ 目录",
                "更新 skills/skills.md 索引",
                "git_admin 记录到 changelog.md",
            ],
        }
    
    def _self_optimize_flow(self, context: Dict) -> Dict:
        """自优化上报流"""
        impact_scope = context.get("impact_scope", "self")  # self | multi_role | file_change
        
        approvers = ["workflow_admin"]
        if impact_scope == "multi_role":
            approvers.append("相关角色同步确认")
        if impact_scope == "file_change":
            approvers.append("security_admin")
        
        return {
            "success": True,
            "scenario": "self_optimize",
            "approvers": approvers,
            "steps": [
                "角色生成优化报告（原因、优化前后、影响分析、涉及文件）",
                "提交 workflow_admin 审核",
                "审核通过 → suri 向用户申请批准",
                "用户批准 → 执行修改",
                "git_admin 记录到 changelog.md",
            ],
            "constraints": [
                "workflow_admin 有权拒绝不合理优化",
                "用户拥有最终否决权",
            ],
        }
