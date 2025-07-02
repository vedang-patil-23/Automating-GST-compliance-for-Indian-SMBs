# Automated GST Invoice Reconciliation & Filing Assistant (AGIRFA)

**Note: This is a simplified, public version of the application. Sensitive information and proprietary logic have been removed.**

## Overview

AGIRFA is a web application designed to automate the process of GST invoice reconciliation and filing for Indian businesses. This public repository contains a sanitized version of the codebase with sensitive information and proprietary logic removed.

## Features

- **Invoice Upload**: Upload GST invoices in various formats (PDF, JPG, PNG)
- **Data Extraction**: Extract structured data from invoices using OCR
- **GST Validation**: Validate GSTIN numbers and other tax details
- **Reconciliation**: Match purchase and sales invoices for accurate GST filing
- **Report Generation**: Generate GSTR-1, GSTR-3B, and other GST returns
- **User Management**: Role-based access control for different team members

## Tech Stack

- **Backend**: Django REST Framework
- **Frontend**: Vue.js with Vuetify
- **Database**: PostgreSQL
- **Task Queue**: Celery with Redis
- **OCR**: Custom implementation with Tesseract and LayoutLM
- **Cloud Storage**: AWS S3
- **Containerization**: Docker

## Getting Started

### Prerequisites

- Python 3.8+
- Node.js 16+
- PostgreSQL
- Redis
- Tesseract OCR

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/vedang-patil-23/agirfa-public.git
   cd agirfa-public
   ```

2. Set up the backend:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   cp .env.example .env
   # Edit .env with your configuration
   python manage.py migrate
   python manage.py createsuperuser
   ```

3. Start the development server:
   ```bash
   python manage.py runserver
   ```

## Security Notice

This is a simplified version of the application intended for demonstration purposes only. The actual production application includes additional security measures, optimizations, and proprietary logic that are not included in this public repository.

## License

This project is proprietary software. Unauthorized copying, distribution, modification, public display, or public performance of this software is strictly prohibited.

## Contributing

This is a private project. No contributions are being accepted at this time.

## Contact

For more information, please contact me via email.
