# Oracle AI Accounts Receivable Agent

An AI-powered Oracle Accounts Receivable solution that processes retail transaction data, creates normalized AR records, calculates payments and aging, assigns collection risk, and uses an AI router to call trusted Oracle PL/SQL tools.

## Current capabilities

- Python ETL for more than 1 million retail transactions
- Oracle staging and normalized AR tables
- Customer, invoice, invoice-line, and payment processing
- AR aging and collection-priority analysis
- Customer risk scoring
- PL/SQL agent tools
- Python-to-Oracle integration
- Natural-language tool routing using OpenAI

## Architecture

Real retail data  
→ Python ETL  
→ Oracle staging  
→ AR business tables  
→ Aging and risk views  
→ PL/SQL agent tools  
→ Python agent router  
→ AI-generated tool selection

## Technologies

- Oracle Database
- SQL and PL/SQL
- Python
- pandas
- python-oracledb
- OpenAI API
- Git and GitHub
- VS Code

## Security

Credentials are stored in `.env` and excluded from Git using `.gitignore`.

## Status

Days 1–10 completed. The next phase includes conversational responses, memory, approval workflows, APIs, and an APEX dashboard.
