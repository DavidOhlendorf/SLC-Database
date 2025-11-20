# Student Life Cycle Question and Variable Database

A web-based system for managing, documenting, and searching questions, variables, waves, and constructs of the **Student Life Cycle (SLC)** panel study.  
The project replaces a former MS Access system and migrates all structures into a modular **Django + PostgreSQL** architecture.

## 🔍 Key Features

- **Hybrid search engine**
  - Fuzzy search using `pg_trgm` (GIN index)  
  - Vector-based semantic search using `tsvector`  
  - Combined ranking logic for robust and relevant results

- **Detail pages**
  - Questions with wave assignments, constructs, keywords, and screenshots
  - Variables with JSON-based value labels, waves, and metadata

- **Backend architecture**
  - Modular Django apps: Waves, Questions, Pages, Variables, Constructs, Keywords, Search, Accounts

- **Admin & Data Import**
  - Optimized Django Admin interfaces
  - Import/Export via `django-import-export`
  - Backwards compatibility using `legacy_id` mappings

## 🗄️ Data Model

A full ER diagram will follow.

Core entities include:
- `Question`, `Keyword`, `Construct`, `QuestionScreenshot`
- `Variable`
- `Wave`, `WaveQuestion`
- `VariableWaves` and related linking tables

## 🚀 Purpose of the Project

The system is designed to:
- centralize question and variable documentation  
- ensure traceability and versioning  
- enable fast searching and filtering  
- support internal and external research workflows  
- serve as a long-term documentation and research platform  

## 🛠️ Tech Stack

- **Backend:** Django 5  
- **Database:** PostgreSQL 16
- **Frontend:** Bootstrap, HTML, JavaScript  

## 📚 License
The source code is publicly visible for transparency.
Usage, modification, deployment, or redistribution is not permitted.
See the LICENSE file for details.
