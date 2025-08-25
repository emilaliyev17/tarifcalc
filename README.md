# NEXUS COGS Calculator

This is a web application to calculate the true cost of goods for an e-commerce business.

## Features

-   Accurately calculate Total Cost for each invoice line by combining vendor price with additional costs.
-   Allocate multiple cost types with different methods (price, volume, quantity).
-   Import invoices from CSV files.
-   Manage HSUS tariff codes.
-   Export results to CSV.
-   User authentication.

## Technologies

-   Backend: Python + Django
-   Database: PostgreSQL on Supabase (free tier). Locally use SQLite
-   Frontend: Django templates + HTMX (minimal JavaScript).
-   Docker for local development and deployment.

## Getting Started

### Prerequisites

-   Python 3.11
-   Docker
-   Docker Compose

### Installation

1.  **Clone the repository:**

    ```bash
    git clone <repository-url>
    cd nexus-cogs-app
    ```

2.  **Create a virtual environment and install dependencies:**

    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Create a `.env` file:**

    Create a `.env` file in the root of the project and add the following environment variables:

    ```
    DJANGO_SECRET_KEY=your-secret-key
    DATABASE_URL=postgres://user:password@db:5432/mydatabase
    DEBUG=True
    ```

4.  **Run the database migrations:**

    ```bash
    python3 manage.py migrate
    ```

5.  **Create a superuser:**

    ```bash
    python3 manage.py createsuperuser
    ```

6.  **Run the application:**

    Using Docker Compose:

    ```bash
    docker-compose up --build
    ```

    Or locally:

    ```bash
    python3 manage.py runserver
    ```

## Usage

1.  Login to the application with your superuser credentials.
2.  Upload a sample CSV file with your invoice data.
3.  Enable HSUS tariff and add other costs as needed.
4.  View the results and export them to CSV.

## Running Tests

To run the tests, run the following command:

```bash
pytest
```
