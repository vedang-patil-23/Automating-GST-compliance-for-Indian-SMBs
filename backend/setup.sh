#!/bin/bash

# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate  # On Windows, use: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example"
    cp .env.example .env
    echo "Please update the .env file with your configuration"
else
    echo ".env file already exists, skipping creation"
fi

echo "Setup complete. Don't forget to:"
echo "1. Update the .env file with your configuration"
echo "2. Run 'python manage.py migrate' to set up the database"
echo "3. Run 'python manage.py createsuperuser' to create an admin user"
echo "4. Start the development server with 'python manage.py runserver'"
