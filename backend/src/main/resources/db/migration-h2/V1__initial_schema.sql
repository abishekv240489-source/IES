create table invoice_jobs (
    id uuid primary key,
    batch_id uuid not null,
    original_filename varchar(255) not null,
    stored_filename varchar(255) not null,
    sha256 varchar(64) not null,
    content_type varchar(100) not null,
    size_bytes bigint not null,
    status varchar(40) not null,
    overall_confidence double,
    extraction_engine varchar(80),
    extraction_json clob,
    validation_json clob,
    error_message varchar(1000),
    created_at timestamp with time zone not null,
    updated_at timestamp with time zone not null,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    version bigint not null default 0
);
create index idx_invoice_jobs_created_at on invoice_jobs(created_at);
create index idx_invoice_jobs_status on invoice_jobs(status);
create index idx_invoice_jobs_sha256 on invoice_jobs(sha256);
create table audit_events (
    id uuid primary key,
    job_id uuid not null,
    action varchar(80) not null,
    actor varchar(120) not null,
    detail varchar(1000),
    created_at timestamp with time zone not null,
    constraint fk_audit_job foreign key (job_id) references invoice_jobs(id)
);
create index idx_audit_job_created on audit_events(job_id, created_at);
