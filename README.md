# Oracle AI Accounts Receivable Agent

## Overview

The **Oracle AI Accounts Receivable Agent** is an end-to-end Accounts Receivable collections automation project built using **Oracle Database, SQL, PL/SQL, and Python**.

The goal of the project is to reduce manual AR collection work by automatically identifying overdue invoices, calculating outstanding balances and aging, prioritizing collection activity, managing approval-controlled actions, processing payment-reminder notifications, tracking workflow execution, and providing management-level reporting.

The solution follows an agent-oriented architecture in which the system can analyze AR data, determine the next collection action, request human approval when required, execute the approved action, record the result, and monitor failures or incomplete workflows.

---

## Business Problem

Accounts Receivable teams often manually perform activities such as:

* Reviewing thousands of invoices
* Identifying overdue balances
* Calculating aging
* Prioritizing customers for collections
* Sending payment reminders
* Requesting manager approval
* Tracking collection actions
* Monitoring failed notifications
* Preparing AR management reports

This project automates and organizes those activities through an Oracle-based AR data platform and a Python agent workflow.

---

## High-Level Architecture

```text
                    Oracle AI Accounts Receivable Agent
                                  |
                                  v
                         Source AR Data
                                  |
                                  v
                         Staging / Validation
                                  |
                                  v
                         Oracle AR Database
                                  |
                  +---------------+---------------+
                  |               |               |
                  v               v               v
              Customers        Invoices        Payments
                  |               |               |
                  +---------------+---------------+
                                  |
                                  v
                       Outstanding Balance Logic
                                  |
                                  v
                         AR Aging Analysis
                                  |
                                  v
                    Collection Priority / Risk
                                  |
                                  v
                        Agent Decision Layer
                                  |
                                  v
                       Human Approval Workflow
                                  |
                                  v
                        Action Orchestrator
                                  |
                   +--------------+--------------+
                   |                             |
                   v                             v
           Notification Outbox             Recovery / Retry
                   |
                   v
            Payment Reminder
                   |
                   v
          Collections Reporting
                   |
                   v
        Production Readiness Checks
```

---

## End-to-End Workflow

```text
Source Data
    |
    v
Oracle Staging
    |
    v
Data Validation
    |
    v
Customers / Invoices / Payments
    |
    v
Payment Reconciliation
    |
    v
Outstanding Amount Calculation
    |
    v
AR Aging
    |
    v
Collection Prioritization
    |
    v
Agent Action
    |
    v
Approval Request
    |
    v
Action Orchestrator
    |
    v
Notification Processing
    |
    v
Audit / Recovery
    |
    v
Collections Dashboard
    |
    v
Production Validation
```

---

## Major Features

### AR Data Processing

The project manages core Accounts Receivable information including customer, invoice, and payment data.

Payment information is reconciled against invoices to calculate:

* Invoice amount
* Amount paid
* Outstanding amount
* Invoice payment status

Invoices can be classified as statuses such as:

```text
OPEN
PARTIALLY_PAID
PAID
```

---

## Staging and Data Validation

Incoming source data is first handled through a staging-style process rather than being trusted immediately as production AR data.

The staging layer provides a place to validate incoming information before it is used by the agent.

Typical validations include:

```text
Customer validation
Invoice validation
Payment validation
Required field checks
Relationship validation
Duplicate/error detection
```

The general loading pattern is:

```text
CSV / Source Data
        |
        v
Oracle Staging Tables
        |
        v
Validation / Transformation
        |
        v
Core AR Tables
```

---

## AR Aging

The system calculates how long an outstanding invoice has been overdue based on its due date.

Example aging categories include:

```text
CURRENT
1-30 DAYS
31-60 DAYS
61-90 DAYS
90+ DAYS
```

This gives the agent and AR team visibility into collection risk.

The project also uses:

```text
VW_AR_AGING_DETAIL
```

as an AR aging reporting layer.

---

## Collection Prioritization

Outstanding invoices are analyzed and assigned collection priority based on factors such as overdue age and outstanding exposure.

The purpose is to help the AR team focus first on invoices requiring the most attention.

Example priorities include:

```text
HIGH
MEDIUM
LOW
```

The agent can also associate recommended collection actions with overdue invoices.

---

## Agent Decision Layer

The project goes beyond static reporting.

The agent uses AR information to determine when a collection action may be required.

For example:

```text
Overdue invoice detected
        |
        v
Collection action identified
        |
        v
Payment reminder proposed
        |
        v
Approval request generated
```

The action is not blindly executed.

Human approval is incorporated into the workflow.

---

## Human-in-the-Loop Approval

Before certain collection actions are executed, the system creates an approval request.

Approval information is stored in:

```text
AGENT_APPROVAL_REQUESTS
```

The approval workflow can track information such as:

```text
Approval ID
Conversation ID
Action type
Action description
Action payload
Approval status
Reviewer
Review time
Execution status
Execution message
```

