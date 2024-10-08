"""Seed database with sneaker data from CSV Files."""

from csv import DictReader
from app import app, db
from models import Sneaker

def clean_price(price):
    """Convert price string to a float after removing '$'."""
    return float(price.replace('$', '').replace(',', '')) if price else None

with app.app_context():
    db.drop_all()
    db.create_all()

    # Open the CSV file and read the data
    with open('generator/sneakers.csv') as sneakers:
        reader = DictReader(sneakers)
        
        # Clean data before inserting
        data = []
        for row in reader:
            row['retail_price'] = clean_price(row['retail_price'])  # Clean price
            print(f"Inserting: {row}")  # Log each row for debugging
            data.append(row)
        
        # Insert data in bulk
        db.session.bulk_insert_mappings(Sneaker, data)

    db.session.commit()
    print("Data has been successfully seeded!")
