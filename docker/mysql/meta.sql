SET NAMES utf8mb4;
CREATE DATABASE meta DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
GRANT ALL PRIVILEGES ON meta.* TO 'baimiao'@'%';

USE meta;

DROP TABLE IF EXISTS table_info;
CREATE TABLE table_info
(
    id          VARCHAR(64) PRIMARY KEY COMMENT '表编号',
    name        VARCHAR(128) COMMENT '表名称',
    role        VARCHAR(32) COMMENT '表类型(fact/dim)',
    description TEXT COMMENT '表描述'
);



DROP TABLE IF EXISTS column_info;
CREATE TABLE column_info
(
    id          VARCHAR(64) PRIMARY KEY COMMENT '列编号',
    name        VARCHAR(128) COMMENT '列名称',
    type        VARCHAR(64) COMMENT '数据类型',
    role        VARCHAR(32) COMMENT '列类型(primary_key,foreign_key,measure,dimension)',
    examples    JSON COMMENT '数据示例',
    description TEXT COMMENT '列描述',
    alias       JSON COMMENT '列别名',
    table_id    VARCHAR(64) COMMENT '所属表编号'
);

DROP TABLE IF EXISTS metric_info;
CREATE TABLE metric_info
(
    id               VARCHAR(64) PRIMARY KEY COMMENT '指标编码',
    name             VARCHAR(128) COMMENT '指标名称',
    description      TEXT COMMENT '指标描述',
    relevant_columns JSON COMMENT '关联的列',
    alias            JSON COMMENT '指标别名'
);


DROP TABLE IF EXISTS column_metric;
CREATE TABLE column_metric
(
    column_id VARCHAR(64) COMMENT '列编号',
    metric_id VARCHAR(64) COMMENT '指标编号',
    PRIMARY KEY (column_id, metric_id)
);

CREATE TABLE IF NOT EXISTS app_user
(
    id            BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '用户编号',
    username      VARCHAR(64) UNIQUE NOT NULL COMMENT '用户名',
    nickname      VARCHAR(64) NULL COMMENT '昵称',
    avatar        TEXT NULL COMMENT '头像(base64 或 URL)',
    password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希(bcrypt)',
    role          VARCHAR(32) NOT NULL DEFAULT 'user' COMMENT '角色(user/admin)',
    scope         JSON NULL COMMENT '数据权限范围(预留,行级权限扩展点)',
    disabled      TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否禁用(1=禁用)',
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
);

CREATE TABLE IF NOT EXISTS chat_session
(
    id         BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '会话编号',
    user_id    BIGINT NOT NULL COMMENT '所属用户编号',
    title      VARCHAR(255) NOT NULL DEFAULT '新会话' COMMENT '会话标题',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    KEY idx_chat_session_user (user_id)
);

CREATE TABLE IF NOT EXISTS chat_message
(
    id             BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '消息编号',
    session_id     BIGINT NOT NULL COMMENT '所属会话编号',
    role           VARCHAR(16) NOT NULL COMMENT '角色(user/assistant)',
    content        TEXT NULL COMMENT '消息内容',
    query_sql      TEXT NULL COMMENT '本轮最终 SQL(预留)',
    result_summary TEXT NULL COMMENT '结果或报告摘要',
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    KEY idx_chat_message_session (session_id)
);

CREATE TABLE IF NOT EXISTS chat_feedback
(
    id            BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '反馈编号',
    message_id    BIGINT NOT NULL COMMENT '被反馈的消息编号',
    session_id    BIGINT NOT NULL COMMENT '所属会话编号',
    user_id       BIGINT NOT NULL COMMENT '反馈用户编号',
    kind          VARCHAR(16) NOT NULL COMMENT '反馈类型(like/dislike/correct)',
    comment       TEXT NULL COMMENT '补充说明',
    corrected_sql TEXT NULL COMMENT '用户纠正后的 SQL',
    question      TEXT NULL COMMENT '原问题(冗余,便于 few-shot)',
    wrong_sql     TEXT NULL COMMENT '原错误 SQL(冗余,便于 few-shot)',
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '反馈时间',
    KEY idx_feedback_message (message_id),
    KEY idx_feedback_user (user_id)
);

CREATE TABLE IF NOT EXISTS table_permission
(
    id           BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '权限编号',
    user_id      BIGINT NOT NULL COMMENT '用户编号',
    table_name   VARCHAR(128) NOT NULL COMMENT '表名(对应 table_info.id)',
    status       VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/approved/rejected',
    requested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '申请时间',
    reviewed_at  DATETIME NULL COMMENT '审批时间',
    reviewed_by  BIGINT NULL COMMENT '审批人用户编号',
    UNIQUE KEY uq_perm_user_table (user_id, table_name),
    KEY idx_perm_status (status)
);

CREATE TABLE IF NOT EXISTS data_source
(
    id                BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '数据源编号',
    name              VARCHAR(128) NOT NULL COMMENT '数据源名称',
    description       TEXT NULL COMMENT '说明',
    host              VARCHAR(128) NOT NULL COMMENT '源库主机',
    port              INT NOT NULL COMMENT '源库端口',
    `database`        VARCHAR(128) NOT NULL COMMENT '源库名',
    username          VARCHAR(128) NOT NULL COMMENT '源库账号',
    password_encrypted VARCHAR(512) NOT NULL COMMENT '源库密码(可逆加密)',
    table_prefix      VARCHAR(64) NOT NULL COMMENT '镜像表名前缀',
    status            VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/approved/rejected/syncing/active/error/disabled',
    binlog_file       VARCHAR(128) NULL COMMENT 'binlog 文件名',
    binlog_pos        BIGINT NULL COMMENT 'binlog 位点',
    sync_error        TEXT NULL COMMENT '最近同步错误',
    last_sync_at      DATETIME NULL COMMENT '最近同步时间',
    created_by        BIGINT NULL COMMENT '申请人/创建人',
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    reviewed_by       BIGINT NULL COMMENT '审批人',
    reviewed_at       DATETIME NULL COMMENT '审批时间',
    UNIQUE KEY uq_ds_host_db (host, port, `database`),
    KEY idx_ds_status (status)
);