This design provides governance around agent actions.

---

## Action Orchestrator

The **Action Orchestrator** coordinates the complete collection action workflow.

It tracks the process from the initial invoice validation through approval and notification execution.

The orchestration lifecycle can include statuses such as:

```text
STARTED
WAITING_APPROVAL
APPROVED
QUEUED
PROCESSING
COMPLETED
FAILED
```

The orchestrator stores operational information including:

```text
Orchestration ID
Invoice number
Approval ID
Notification ID
Current step
Status
Start timestamp
Completion timestamp
Error message
```

This provides an audit trail for every agent-controlled action.

---

## Notification Outbox

Approved payment-reminder actions are placed into:

```text
AGENT_NOTIFICATION_OUTBOX
```

The notification workflow can move through statuses such as:

```text
PENDING
PROCESSING
SENT
FAILED
```

The outbox stores details including:

```text
Recipient
Subject
Message body
Notification type
Retry count
Processing status
Error information
```

The current project uses simulated delivery for demonstrating the full notification lifecycle safely without depending on a live production email service.

---

## Retry and Recovery

The project includes recovery concepts for failed or interrupted agent operations.

The system can track:

```text
Failed notifications
Retry counts
Failure reasons
Pending work
Stuck processing records
Failed orchestrations
```

This helps prevent agent actions from disappearing silently when an operation fails.

---

## Conversation and Audit Tracking

Agent activity is associated with conversation and workflow records.

This provides traceability across:

```text
Agent request
Approval
Execution
Notification
Result
Error
```

The purpose is to make agent behavior explainable and auditable rather than operating as an uncontrolled background process.

---

## Collections Reporting

The reporting module provides an AR management view of the system.

It includes:

### AR Portfolio KPIs

```text
Total invoices
Total invoice amount
Total amount paid
Total outstanding
Paid invoices
Open invoices
Partially paid invoices
```

### Overdue Exposure

```text
Number of overdue invoices
Total overdue outstanding amount
Maximum days past due
Average days past due
```

### Aging Summary

Outstanding AR can be summarized by aging category.

### Collection Priority Summary

Invoices can be grouped based on collection priority.

### Top Overdue Targets

The system can display collection targets with information such as:

```text
Invoice number
Customer
Due date
Outstanding amount
Days past due
Aging bucket
Priority
Recommended action
```

### Agent Activity Reporting

The reporting module also displays recent orchestration activity and workflow status.

---

## Collections Management Summary

The project generates a management-oriented collections summary using the AR and operational metrics collected from Oracle.

The summary can explain:

```text
Current outstanding receivables
Overdue exposure
Number of overdue invoices
Oldest delinquency
Pending collection approvals
Completed agent workflows
Failed workflows
Sent reminders
Notification failures
```

This gives an AR manager a concise operational view instead of requiring manual analysis across several tables.

---

## Production Validation and Hardening

A production-readiness validation module was added to test the health of the complete solution.

### Database Validation

Checks include:

```text
Oracle connectivity
Required tables
Required views
```

### AR Data Integrity

Checks include:

```text
Negative outstanding balances
Negative payment amounts
Outstanding amount greater than invoice amount
Missing due dates
Orphan invoices
Customers without email addresses
```

### Agent Workflow Health

Checks include:

```text
Stale STARTED orchestrations
Failed orchestrations
Pending approvals
Failed notifications
Stuck PROCESSING notifications
```

### Production Readiness Report

The validation process produces an overall result:

```text
PASS
WARNING
FAIL
```

During the Day 23 validation run, the project completed all critical checks without a critical failure. Warnings were intentionally surfaced for operational/data-quality conditions that should be reviewed before a real production deployment.

---

## Core Oracle Objects

Important Oracle objects used by the project include:

```text
CUSTOMERS
INVOICES
PAYMENTS
AGENT_CONVERSATIONS
AGENT_APPROVAL_REQUESTS
AGENT_NOTIFICATION_OUTBOX
AGENT_ORCHESTRATION_RUNS
VW_AR_AGING_DETAIL
```

Additional staging and supporting objects are used throughout the data-loading and agent workflow.

---

## Python Components

The Python layer connects to Oracle and coordinates the agent workflow.

Important later-stage modules include:

```text
17_action_orchestrator.py
18_collections_summary.py
19_validation_hardening.py
agent_tool_client.py
```

### `17_action_orchestrator.py`

Handles the end-to-end agent action workflow:

```text
Invoice validation
Recipient resolution
Conversation creation
Approval creation
Approval execution
Notification creation
Notification processing
Workflow completion
Failure tracking
History
Status
```

### `18_collections_summary.py`

Provides:

```text
Executive dashboard
AR aging summary
Collection priority summary
Top overdue invoices
Recent agent actions
Collections management summary
Full report
```

