-- Migration 002: Agent Registry tables
-- Creates tables for agent_registry plugin

CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    task_name TEXT,
    parent_agent_id TEXT,
    role_id TEXT NOT NULL,
    status TEXT DEFAULT 'planning',
    user_id TEXT NOT NULL,
    plan_id TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS agent_steps (
    step_id TEXT,
    agent_id TEXT,
    description TEXT,
    status TEXT DEFAULT 'pending',
    assignee TEXT,
    depends_on TEXT,          -- JSON array
    estimated_time INTEGER,
    started_at TEXT,
    completed_at TEXT,
    block_reason TEXT,
    result TEXT,
    PRIMARY KEY (step_id, agent_id)
);

CREATE INDEX IF NOT EXISTS idx_agents_user ON agents(user_id, status);
CREATE INDEX IF NOT EXISTS idx_agents_parent ON agents(parent_agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_steps_agent ON agent_steps(agent_id);
