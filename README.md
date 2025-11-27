# Student Life Cycle Question and Variable Database

A web-based system for managing, documenting, and searching questions, variables, surveys, instrumentsd and constructs of the **Student Life Cycle (SLC)** panel study.  
The project replaces a former MS Access system and migrated all structures into a modular **Django + PostgreSQL** architecture.

This project is part of the SLC infrastructure and centralizes question/variable documentation and metadata for research purposes.

---

## Key Features

- **Hybrid search engine**
  - Full Text and keyword search
  - Fuzzy search using `pg_trgm`  
  - Vector-based semantic search using `tsvector`  
  - Combined ranking logic for robust and relevant results
  - Option to filter and sort search results

- **Detail pages**
  - Questions with surveys assignments, constructs, keywords, and screenshots
  - Variables with JSON-based value labels, waves, and metadata

- **Backend architecture**
  - Modular Django apps: Waves, Questions, Pages, Variables, Constructs, Keywords, Search, Accounts

- **Admin & Data Import**
  - Optimized Django Admin interfaces
  - Import/Export via `django-import-export`
  - Backwards compatibility with former MS Access Database using `legacy_id` mappings
 
- **User authentication** (Django Auth)
  
- **Responsive UI** with Bootstrap 5 and GLightbox

---

## Data Model

A full ER diagram will follow.

Core entities include:
- `Question`, `Keyword`, `Construct`,
- `Variable`
- `Survey`, `Cycle`
- `Pages`
- related linking tables

## Purpose of the Project

The system is designed to:
- centralize question and variable documentation  
- ensure traceability and versioning  
- enable fast searching and filtering  
- support internal and external research workflows  
- serve as a long-term documentation and research platform  

## Tech Stack

- **Python:** 3.13  
- **Backend:** Django 5.x  
- **Database:** PostgreSQL  
- **Frontend:** Django Templates, Bootstrap 5  
- **Web Server:** Nginx
- **WSGI Server:** Gunicorn
- **Operating System (prod):** Ubuntu 24.04 LTS
- **HTTPS:** Let’s Encrypt (Certbot)  

Deployment documentation: see [DEPLOYMENT.md](DEPLOYMENT.md)

---

## 📚 License
The source code is publicly visible for transparency.
Usage, modification, deployment, or redistribution is not permitted.
See the LICENSE file for details.