### `19_validation_hardening.py`

Provides:

```text
Database health checks
Schema validation
AR data-integrity checks
Agent workflow health
Production readiness scoring
```

---

## Technology Stack

```text
Oracle Database
Oracle SQL
PL/SQL
Python
python-oracledb / Oracle Python connectivity
VS Code
PowerShell
Git
GitHub
```

---

## Project Structure

A simplified project structure is:

```text
Oracle-AI-AR-Agent/
|
+-- python/
|   |
|   +-- agent_tool_client.py
|   +-- ...
|   +-- 17_action_orchestrator.py
|   +-- 18_collections_summary.py
|   +-- 19_validation_hardening.py
|
+-- sql/
|   |
|   +-- DDL scripts
|   +-- PL/SQL packages
|   +-- Views
|   +-- Agent workflow objects
|
+-- README.md
```

---

## Running the Project

### Prerequisites

Install or configure:

```text
Python 3.x
Oracle Database
Oracle client/database connectivity
Python Oracle driver
Git
VS Code or another Python IDE
```

The Oracle connection configuration must be available to:

```text
agent_tool_client.py
```

---

## Run Action Orchestrator

From the project root:

```powershell
python python/17_action_orchestrator.py
```

Example commands:

```text
run <invoice_number>
approve <orchestration_id>
status <orchestration_id>
history
exit
```

Example workflow:

```text
Orchestrator> run 490139
```

The agent creates an orchestration and, when applicable, an approval request.

Then:

```text
Orchestrator> approve 1
```

The workflow processes the approved action and notification.

---

## Run Collections Reporting

```powershell
python python/18_collections_summary.py
```

Available commands include:

```text
dashboard
aging
priority
overdue
actions
summary
report
exit
```

For a complete report:

```text
Collections> report
```

---

## Run Production Validation

```powershell
python python/19_validation_hardening.py
```

The validation process evaluates database, schema, AR data, and workflow health before displaying the production-readiness result.

---

## Example Business Scenario

Consider an invoice that remains unpaid after its due date.

```text
Invoice becomes overdue
        |
        v
Agent detects outstanding balance
        |
        v
Aging and collection priority calculated
        |
        v
Agent determines payment reminder is appropriate
        |
        v
Approval request created
        |
        v
AR Manager approves
        |
        v
Action Orchestrator creates notification
        |
        v
Notification moves PENDING -> PROCESSING -> SENT
        |
        v
Orchestration marked COMPLETED
        |
        v
Action appears in reporting and audit history
```

If execution fails:

```text
Failure
   |
   v
Error captured
   |
   v
Workflow marked FAILED
   |
   v
Recovery / retry information retained
   |
   v
Production health checks identify the issue
```

---

## Why This Project Is Agent-Oriented

This project is not limited to an AR dashboard.

It combines:

```text
Observe
   |
   v
Analyze
   |
   v
Decide
   |
   v
Request Approval
   |
   v
Act
   |
   v
Track
   |
   v
Recover
   |
   v
Report
```

This makes the solution behave like an **Accounts Receivable collection agent** rather than only a reporting application.

---

## Human-in-the-Loop Design

Collection actions can affect real customers, so the architecture deliberately includes an approval layer.

The agent can identify and prepare an action, while the AR manager retains control over execution.

This provides:

```text
Governance
Auditability
Operational control
Reduced automation risk
```

---

## Project Objectives Achieved

The project demonstrates:

```text
Oracle relational database design
SQL and PL/SQL development
AR business logic
Data staging and validation
Payment reconciliation
Aging analysis
Python-to-Oracle integration
Agent workflow design
Human approval workflows
Action orchestration
Notification processing
Failure recovery
Auditability
Collections analytics
Production readiness validation
Git/GitHub development workflow
```

---

## Current Scope

The project is a portfolio and learning implementation that simulates an enterprise Accounts Receivable collection environment.

The Oracle and agent architecture is designed so that the same concepts could later integrate with enterprise systems and services.

The current implementation does **not** claim to directly send production customer emails or connect to a live production Oracle ERP instance.

---

## Future Enhancements

Potential future improvements include:

```text
Oracle Fusion ERP integration
REST API ingestion
Oracle Integration Cloud integration
Live email provider integration
LLM-based natural-language reasoning
RAG over customer/account history
Predictive payment-risk scoring
Customer payment prediction
Automated collection strategy recommendations
Web-based AR dashboard
Role-based access control
OCI deployment
Containerization
Automated CI/CD
Enterprise monitoring
```

---


## Business Value

The project demonstrates how an agent-oriented solution can help an Accounts Receivable organization:

```text
Reduce manual invoice monitoring
Identify overdue exposure faster
Prioritize collection activity
Maintain human control over customer-facing actions
Automate repeatable collection workflows
Improve auditability
Detect workflow failures
Provide management-level AR visibility
```

---
